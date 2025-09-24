"""
学習指導要領サービス - Cloud Storageから学習指導要領PDFを読み込み・解析
"""

import os
import io
import json
from typing import Dict, List, Optional
from datetime import datetime
import PyPDF2
from google.cloud import storage, firestore
import logging

class CurriculumGuidelineService:
    """学習指導要領PDFの管理・解析サービス"""

    def __init__(self, project_id: str = None):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.bucket_name = "manatasu-ai-curriculum-guidelines"

        if self.project_id:
            self.storage_client = storage.Client(project=self.project_id)
            self.db = firestore.Client(project=self.project_id)
            self.bucket = self.storage_client.bucket(self.bucket_name)

        # 学習指導要領ファイルのメタデータ
        self.guideline_files = {
            "国語": "middle-school/国語.pdf",
            "理科": "middle-school/理科.pdf",
            "社会": "middle-school/社会.pdf",
            "時間割": "middle-school/時間割.pdf"
        }

        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _calculate_japanese_score(self, text: str) -> float:
        """
        テキストの日本語品質スコアを計算（中国語との区別を含む）

        Args:
            text: 評価するテキスト

        Returns:
            float: 日本語品質スコア (0.0-1.0)
        """
        if not text or len(text) < 3:
            return 0.0

        hiragana_count = 0
        katakana_count = 0
        kanji_count = 0
        japanese_specific_count = 0
        chinese_specific_count = 0
        total_chars = 0

        # 日本語特有の文字パターンをチェック
        japanese_particles = ['は', 'が', 'を', 'に', 'で', 'と', 'の', 'か', 'も', 'や']
        japanese_endings = ['です', 'である', 'します', 'ます', 'った', 'って', 'だ', 'である']

        # 中国語特有のパターン（簡体字、繁体字）
        chinese_chars = ['的', '了', '在', '是', '我', '你', '他', '她', '这', '那', '有', '个', '与', '國', '們', '為']

        for char in text:
            if char.strip() and not char.isspace():
                total_chars += 1
                code_point = ord(char)

                # ひらがな (U+3040-U+309F)
                if 0x3040 <= code_point <= 0x309F:
                    hiragana_count += 1
                    japanese_specific_count += 3  # ひらがなは日本語特有なので高スコア
                # カタカナ (U+30A0-U+30FF)
                elif 0x30A0 <= code_point <= 0x30FF:
                    katakana_count += 1
                    japanese_specific_count += 2  # カタカナも日本語特有
                # CJK統合漢字 (U+4E00-U+9FFF)
                elif 0x4E00 <= code_point <= 0x9FFF:
                    kanji_count += 1
                    # 中国語特有の漢字かチェック
                    if char in chinese_chars:
                        chinese_specific_count += 2
                    else:
                        japanese_specific_count += 1  # 一般的な漢字

        if total_chars == 0:
            return 0.0

        # 日本語助詞・語尾パターンのチェック
        particle_bonus = 0
        for particle in japanese_particles:
            if particle in text:
                particle_bonus += 0.1

        ending_bonus = 0
        for ending in japanese_endings:
            if ending in text:
                ending_bonus += 0.1

        # スコア計算
        hiragana_ratio = hiragana_count / total_chars
        katakana_ratio = katakana_count / total_chars
        japanese_ratio = japanese_specific_count / total_chars
        chinese_penalty = chinese_specific_count / total_chars

        # 日本語らしさのスコア
        japanese_score = (
            hiragana_ratio * 0.4 +  # ひらがなは日本語の証拠
            katakana_ratio * 0.2 +  # カタカナも重要
            japanese_ratio * 0.3 +  # 日本語特有文字
            particle_bonus * 0.05 + # 助詞ボーナス
            ending_bonus * 0.05     # 語尾ボーナス
        )

        # 中国語ペナルティを適用
        final_score = max(0.0, japanese_score - chinese_penalty * 0.3)

        return min(final_score, 1.0)

    def _fix_encoding_issues(self, text: str) -> str:
        """
        PDFから抽出されたテキストのエンコーディング問題を修正
        Args:
            text: 抽出されたテキスト
        Returns:
            str: エンコーディング修正されたテキスト
        """
        if not text:
            return text

        # 複数のエンコーディング修正を試行
        best_result = text
        best_score = 0

        try:
            # 方法1: Latin-1として誤解釈されたUTF-8を修正
            if any(ord(c) > 127 for c in text):  # 非ASCII文字が含まれている場合
                try:
                    # Latin-1でエンコードしてUTF-8でデコード
                    fixed_text = text.encode('latin-1').decode('utf-8', errors='ignore')
                    score = self._calculate_japanese_score(fixed_text)
                    if score > best_score:
                        best_result = fixed_text
                        best_score = score
                except (UnicodeError, UnicodeDecodeError):
                    pass

            # 方法2: CP1252として誤解釈されたUTF-8を修正
            try:
                fixed_text = text.encode('cp1252').decode('utf-8', errors='ignore')
                score = self._calculate_japanese_score(fixed_text)
                if score > best_score:
                    best_result = fixed_text
                    best_score = score
            except (UnicodeError, UnicodeDecodeError):
                pass

            # 方法3: 日本語特有のエンコーディングを試行（優先順位付き）
            encodings_to_try = [
                ('shift_jis', 'Shift_JIS'),
                ('euc-jp', 'EUC-JP'),
                ('iso-2022-jp', 'ISO-2022-JP'),
                ('utf-8', 'UTF-8'),
                ('utf-16', 'UTF-16')
            ]

            for encoding, name in encodings_to_try:
                try:
                    if isinstance(text, str):
                        # 文字列をバイトに変換してからデコード
                        text_bytes = text.encode('latin-1', errors='ignore')
                        fixed_text = text_bytes.decode(encoding, errors='ignore')
                        score = self._calculate_japanese_score(fixed_text)
                        if score > best_score:
                            best_result = fixed_text
                            best_score = score
                except (UnicodeError, UnicodeDecodeError):
                    continue

        except Exception as e:
            self.logger.warning(f"Encoding fix failed: {e}")

        # 最良の結果を返す（スコアが0.1以上の場合のみ）
        if best_score >= 0.1:
            return best_result
        else:
            return text

    def _is_readable_japanese(self, text: str) -> bool:
        """
        テキストが読み取り可能な日本語かどうかを判定

        Args:
            text: 判定するテキスト

        Returns:
            bool: 読み取り可能な日本語の場合True
        """
        if not text or len(text) < 3:
            return False

        # 日本語品質スコアを使用
        score = self._calculate_japanese_score(text)
        return score >= 0.3

    def download_pdf_from_storage(self, blob_path: str) -> Optional[bytes]:
        """Cloud StorageからPDFファイルをダウンロード"""
        try:
            blob = self.bucket.blob(blob_path)
            if blob.exists():
                return blob.download_as_bytes()
            else:
                self.logger.warning(f"File not found in storage: {blob_path}")
                return None
        except Exception as e:
            self.logger.error(f"Error downloading {blob_path}: {e}")
            return None

    def extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """PDFからテキストを抽出（UTF-8エンコーディング対応）"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            text = ""

            for page in pdf_reader.pages:
                page_text = page.extract_text()
                # 強化されたエンコーディング修正を適用
                fixed_text = self._fix_encoding_issues(page_text)
                text += fixed_text + "\n"

            return text.strip()
        except Exception as e:
            self.logger.error(f"Error extracting text from PDF: {e}")
            return ""

    def parse_curriculum_content(self, text: str, subject: str) -> Dict:
        """学習指導要領テキストを解析して構造化データに変換"""
        lines = text.split('\n')
        parsed_data = {
            'subject': subject,
            'grade_levels': [],
            'learning_goals': [],
            'topics': [],
            'keywords': [],
            'content_areas': []
        }

        current_section = None
        current_grade = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 学年の検出
            if any(grade in line for grade in ['第1学年', '第2学年', '第3学年', '1学年', '2学年', '3学年']):
                if '第1学年' in line or '1学年' in line:
                    current_grade = '中学1年'
                elif '第2学年' in line or '2学年' in line:
                    current_grade = '中学2年'
                elif '第3学年' in line or '3学年' in line:
                    current_grade = '中学3年'

                if current_grade and current_grade not in parsed_data['grade_levels']:
                    parsed_data['grade_levels'].append(current_grade)

            # 目標の検出
            if '目標' in line or '目的' in line:
                current_section = 'goals'
                if line not in parsed_data['learning_goals']:
                    parsed_data['learning_goals'].append(line)

            # 内容領域の検出
            elif any(keyword in line for keyword in ['ア ', 'イ ', 'ウ ', 'エ ', 'オ ']):
                current_section = 'content'
                parsed_data['content_areas'].append({
                    'grade': current_grade,
                    'content': line
                })

            # キーワードの抽出（重要そうな単語）
            keywords = self._extract_keywords(line, subject)
            for keyword in keywords:
                if keyword not in parsed_data['keywords']:
                    parsed_data['keywords'].append(keyword)

        # トピックの生成（内容領域から）
        parsed_data['topics'] = self._generate_topics(parsed_data['content_areas'], subject)

        return parsed_data

    def _extract_keywords(self, text: str, subject: str) -> List[str]:
        """テキストから重要なキーワードを抽出"""
        keywords = []

        # 教科別の重要キーワード
        subject_keywords = {
            '国語': ['読解', '作文', '文法', '漢字', '語彙', '表現', '文学', '古典'],
            '理科': ['実験', '観察', '化学', '物理', '生物', '地学', '元素', '反応'],
            '社会': ['歴史', '地理', '公民', '政治', '経済', '文化', '地域', '国際'],
            '時間割': ['時間', '教科', '授業', '週', '年間', '単位', '計画']
        }

        # 一般的な教育キーワード
        general_keywords = ['学習', '理解', '思考', '判断', '表現', '技能', '知識', '態度']

        target_keywords = subject_keywords.get(subject, []) + general_keywords

        for keyword in target_keywords:
            if keyword in text:
                keywords.append(keyword)

        return keywords

    def _generate_topics(self, content_areas: List[Dict], subject: str) -> List[str]:
        """内容領域からトピックを生成"""
        topics = []

        for area in content_areas:
            content = area.get('content', '')

            # 簡易的なトピック抽出
            if len(content) > 10:  # 十分な長さのコンテンツのみ
                # 最初の20文字をトピックとして使用
                topic = content[:20].replace('ア ', '').replace('イ ', '').replace('ウ ', '').strip()
                if topic and topic not in topics:
                    topics.append(topic)

        return topics[:10]  # 最大10個のトピック

    def process_and_store_guidelines(self):
        """全ての学習指導要領PDFを処理してFirestoreに保存"""
        for subject, blob_path in self.guideline_files.items():
            self.logger.info(f"Processing {subject} curriculum guidelines...")

            # PDFをダウンロード
            pdf_bytes = self.download_pdf_from_storage(blob_path)
            if not pdf_bytes:
                continue

            # テキストを抽出
            text = self.extract_text_from_pdf(pdf_bytes)
            if not text:
                continue

            # 構造化データに解析
            parsed_data = self.parse_curriculum_content(text, subject)
            parsed_data['raw_text'] = text[:5000]  # 最初の5000文字を保存
            parsed_data['processed_at'] = firestore.SERVER_TIMESTAMP
            parsed_data['source_file'] = blob_path

            # Firestoreに保存
            try:
                doc_ref = self.db.collection('curriculum_guidelines').document(subject)
                doc_ref.set(parsed_data)
                self.logger.info(f"Stored {subject} guidelines in Firestore")
            except Exception as e:
                self.logger.error(f"Error storing {subject} guidelines: {e}")

    def get_guidelines_for_subject(self, subject: str, grade: str = None) -> Optional[Dict]:
        """特定の教科の学習指導要領を取得"""
        try:
            doc_ref = self.db.collection('curriculum_guidelines').document(subject)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()

                # 学年でフィルタリング
                if grade:
                    if grade in data.get('grade_levels', []):
                        # 該当学年の内容のみ抽出
                        filtered_content = []
                        for area in data.get('content_areas', []):
                            if area.get('grade') == grade:
                                filtered_content.append(area)
                        data['content_areas'] = filtered_content
                    else:
                        return None

                return data
            else:
                return None

        except Exception as e:
            self.logger.error(f"Error getting guidelines for {subject}: {e}")
            return None

    def search_guidelines(self, query: str, subject: str = None, grade: str = None) -> List[Dict]:
        """学習指導要領を検索"""
        results = []

        try:
            query_ref = self.db.collection('curriculum_guidelines')

            # 教科でフィルタリング
            if subject:
                docs = [query_ref.document(subject).get()]
            else:
                docs = query_ref.stream()

            for doc in docs:
                if doc.exists:
                    data = doc.to_dict()

                    # 学年でフィルタリング
                    if grade and grade not in data.get('grade_levels', []):
                        continue

                    # テキスト検索（簡易版）
                    raw_text = data.get('raw_text', '').lower()
                    if query.lower() in raw_text:
                        # 関連度スコアを計算
                        score = raw_text.count(query.lower()) / len(raw_text) * 1000

                        results.append({
                            'id': doc.id,
                            'subject': data.get('subject'),
                            'grade_levels': data.get('grade_levels', []),
                            'score': score,
                            'topics': data.get('topics', []),
                            'learning_goals': data.get('learning_goals', [])[:3],  # 最初の3つの目標
                            'keywords': data.get('keywords', [])[:10]  # 最初の10個のキーワード
                        })

            # スコアでソート
            results.sort(key=lambda x: x['score'], reverse=True)
            return results[:5]  # 最大5件を返す

        except Exception as e:
            self.logger.error(f"Error searching guidelines: {e}")
            return []

    def get_all_subjects(self) -> List[str]:
        """利用可能な全教科を取得"""
        return list(self.guideline_files.keys())

    def initialize_guidelines(self):
        """学習指導要領の初期化処理"""
        self.logger.info("Initializing curriculum guidelines...")
        self.process_and_store_guidelines()
        self.logger.info("Curriculum guidelines initialization completed")


# 初期化用のスクリプト
if __name__ == "__main__":
    service = CurriculumGuidelineService()
    service.initialize_guidelines()