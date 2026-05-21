"""HTTP / .env / serverinfo / 共通 entrypoint をまとめた汎用ヘルパー."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path


USER_AGENT = "tableau-rest-api-oauth-example/0.1 (python)"

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = REPO_ROOT / ".env"


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


def http_post_form(url: str, body: dict[str, str], timeout: int = 30) -> dict:
    data = urllib.parse.urlencode(body).encode()
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
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


def get_api_version(server: str) -> str:
    """無認証で /api/3.0/serverinfo を叩き、restApiVersion を取得."""
    info = http_get_json(
        f"{server}/api/3.0/serverinfo",
        headers={"Accept": "application/json"},
    )
    s = info["serverInfo"]
    print(
        f"[serverinfo] productVersion={s['productVersion']['value']} "
        f"restApiVersion={s['restApiVersion']}",
        flush=True,
    )
    return s["restApiVersion"]


def prepare() -> tuple[str, str, str, str]:
    """全 example の共通前処理.

    .env を読み、serverinfo で api_version を取り、OAuth サインインを実行し、
    access_token を 3 パートに分割して site_luid を取り出す。

    Returns: (origin_host, api_version, site_luid, access_token)
    """
    # circular import 回避のため関数内 import
    from .oauth import derive_site_luid, run_oauth_flow

    env = load_env(ENV_PATH)
    server = env.get("TABLEAU_SERVER", "").rstrip("/")
    site_name = env.get("TABLEAU_SITE_NAME", "")
    port = int(env.get("LOCAL_CALLBACK_PORT", "8765"))
    if not server or not site_name:
        raise SystemExit(
            f"TABLEAU_SERVER / TABLEAU_SITE_NAME を {ENV_PATH} に設定してください。"
        )

    api_version = get_api_version(server)
    access_token, origin_host = run_oauth_flow(server, site_name, port)
    site_luid = derive_site_luid(access_token)
    print(f"[token] derived site_luid: {site_luid}", flush=True)
    return origin_host, api_version, site_luid, access_token
