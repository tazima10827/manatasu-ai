#!/usr/bin/env python3
"""
文部科学省の学習指導要領をFirestoreにアップロードするスクリプト
"""

import os
import sys
import argparse
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from services.guidelines_service import GuidelinesService
from dotenv import load_dotenv

load_dotenv()

def upload_single_guideline(pdf_path: str, subject: str, grade: str):
    """
    単一の指導要領PDFをアップロード

    Args:
        pdf_path: PDFファイルのパス
        subject: 教科名
        grade: 学年
    """
    service = GuidelinesService()

    print(f"アップロード中: {pdf_path}")
    print(f"教科: {subject}, 学年: {grade}")

    try:
        result = service.upload_guideline_pdf(pdf_path, subject, grade)
        print("アップロード成功！")
        print(f"トピック: {result.get('topics')}")
        print(f"キーワード: {result.get('keywords')}")
    except Exception as e:
        print(f"エラー: {e}")

def upload_batch_guidelines(directory_path: str):
    """
    ディレクトリ内のすべての指導要領PDFをバッチアップロード

    Args:
        directory_path: PDFファイルが含まれるディレクトリパス
    """
    service = GuidelinesService()

    # ファイル名から教科と学年を推測するマッピング
    file_mappings = {
        "小学校_算数": ("算数", "小学校全学年"),
        "小学校_国語": ("国語", "小学校全学年"),
        "小学校_理科": ("理科", "小学校3-6年"),
        "小学校_社会": ("社会", "小学校3-6年"),
        "中学校_数学": ("数学", "中学校全学年"),
        "中学校_国語": ("国語", "中学校全学年"),
        "中学校_理科": ("理科", "中学校全学年"),
        "中学校_社会": ("社会", "中学校全学年"),
        "中学校_英語": ("英語", "中学校全学年"),
        "高等学校_数学": ("数学", "高等学校"),
        "高等学校_国語": ("国語", "高等学校"),
        "高等学校_理科": ("理科", "高等学校"),
        "高等学校_地理歴史": ("地理歴史", "高等学校"),
        "高等学校_公民": ("公民", "高等学校"),
        "高等学校_外国語": ("英語", "高等学校"),
    }

    directory = Path(directory_path)
    if not directory.exists():
        print(f"ディレクトリが見つかりません: {directory_path}")
        return

    pdf_files = list(directory.glob("*.pdf"))
    print(f"{len(pdf_files)}個のPDFファイルが見つかりました")

    for pdf_file in pdf_files:
        # ファイル名から教科と学年を推測
        file_stem = pdf_file.stem

        matched = False
        for pattern, (subject, grade) in file_mappings.items():
            if pattern in file_stem:
                print(f"\n処理中: {pdf_file.name}")
                try:
                    result = service.upload_guideline_pdf(
                        str(pdf_file),
                        subject,
                        grade
                    )
                    print(f"✓ {subject} ({grade}) アップロード完了")
                    matched = True
                    break
                except Exception as e:
                    print(f"✗ エラー: {e}")
                    matched = True
                    break

        if not matched:
            print(f"⚠ スキップ: {pdf_file.name} (マッピングが見つかりません)")

