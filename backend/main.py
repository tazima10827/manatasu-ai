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

load_dotenv()

app = FastAPI(title="manatasuAI API", version="1.0.0")

security = HTTPBearer()

origins = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:5000",
    "https://manatasu-ai.web.app",
    "https://manatasu-ai.firebaseapp.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

        from io import BytesIO
        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
        text_content = ""
        for page_num, page in enumerate(pdf_reader.pages):
            text_content += f"\n--- Page {page_num + 1} ---\n"
            text_content += page.extract_text()

        print(f"Extracted PDF content length: {len(text_content)}")
        print(f"PDF content preview: {text_content[:200]}...")

        model = GenerativeModel("gemini-1.5-flash")

        prompt = f"""
        以下のPDF内容から、{problem_params.subject}の{problem_params.grade}向けの問題を{problem_params.problemCount}問生成してください。

        条件:
        - 難易度: {problem_params.difficulty}
        - 問題形式: {problem_params.problemType}
        {'- トピック: ' + problem_params.specificTopic if problem_params.specificTopic else ''}
        {'- 追加指示: ' + problem_params.additionalInstructions if problem_params.additionalInstructions else ''}

        PDF内容:
        {text_content[:10000]}

        以下の形式でJSONとして出力してください:
        {{
            "problems": [
                {{
                    "question": "問題文",
                    "answer": "解答",
                    "explanation": "解説",
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

@app.post("/api/extract-pdf")
async def extract_pdf_text(
    pdf: UploadFile = File(...),
    api_key: str = Depends(verify_api_key)
):
    try:
        pdf_content = await pdf.read()
        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))

        pages = []
        for page_num, page in enumerate(pdf_reader.pages):
            pages.append({
                "page": page_num + 1,
                "text": page.extract_text()
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)