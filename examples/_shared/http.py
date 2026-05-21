"""HTTP helpers: 標準ライブラリ urllib 上で JSON GET / form POST を扱う薄いラッパー."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from ._constants import USER_AGENT


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
