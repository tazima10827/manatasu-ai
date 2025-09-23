#!/usr/bin/env python3
"""
Vertex AI モデルのトレーニングスクリプト
"""

import os
import sys
import argparse
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from services.vertex_ai_training_service import VertexAITrainingService
from dotenv import load_dotenv

load_dotenv()

def train_from_firestore_history():
    """
    Firestoreの生成履歴からモデルをトレーニング
    """
    print("=" * 50)
    print("Firestoreの生成履歴からモデルをトレーニング")
    print("=" * 50)

    service = VertexAITrainingService()

    try:
        # 1. トレーニングデータを準備
        print("\n1. トレーニングデータを準備中...")
        training_file = service.prepare_training_data_from_history()

        # 2. GCSにアップロード
        print("\n2. Cloud Storageにアップロード中...")
        gcs_uri = service.upload_training_data_to_gcs(training_file)

        # 3. ファインチューニングを開始
        print("\n3. ファインチューニングを開始中...")
        result = service.start_fine_tuning(
            training_data_uri=gcs_uri,
            model_display_name="manatasu-custom-model",
            epochs=3
        )

        print("\n✅ トレーニングジョブが正常に開始されました！")
        print(f"ジョブ名: {result['job'].name}")
        print(f"モデル名: {result['model_display_name']}")
        print("\n⏰ トレーニングには通常1-2時間かかります。")
        print("完了後、モデル名を使用して推論を実行できます。")

        return result

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        return None

def train_from_guidelines():
    """
    指導要領データからモデルをトレーニング
    """
    print("=" * 50)
    print("指導要領データからモデルをトレーニング")
    print("=" * 50)

    service = VertexAITrainingService()

    try:
        # 1. 指導要領からトレーニングデータを準備
        print("\n1. 指導要領からトレーニングデータを準備中...")
        training_file = service.prepare_training_data_from_guidelines()

        # 2. GCSにアップロード
        print("\n2. Cloud Storageにアップロード中...")
        gcs_uri = service.upload_training_data_to_gcs(training_file)

        # 3. ファインチューニングを開始
        print("\n3. ファインチューニングを開始中...")
        result = service.start_fine_tuning(
            training_data_uri=gcs_uri,
            model_display_name="manatasu-guidelines-model",
            epochs=5
        )

        print("\n✅ トレーニングジョブが正常に開始されました！")
        print(f"ジョブ名: {result['job'].name}")
        print(f"モデル名: {result['model_display_name']}")

        return result

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        return None

def setup_rag_system():
    """
    RAG（Retrieval-Augmented Generation）システムをセットアップ
    """
    print("=" * 50)
    print("RAGシステムをセットアップ")
    print("=" * 50)

    service = VertexAITrainingService()

    try:
        # Firestoreから指導要領データを取得してエンベディング
        print("\n1. 指導要領データを取得中...")

        if not service.db:
            print("❌ Firestoreクライアントが初期化されていません")
            return None

        docs = service.db.collection('guidelines').stream()

        documents = []
        for doc in docs:
            data = doc.to_dict()
            # 各トピックをドキュメント化
            for topic in data.get('topics', []):
                documents.append({
                    'id': f"{doc.id}_{topic}",
                    'content': f"{data.get('subject')} - {data.get('grade')} - {topic}\n"
                              f"学習目標: {', '.join(data.get('learning_goals', [])[:3])}",
                    'title': f"{data.get('subject')} {topic}"
                })

        print(f"  ドキュメント数: {len(documents)}")

        # 2. エンベディングインデックスを作成
        print("\n2. エンベディングインデックスを作成中...")
        index_name = service.create_embedding_index(documents)

        print("\n✅ RAGシステムのセットアップが完了しました！")
        print(f"インデックス名: {index_name}")
        print(f"ドキュメント数: {len(documents)}")

        return index_name

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        return None

def test_custom_model(model_name: str, prompt: str = None):
    """
    カスタムモデルをテスト

    Args:
        model_name: モデル名またはエンドポイント
        prompt: テストプロンプト
    """
    print("=" * 50)
    print("カスタムモデルをテスト")
    print("=" * 50)

    service = VertexAITrainingService()

    if not prompt:
        prompt = """
        小学3年生の算数で、かけ算の文章問題を1つ作成してください。
        実生活に関連した内容で、子供が興味を持てるような問題にしてください。
        """

    try:
        print(f"\nモデル: {model_name}")
        print(f"\nプロンプト:\n{prompt}")

        # モデルを取得
        model = service.get_tuned_model(model_name)

        # 推論を実行
        print("\n回答を生成中...")
        response = model.generate_content(prompt)

        print("\n=== モデルの回答 ===")
        print(response.text)

        return response.text

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        return None

def test_rag_search(query: str):
    """
    RAG検索をテスト

    Args:
        query: 検索クエリ
    """
    print("=" * 50)
    print("RAG検索をテスト")
    print("=" * 50)

    service = VertexAITrainingService()

    try:
        print(f"\n検索クエリ: {query}")

        # 類似コンテンツを検索
        print("\n類似コンテンツを検索中...")
        similar_docs = service.search_similar_content(query, top_k=3)

        print("\n=== 検索結果 ===")
        for i, doc in enumerate(similar_docs, 1):
            print(f"\n{i}. {doc['metadata'].get('title', 'タイトルなし')}")
            print(f"   類似度: {doc['similarity']:.4f}")
            print(f"   内容: {doc['metadata'].get('content', '')[:100]}...")

        # RAGプロンプトを作成
        rag_prompt = service.create_rag_prompt(query, similar_docs)

        # 標準モデルで回答を生成
        print("\n\n=== RAGベースの回答 ===")
        model = GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(rag_prompt)
        print(response.text)

        return similar_docs

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(
        description="Vertex AI モデルのトレーニングとテスト"
    )

    subparsers = parser.add_subparsers(dest="command", help="実行するコマンド")

    # train-history コマンド
    subparsers.add_parser(
        "train-history",
        help="生成履歴からモデルをトレーニング"
    )

    # train-guidelines コマンド
    subparsers.add_parser(
        "train-guidelines",
        help="指導要領からモデルをトレーニング"
    )

    # setup-rag コマンド
    subparsers.add_parser(
        "setup-rag",
        help="RAGシステムをセットアップ"
    )

    # test-model コマンド
    test_model_parser = subparsers.add_parser(
        "test-model",
        help="カスタムモデルをテスト"
    )
    test_model_parser.add_argument(
        "model_name",
        help="モデル名またはエンドポイント"
    )
    test_model_parser.add_argument(
        "--prompt",
        help="テストプロンプト"
    )

    # test-rag コマンド
    test_rag_parser = subparsers.add_parser(
        "test-rag",
        help="RAG検索をテスト"
    )
    test_rag_parser.add_argument(
        "query",
        help="検索クエリ"
    )

    args = parser.parse_args()

    if args.command == "train-history":
        train_from_firestore_history()

    elif args.command == "train-guidelines":
        train_from_guidelines()

    elif args.command == "setup-rag":
        setup_rag_system()

    elif args.command == "test-model":
        test_custom_model(args.model_name, args.prompt)

    elif args.command == "test-rag":
        test_rag_search(args.query)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()