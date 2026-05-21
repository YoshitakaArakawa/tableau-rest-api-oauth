# tableau-rest-api-oauth — Claude 向け作業ノート

リポの目的・構造・使い方・制約は [README.md](README.md) を読むこと。
ここには README で語らない作業時のガードと TODO だけ書く。

## このリポは Public 化前提

- ファイル本文・コミットメッセージ・サンプル値に、公開されたら困る情報を書かない
- 実 URL / 実 ID / 実プロジェクト名 / 実メール等は埋めない（`.env` は gitignored）
- `.env.example` 等のテンプレートにはダミー値のみ
- 認証シークレット（refresh_token、JWE 鍵 etc.）はファイル commit しない

## 新しい example を追加するとき

`examples/list_<resource>.py` の形で 1 ファイル追加。既存 example をコピペし
`from _shared import prepare, http_get_json, USER_AGENT` で共通部品を取り込み、
固有の `fetch_<resource>` 関数だけ差し替える。

## 関連リポ

詳細な経緯・仮説検証ログは別の private リポ（Desktop 直下）にある。
本リポには成果物のみ抽出。

## 次にやる候補（拾える時に）

- Tableau Server 2025.3+ での同フロー動作確認
- `examples/refresh_demo.py`: refresh_token grant と rotation 挙動の観察用
- `examples/revoke_demo.py`: `/oauth2/v1/revoke` の動作確認
- consent 画面の挙動（初回 / 再 connect / 別 client_type）
- token 保存を OS の Keychain / DPAPI 等に変える（refresh 系 example 時）
- Production 移行ガイド（EAS / UAT / PAT への乗り換えを README に追記）
