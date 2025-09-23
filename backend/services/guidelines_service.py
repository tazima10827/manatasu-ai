"""
文部科学省指導要領管理サービス
"""
import os
import json
from typing import Dict, List, Optional
from google.cloud import firestore
from google.cloud import storage
import PyPDF2
from io import BytesIO

class GuidelinesService:
    """指導要領データを管理するサービスクラス"""

    def __init__(self, project_id: str = None):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        if self.project_id:
            self.db = firestore.Client(project=self.project_id)
            self.storage_client = storage.Client(project=self.project_id)
            self.bucket_name = f"{self.project_id}-guidelines"
        else:
            self.db = None
            self.storage_client = None

    def upload_guideline_pdf(self, pdf_path: str, subject: str, grade: str) -> Dict:
        """
        指導要領PDFをアップロードして解析

        Args:
            pdf_path: PDFファイルのパス
            subject: 教科（例: "数学", "国語"）
            grade: 学年（例: "小学1年", "中学2年"）

        Returns:
            保存された指導要領データ
        """
        # PDFを読み込み
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text_content = ""

            for page_num, page in enumerate(pdf_reader.pages):
                text_content += f"\n--- Page {page_num + 1} ---\n"
                text_content += page.extract_text()

        # データ構造を作成
        guideline_data = {
            "subject": subject,
            "grade": grade,
            "content": text_content,
            "topics": self._extract_topics(text_content),
            "learning_goals": self._extract_learning_goals(text_content),
            "keywords": self._extract_keywords(text_content),
            "uploaded_at": firestore.SERVER_TIMESTAMP
        }

        # Firestoreに保存
        if self.db:
            doc_ref = self.db.collection('guidelines').document(f"{subject}_{grade}")
            doc_ref.set(guideline_data)

            # Cloud Storageにも元のPDFを保存
            if self.storage_client:
                bucket = self.storage_client.bucket(self.bucket_name)
                blob = bucket.blob(f"guidelines/{subject}/{grade}/guideline.pdf")
                blob.upload_from_filename(pdf_path)

        return guideline_data

    def _extract_topics(self, text: str) -> List[str]:
        """テキストから主要トピックを抽出"""
        topics = []

        # 指導要領でよく使われるキーワードパターン
        topic_keywords = [
            "数と計算", "量と測定", "図形", "数量関係",
            "話すこと・聞くこと", "書くこと", "読むこと",
            "物質・エネルギー", "生命・地球",
            "地理的分野", "歴史的分野", "公民的分野"
        ]

        for keyword in topic_keywords:
            if keyword in text:
                topics.append(keyword)

        return topics

    def _extract_learning_goals(self, text: str) -> List[str]:
        """学習目標を抽出"""
        goals = []

        # "目標" や "ねらい" を含む行を抽出
        lines = text.split('\n')
        for line in lines:
            if '目標' in line or 'ねらい' in line:
                goals.append(line.strip())

        return goals[:10]  # 最初の10個まで

    def _extract_keywords(self, text: str) -> List[str]:
        """重要キーワードを抽出"""
        # 簡易的なキーワード抽出
        # 実際の実装では形態素解析などを使用
        keywords = []

        important_terms = [
            "基礎的", "基本的", "思考力", "判断力", "表現力",
            "主体的", "対話的", "深い学び", "資質・能力"
        ]

        for term in important_terms:
            if term in text:
                keywords.append(term)

        return keywords

    def get_guideline(self, subject: str, grade: str) -> Optional[Dict]:
        """
        指定された教科・学年の指導要領を取得

        Args:
            subject: 教科
            grade: 学年

        Returns:
            指導要領データ
        """
        if not self.db:
            return None

        doc_ref = self.db.collection('guidelines').document(f"{subject}_{grade}")
        doc = doc_ref.get()

        if doc.exists:
            return doc.to_dict()
        return None

    def get_relevant_guidelines(self, subject: str, grade: str, topic: str = None) -> List[Dict]:
        """
        関連する指導要領を検索

        Args:
            subject: 教科
            grade: 学年
            topic: トピック（オプション）

        Returns:
            関連する指導要領のリスト
        """
        if not self.db:
            return []

        # 基本クエリ
        query = self.db.collection('guidelines')
        query = query.where('subject', '==', subject)

        results = []
        for doc in query.stream():
            data = doc.to_dict()

            # 学年でフィルタリング
            if grade in data.get('grade', ''):
                # トピックが指定されている場合は関連度をチェック
                if topic:
                    if topic in data.get('content', '') or topic in data.get('topics', []):
                        results.append(data)
                else:
                    results.append(data)

        return results

    def create_problem_with_guidelines(self,
                                      subject: str,
                                      grade: str,
                                      problem_type: str,
                                      pdf_content: str) -> str:
        """
        指導要領を参照して問題生成用のプロンプトを作成

        Args:
            subject: 教科
            grade: 学年
            problem_type: 問題タイプ
            pdf_content: アップロードされたPDFの内容

        Returns:
            指導要領を含むプロンプト
        """
        # 関連する指導要領を取得
        guidelines = self.get_relevant_guidelines(subject, grade)

        prompt = f"""
        以下の情報を参考に、{subject}の{grade}向けの{problem_type}を生成してください。

        【文部科学省学習指導要領】
        """

        if guidelines:
            for guideline in guidelines[:2]:  # 最大2つまで
                prompt += f"""
        ■ {guideline.get('grade')} - {guideline.get('subject')}
        学習目標: {', '.join(guideline.get('learning_goals', [])[:3])}
        重要トピック: {', '.join(guideline.get('topics', []))}
        キーワード: {', '.join(guideline.get('keywords', []))}

        """
        else:
            prompt += """
        ※指導要領データが見つかりませんでした。一般的な学習目標に基づいて問題を作成します。
        """

        prompt += f"""
        【参考資料（PDF内容）】
        {pdf_content[:5000]}

        上記の指導要領と参考資料を踏まえて、以下の条件で問題を作成してください：
        - 学習指導要領の目標に沿った内容
        - 発達段階に適した難易度
        - 思考力・判断力・表現力を育成する問題

        JSON形式で出力してください。
        """

        return prompt


# 使用例
if __name__ == "__main__":
    service = GuidelinesService()

    # 指導要領PDFをアップロード
    # service.upload_guideline_pdf(
    #     pdf_path="/path/to/小学校学習指導要領_算数.pdf",
    #     subject="算数",
    #     grade="小学校全学年"
    # )

    # 指導要領を取得
    # guideline = service.get_guideline("算数", "小学1年")
    # print(guideline)