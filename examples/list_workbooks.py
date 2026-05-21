"""
OAuth → REST API で workbooks 一覧を取得する example.

list_datasources.py とほぼ同じ構造。違いはエンドポイント (datasources → workbooks)
と pagination 配下のキー (datasource → workbook)、表示するフィールドのみ。

実行:
  python examples/list_workbooks.py

依存: Python 標準ライブラリのみ。
"""

from __future__ import annotations

from _shared import USER_AGENT, http_get_json, prepare


def fetch_workbooks(
    origin_host: str,
    api_version: str,
    site_luid: str,
    access_token: str,
    page_size: int = 25,
) -> None:
    url = (
        f"https://{origin_host}/api/{api_version}/sites/{site_luid}"
        f"/workbooks?pageSize={page_size}"
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
    workbooks = data.get("workbooks", {}).get("workbook", [])
    print(f"\n[workbooks] totalAvailable: {pagination.get('totalAvailable')}")
    print(f"[workbooks] returned: {len(workbooks)} item(s) (pageSize={page_size})")
    for wb in workbooks:
        project = wb.get("project", {}).get("name", "?")
        owner_id = wb.get("owner", {}).get("id", "?")
        print(
            f"  - {wb.get('name')!r} (project={project!r}, owner_id={owner_id}, id={wb.get('id')})"
        )


def main() -> None:
    origin_host, api_version, site_luid, access_token = prepare()
    fetch_workbooks(origin_host, api_version, site_luid, access_token)
    print("\n[done] OAuth → REST API 一気通貫 完了", flush=True)


if __name__ == "__main__":
    main()
