# manatasuAI - 中学校教員向け問題自動生成システム

## 概要
manatasuAIは、中学校教員向けの問題自動生成Webアプリケーションです。PDFファイルをアップロードし、AIを活用して自動的に問題を生成します。生成された問題には出典情報が自動的に付与され、PDF形式でダウンロード可能です。

## 主な機能
- PDFファイルのアップロード
- 問題生成パラメータの設定（教科、学年、難易度、問題数など）
- AI（Google Vertex AI）による問題自動生成
- 出典情報の自動付与
- 生成結果のプレビュー表示
- PDF形式での書き出し・ダウンロード・印刷

## 技術スタック

### フロントエンド
- Flutter Web (PWA対応)
- Provider (状態管理)
- GoRouter (ルーティング)
- Syncfusion Flutter PDF (PDFビューア)

### バックエンド
- FastAPI (Python)
- Google Cloud Run
- Google Vertex AI (Gemini 1.5)
- Google Cloud Firestore
- Google Cloud Storage

## セットアップ

### 前提条件
- Flutter SDK (3.0以上)
- Python 3.11以上
- Google Cloud Project
- Vertex AI APIの有効化

### フロントエンドのセットアップ
```bash
cd manatasu_ai
flutter pub get
flutter run -d chrome
```

### バックエンドのセットアップ
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# .envファイルを編集して必要な環境変数を設定
python main.py
```

## 環境変数

### バックエンド (.env)
```
GOOGLE_CLOUD_PROJECT=your-project-id
VERTEX_AI_LOCATION=asia-northeast1
API_KEY=your-secure-api-key
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
```

### フロントエンド
`lib/utils/config.dart`でAPI設定を管理:
- `useMockData`: 開発時はtrueに設定（モックデータを使用）
- `apiBaseUrl`: APIエンドポイントURL
- `apiKey`: APIキー

## デプロイ

### Cloud Runへのデプロイ
```bash
cd backend
gcloud run deploy manatasu-ai-api \
  --source . \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated
```

### Flutter Webのビルド
```bash
flutter build web --release
```

## セキュリティ
- API認証にはBearer Tokenを使用
- CORSの適切な設定
- 環境変数による機密情報の管理
- アップロードファイルのサイズ制限（50MB）

## ライセンス
MIT