"""
Tableau Cloud に対する OAuth 認可コードフローを MCP server を介さず最小実装で再現する。

3 モード:
  - flow (default):  authorization_code grant でフル OAuth → REST API
  - refresh:         保存済み refresh_token で /oauth2/v1/token を叩いて再取得 → REST API
  - serverinfo:      /api/serverinfo を叩いて Tableau の API version 等を表示するだけ (無認証)

依存: Python 標準ライブラリのみ。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import socketserver
import sys
import threading
import urllib.parse
import urllib.request
import uuid
import webbrowser
from pathlib import Path


HERE = Path(__file__).parent
TOKEN_CACHE = HERE / ".token-cache.json"  # gitignored


# ----- .env loader (no python-dotenv dependency) -----
def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


# ----- PKCE -----
def pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


# ----- Callback listener -----
class CallbackResult:
    code: str | None = None
    state: str | None = None
    error: str | None = None
    event = threading.Event()


def make_callback_handler(expected_state: str, result: CallbackResult):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/Callback":
                self.send_response(404)
                self.end_headers()
                return
            query = urllib.parse.parse_qs(parsed.query)
            received_state = (query.get("state") or [None])[0]
            if received_state != expected_state:
                result.error = f"state mismatch: expected {expected_state!r}, got {received_state!r}"
            else:
                result.code = (query.get("code") or [None])[0]
                result.state = received_state
                if "error" in query:
                    result.error = (query.get("error") or [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>OAuth callback received.</h2>"
                b"<p>You can close this tab. Return to your terminal.</p></body></html>"
            )
            result.event.set()

        def log_message(self, *_args, **_kwargs):
            return

    return Handler


# ----- HTTP helpers -----
def http_post_form(url: str, body: dict[str, str], timeout: int = 30) -> dict:
    data = urllib.parse.urlencode(body).encode()
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "verify-cloud-replay/0.2 (python)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise SystemExit(f"[error] POST {url} -> HTTP {e.code}\nbody: {body_text}")


def http_get_json(url: str, headers: dict[str, str], timeout: int = 30) -> dict:
    req = urllib.request.Request(url=url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise SystemExit(f"[error] GET {url} -> HTTP {e.code}\nbody: {body_text}")


def get_server_info(server: str) -> tuple[str, str]:
    """無認証で /api/serverinfo を叩き、(productVersion, restApiVersion) を返す."""
    info = http_get_json(
        f"{server}/api/3.0/serverinfo",
        headers={"Accept": "application/json"},
    )
    s = info["serverInfo"]
    return s["productVersion"]["value"], s["restApiVersion"]


def call_list_datasources(
    origin_host: str, api_version: str, site_luid: str, access_token: str
) -> None:
    api_base = f"https://{origin_host}"
    url = f"{api_base}/api/{api_version}/sites/{site_luid}/datasources?pageSize=5"
    data = http_get_json(
        url,
        headers={
            "Accept": "application/json",
            "X-Tableau-Auth": access_token,
            "User-Agent": "verify-cloud-replay/0.2 (python)",
        },
    )
    pagination = data.get("pagination", {})
    datasources = data.get("datasources", {}).get("datasource", [])
    print(f"[rest-api] totalAvailable: {pagination.get('totalAvailable')}", flush=True)
    print(f"[rest-api] returned: {len(datasources)} datasource(s)", flush=True)
    for ds in datasources[:5]:
        project = ds.get("project", {}).get("name", "?")
        print(
            f"  - {ds.get('name')!r} (project={project!r}, id={ds.get('id')})",
            flush=True,
        )


def derive_site_luid(access_token: str) -> str:
    parts = access_token.split("|")
    if len(parts) != 3:
        raise SystemExit(
            f"[error] unexpected access_token shape (expected 3 parts, got {len(parts)})"
        )
    return parts[2]


def save_token_cache(payload: dict) -> None:
    TOKEN_CACHE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[cache] saved → {TOKEN_CACHE.name}", flush=True)


def load_token_cache() -> dict:
    if not TOKEN_CACHE.exists():
        raise SystemExit(f"[error] {TOKEN_CACHE} not found; run `flow` first")
    return json.loads(TOKEN_CACHE.read_text(encoding="utf-8"))


# ----- modes -----
def mode_serverinfo(server: str) -> None:
    product_version, rest_api_version = get_server_info(server)
    print(f"[serverinfo] productVersion: {product_version}", flush=True)
    print(f"[serverinfo] restApiVersion: {rest_api_version}", flush=True)


def mode_flow(server: str, site_name: str, port: int, client_type: str) -> None:
    redirect_uri = f"http://127.0.0.1:{port}/Callback"

    # 動的に api_version を取る (ハードコードを避ける)
    product_version, api_version = get_server_info(server)
    print(
        f"[serverinfo] productVersion={product_version} restApiVersion={api_version}",
        flush=True,
    )

    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(32)
    client_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    device_name = f"verify-cloud-replay (python, client_type={client_type})"

    result = CallbackResult()
    handler_cls = make_callback_handler(state, result)
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler_cls)
    listener_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    listener_thread.start()
    print(
        f"[listener] http://127.0.0.1:{port}/Callback で待ち受け中", flush=True
    )

    auth_params = {
        "client_id": client_id,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
        "device_id": device_id,
        "device_name": device_name,
        "target_site": site_name,
        "client_type": client_type,
    }
    auth_url = f"{server}/oauth2/v1/auth?" + urllib.parse.urlencode(auth_params)
    print(f"[browser] client_type={client_type}", flush=True)
    print(f"[browser] {auth_url}", flush=True)
    webbrowser.open(auth_url)

    print("[wait] ブラウザでサインインしてください (最大 5 分)...", flush=True)
    received = result.event.wait(timeout=300)
    httpd.shutdown()
    if not received:
        raise SystemExit("[error] timeout waiting for callback")
    if result.error or not result.code:
        raise SystemExit(f"[error] callback error: {result.error!r}")
    code = result.code
    print(f"[code] received (length={len(code)})", flush=True)

    token = http_post_form(
        f"{server}/oauth2/v1/token",
        {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
        },
    )
    access_token = token["access_token"]
    refresh_token = token.get("refresh_token")
    origin_host = token.get("origin_host")
    expires_in = token.get("expires_in")

    print(f"[token] access_token length: {len(access_token)}", flush=True)
    print(f"[token] expires_in: {expires_in}", flush=True)
    print(f"[token] origin_host: {origin_host}", flush=True)
    print(f"[token] refresh_token present: {refresh_token is not None}", flush=True)

    site_luid = derive_site_luid(access_token)
    print(f"[token] derived site_luid: {site_luid}", flush=True)

    save_token_cache(
        {
            "client_id": client_id,
            "refresh_token": refresh_token,
            "site_namespace": site_name,
            "origin_host": origin_host,
            "server": server,
            "api_version": api_version,
            "client_type": client_type,
        }
    )

    call_list_datasources(origin_host, api_version, site_luid, access_token)
    print("[done] OAuth → REST API round trip 完了", flush=True)


def mode_refresh(server_override: str | None) -> None:
    cache = load_token_cache()
    server = server_override or cache["server"]
    client_id = cache["client_id"]
    refresh_token = cache["refresh_token"]
    site_namespace = cache["site_namespace"]
    api_version = cache["api_version"]

    print(
        f"[refresh] grant_type=refresh_token, client_id={client_id}, site_namespace={site_namespace}",
        flush=True,
    )
    token = http_post_form(
        f"{server}/oauth2/v1/token",
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "site_namespace": site_namespace,
        },
    )
    new_access_token = token["access_token"]
    new_refresh_token = token.get("refresh_token")
    origin_host = token.get("origin_host", cache.get("origin_host"))
    expires_in = token.get("expires_in")

    print(f"[refresh] new access_token length: {len(new_access_token)}", flush=True)
    print(f"[refresh] new expires_in: {expires_in}", flush=True)
    print(f"[refresh] new origin_host: {origin_host}", flush=True)
    print(
        f"[refresh] new refresh_token issued: {new_refresh_token is not None}",
        flush=True,
    )
    print(
        f"[refresh] refresh_token rotated: {new_refresh_token != refresh_token}",
        flush=True,
    )

    site_luid = derive_site_luid(new_access_token)
    print(f"[refresh] derived site_luid: {site_luid}", flush=True)

    # 新トークンで cache を更新（refresh token rotation 対応）
    cache["refresh_token"] = new_refresh_token or refresh_token
    cache["origin_host"] = origin_host
    save_token_cache(cache)

    call_list_datasources(origin_host, api_version, site_luid, new_access_token)
    print("[done] refresh_token → REST API round trip 完了", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=("flow", "refresh", "serverinfo"),
        nargs="?",
        default="flow",
    )
    parser.add_argument(
        "--client-type",
        default="tableau-mcp",
        help="`client_type` query param to send (default: tableau-mcp)",
    )
    args = parser.parse_args()

    env = load_env(HERE / ".env")
    server = env.get("TABLEAU_SERVER", "").rstrip("/")
    site_name = env.get("TABLEAU_SITE_NAME", "")
    port = int(env.get("LOCAL_CALLBACK_PORT", "8765"))

    if args.mode == "serverinfo":
        if not server:
            raise SystemExit("TABLEAU_SERVER を .env に設定してください。")
        mode_serverinfo(server)
        return

    if args.mode == "refresh":
        mode_refresh(server_override=server or None)
        return

    # flow
    if not server or not site_name:
        raise SystemExit("TABLEAU_SERVER / TABLEAU_SITE_NAME を .env に設定してください。")
    mode_flow(server, site_name, port, args.client_type)


if __name__ == "__main__":
    main()
