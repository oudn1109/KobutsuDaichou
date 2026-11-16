# 古物商対応・物販管理Webアプリ

メルカリでの物販および古物営業法に基づく台帳管理を行うWebアプリです。
**Streamlit Community Cloud（無料）** を使えば、専用URLを発行してChromeのブックマークからどのパソコン・スマホでもパッと開けるようになります。

---

## どのパソコンからでもURLで開けるようにする手順（クラウド公開）

一度だけ以下の設定を行えば、今後は黒い画面（コマンドプロンプト）を開く必要がなくなり、パソコンを買い替えてもChromeのブックマークからそのまま使えます。

### 事前準備：GoogleスプレッドシートとGemini APIキーの用意
（※別のパソコンとデータを共有するため、保存先をGoogleスプレッドシートにします）

1. **Gemini APIキーの取得**
   - [Google AI Studio](https://aistudio.google.com/) からAPIキーを取得します。
2. **GoogleスプレッドシートとサービスアカウントJSONの準備**
   - [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成し、「Google Sheets API」と「Google Drive API」を有効化します。
   - 「IAMと管理」＞「サービスアカウント」からアカウントを作成し、「キー」タブから **JSON形式の鍵ファイル** をダウンロードします。
   - 新規作成したGoogleスプレッドシートの「共有」ボタンから、サービスアカウントのメールアドレス（`xxx@xxx.iam.gserviceaccount.com`）を「編集者」として追加し、スプレッドシートのURLから `SPREADSHEET_ID`（`/d/` と `/edit` の間の文字列）を控えます。

---

### STEP 1：GitHubにアプリのファイルを入れる
1. [GitHub](https://github.com/) にログインし、右上の「**＋**」＞「**New repository**」をクリックします。
2. Repository name に `buppan-app` など好きな名前を入力し、**「Private（非公開）」** を選んで「**Create repository**」を押します。
3. 画面内の「**uploading an existing file**」というリンクをクリックし、このフォルダの中にある以下のファイル・フォルダをドラッグ＆ドロップでアップロードして「**Commit changes**」を押します。
   - `app.py`
   - `requirements.txt`
   - `services` フォルダ
   - `.streamlit` フォルダ
   - `data` フォルダ
   （※ `service_account.json` や `.env` などの鍵ファイルはアップロードしないでください）

---

### STEP 2：Streamlit Community Cloudで専用URLを発行する
1. [Streamlit Community Cloud](https://share.streamlit.io/) にアクセスし、GoogleアカウントまたはGitHubアカウントでログインします。
2. 右上の「**Create app**」ボタンをクリックします。
3. 先ほど作成したリポジトリ（`buppan-app`）を選択し、Main file path に `app.py` と入力します。
4. **「Advanced settings...」** をクリックし、**Secrets** の入力欄に以下のようにAPIキーとスプレッドシート情報を貼り付けます。

```toml
GEMINI_API_KEY = "ここにGeminiのAPIキー"
SPREADSHEET_ID = "ここにスプレッドシートのID"

# ダウンロードしたサービスアカウントJSONの中身をそのままトリプルクォートの中に貼り付けます
GOOGLE_SERVICE_ACCOUNT_JSON = '''
{
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "...@...iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "..."
}
'''
```

5. 「**Deploy!**」ボタンを押すと、1〜2分ほどであなた専用のURL（`https://〇〇〇.streamlit.app`）が発行されて画面が開きます。
6. そのページを **Chromeのブックマークに登録** すれば完了です！
