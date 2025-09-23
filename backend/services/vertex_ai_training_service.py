"""
Vertex AI モデルのファインチューニングと学習管理サービス
"""
import os
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from google.cloud import aiplatform
from google.cloud import storage
from google.cloud import firestore
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.preview.tuning import sft

class VertexAITrainingService:
    """
    Vertex AIのモデル学習とファインチューニングを管理するサービス
    """

    def __init__(self, project_id: str = None, location: str = "asia-northeast1"):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location

        if self.project_id:
            vertexai.init(project=self.project_id, location=self.location)
            aiplatform.init(project=self.project_id, location=self.location)
            self.storage_client = storage.Client(project=self.project_id)
            self.db = firestore.Client(project=self.project_id)
            self.training_bucket = f"{self.project_id}-training-data"

    def prepare_training_data_from_history(self,
                                          collection: str = "generated_problems",
                                          output_path: str = None) -> str:
        """
        生成履歴からトレーニングデータを作成

        Args:
            collection: Firestoreコレクション名
            output_path: 出力ファイルパス

        Returns:
            作成されたトレーニングデータのパス
        """
        if not self.db:
            raise Exception("Firestore client not initialized")

        # 生成履歴を取得
        docs = self.db.collection(collection).stream()

        training_examples = []

        for doc in docs:
            data = doc.to_dict()

            # 学習データ形式に変換
            example = {
                "messages": [
                    {
                        "role": "user",
                        "content": f"以下の条件で{data.get('subject')}の問題を作成してください。\n"
                                 f"学年: {data.get('grade')}\n"
                                 f"難易度: {data.get('difficulty')}\n"
                                 f"参考資料: {data.get('sourceFile', 'なし')}"
                    },
                    {
                        "role": "assistant",
                        "content": json.dumps({
                            "question": data.get('question'),
                            "answer": data.get('answer'),
                            "explanation": data.get('explanation')
                        }, ensure_ascii=False)
                    }
                ]
            }
            training_examples.append(example)

        # JSONL形式で保存
        output_path = output_path or f"training_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

        with open(output_path, 'w', encoding='utf-8') as f:
            for example in training_examples:
                f.write(json.dumps(example, ensure_ascii=False) + '\n')

        print(f"トレーニングデータを作成しました: {output_path}")
        print(f"例の数: {len(training_examples)}")

        return output_path

    def prepare_training_data_from_guidelines(self,
                                             guidelines_collection: str = "guidelines") -> str:
        """
        指導要領からトレーニングデータを作成

        Args:
            guidelines_collection: 指導要領のコレクション名

        Returns:
            作成されたトレーニングデータのパス
        """
        if not self.db:
            raise Exception("Firestore client not initialized")

        docs = self.db.collection(guidelines_collection).stream()

        training_examples = []

        for doc in docs:
            guideline = doc.to_dict()

            # 各学年の内容からトレーニングデータを生成
            if 'grade_specific' in guideline:
                for grade, topics in guideline.get('grade_specific', {}).items():
                    for topic in topics:
                        example = {
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "あなたは日本の学習指導要領に精通した教育問題作成の専門家です。"
                                },
                                {
                                    "role": "user",
                                    "content": f"{guideline.get('subject')}の{grade}で「{topic}」に関する問題を作成してください。"
                                },
                                {
                                    "role": "assistant",
                                    "content": f"学習指導要領に基づき、{grade}の「{topic}」に関する適切な問題を作成します。"
                                }
                            ]
                        }
                        training_examples.append(example)

        output_path = f"guidelines_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

        with open(output_path, 'w', encoding='utf-8') as f:
            for example in training_examples:
                f.write(json.dumps(example, ensure_ascii=False) + '\n')

        print(f"指導要領ベースのトレーニングデータを作成: {output_path}")
        print(f"例の数: {len(training_examples)}")

        return output_path

    def upload_training_data_to_gcs(self, local_path: str) -> str:
        """
        トレーニングデータをCloud Storageにアップロード

        Args:
            local_path: ローカルファイルパス

        Returns:
            GCS URI
        """
        bucket = self.storage_client.bucket(self.training_bucket)

        # バケットが存在しない場合は作成
        if not bucket.exists():
            bucket = self.storage_client.create_bucket(
                self.training_bucket,
                location=self.location
            )
            print(f"バケットを作成しました: {self.training_bucket}")

        blob_name = f"training_data/{os.path.basename(local_path)}"
        blob = bucket.blob(blob_name)

        blob.upload_from_filename(local_path)

        gcs_uri = f"gs://{self.training_bucket}/{blob_name}"
        print(f"データをアップロードしました: {gcs_uri}")

        return gcs_uri

    def start_fine_tuning(self,
                         training_data_uri: str,
                         model_display_name: str = None,
                         base_model: str = "gemini-1.5-flash-002",
                         epochs: int = 3) -> Dict:
        """
        ファインチューニングジョブを開始

        Args:
            training_data_uri: トレーニングデータのGCS URI
            model_display_name: モデルの表示名
            base_model: ベースモデル
            epochs: エポック数

        Returns:
            ジョブ情報
        """
        model_display_name = model_display_name or f"manatasu-model-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # ファインチューニングジョブを作成
        sft_tuning_job = sft.train(
            source_model=base_model,
            train_dataset=training_data_uri,
            epochs=epochs,
            adapter_size=4,
            learning_rate_multiplier=1.0,
            tuned_model_display_name=model_display_name,
        )

        print(f"ファインチューニングジョブを開始しました")
        print(f"ジョブ名: {sft_tuning_job.name}")
        print(f"モデル名: {model_display_name}")

        # ジョブ情報をFirestoreに保存
        if self.db:
            job_data = {
                "job_name": sft_tuning_job.name,
                "model_display_name": model_display_name,
                "base_model": base_model,
                "training_data_uri": training_data_uri,
                "epochs": epochs,
                "status": "running",
                "created_at": firestore.SERVER_TIMESTAMP
            }

            self.db.collection("training_jobs").document(sft_tuning_job.name).set(job_data)

        return {
            "job": sft_tuning_job,
            "model_display_name": model_display_name
        }

    def get_tuned_model(self, model_name: str) -> GenerativeModel:
        """
        ファインチューニング済みモデルを取得

        Args:
            model_name: モデル名

        Returns:
            GenerativeModel インスタンス
        """
        # チューニング済みモデルのエンドポイントを取得
        model = GenerativeModel(model_name)
        return model

    def create_embedding_index(self, documents: List[Dict]) -> str:
        """
        ドキュメントのエンベディングインデックスを作成（Vector Search用）

        Args:
            documents: インデックス化するドキュメント

        Returns:
            インデックスID
        """
        from vertexai.language_models import TextEmbeddingModel

        # エンベディングモデルを初期化
        embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-005")

        # エンベディングを生成
        embeddings = []
        for doc in documents:
            text = doc.get('content', '')
            if text:
                embedding = embedding_model.get_embeddings([text])[0].values
                embeddings.append({
                    'id': doc.get('id'),
                    'embedding': embedding,
                    'metadata': doc
                })

        # Vector Search インデックスを作成
        index_name = f"manatasu-index-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Firestoreに保存（簡易版）
        if self.db:
            for emb in embeddings:
                self.db.collection('embeddings').document(emb['id']).set({
                    'embedding': emb['embedding'],
                    'metadata': emb['metadata'],
                    'created_at': firestore.SERVER_TIMESTAMP
                })

        print(f"エンベディングインデックスを作成: {index_name}")
        print(f"ドキュメント数: {len(embeddings)}")

        return index_name

    def search_similar_content(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        類似コンテンツを検索

        Args:
            query: 検索クエリ
            top_k: 取得する結果数

        Returns:
            類似ドキュメントのリスト
        """
        from vertexai.language_models import TextEmbeddingModel
        import numpy as np

        # クエリのエンベディングを生成
        embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-005")
        query_embedding = embedding_model.get_embeddings([query])[0].values

        # Firestoreから全エンベディングを取得（実際の実装では効率化が必要）
        if not self.db:
            return []

        docs = self.db.collection('embeddings').stream()

        similarities = []
        for doc in docs:
            data = doc.to_dict()
            doc_embedding = data.get('embedding', [])

            if doc_embedding:
                # コサイン類似度を計算
                similarity = np.dot(query_embedding, doc_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding)
                )

                similarities.append({
                    'id': doc.id,
                    'similarity': similarity,
                    'metadata': data.get('metadata', {})
                })

        # 類似度でソート
        similarities.sort(key=lambda x: x['similarity'], reverse=True)

        return similarities[:top_k]

    def create_rag_prompt(self, query: str, context_docs: List[Dict]) -> str:
        """
        RAG (Retrieval-Augmented Generation) 用のプロンプトを作成

        Args:
            query: ユーザーのクエリ
            context_docs: 関連ドキュメント

        Returns:
            RAGプロンプト
        """
        prompt = f"""
        以下の参考情報を基に、質問に答えてください。

        【参考情報】
        """

        for i, doc in enumerate(context_docs, 1):
            prompt += f"""
        {i}. {doc.get('metadata', {}).get('title', 'ドキュメント' + str(i))}
        {doc.get('metadata', {}).get('content', '')}
        """

        prompt += f"""

        【質問】
        {query}

        【回答】
        参考情報に基づいて、正確かつ詳細に回答してください。
        """

        return prompt


# 使用例とヘルパー関数
def train_model_from_history():
    """
    生成履歴からモデルをトレーニングする例
    """
    service = VertexAITrainingService()

    # 1. トレーニングデータを準備
    training_file = service.prepare_training_data_from_history()

    # 2. GCSにアップロード
    gcs_uri = service.upload_training_data_to_gcs(training_file)

    # 3. ファインチューニングを開始
    result = service.start_fine_tuning(
        training_data_uri=gcs_uri,
        model_display_name="manatasu-custom-model",
        epochs=5
    )

    print(f"トレーニングジョブを開始しました: {result['job'].name}")

    return result

def use_tuned_model(model_name: str, prompt: str):
    """
    ファインチューニング済みモデルを使用する例
    """
    service = VertexAITrainingService()

    # チューニング済みモデルを取得
    model = service.get_tuned_model(model_name)

    # 推論を実行
    response = model.generate_content(prompt)

    return response.text

def setup_rag_system():
    """
    RAGシステムをセットアップする例
    """
    service = VertexAITrainingService()

    # ドキュメントを準備
    documents = [
        {
            "id": "doc1",
            "content": "小学1年生の算数では、10までの数の概念を学習します...",
            "title": "小学1年算数指導要領"
        },
        {
            "id": "doc2",
            "content": "たし算とひき算の基礎を身につけることが重要です...",
            "title": "計算の基礎"
        }
    ]

    # エンベディングインデックスを作成
    index_name = service.create_embedding_index(documents)

    print(f"RAGシステムをセットアップしました: {index_name}")

    return index_name


if __name__ == "__main__":
    # 使用例
    # train_model_from_history()
    # setup_rag_system()
    pass