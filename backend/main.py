import os
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import json
import PyPDF2
from google.cloud import aiplatform
from google.cloud import storage
from google.cloud import firestore
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from dotenv import load_dotenv
from services.guidelines_service import GuidelinesService
from services.mvp_rag_service import MVPRAGService
from services.enhanced_pdf_extractor import EnhancedPDFExtractor
import base64

load_dotenv()

# MVP版RAGサービスを有効にするフラグ
USE_MVP_RAG = os.getenv("USE_MVP_RAG", "true").lower() == "true"

app = FastAPI(title="manatasuAI API", version="1.0.0")

security = HTTPBearer()

origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "http://localhost:3004",
    "http://localhost:3005",
    "http://localhost:3006",
    "http://localhost:3007",
    "http://localhost:8080",
    "http://localhost:5000",
    "https://manatasu-ai.web.app",
    "https://manatasu-ai.firebaseapp.com",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.getenv("VERTEX_AI_LOCATION", "asia-northeast1")
API_KEY = os.getenv("API_KEY", "")

if PROJECT_ID:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    db = firestore.Client(project=PROJECT_ID)
    storage_client = storage.Client(project=PROJECT_ID)

class ProblemGenerationParams(BaseModel):
    subject: str
    grade: str
    difficulty: str
    problemCount: int
    problemType: str
    specificTopic: Optional[str] = None
    additionalInstructions: Optional[str] = None

class GeneratedProblem(BaseModel):
    id: str
    question: str
    answer: str
    explanation: str
    choices: Optional[List[str]] = None
    difficulty: str
    subject: str
    grade: str
    sourceFile: str
    sourcePage: str
    sourceUri: Optional[str] = None
    generatedAt: datetime

class Base64ProblemRequest(BaseModel):
    pdfBase64: str
    filename: str
    params: ProblemGenerationParams

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return credentials.credentials

