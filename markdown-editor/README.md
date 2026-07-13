# Markdown エディタ (PWA)

StackEdit 風の UI を持つ Markdown エディタです。PWA としてインストールでき、オフラインでも動作します。ドキュメントはブラウザ内(IndexedDB)に自動保存され、Google Drive / GitHub / Dropbox への保存にも対応しています。

## 機能

- **StackEdit 風レイアウト**: 左サイドバーでドキュメント管理、エディタ + ライブプレビューの分割表示(スクロール同期付き)
- **書式ツールバー**: 太字・斜体・見出し・リスト・タスクリスト・引用・コード・リンク・画像・表などをワンクリック挿入
- **表示モード**: エディタのみ / 分割 / プレビューのみ、ダーク・ライトテーマ
- **ローカル自動保存**: IndexedDB にデバウンス付きで自動保存。オフラインでも編集可能
- **インポート / エクスポート**: `.md` ファイルの読み込み、`.md` / `.html` のダウンロード
- **クラウド保存**: Google Drive / GitHub / Dropbox に保存・読み込み(下記の設定が必要)
- **PWA**: Service Worker によるオフラインキャッシュ、ホーム画面へのインストール対応

## 開発

```bash
npm install
npm run dev      # 開発サーバー
npm run build    # 本番ビルド (dist/)
npm run preview  # ビルド結果のプレビュー
```

PWA アイコンを再生成する場合(Chromium が必要):

```bash
node scripts/make-icons.mjs
```

## クラウド連携の設定

このアプリはサーバーを持たない静的 PWA のため、各サービスの認証情報は**利用者自身が取得して**アプリ内の「⚙ 設定」画面で入力します。認証情報はブラウザの localStorage にのみ保存されます。**共有端末では設定しないでください。**

### Google Drive

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成し、**Google Drive API** を有効化
2. 「API とサービス → 認証情報」で **OAuth クライアント ID(ウェブアプリケーション)** を作成
3. 「承認済みの JavaScript 生成元」にこのアプリの URL(例: `https://example.com`、開発時は `http://localhost:5173`)を追加
4. 発行されたクライアント ID を設定画面に入力

スコープは `drive.file`(このアプリが作成・開いたファイルのみアクセス可)を使用します。

### GitHub

1. GitHub の **Settings → Developer settings → Fine-grained personal access tokens** でトークンを作成
2. 対象リポジトリを選び、権限は **Contents: Read and write** のみ付与
3. 設定画面にトークン・リポジトリ(`owner/repo`)・ブランチ・保存先ディレクトリ(任意)を入力

保存すると対象リポジトリに `タイトル.md` としてコミットされます。

> GitHub の OAuth ウェブフローはクライアントシークレットを必要とするため、静的サイトでは PAT 方式を採用しています。

### Dropbox

1. [Dropbox App Console](https://www.dropbox.com/developers/apps) でアプリを作成(Scoped access / App folder または Full Dropbox)
2. Permissions で `files.content.write` と `files.content.read` を有効化
3. **Redirect URIs** にこのアプリの URL を登録
4. App key を設定画面に入力

認証は PKCE 付き OAuth 2 で行うため、クライアントシークレットは不要です。

## デプロイ

`npm run build` で生成される `dist/` を任意の静的ホスティング(GitHub Pages、Cloudflare Pages、Netlify など)に配置してください。PWA(Service Worker)の動作には HTTPS が必要です。

## 技術スタック

- React 18 + TypeScript + Vite
- CodeMirror 6(エディタ)/ markdown-it + DOMPurify + highlight.js(プレビュー)
- zustand(状態管理)/ idb(IndexedDB)
- vite-plugin-pwa(Service Worker / manifest)
