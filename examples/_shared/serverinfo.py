"""Tableau /api/3.0/serverinfo (無認証) の呼び出し."""

from __future__ import annotations

from .http import http_get_json


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
