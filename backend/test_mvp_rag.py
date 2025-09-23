#!/usr/bin/env python3
"""
MVP RAGサービスのテストスクリプト
"""

import os
import sys
import traceback

# 親ディレクトリをPythonパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.mvp_rag_service import MVPRAGService

def test_mvp_rag():
    print("MVP RAGサービスのテストを開始")

    # 環境変数を設定
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    print(f"Project ID: {project_id}")

    try:
        # MVPRAGサービスのインスタンスを作成
        mvp_rag = MVPRAGService(project_id=project_id)
        print("MVPRAGService インスタンス作成完了")

        # テストパラメータ
        test_params = {
            "subject": "数学",
            "grade": "小学5年",
            "difficulty": "普通",
            "problem_count": 1,
            "problem_type": "計算問題",
            "pdf_content": "テスト用のPDFコンテンツです。",
            "specific_topic": "掛け算"
        }

        print("問題生成テストを開始...")
        result = mvp_rag.generate_with_rag(**test_params)

        print("テスト成功!")
        print(f"結果: {result}")

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        print("詳細なトレースバック:")
        traceback.print_exc()

if __name__ == "__main__":
    test_mvp_rag()