# Yahoo!ファイナンス掲示板「アレム」さん通知Bot

「アレム」さんの新着投稿を **GitHub Actions** で15分おきに監視して **Telegram** に通知します。
スマホ側ではTelegramアプリにプッシュ通知が届きます。

## 構成
```
GitHub Actions (15分おき)
   ↓ scraper.py 実行
Yahoo!ファイナンス 投稿履歴ページ
   ↓ 差分検出
Telegram Bot → スマホのTelegramアプリ 🔔
```

## セットアップ手順

所要時間：約15分。

### Step 1. Telegram Bot を作る

1. スマホで **Telegram** をインストールしてアカウントを作成
2. Telegram内で **`@BotFather`** を検索してチャットを開く
3. `/newbot` と送信
4. ボットの名前を聞かれる：何でもOK（例：`Alem Notify`）
5. ユーザー名を聞かれる：末尾が `bot` で終わる必要あり（例：`alem_notify_bot`）
6. BotFatherが **HTTP API token** を返してくる。
   - 例：`7891234567:AAH-abcdefGHIJ...`
   - **これを TELEGRAM_TOKEN として控える**

### Step 2. 自分の chat_id を取得する

1. 作ったボットをTelegramで開いて **`/start` を送信** （これをしないとBotが自分に話しかけられない）
2. ブラウザで以下のURLを開く（`<TOKEN>`を置き換え）：
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. 返ってきたJSONの中に `"chat":{"id":123456789, ...}` がある。
   - **この数字が TELEGRAM_CHAT_ID**

### Step 3. GitHubリポジトリ作成

1. [github.com/new](https://github.com/new) でリポジトリ作成
   - 名前：`yahoo-alem-notifier` など
   - **Public** 推奨（無料プランでもActions無制限）
   - もしPrivateにする場合は `*/15` → `*/30` に変更（無料2000分/月の節約）
2. このフォルダ（`yahoo-alem-notifier/`）の中身をリポジトリにpush：

   ```bash
   cd yahoo-alem-notifier
   git init
   git add .
   git commit -m "init"
   git branch -M main
   git remote add origin https://github.com/<あなたのユーザー名>/yahoo-alem-notifier.git
   git push -u origin main
   ```

### Step 4. Secretsを設定

GitHubリポジトリの **Settings → Secrets and variables → Actions → New repository secret** で以下3つを追加：

| Name | 値 |
|------|-----|
| `YAHOO_USER_ID` | `a0e75bad9ac76a357687d1a3ca723486b99744308f803019ba98546a376608cc` |
| `TELEGRAM_TOKEN` | Step 1 で控えたトークン |
| `TELEGRAM_CHAT_ID` | Step 2 で取得したID |

### Step 5. Actionsの書き込み権限を有効化

**Settings → Actions → General → Workflow permissions** で
**「Read and write permissions」** を選択して **Save**。
（`state.json` を自動コミットするのに必要）

### Step 6. 動作確認

1. GitHubの **Actions** タブを開く
2. 左メニュー **「Yahoo Alem Notifier」** をクリック
3. **「Run workflow」** ボタンを押して手動実行
4. 緑チェックになればOK
5. 初回はTelegramには通知が来ない（`state.json` に現状を記録するだけ）
6. **2回目の実行以降**、新しい投稿があればTelegramに通知が届きます 🎉

## 仕様
- 監視間隔：15分（`*/15 * * * *`）。`.github/workflows/notify.yml` で変更可
- 通知タイミング：初回ラン後、次のラン以降の新着のみ
- 重複防止：直近300件の `(thread_url + No.x)` を `state.json` に保存
- ページ構造が変わって0件パースになっても通知は飛ばさず警告ログのみ

## 注意事項
- Yahoo! JAPANの利用規約上、過度なスクレイピングは禁止。本ツールは **15分に1回 / 1ページ取得** に留めており、個人的閲覧の延長として運用する想定
- HTML構造は予告なく変わる可能性あり。0件パースが続いたら `scraper.py` の `parse_comments` を要修正
- Telegram Botトークンは絶対に公開しない（Secretsに入れる）

## ローカルテスト（任意）
```bash
pip install -r requirements.txt
$env:YAHOO_USER_ID="a0e75bad..."
$env:TELEGRAM_TOKEN="7891234567:AAH-..."
$env:TELEGRAM_CHAT_ID="123456789"
python scraper.py
```
