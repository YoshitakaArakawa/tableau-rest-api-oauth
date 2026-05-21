"""OAuth authorization_code (PKCE) フローと access_token のパース."""

from __future__ import annotations

import base64
import hashlib
import http.server
import secrets
import socketserver
import threading
import urllib.parse
import uuid
import webbrowser

from ._constants import CLIENT_TYPE
from .http import http_post_form


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


# ----- authorization_code flow -----
def run_oauth_flow(server: str, site_name: str, port: int) -> tuple[str, str]:
    """ブラウザサインインで access_token を取得.

    Returns: (access_token, origin_host)
    """
    redirect_uri = f"http://127.0.0.1:{port}/Callback"
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(32)
    client_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    result = CallbackResult()
    handler_cls = make_callback_handler(state, result)
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler_cls)
    listener_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    listener_thread.start()
    print(f"[listener] http://127.0.0.1:{port}/Callback で待ち受け中", flush=True)

    auth_params = {
        "client_id": client_id,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
        "device_id": device_id,
        "device_name": "tableau-rest-api-oauth-example (python)",
        "target_site": site_name,
        "client_type": CLIENT_TYPE,
    }
    auth_url = f"{server}/oauth2/v1/auth?" + urllib.parse.urlencode(auth_params)
    print(f"[browser] {auth_url}", flush=True)
    webbrowser.open(auth_url)

    print("[wait] ブラウザでサインインしてください (最大 5 分)...", flush=True)
    received = result.event.wait(timeout=300)
    httpd.shutdown()
    if not received:
        raise SystemExit("[error] timeout waiting for callback")
    if result.error or not result.code:
        raise SystemExit(f"[error] callback error: {result.error!r}")
    print(f"[code] received (length={len(result.code)})", flush=True)

    token = http_post_form(
        f"{server}/oauth2/v1/token",
        {
            "grant_type": "authorization_code",
            "code": result.code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
        },
    )
    access_token = token["access_token"]
    origin_host = token.get("origin_host")
    print(f"[token] access_token length: {len(access_token)}", flush=True)
    print(f"[token] expires_in: {token.get('expires_in')}", flush=True)
    print(f"[token] origin_host: {origin_host}", flush=True)
    return access_token, origin_host


# ----- access_token のパース -----
def derive_site_luid(access_token: str) -> str:
    """access_token は `<id1>|<id2>|<site-luid>` の 3 パート構造。3 つ目が site LUID."""
    parts = access_token.split("|")
    if len(parts) != 3:
        raise SystemExit(
            f"[error] unexpected access_token shape (expected 3 parts, got {len(parts)})"
        )
    return parts[2]
