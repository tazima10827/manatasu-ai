"""
MVP版 RAGサービス - 小規模テスト向け最適化版
月額$50以下で動作するように設計
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import hashlib
from google.cloud import firestore
import vertexai
from vertexai.generative_models import GenerativeModel
from .curriculum_guideline_service import CurriculumGuidelineService

class MVPRAGService:
    """
    MVP版RAGサービス
    - Firestore内蔵検索を使用（Vector Searchの代わり）
    - シンプルなキャッシング
    - 基本的なRAG機能
    """

    def __init__(self, project_id: str = None):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")

        if self.project_id:
            vertexai.init(project=self.project_id, location="asia-northeast1")
            self.db = firestore.Client(project=self.project_id)
            self.model = GenerativeModel("gemini-1.5-flash-002")

        # インメモリキャッシュ（簡易版）
        self.cache = {}
        self.cache_expiry = {}

        # 学習指導要領サービスを初期化
        self.curriculum_service = CurriculumGuidelineService(project_id)

        # コスト最適化設定
        self.config = {
            "max_input_tokens": 8192,  # 入力トークンを制限
            "max_output_tokens": 1024,  # 出力トークンを制限
            "temperature": 0.7,
            "top_k": 40,
            "top_p": 0.95,
            "cache_ttl_minutes": 60,  # キャッシュ期間
            "max_cache_size": 100,  # 最大キャッシュサイズ
        }

    def search_relevant_content(self,
                                subject: str,
                                grade: str,
                                topic: Optional[str] = None,
                                limit: int = 5) -> List[Dict]:
        """
        Firestoreから関連コンテンツを検索（シンプル版）

        Args:
            subject: 教科
            grade: 学年
            topic: トピック（オプション）
            limit: 取得数

        Returns:
            関連ドキュメントのリスト
        """
        results = []

        # project_idが設定されていない場合は空の結果を返す
        if not hasattr(self, 'db') or self.db is None:
            print("Warning: Firestore not initialized. Returning empty results.")
            return results

        # 1. 学習指導要領を検索（新しいサービスを使用）
        if topic:
            # トピック指定がある場合は検索
            curriculum_results = self.curriculum_service.search_guidelines(
                query=topic, subject=subject, grade=grade
            )
        else:
            # トピック指定がない場合は教科の指導要領を取得
            curriculum_data = self.curriculum_service.get_guidelines_for_subject(subject, grade)
            curriculum_results = [curriculum_data] if curriculum_data else []

        # 学習指導要領結果を追加
        for curriculum in curriculum_results:
            if curriculum:
                content = self._format_curriculum_content(curriculum)
                score = curriculum.get('score', 1.5)  # 学習指導要領は高いスコア
                results.append({
                    'id': curriculum.get('id', f"curriculum_{subject}"),
                    'type': 'curriculum_guideline',
                    'content': content,
                    'score': score,
                    'metadata': curriculum
                })

        # 2. 従来の指導要領検索（下位互換性のため）
        if len(results) < limit:
            guidelines_query = self.db.collection('guidelines')
            guidelines_query = guidelines_query.where('subject', '==', subject)

            for doc in guidelines_query.stream():
                data = doc.to_dict()
                if self._is_relevant_grade(grade, data.get('grade', '')):
                    # 関連度スコアを簡易計算
                    score = self._calculate_relevance_score(topic, data)
                    results.append({
                        'id': doc.id,
                        'type': 'guideline',
                        'content': self._format_guideline_content(data),
                        'score': score,
                        'metadata': data
                    })

        # 3. 過去の生成問題を検索（類似問題の参考用）
        if len(results) < limit:
            problems_query = self.db.collection('generated_problems').limit(20)
            problems_query = problems_query.where('subject', '==', subject)

            for doc in problems_query.stream():
                data = doc.to_dict()
                if self._is_relevant_grade(grade, data.get('grade', '')):
                    results.append({
                        'id': doc.id,
                        'type': 'problem',
                        'content': self._format_problem_content(data),
                        'score': 0.5,  # 固定スコア
                        'metadata': data
                    })

        # スコアでソートして上位を返す
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

    def generate_with_rag(self,
                         subject: str,
                         grade: str,
                         difficulty: str,
                         problem_count: int,
                         problem_type: str,
                         pdf_content: str = "",
                         specific_topic: Optional[str] = None,
                         filename: Optional[str] = None) -> Dict:
        """
        RAGを使用して問題を生成（MVP版）

        Args:
            subject: 教科
            grade: 学年
            difficulty: 難易度
            problem_count: 問題数
            problem_type: 問題形式
            pdf_content: PDF内容
            specific_topic: 特定トピック

        Returns:
            生成された問題
        """
        # キャッシュキーを生成
        cache_key = self._generate_cache_key({
            'subject': subject,
            'grade': grade,
            'difficulty': difficulty,
            'problem_type': problem_type,
            'topic': specific_topic
        })

        # キャッシュチェック
        if cached_result := self._get_from_cache(cache_key):
            print("Cache hit! Returning cached result.")
            return cached_result

        # 関連コンテンツを検索
        relevant_docs = self.search_relevant_content(
            subject=subject,
            grade=grade,
            topic=specific_topic,
            limit=3  # コストを抑えるため少なめに
        )

        # プロンプトを構築
        prompt = self._build_mvp_prompt(
            subject=subject,
            grade=grade,
            difficulty=difficulty,
            problem_count=problem_count,
            problem_type=problem_type,
            relevant_docs=relevant_docs,
            pdf_content=pdf_content[:15000],  # PDFコンテンツを大幅に拡張
            specific_topic=specific_topic,
            filename=filename
        )

        # トークン数を確認（コスト管理）
        estimated_tokens = len(prompt) / 4  # 概算
        if estimated_tokens > self.config['max_input_tokens']:
            # プロンプトを短縮
            prompt = prompt[:self.config['max_input_tokens'] * 4]

        try:
            # modelが初期化されていない場合はエラーを投げる
            if not hasattr(self, 'model') or self.model is None:
                raise Exception("Google Cloud Project ID not configured. Cannot generate content.")

            # Geminiで生成
            generation_config = {
                "temperature": self.config['temperature'],
                "top_k": self.config['top_k'],
                "top_p": self.config['top_p'],
                "max_output_tokens": self.config['max_output_tokens'],
            }

            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )

            # レスポンスを解析
            result = self._parse_response(response.text)

            # ファイル名情報を追加
            if filename and pdf_content and result.get('problems'):
                for problem in result['problems']:
                    problem['source'] = filename

            # キャッシュに保存
            self._save_to_cache(cache_key, result)

            # 使用統計を記録（コスト追跡用）
            self._log_usage(estimated_tokens, len(response.text) / 4)

            return result

        except Exception as e:
            print(f"Error in generation: {e}")
            # フォールバック: 基本的な応答を返す
            return self._get_fallback_response(
                subject, grade, difficulty, problem_count, problem_type
            )

    def _build_mvp_prompt(self, **kwargs) -> str:
        """MVP版プロンプトを構築"""

        # PDF内容がある場合は最優先で扱う
        if pdf_content := kwargs.get('pdf_content'):
            filename = kwargs.get('filename', 'document.pdf')
            prompt = f"""
