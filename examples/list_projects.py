"""
OAuth → REST API で projects 一覧を取得する example.

list_datasources.py / list_workbooks.py と同じ構造。エンドポイントは
/api/<ver>/sites/<luid>/projects、レスポンス配下のキーは project。

実行:
  python examples/list_projects.py

依存: Python 標準ライブラリのみ。
"""

from __future__ import annotations

from _shared import USER_AGENT, http_get_json, prepare


def fetch_projects(
    origin_host: str,
    api_version: str,
    site_luid: str,
    access_token: str,
    page_size: int = 25,
) -> None:
    url = (
        f"https://{origin_host}/api/{api_version}/sites/{site_luid}"
        f"/projects?pageSize={page_size}"
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
    projects = data.get("projects", {}).get("project", [])
    print(f"\n[projects] totalAvailable: {pagination.get('totalAvailable')}")
    print(f"[projects] returned: {len(projects)} item(s) (pageSize={page_size})")
    for proj in projects:
        parent = proj.get("parentProjectId") or "(top-level)"
        print(
            f"  - {proj.get('name')!r} (parent={parent}, id={proj.get('id')})"
        )


def main() -> None:
    origin_host, api_version, site_luid, access_token = prepare()
    fetch_projects(origin_host, api_version, site_luid, access_token)
    print("\n[done] OAuth → REST API 一気通貫 完了", flush=True)


if __name__ == "__main__":
    main()