@app.post("/api/generate-problems")
async def generate_problems(
    pdf: UploadFile = File(...),
    params: str = Form(...),
    api_key: str = Depends(verify_api_key)
):
    try:
        params_data = json.loads(params)
        problem_params = ProblemGenerationParams(**params_data)

        pdf_content = await pdf.read()

        # Enhanced PDF text extraction
        extractor = EnhancedPDFExtractor()
        text_content = extractor.extract_with_fallback(pdf_content, pdf.filename)

        print(f"Enhanced extracted PDF content length: {len(text_content)}")
        print(f"PDF content preview: {text_content[:200]}...")

        # MVP版RAGを使用するかチェック
        if USE_MVP_RAG:
            print("Using MVP RAG Service for cost optimization")
            mvp_rag = MVPRAGService(project_id=PROJECT_ID)

            try:
                # MVP版RAGで生成
                result = mvp_rag.generate_with_rag(
                    subject=problem_params.subject,
                    grade=problem_params.grade,
                    difficulty=problem_params.difficulty,
                    problem_count=problem_params.problemCount,
                    problem_type=problem_params.problemType,
                    pdf_content=text_content,
                    specific_topic=problem_params.specificTopic,
                    filename=pdf.filename
                )

                # 結果から問題を抽出
                generated_data = result
            except Exception as mvp_error:
                print(f"MVP RAG error: {mvp_error}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"MVP RAG error: {str(mvp_error)}")

        else:
            model = GenerativeModel("gemini-1.5-flash")

            # 指導要領サービスを初期化
            guidelines_service = GuidelinesService(project_id=PROJECT_ID)

            # 関連する指導要領を取得
            guidelines = []
            if guidelines_service.db:
                guidelines = guidelines_service.get_relevant_guidelines(
                    subject=problem_params.subject,
                    grade=problem_params.grade,
                    topic=problem_params.specificTopic
                )

            # 指導要領を含むプロンプトを生成
            prompt = f"""
            以下の情報を参考に、{problem_params.subject}の{problem_params.grade}向けの問題を{problem_params.problemCount}問生成してください。
            """

            # 指導要領がある場合は追加
            if guidelines:
                prompt += f"""

        【文部科学省学習指導要領】
        """
                for guideline in guidelines[:2]:  # 最大2つまで使用
                    prompt += f"""
        ■ {guideline.get('subject')} - {guideline.get('grade')}
        学習目標: {', '.join(guideline.get('learning_goals', [])[:3]) if guideline.get('learning_goals') else ''}
        重要トピック: {', '.join(guideline.get('topics', [])) if guideline.get('topics') else ''}
        キーワード: {', '.join(guideline.get('keywords', [])) if guideline.get('keywords') else ''}
        """

                    # 学年別の詳細があれば追加
                    if 'grade_specific' in guideline and problem_params.grade in str(guideline.get('grade_specific', {})):
                        for grade_key, topics in guideline.get('grade_specific', {}).items():
                            if grade_key in problem_params.grade:
                                prompt += f"""
        {grade_key}の学習内容: {', '.join(topics)}
        """

            prompt += f"""

        【生成条件】
        - 難易度: {problem_params.difficulty}
        - 問題形式: {problem_params.problemType}
        {'- トピック: ' + problem_params.specificTopic if problem_params.specificTopic else ''}
        {'- 追加指示: ' + problem_params.additionalInstructions if problem_params.additionalInstructions else ''}

        【参考資料（アップロードされたPDF内容）】
        {text_content[:10000]}

        【要求事項】
        - 学習指導要領の目標と内容に準拠した問題を作成
        - 児童・生徒の発達段階に適した難易度と表現を使用
        - 思考力・判断力・表現力を育成する問題を含める
        - 基礎的・基本的な知識・技能の定着を確認できる問題

        以下の形式でJSONとして出力してください:
        {{
            "problems": [
                {{
                    "question": "問題文",
                    "answer": "解答",
                    "explanation": "解説（学習指導要領の観点も含める）",
                    "choices": ["選択肢1", "選択肢2", ...] (選択問題の場合のみ),
                    "sourcePage": "参照ページ番号"
                }}
            ]
        }}
        """

            response = model.generate_content(prompt)

            try:
                response_text = response.text
                print(f"Raw AI response: {response_text[:500]}...")  # Log for debugging

                # Clean up response text
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]

                # Try to extract just the JSON part if there's extra text
                response_text = response_text.strip()
                if "{" in response_text:
                    start = response_text.find("{")
                    # Find the matching closing brace
                    brace_count = 0
                    end = start
                    for i, char in enumerate(response_text[start:], start):
                        if char == "{":
                            brace_count += 1
                        elif char == "}":
                            brace_count -= 1
                            if brace_count == 0:
                                end = i + 1
                                break
                    response_text = response_text[start:end]

                generated_data = json.loads(response_text)
                print(f"Parsed JSON: {generated_data}")  # Log for debugging
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                print(f"Failed to parse: {response_text}")
                generated_data = {
                    "problems": [
                        {
                            "question": f"問題{i+1}: {problem_params.subject}に関する{problem_params.problemType}",
                            "answer": "解答例",
                            "explanation": "解説文",
                            "choices": ["選択肢A", "選択肢B", "選択肢C", "選択肢D"] if problem_params.problemType == "選択問題" else None,
                            "sourcePage": f"p.{i+1}"
                        }
                        for i in range(problem_params.problemCount)
                    ]
                }


        problems = []
        for i, problem_data in enumerate(generated_data.get("problems", [])):
            question = problem_data.get("question", "").strip()
            answer = problem_data.get("answer", "").strip()
            explanation = problem_data.get("explanation", "").strip()

            # Use fallback if empty
            if not question:
                question = f"問題{i+1}: {problem_params.subject}に関する{problem_params.problemType}"
            if not answer:
                answer = "解答例"
            if not explanation:
                explanation = "解説文"

            problem = GeneratedProblem(
                id=str(uuid.uuid4()),
                question=question,
                answer=answer,
                explanation=explanation,
                choices=problem_data.get("choices"),
                difficulty=problem_params.difficulty,
                subject=problem_params.subject,
                grade=problem_params.grade,
                sourceFile=pdf.filename,
                sourcePage=problem_data.get("sourcePage", f"p.{i+1}"),
                sourceUri=None,
                generatedAt=datetime.now()
            )
            problems.append(problem)

        if db:
            batch = db.batch()
            for problem in problems:
                doc_ref = db.collection("generated_problems").document(problem.id)
                batch.set(doc_ref, problem.dict())
            batch.commit()

        return {"problems": [p.dict() for p in problems]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-problems-base64")
async def generate_problems_base64(
    request: Base64ProblemRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Base64エンコードされたPDFを使用した問題生成（Flutter Web対応）
    """
    try:
        # Base64をデコードしてPDFバイトに変換
        try:
            pdf_content = base64.b64decode(request.pdfBase64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 PDF data: {str(e)}")

        problem_params = request.params

        # Enhanced PDF text extraction for Base64 request
        extractor = EnhancedPDFExtractor()
        text_content = extractor.extract_with_fallback(pdf_content, request.filename)

        print(f"Base64 PDF content length: {len(text_content)}")
        print(f"Base64 PDF content preview: {text_content[:200]}...")

        # MVP版RAGを使用するかチェック
        if USE_MVP_RAG:
            print("Using MVP RAG Service for base64 request")
            mvp_rag = MVPRAGService(project_id=PROJECT_ID)

            try:
                # MVP版RAGで生成
                result = mvp_rag.generate_with_rag(
                    subject=problem_params.subject,
                    grade=problem_params.grade,
                    difficulty=problem_params.difficulty,
                    problem_count=problem_params.problemCount,
                    problem_type=problem_params.problemType,
                    pdf_content=text_content,
                    specific_topic=problem_params.specificTopic,
                    filename=request.filename
                )

                # 結果から問題を抽出
                generated_data = result
            except Exception as mvp_error:
                print(f"MVP RAG error: {mvp_error}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"MVP RAG error: {str(mvp_error)}")

        else:
            model = GenerativeModel("gemini-1.5-flash")

            # 指導要領サービスを初期化
            guidelines_service = GuidelinesService(project_id=PROJECT_ID)

            # 関連する指導要領を取得
            guidelines = []
            if guidelines_service.db:
                guidelines = guidelines_service.get_relevant_guidelines(
                    subject=problem_params.subject,
                    grade=problem_params.grade,
                    topic=problem_params.specificTopic
                )

            # 指導要領を含むプロンプトを生成
            prompt = f"""
            以下の情報を参考に、{problem_params.subject}の{problem_params.grade}向けの問題を{problem_params.problemCount}問生成してください。
            """

            # 指導要領がある場合は追加
            if guidelines:
                prompt += f"""

        【文部科学省学習指導要領】
        """
                for guideline in guidelines[:2]:  # 最大2つまで使用
                    prompt += f"""
        ■ {guideline.get('subject')} - {guideline.get('grade')}
        学習目標: {', '.join(guideline.get('learning_goals', [])[:3]) if guideline.get('learning_goals') else ''}
        重要トピック: {', '.join(guideline.get('topics', [])) if guideline.get('topics') else ''}
        キーワード: {', '.join(guideline.get('keywords', [])) if guideline.get('keywords') else ''}
        """

                    # 学年別の詳細があれば追加
                    if 'grade_specific' in guideline and problem_params.grade in str(guideline.get('grade_specific', {})):
                        for grade_key, topics in guideline.get('grade_specific', {}).items():
                            if grade_key in problem_params.grade:
                                prompt += f"""
        {grade_key}の学習内容: {', '.join(topics)}
        """

            prompt += f"""

        【生成条件】
        - 難易度: {problem_params.difficulty}
        - 問題形式: {problem_params.problemType}
        {'- トピック: ' + problem_params.specificTopic if problem_params.specificTopic else ''}
        {'- 追加指示: ' + problem_params.additionalInstructions if problem_params.additionalInstructions else ''}

        【参考資料（アップロードされたPDF内容）】
        {text_content[:10000]}

        【要求事項】
        - 学習指導要領の目標と内容に準拠した問題を作成
        - 児童・生徒の発達段階に適した難易度と表現を使用
        - 思考力・判断力・表現力を育成する問題を含める
        - 基礎的・基本的な知識・技能の定着を確認できる問題

        以下の形式でJSONとして出力してください:
        {{
            "problems": [
                {{
                    "question": "問題文",
                    "answer": "解答",
                    "explanation": "解説（学習指導要領の観点も含める）",
                    "choices": ["選択肢1", "選択肢2", ...] (選択問題の場合のみ),
                    "sourcePage": "参照ページ番号"
                }}
            ]
        }}
        """

            response = model.generate_content(prompt)

            try:
                response_text = response.text
                print(f"Raw AI response: {response_text[:500]}...")  # Log for debugging

                # Clean up response text
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]

                # Try to extract just the JSON part if there's extra text
                response_text = response_text.strip()
                if "{" in response_text:
                    start = response_text.find("{")
                    # Find the matching closing brace
                    brace_count = 0
                    end = start
                    for i, char in enumerate(response_text[start:], start):
                        if char == "{":
                            brace_count += 1
                        elif char == "}":
                            brace_count -= 1
                            if brace_count == 0:
                                end = i + 1
                                break
                    response_text = response_text[start:end]

                generated_data = json.loads(response_text)
                print(f"Parsed JSON: {generated_data}")  # Log for debugging
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                print(f"Failed to parse: {response_text}")
                generated_data = {
                    "problems": [
                        {
                            "question": f"問題{i+1}: {problem_params.subject}に関する{problem_params.problemType}",
                            "answer": "解答例",
                            "explanation": "解説文",
                            "choices": ["選択肢A", "選択肢B", "選択肢C", "選択肢D"] if problem_params.problemType == "選択問題" else None,
                            "sourcePage": f"p.{i+1}"
                        }
                        for i in range(problem_params.problemCount)
                    ]
                }

        problems = []
        for i, problem_data in enumerate(generated_data.get("problems", [])):
            question = problem_data.get("question", "").strip()
            answer = problem_data.get("answer", "").strip()
            explanation = problem_data.get("explanation", "").strip()

            # Use fallback if empty
            if not question:
                question = f"問題{i+1}: {problem_params.subject}に関する{problem_params.problemType}"
            if not answer:
                answer = "解答例"
            if not explanation:
                explanation = "解説文"

            problem = GeneratedProblem(
                id=str(uuid.uuid4()),
                question=question,
                answer=answer,
                explanation=explanation,
                choices=problem_data.get("choices"),
                difficulty=problem_params.difficulty,
                subject=problem_params.subject,
                grade=problem_params.grade,
                sourceFile=request.filename,
                sourcePage=problem_data.get("sourcePage", f"p.{i+1}"),
                sourceUri=None,
                generatedAt=datetime.now()
            )
            problems.append(problem)

        if db:
            batch = db.batch()
            for problem in problems:
                doc_ref = db.collection("generated_problems").document(problem.id)
                batch.set(doc_ref, problem.dict())
            batch.commit()

        return {"problems": [p.dict() for p in problems]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-problems-no-pdf")
async def generate_problems_without_pdf(
    params: ProblemGenerationParams,
    api_key: str = Depends(verify_api_key)
):
    """
    PDFなしで問題を生成するエンドポイント
    """
    try:
        problem_params = params

        # MVP版RAGを使用するかチェック
        if USE_MVP_RAG:
            print("Using MVP RAG Service for no-PDF request")
            mvp_rag = MVPRAGService(project_id=PROJECT_ID)

            try:
                # MVP版RAGで生成（PDF内容なし）
                result = mvp_rag.generate_with_rag(
                    subject=problem_params.subject,
                    grade=problem_params.grade,
                    difficulty=problem_params.difficulty,
                    problem_count=problem_params.problemCount,
                    problem_type=problem_params.problemType,
                    pdf_content="",  # PDF内容なし
                    specific_topic=problem_params.specificTopic
                )

                # 結果から問題を抽出
                generated_data = result
            except Exception as mvp_error:
                print(f"MVP RAG error: {mvp_error}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"MVP RAG error: {str(mvp_error)}")

        else:
            model = GenerativeModel("gemini-1.5-flash")

            # 指導要領サービスを初期化
            guidelines_service = GuidelinesService(project_id=PROJECT_ID)

            # 関連する指導要領を取得
            guidelines = []
            if guidelines_service.db:
                guidelines = guidelines_service.get_relevant_guidelines(
                    subject=problem_params.subject,
                    grade=problem_params.grade,
                    topic=problem_params.specificTopic
                )

            # 指導要領を含むプロンプトを生成
            prompt = f"""
            以下の情報を参考に、{problem_params.subject}の{problem_params.grade}向けの問題を{problem_params.problemCount}問生成してください。
            """

            # 指導要領がある場合は追加
            if guidelines:
                prompt += f"""

        【文部科学省学習指導要領】
        """
                for guideline in guidelines[:2]:  # 最大2つまで使用
                    prompt += f"""
        ■ {guideline.get('subject')} - {guideline.get('grade')}
        学習目標: {', '.join(guideline.get('learning_goals', [])[:3]) if guideline.get('learning_goals') else ''}
        重要トピック: {', '.join(guideline.get('topics', [])) if guideline.get('topics') else ''}
        キーワード: {', '.join(guideline.get('keywords', [])) if guideline.get('keywords') else ''}
        """

                    # 学年別の詳細があれば追加
                    if 'grade_specific' in guideline and problem_params.grade in str(guideline.get('grade_specific', {})):
                        for grade_key, topics in guideline.get('grade_specific', {}).items():
                            if grade_key in problem_params.grade:
                                prompt += f"""
        {grade_key}の学習内容: {', '.join(topics)}
        """

            prompt += f"""

        【生成条件】
        - 難易度: {problem_params.difficulty}
        - 問題形式: {problem_params.problemType}
        {'- トピック: ' + problem_params.specificTopic if problem_params.specificTopic else ''}
        {'- 追加指示: ' + problem_params.additionalInstructions if problem_params.additionalInstructions else ''}

        【要求事項】
        - 学習指導要領の目標と内容に準拠した問題を作成
        - 児童・生徒の発達段階に適した難易度と表現を使用
        - 思考力・判断力・表現力を育成する問題を含める
        - 基礎的・基本的な知識・技能の定着を確認できる問題

        以下の形式でJSONとして出力してください:
        {{
            "problems": [
                {{
                    "question": "問題文",
                    "answer": "解答",
                    "explanation": "解説（学習指導要領の観点も含める）",
                    "choices": ["選択肢1", "選択肢2", ...] (選択問題の場合のみ),
                    "sourcePage": "生成元"
                }}
            ]
        }}
        """

            response = model.generate_content(prompt)

            try:
                response_text = response.text
                print(f"Raw AI response: {response_text[:500]}...")  # Log for debugging

                # Clean up response text
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]

                # Try to extract just the JSON part if there's extra text
                response_text = response_text.strip()
                if "{" in response_text:
                    start = response_text.find("{")
                    # Find the matching closing brace
                    brace_count = 0
                    end = start
                    for i, char in enumerate(response_text[start:], start):
                        if char == "{":
                            brace_count += 1
                        elif char == "}":
                            brace_count -= 1
                            if brace_count == 0:
                                end = i + 1
                                break
                    response_text = response_text[start:end]

                generated_data = json.loads(response_text)
                print(f"Parsed JSON: {generated_data}")  # Log for debugging
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                print(f"Failed to parse: {response_text}")
                generated_data = {
                    "problems": [
                        {
                            "question": f"問題{i+1}: {problem_params.subject}に関する{problem_params.problemType}",
                            "answer": "解答例",
                            "explanation": "解説文",
                            "choices": ["選択肢A", "選択肢B", "選択肢C", "選択肢D"] if problem_params.problemType == "選択問題" else None,
                            "sourcePage": f"指導要領準拠"
                        }
                        for i in range(problem_params.problemCount)
                    ]
                }

        problems = []
        for i, problem_data in enumerate(generated_data.get("problems", [])):
            question = problem_data.get("question", "").strip()
            answer = problem_data.get("answer", "").strip()
            explanation = problem_data.get("explanation", "").strip()

            # Use fallback if empty
            if not question:
                question = f"問題{i+1}: {problem_params.subject}に関する{problem_params.problemType}"
            if not answer:
                answer = "解答例"
            if not explanation:
                explanation = "解説文"

            problem = GeneratedProblem(
                id=str(uuid.uuid4()),
                question=question,
                answer=answer,
                explanation=explanation,
                choices=problem_data.get("choices"),
                difficulty=problem_params.difficulty,
                subject=problem_params.subject,
                grade=problem_params.grade,
                sourceFile="指導要領準拠",
                sourcePage=problem_data.get("sourcePage", f"生成問題{i+1}"),
                sourceUri=None,
                generatedAt=datetime.now()
            )
            problems.append(problem)

        if db:
            batch = db.batch()
            for problem in problems:
                doc_ref = db.collection("generated_problems").document(problem.id)
                batch.set(doc_ref, problem.dict())
            batch.commit()

        return {"problems": [p.dict() for p in problems]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/extract-pdf")
async def extract_pdf_text(
    pdf: UploadFile = File(...),
    api_key: str = Depends(verify_api_key)
):
    try:
        pdf_content = await pdf.read()

        # Enhanced PDF text extraction for extract-pdf endpoint
        extractor = EnhancedPDFExtractor()
        extracted_content = extractor.extract_text_from_pdf(pdf_content, pdf.filename)

        # Parse the text content into pages for backward compatibility
        pages = []
        if extracted_content.text:
            # Split by page markers if they exist
            page_sections = extracted_content.text.split('--- Page ')
            for i, section in enumerate(page_sections[1:], 1):  # Skip first empty split
                # Remove page number from section
                if ' ---' in section:
                    page_text = section.split(' ---', 1)[1].strip()
                else:
                    page_text = section.strip()

                pages.append({
                    "page": i,
                    "text": page_text
                })

        return {
            "filename": pdf.filename,
            "pageCount": len(pdf_reader.pages),
            "pages": pages
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/usage-stats")
async def get_usage_stats(api_key: str = Depends(verify_api_key)):
    """
    MVP版RAGの使用統計を取得
    """
    try:
        mvp_rag = MVPRAGService(project_id=PROJECT_ID)
        stats = mvp_rag.get_monthly_usage()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)