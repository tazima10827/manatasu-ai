"""
Enhanced PDF Text Extraction Service - 高品質PDFテキスト抽出サービス

PyPDF2、pdfplumber、OCRを組み合わせて最高品質のテキスト抽出を提供
"""

import io
import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

# PDF処理用ライブラリ
import PyPDF2
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logging.warning("pdfplumber not available, will use PyPDF2 only")

try:
    from pdf2image import convert_from_bytes
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logging.warning("OCR libraries not available, will skip OCR extraction")

@dataclass
class ExtractedContent:
    """抽出されたPDFコンテンツ"""
    text: str
    page_count: int
    extraction_method: str
    confidence_score: float
    metadata: Dict

class EnhancedPDFExtractor:
    """高品質PDFテキスト抽出サービス"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

    def extract_text_from_pdf(self, pdf_bytes: bytes, filename: str = "document.pdf") -> ExtractedContent:
        """
        PDFからテキストを抽出（複数手法を試行して最適な結果を返す）

        Args:
            pdf_bytes: PDFファイルのバイナリデータ
            filename: ファイル名（ログ用）

        Returns:
            ExtractedContent: 抽出されたテキストとメタデータ
        """
        self.logger.info(f"Starting enhanced PDF extraction for {filename}")

        # 複数の抽出手法を試行
        extraction_results = []

        # 1. PyPDF2による抽出（基本）
        pypdf2_result = self._extract_with_pypdf2(pdf_bytes)
        if pypdf2_result:
            extraction_results.append(pypdf2_result)

        # 2. pdfplumberによる抽出（高品質）
        if PDFPLUMBER_AVAILABLE:
            pdfplumber_result = self._extract_with_pdfplumber(pdf_bytes)
            if pdfplumber_result:
                extraction_results.append(pdfplumber_result)

        # 3. OCRによる抽出（画像化されたPDF用）
        if OCR_AVAILABLE and len(extraction_results) == 0:
            ocr_result = self._extract_with_ocr(pdf_bytes)
            if ocr_result:
                extraction_results.append(ocr_result)

        # 最適な結果を選択
        if not extraction_results:
            return ExtractedContent(
                text="",
                page_count=0,
                extraction_method="none",
                confidence_score=0.0,
                metadata={"error": "すべての抽出手法が失敗しました"}
            )

        # 信頼度スコアが最も高い結果を選択
        best_result = max(extraction_results, key=lambda x: x.confidence_score)

        self.logger.info(f"Best extraction method: {best_result.extraction_method} "
                        f"(confidence: {best_result.confidence_score:.2f})")

        return best_result

    def _extract_with_pypdf2(self, pdf_bytes: bytes) -> Optional[ExtractedContent]:
        """PyPDF2を使用したテキスト抽出"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            text_content = ""
            page_count = len(pdf_reader.pages)

            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():
                        text_content += f"\n--- Page {page_num + 1} ---\n"
                        text_content += page_text
                except Exception as e:
                    self.logger.warning(f"PyPDF2: Failed to extract page {page_num + 1}: {e}")
                    continue

            # 信頼度スコア計算（テキスト長と文字の多様性で判定）
            confidence = self._calculate_text_confidence(text_content)

            return ExtractedContent(
                text=text_content.strip(),
                page_count=page_count,
                extraction_method="PyPDF2",
                confidence_score=confidence,
                metadata={
                    "extracted_pages": page_count,
                    "text_length": len(text_content),
                }
            )
        except Exception as e:
            self.logger.error(f"PyPDF2 extraction failed: {e}")
            return None

    def _extract_with_pdfplumber(self, pdf_bytes: bytes) -> Optional[ExtractedContent]:
        """pdfplumberを使用したテキスト抽出（高品質・テーブル対応）"""
        if not PDFPLUMBER_AVAILABLE:
            return None

        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                text_content = ""
                page_count = len(pdf.pages)
                tables_found = 0

                for page_num, page in enumerate(pdf.pages):
                    try:
                        text_content += f"\n--- Page {page_num + 1} ---\n"

                        # 通常テキストの抽出
                        page_text = page.extract_text()
                        if page_text:
                            text_content += page_text + "\n"

                        # テーブルの抽出
                        tables = page.extract_tables()
                        for table_num, table in enumerate(tables):
                            if table:
                                tables_found += 1
                                text_content += f"\n--- テーブル {table_num + 1} ---\n"
                                for row in table:
                                    if row and any(cell for cell in row if cell):
                                        text_content += " | ".join(str(cell) if cell else "" for cell in row) + "\n"

                    except Exception as e:
                        self.logger.warning(f"pdfplumber: Failed to extract page {page_num + 1}: {e}")
                        continue

                # 信頼度スコア計算（テーブルが見つかった場合はボーナス）
                confidence = self._calculate_text_confidence(text_content)
                if tables_found > 0:
                    confidence += 0.2  # テーブル発見ボーナス

                confidence = min(confidence, 1.0)  # 最大値は1.0

                return ExtractedContent(
                    text=text_content.strip(),
                    page_count=page_count,
                    extraction_method="pdfplumber",
                    confidence_score=confidence,
                    metadata={
                        "extracted_pages": page_count,
                        "text_length": len(text_content),
                        "tables_found": tables_found,
                    }
                )

        except Exception as e:
            self.logger.error(f"pdfplumber extraction failed: {e}")
            return None

    def _extract_with_ocr(self, pdf_bytes: bytes) -> Optional[ExtractedContent]:
        """OCR（光学文字認識）を使用したテキスト抽出"""
        if not OCR_AVAILABLE:
            return None

        try:
            # PDFを画像に変換
            images = convert_from_bytes(pdf_bytes, dpi=300)  # 高解像度で変換
            text_content = ""
            page_count = len(images)

            for page_num, image in enumerate(images[:5]):  # 最初の5ページのみ（処理時間考慮）
                try:
                    text_content += f"\n--- Page {page_num + 1} (OCR) ---\n"
                    # OCRでテキスト抽出
                    page_text = pytesseract.image_to_string(image, lang='jpn+eng')
                    if page_text.strip():
                        text_content += page_text
                except Exception as e:
                    self.logger.warning(f"OCR: Failed to process page {page_num + 1}: {e}")
                    continue

            # OCRは通常信頼度が低めなので調整
            confidence = self._calculate_text_confidence(text_content) * 0.7

            return ExtractedContent(
                text=text_content.strip(),
                page_count=page_count,
                extraction_method="OCR",
                confidence_score=confidence,
                metadata={
                    "extracted_pages": min(5, page_count),
                    "text_length": len(text_content),
                    "note": "OCR extraction (first 5 pages only)"
                }
            )

        except Exception as e:
            self.logger.error(f"OCR extraction failed: {e}")
            return None

    def _calculate_text_confidence(self, text: str) -> float:
        """
        抽出されたテキストの品質を評価して信頼度スコアを計算

        Args:
            text: 抽出されたテキスト

        Returns:
            float: 信頼度スコア (0.0-1.0)
        """
        if not text or len(text.strip()) < 10:
            return 0.0

        # 基本スコア：テキスト長に基づく
        length_score = min(len(text) / 1000, 0.5)  # 1000文字で0.5点

        # 文字多様性スコア：異なる文字種の割合
        unique_chars = len(set(text.lower()))
        total_chars = len(text)
        diversity_score = min(unique_chars / total_chars * 2, 0.3)  # 最大0.3点

        # 構造スコア：改行や句読点の存在
        structure_indicators = ['\n', '。', '、', '.', ',', '!', '?']
        structure_count = sum(text.count(indicator) for indicator in structure_indicators)
        structure_score = min(structure_count / total_chars * 100, 0.2)  # 最大0.2点

        total_score = length_score + diversity_score + structure_score
        return min(total_score, 1.0)

    def extract_with_fallback(self, pdf_bytes: bytes, filename: str = "document.pdf") -> str:
        """
        フォールバック機能付きのシンプルなテキスト抽出
        （既存コードとの互換性のため）

        Args:
            pdf_bytes: PDFファイルのバイナリデータ
            filename: ファイル名

        Returns:
            str: 抽出されたテキスト
        """
        result = self.extract_text_from_pdf(pdf_bytes, filename)

        if result.text and len(result.text.strip()) > 50:
            self.logger.info(f"Enhanced extraction successful with {result.extraction_method} "
                           f"(confidence: {result.confidence_score:.2f})")
            return result.text
        else:
            # フォールバック：基本的なPyPDF2抽出
            self.logger.warning("Enhanced extraction failed, falling back to basic PyPDF2")
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
                text_content = ""
                for page_num, page in enumerate(pdf_reader.pages):
                    text_content += f"\n--- Page {page_num + 1} ---\n"
                    text_content += page.extract_text()
                return text_content.strip()
            except Exception as e:
                self.logger.error(f"Fallback extraction also failed: {e}")
                return ""