"""
OAuth → REST API で datasources 一覧を取得する example.

事前準備:
  - .env に TABLEAU_SERVER / TABLEAU_SITE_NAME を設定 (.env.example 参照)

実行:
  python examples/list_datasources.py

共通の OAuth フローは _shared/ に分離してあるので、本ファイルは REST 呼び出しのみが
example 固有のコード。別エンドポイントを試したい場合は fetch_datasources を差し替える。

依存: Python 標準ライブラリのみ。
"""

from __future__ import annotations

from _shared import USER_AGENT, http_get_json, prepare


def fetch_datasources(
    origin_host: str,
    api_version: str,
    site_luid: str,
    access_token: str,
    page_size: int = 25,
) -> None:
    url = (
        f"https://{origin_host}/api/{api_version}/sites/{site_luid}"
        f"/datasources?pageSize={page_size}"
    )
    data = http_get_json(
        url,
        headers={
            "Accept": "application/json",
            "X-Tableau-Auth": access_token,
            "User-Agent": USER_AGENT,
        },
    )
    pagination = data.get("pagination", {})
    datasources = data.get("datasources", {}).get("datasource", [])
    print(f"\n[datasources] totalAvailable: {pagination.get('totalAvailable')}")
    print(f"[datasources] returned: {len(datasources)} item(s) (pageSize={page_size})")
    for ds in datasources:
        project = ds.get("project", {}).get("name", "?")
        print(f"  - {ds.get('name')!r} (project={project!r}, id={ds.get('id')})")


def main() -> None:
    origin_host, api_version, site_luid, access_token = prepare()
    fetch_datasources(origin_host, api_version, site_luid, access_token)
    print("\n[done] OAuth → REST API 一気通貫 完了", flush=True)


if __name__ == "__main__":
    main()