あなたは日本の教育専門家です。

【重要: 必ずアップロードされたPDFファイルの内容を基に問題を作成してください】

=== 主要参考資料（最優先） ===
--- アップロードされたPDF: {filename} ---
{pdf_content[:8000]}  # PDFコンテンツを8000文字まで拡張

上記PDFファイルの内容から、具体的な問題、例題、テーマ、コンセプトを抽出し、
それらを直接参考にして問題を作成してください。

【追加参考情報】
"""
        else:
            prompt = f"""
あなたは日本の教育専門家です。以下の情報を参考に問題を生成してください。

【参考情報】
"""

        # 関連ドキュメントを追加（最大3つ）
        for i, doc in enumerate(kwargs.get('relevant_docs', [])[:3], 1):
            prompt += f"""
--- 参考{i} ---
{doc['content'][:1000]}  # 各参考情報を1000文字に制限
"""

        prompt += f"""

【生成条件】
- 教科: {kwargs.get('subject')}
- 学年: {kwargs.get('grade')}
- 難易度: {kwargs.get('difficulty')}
- 問題数: {kwargs.get('problem_count')}
- 問題形式: {kwargs.get('problem_type')}
{f"- トピック: {kwargs.get('specific_topic')}" if kwargs.get('specific_topic') else ""}

【重要な制約と注意事項】
1. 🚨 PDFファイルがアップロードされている場合は、必ずそのPDF内容を直接参考にして問題を作成してください
2. 📚 PDF内の例題、問題、図表、概念を積極的に活用してください
3. 🎯 PDF内容に関連する具体的な問題を生成し、一般的な問題は避けてください
4. 📖 PDF内のテキスト、数式、データがある場合はそれらを問題に組み込んでください
5. ✅ 学習指導要領に準拠しつつ、PDF内容を最優先で反映してください
6. 📝 JSON形式で出力してください

以下の形式で出力してください：
{{
    "problems": [
        {{
            "question": "問題文",
            "answer": "答え",
            "explanation": "簡潔な解説"
        }}
    ]
}}
"""
        return prompt

    def _calculate_relevance_score(self, topic: Optional[str], data: Dict) -> float:
        """関連度スコアを計算（簡易版）"""
        score = 1.0

        if topic and data.get('topics'):
            # トピックが含まれているかチェック
            for t in data.get('topics', []):
                if topic in t or t in topic:
                    score += 0.5
                    break

        if data.get('keywords'):
            score += 0.2 * min(len(data['keywords']), 3)

        return min(score, 2.0)

    def _is_relevant_grade(self, query_grade: str, doc_grade: str) -> bool:
        """学年の関連性をチェック"""
        # 簡易的なマッチング
        grade_mappings = {
            '小学1年': ['小学', '小学校', '小1', '1年'],
            '小学2年': ['小学', '小学校', '小2', '2年'],
            '小学3年': ['小学', '小学校', '小3', '3年'],
            '小学4年': ['小学', '小学校', '小4', '4年'],
            '小学5年': ['小学', '小学校', '小5', '5年'],
            '小学6年': ['小学', '小学校', '小6', '6年'],
            '中学1年': ['中学', '中学校', '中1', '1年'],
            '中学2年': ['中学', '中学校', '中2', '2年'],
            '中学3年': ['中学', '中学校', '中3', '3年'],
        }

        for key in grade_mappings.get(query_grade, [query_grade]):
            if key in doc_grade:
                return True
        return query_grade == doc_grade

    def _format_guideline_content(self, data: Dict) -> str:
        """指導要領コンテンツをフォーマット"""
        content = f"{data.get('subject', '')} - {data.get('grade', '')}\n"

        if topics := data.get('topics'):
            content += f"トピック: {', '.join(topics[:5])}\n"

        if goals := data.get('learning_goals'):
            content += f"学習目標: {goals[0] if goals else ''}\n"

        return content[:500]  # 500文字に制限

    def _format_problem_content(self, data: Dict) -> str:
        """問題コンテンツをフォーマット"""
        return f"""
