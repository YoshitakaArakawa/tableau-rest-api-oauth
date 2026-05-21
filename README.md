# tableau-rest-api-oauth

Tableau REST API を **ユーザのブラウザサインインを経た OAuth access_token** で叩く最小実装。Python 標準ライブラリのみ、外部依存ゼロ。

## なぜこのリポがあるか

Tableau の公式 [REST API Authentication Methods](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_ref_authentication.htm) には、PAT / Connected App (JWT) / UAT / EAS Bearer はあるが、**OAuth 2.0 authorization_code フロー** によるサインインは載っていない。

一方、Tableau Server 2025.3 から `/oauth2/v1/auth` と `/oauth2/v1/token` という **OAuth 認可サーバエンドポイント**が追加され（Tableau Cloud にも存在する）、[公式 Tableau MCP](https://github.com/tableau/tableau-mcp) はこれを叩いて REST API を呼んでいる。Tableau MCP の動作観察から判明したのは:

1. `/oauth2/v1/token` から返ってくる `access_token` は **`<id1>|<id2>|<site-luid>` の 3 パート文字列**
2. それを **`X-Tableau-Auth` ヘッダにそのまま渡せば REST API が叩ける**（通常の session token と互換）
3. つまり「REST API には OAuth が無い」のではなく、「OAuth で取った token が既存の認証ヘッダに収まる形で発行される」が実態

本リポはこの仕組みを Tableau MCP を経由せず Python 単体で再現したもの。

## 動作要件

- Python 3.10+（型ヒント `dict[str, str]` 等を使用、3.10 から動く）
- Tableau Cloud アカウント（Tableau Server 2025.3+ も同じ仕組みで動くはずだが本リポでは未確認）
- ブラウザ（OAuth サインイン用）

## 使い方

```bash
git clone https://github.com/<owner>/tableau-rest-api-oauth.git
cd tableau-rest-api-oauth
cp .env.example .env
# .env を実値で埋める
python oauth_flow.py flow
```

ブラウザが自動で開いて Tableau Cloud のサインイン画面が出る → サインインすると `http://127.0.0.1:8765/Callback` に戻ってきて、ターミナルに access_token の構造と取得したデータソース一覧が表示される。

### `.env` の中身

```dotenv
TABLEAU_SERVER=https://<pod>.online.tableau.com   # 自テナントの pod URL
TABLEAU_SITE_NAME=<your-content-url>              # Content URL（display name ではない）
LOCAL_CALLBACK_PORT=8765
```

### 3 つのモード

```bash
# 1. authorization_code grant（デフォルト）: ブラウザサインイン → token → REST API
python oauth_flow.py flow

# 1b. client_type を変えて挙動を見る（自由値で OK、Tableau Cloud は値検証していない）
python oauth_flow.py flow --client-type my-app

# 2. refresh_token grant: 前回 flow で得た refresh_token を使って再取得
python oauth_flow.py refresh

# 3. /api/serverinfo（無認証）: productVersion / restApiVersion 確認
python oauth_flow.py serverinfo
```

`flow` 成功時に `.token-cache.json`（gitignored）に `client_id` / `refresh_token` / `site_namespace` / `origin_host` 等を保存。`refresh` モードがこれを読み、毎回 rotation された新 refresh_token でファイルを上書きする（OAuth 2.1 準拠の挙動）。

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
- **Tableau Cloud の本番ホスト構成は未対応**（執筆時点）。Tableau MCP の[公式 docs](https://github.com/tableau/tableau-mcp/blob/main/docs/docs/configuration/mcp-config/oauth.md) によると ETA Q2 2026。

## 制約 / 警告

本リポは **学習・実験用**。Production 用途には推奨しない理由:

| 弱点 | 内容 |
| --- | --- |
| **refresh_token の平文保存** | `.token-cache.json` に refresh_token が平文。OS のファイル ACL のみが防御 |
| **localhost 限定** | 本番ホストの redirect_uri は Tableau Cloud が許可していない |
| **アタックサーフェスの分散** | 各ユーザ PC で listener を立てる構成。中央集権 web app の方が監査・防御しやすい |
| **scope 制限が効きづらい** | Tableau access_token は site 全権限相当 |

Production で REST API をユーザ文脈で叩きたい場合は、Tableau 公式ルートを推奨:

- **[Connected App with OAuth 2.0 Trust (EAS)](https://help.tableau.com/current/online/en-us/connected_apps_eas.htm)**: 外部 IdP の JWT を `Authorization: Bearer` で REST API に渡す
- **Unified Access Token (UAT)**: 自前で署名した JWT を渡す
- **Personal Access Token (PAT)**: 簡単だが concurrent 不可

## ファイル構成

```
oauth_flow.py        # メインスクリプト (argparse、3 モード対応)
.env.example         # 環境変数テンプレート
.env                 # 実値（gitignored、自分でコピーして編集）
.token-cache.json    # refresh_token 等のキャッシュ（gitignored、flow 成功時に自動生成）
.gitignore
LICENSE              # MIT
README.md
```

## 参考

- [Tableau MCP (公式リポ)](https://github.com/tableau/tableau-mcp)
- [Tableau MCP — Enabling OAuth (公式 docs)](https://github.com/tableau/tableau-mcp/blob/main/docs/docs/configuration/mcp-config/oauth.md)
- [Tableau REST API Authentication Methods](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_ref_authentication.htm)
- [OAuth 2.1 Draft](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1)
- [RFC 7636 (PKCE)](https://datatracker.ietf.org/doc/html/rfc7636)

## License

MIT（[LICENSE](LICENSE) 参照）
