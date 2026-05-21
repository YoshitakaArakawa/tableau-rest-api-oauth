# tableau-rest-api-oauth

## このリポの目的

Tableau Cloud / Server に対して、**ブラウザサインインで取った OAuth access_token を `X-Tableau-Auth` ヘッダで REST API に渡す**ところまでを Python 標準ライブラリだけで再現する最小実装。

Tableau MCP の動作観察から逆算した。詳細な経緯と仮説検証の調査メモは別の **private リポ（Desktop 直下）** にあり、本リポにはそのうち成果物（スクリプト）と一般読者に必要な背景のみを抽出している。

## このリポは Public 化前提

Public GitHub リポとして運用する。個人ルールデフォルトに従い:

- ファイル本文・コミットメッセージ・コード・コメント・サンプル値に、公開されたら困る情報を書かない
- 実 URL / 実 ID / 実プロジェクト名 / 実メール等は埋めない（`.env` は gitignored）
- `.env.example` 等のテンプレートにはダミー値のみ
- LICENSE: MIT

## 進め方

- メインの実装は [`oauth_flow.py`](oauth_flow.py)（argparse で `flow` / `refresh` / `serverinfo` の 3 モード）
- 設定は [`.env.example`](.env.example) を `.env` にコピーして実値を入れる
- 一般読者向けの説明は [`README.md`](README.md)
- 認証関連のシークレット（refresh_token、JWE 鍵 etc.）はファイル commit しない。`.gitignore` で `.env` / `.token-cache.json` を排除済み

## 既知の制約

- **Tableau Cloud は redirect_uri が `127.0.0.1` 限定**（本番ホスト未対応、ETA Q2 2026）
- **`redirect_uri` の path は `/Callback`（大文字 C 固定）**
- **Tableau Server で動くかは未確認**（理屈上は同じく動くはず、`tsm configuration` で許可ホスト登録すれば任意ホスト可）
- Cloud 側が `client_type` の値検証はしていないことは確認済み（独自値 OK）

## 次にやる候補（拾える時に）

- Tableau Server 2025.3+ に対する同じフローの動作確認
- `/oauth2/v1/revoke` の動作確認
- consent 画面の挙動（初回 / 再 connect / 別 client_type）
- token 保存方法を OS の Keychain / DPAPI 等に変える（refresh_token の平文保存を改善）
- Production 移行ガイド（EAS / UAT / PAT への乗り換え説明を README に追記）

## 参考

- 一次資料: [tableau/tableau-mcp](https://github.com/tableau/tableau-mcp)
- 公式: [Tableau REST API Authentication Methods](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_ref_authentication.htm)
