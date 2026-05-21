# tableau-rest-api-oauth

> **Unofficial / 非公式**: 本リポは Tableau Software, LLC とは無関係の個人プロジェクトであり、Tableau の公式プロダクト・サポート対象ではない。商標 "Tableau" は識別目的でのみ使用している。

Tableau Cloud で **ユーザのブラウザサインインから OAuth access_token を取得し、それを `X-Tableau-Auth` ヘッダで REST API に渡す** ところまでを Python スクリプトで通す最小実装。Python 標準ライブラリのみ、外部依存ゼロ。`examples/` 配下にエンドポイント別の example スクリプトを置き、共通の OAuth フローは `examples/_shared/` に分離している。

## なぜこのリポがあるか

Tableau の公式 [REST API Authentication Methods](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_ref_authentication.htm) には、PAT / Connected App (JWT) / UAT / EAS Bearer はあるが、**OAuth 2.0 authorization_code フロー** によるサインインは載っていない。

一方、Tableau Server 2025.3 から `/oauth2/v1/auth` と `/oauth2/v1/token` という **OAuth 認可サーバエンドポイント**が追加され（Tableau Cloud にも存在する）、[公式 Tableau MCP](https://github.com/tableau/tableau-mcp) はこれを叩いて REST API を呼んでいる。Tableau MCP の動作観察から判明したのは:

1. `/oauth2/v1/token` から返ってくる `access_token` は **`<id1>|<id2>|<site-luid>` の 3 パート文字列**
2. それを **`X-Tableau-Auth` ヘッダにそのまま渡せば REST API が叩ける**（通常の session token と互換）
3. つまり「REST API には OAuth が無い」のではなく、「OAuth で取った token が既存の認証ヘッダに収まる形で発行される」が実態

本リポはこの仕組みを Tableau MCP を経由せず Python 単体で再現したもの。

## 動作要件

- Python 3.10+
- Tableau Cloud アカウント（Tableau Server 2025.3+ も同じ仕組みで動くはずだが本リポでは未確認）
- ブラウザ（OAuth サインイン用）

## 使い方

```bash
git clone https://github.com/<owner>/tableau-rest-api-oauth.git
cd tableau-rest-api-oauth
cp .env.example .env
# .env を実値で埋める

# 用途に応じて好きな example を実行
python examples/list_datasources.py
python examples/list_workbooks.py
python examples/list_projects.py
```

実行するとブラウザが自動で開いて Tableau Cloud のサインイン画面が出る → サインインすると `http://127.0.0.1:8765/Callback` に戻ってきて、ターミナルに access_token の情報と各 example 固有の一覧（最大 25 件）が表示される。

設定する環境変数は [`.env.example`](.env.example) 参照（`TABLEAU_SERVER` / `TABLEAU_SITE_NAME` / `LOCAL_CALLBACK_PORT` の 3 つ）。

各 example は OAuth フロー / HTTP ヘルパー / env 読み込みを [`examples/_shared/`](examples/_shared/) に分離しており、example 固有のコードは REST 呼び出し関数（`fetch_datasources` / `fetch_workbooks` / `fetch_projects`）だけ。別エンドポイントを試したい場合はこれらを差し替えるか、新しい example を 1 ファイル追加する。

## 仕組み

```
[Python script]                                      [Tableau Cloud]
      │
      │ 1. PKCE 生成 (verifier, challenge=S256(verifier))
      │ 2. localhost:8765 に HTTP listener 起動
      │ 3. webbrowser.open(authorize_url)
      │      GET /oauth2/v1/auth?client_id=<UUID>&code_challenge=...
      │           &redirect_uri=http://127.0.0.1:8765/Callback
      │           &target_site=<content_url>&client_type=...
      │ ───────────────────────────────────────────────►
      │       [ユーザがブラウザでサインイン]
      │       302 Redirect: /Callback?code=<code>&state=<state>
      │ ◄───────────────────────────────────────────────
      │ 4. listener が code 受信、state を検証
      │ 5. POST /oauth2/v1/token
      │      grant_type=authorization_code&code=...&code_verifier=...
      │ ───────────────────────────────────────────────►
      │      { access_token, refresh_token, expires_in, origin_host }
      │ ◄───────────────────────────────────────────────
      │ 6. access_token を | で分割 → 3 パート目を site_luid に
      │ 7. GET /api/<ver>/sites/<site_luid>/datasources
      │      X-Tableau-Auth: <access_token>     ← Bearer ではなく X-Tableau-Auth
      │ ───────────────────────────────────────────────►
      │      200 OK { datasources: [...] }
      │ ◄───────────────────────────────────────────────
```

`api_version` は startup 時に `/api/3.0/serverinfo`（無認証で叩ける）から取得するのでハードコード不要。

## ハマりポイント

- **`redirect_uri` の path は `/Callback`（大文字 C 固定）**。`/cb` 等にすると Tableau Cloud が `{"error": "invalid_request"}` を返す。
- **host は `127.0.0.1` 必須**（Tableau Cloud の制約）。Tableau Server なら admin が `tsm configuration set -k oauth.allowed_redirect_uri_hosts -v <host>` で任意ホストを許可リスト追加できる。
- **Tableau Cloud の本番ホスト構成は未対応**（20260521 時点）。最新状況は Tableau MCP の[公式 docs](https://github.com/tableau/tableau-mcp/blob/main/docs/docs/configuration/mcp-config/oauth.md) を参照。

## 制約

本リポは **対話的利用**（人がブラウザでサインインする）を前提とした最小実装:

| 制約 | 内容 |
| --- | --- |
| **毎回ブラウザサインイン** | refresh_token を保存していないので、再実行のたびにサインインが要る |
| **localhost 限定** | Tableau Cloud の制約で redirect_uri は 127.0.0.1 のみ。本番ホスト未対応 |

## 参考

- [Tableau MCP (公式リポ)](https://github.com/tableau/tableau-mcp)
- [Tableau MCP — Enabling OAuth (公式 docs)](https://github.com/tableau/tableau-mcp/blob/main/docs/docs/configuration/mcp-config/oauth.md)
- [Tableau REST API Authentication Methods](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_ref_authentication.htm)
- [OAuth 2.1 Draft](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1)
- [RFC 7636 (PKCE)](https://datatracker.ietf.org/doc/html/rfc7636)

## License

MIT（[LICENSE](LICENSE) 参照）