問題: {data.get('question', '')[:200]}
答え: {data.get('answer', '')[:100]}
"""

    def _format_curriculum_content(self, data: Dict) -> str:
        """学習指導要領コンテンツをフォーマット"""
        content = f"【{data.get('subject', '')} 学習指導要領】\n"

        # 学年情報
        if grade_levels := data.get('grade_levels'):
            content += f"対象学年: {', '.join(grade_levels)}\n"

        # 学習目標
        if learning_goals := data.get('learning_goals'):
            content += f"学習目標: {learning_goals[0][:100] if learning_goals else ''}\n"

        # トピック
        if topics := data.get('topics'):
            content += f"主要トピック: {', '.join(topics[:5])}\n"

        # キーワード
        if keywords := data.get('keywords'):
            content += f"重要キーワード: {', '.join(keywords[:8])}\n"

        return content[:800]  # 800文字に制限

    def _generate_cache_key(self, params: Dict) -> str:
        """キャッシュキーを生成"""
        key_string = json.dumps(params, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """キャッシュから取得"""
        if key in self.cache:
            expiry = self.cache_expiry.get(key)
            if expiry and datetime.now() < expiry:
                return self.cache[key]
            else:
                # 期限切れの場合は削除
                del self.cache[key]
                del self.cache_expiry[key]
        return None

    def _save_to_cache(self, key: str, value: Dict):
        """キャッシュに保存"""
        # キャッシュサイズ制限
        if len(self.cache) >= self.config['max_cache_size']:
            # 最も古いエントリを削除
            oldest_key = min(self.cache_expiry.keys(),
                           key=lambda k: self.cache_expiry[k])
            del self.cache[oldest_key]
            del self.cache_expiry[oldest_key]

        self.cache[key] = value
        self.cache_expiry[key] = datetime.now() + timedelta(
            minutes=self.config['cache_ttl_minutes']
        )

    def _parse_response(self, response_text: str) -> Dict:
        """レスポンスを解析"""
        try:
            # JSONを抽出
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "{" in response_text:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                response_text = response_text[start:end]

            return json.loads(response_text)
        except:
            # パースエラーの場合はフォールバック
            return {"problems": []}

    def _get_fallback_response(self, subject, grade, difficulty,
                              problem_count, problem_type) -> Dict:
        """フォールバック応答を生成"""
        return {
            "problems": [
                {
                    "question": f"{subject}の{problem_type}問題 {i+1}",
                    "answer": "解答例",
                    "explanation": f"{grade}向けの{difficulty}レベルの問題です"
                }
                for i in range(problem_count)
            ]
        }

    def _log_usage(self, input_tokens: float, output_tokens: float):
        """使用統計をログ記録"""
        # Firestoreに使用統計を保存
        if hasattr(self, 'db') and self.db:
            usage_data = {
                'timestamp': firestore.SERVER_TIMESTAMP,
                'input_tokens': int(input_tokens),
                'output_tokens': int(output_tokens),
                'estimated_cost': (input_tokens * 0.00005 + output_tokens * 0.00015) / 1000
            }

            self.db.collection('usage_logs').add(usage_data)
            print(f"Usage logged: {input_tokens:.0f} input, {output_tokens:.0f} output tokens")

    def get_monthly_usage(self) -> Dict:
        """月間使用量を取得"""
        if not hasattr(self, 'db') or not self.db:
            return {}

        # 今月の使用量を集計
        now = datetime.now()
        start_of_month = datetime(now.year, now.month, 1)

        query = self.db.collection('usage_logs').where(
            'timestamp', '>=', start_of_month
        )

        total_input = 0
        total_output = 0
        total_cost = 0
        count = 0

        for doc in query.stream():
            data = doc.to_dict()
            total_input += data.get('input_tokens', 0)
            total_output += data.get('output_tokens', 0)
            total_cost += data.get('estimated_cost', 0)
            count += 1

        return {
            'month': now.strftime('%Y-%m'),
            'total_requests': count,
            'total_input_tokens': total_input,
            'total_output_tokens': total_output,
            'estimated_cost_usd': total_cost,
            'problems_generated': count * 3  # 平均3問/リクエスト
        }