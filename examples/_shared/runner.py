"""共通 entrypoint: .env 読込 → serverinfo → OAuth flow → site_luid 抽出までを一括."""

from __future__ import annotations

from pathlib import Path

from .config import load_env
from .oauth import derive_site_luid, run_oauth_flow
from .serverinfo import get_api_version


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = REPO_ROOT / ".env"


def prepare() -> tuple[str, str, str, str]:
    """全 example の共通前処理.

    .env を読み、serverinfo で api_version を取り、OAuth サインインを実行し、
    access_token を 3 パートに分割して site_luid を取り出す。

    Returns: (origin_host, api_version, site_luid, access_token)
    """
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