def create_sample_guidelines():
    """
    サンプルの指導要領データをFirestoreに作成
    （PDFがない場合のテスト用）
    """
    from google.cloud import firestore

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "manatasu-ai-prod")
    db = firestore.Client(project=project_id)

    sample_data = [
        {
            "id": "elementary_math",
            "subject": "算数",
            "grade": "小学校",
            "topics": [
                "数と計算",
                "量と測定",
                "図形",
                "数量関係",
                "データの活用"
            ],
            "learning_goals": [
                "数の概念について理解し、計算の意味と方法を理解する",
                "身の回りの量の単位と測定について理解する",
                "平面図形及び立体図形の基本的な性質を理解する",
                "数量の関係を表したり読み取ったりする力を養う",
                "データを整理・分析し、傾向を読み取る力を養う"
            ],
            "keywords": [
                "基礎的・基本的な知識・技能",
                "数学的な思考力・判断力・表現力",
                "主体的に学習に取り組む態度"
            ],
            "grade_specific": {
                "1年": ["10までの数", "たし算", "ひき算", "長さ", "かたち"],
                "2年": ["100までの数", "かけ算", "時刻と時間", "長さの単位"],
                "3年": ["わり算", "小数", "分数", "円と球", "重さ"],
                "4年": ["大きな数", "がい数", "面積", "角度", "折れ線グラフ"],
                "5年": ["小数のかけ算・わり算", "分数のたし算・ひき算", "体積", "平均", "割合"],
                "6年": ["分数のかけ算・わり算", "比例・反比例", "場合の数", "データの考察"]
            }
        },
        {
            "id": "elementary_japanese",
            "subject": "国語",
            "grade": "小学校",
            "topics": [
                "話すこと・聞くこと",
                "書くこと",
                "読むこと",
                "言葉の特徴や使い方",
                "情報の扱い方",
                "我が国の言語文化"
            ],
            "learning_goals": [
                "日常生活に必要な国語の知識や技能を身に付ける",
                "筋道立てて考える力や豊かに感じたり想像したりする力を養う",
                "言葉がもつよさを認識し、言語感覚を養う",
                "国語を大切にして、思いや考えを伝え合う態度を育てる"
            ],
            "keywords": [
                "言語能力",
                "思考力・判断力・表現力",
                "コミュニケーション能力",
                "読解力"
            ]
        },
        {
            "id": "junior_math",
            "subject": "数学",
            "grade": "中学校",
            "topics": [
                "数と式",
                "図形",
                "関数",
                "データの活用"
            ],
            "learning_goals": [
                "数量や図形などについての基礎的な概念や原理・法則を理解する",
                "事象を数学化したり、数学的に解釈・表現・処理したりする技能を身に付ける",
                "数学的活動を通して、数学的に考える力を養う",
                "数学的活動の楽しさや数学のよさを実感し、数学を活用する態度を育てる"
            ],
            "keywords": [
                "数学的な見方・考え方",
                "論理的思考力",
                "問題解決能力",
                "数学的活動"
            ],
            "grade_specific": {
                "1年": ["正負の数", "文字式", "一次方程式", "比例・反比例", "平面図形", "空間図形"],
                "2年": ["式の計算", "連立方程式", "一次関数", "図形の性質", "確率"],
                "3年": ["多項式", "平方根", "二次方程式", "関数y=ax²", "相似", "三平方の定理"]
            }
        }
    ]

    print("サンプル指導要領データを作成中...")

    for data in sample_data:
        doc_id = data.pop("id")
        doc_ref = db.collection('guidelines').document(doc_id)
        doc_ref.set(data)
        print(f"✓ {data['subject']} ({data['grade']}) を作成しました")

    print("\n完了！")

def main():
    parser = argparse.ArgumentParser(
        description="文部科学省の学習指導要領をアップロード"
    )

    parser.add_argument(
        "command",
        choices=["single", "batch", "sample"],
        help="実行するコマンド"
    )

    parser.add_argument(
        "--pdf",
        help="PDFファイルのパス（singleコマンド用）"
    )

    parser.add_argument(
        "--subject",
        help="教科名（singleコマンド用）"
    )

    parser.add_argument(
        "--grade",
        help="学年（singleコマンド用）"
    )

    parser.add_argument(
        "--directory",
        help="PDFファイルのディレクトリ（batchコマンド用）"
    )

    args = parser.parse_args()

    if args.command == "single":
        if not all([args.pdf, args.subject, args.grade]):
            print("エラー: --pdf, --subject, --grade を指定してください")
            sys.exit(1)
        upload_single_guideline(args.pdf, args.subject, args.grade)

    elif args.command == "batch":
        if not args.directory:
            print("エラー: --directory を指定してください")
            sys.exit(1)
        upload_batch_guidelines(args.directory)

    elif args.command == "sample":
        create_sample_guidelines()

if __name__ == "__main__":
    main()