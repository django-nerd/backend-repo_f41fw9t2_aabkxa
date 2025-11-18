import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime, timezone

# Database helpers
from database import create_document, db

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuizQuestion(BaseModel):
    id: int
    question: str
    options: List[str]
    answer_index: int


class Quiz(BaseModel):
    topic: str
    questions: List[QuizQuestion]


class QuizSubmission(BaseModel):
    name: str = Field(..., description="Display name for certificate")
    topic: str
    answers: List[int]


class QuizResult(BaseModel):
    topic: str
    total: int
    correct: int
    score: int
    passed: bool
    certificate_id: Optional[str] = None


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# --- Quiz endpoints ---

def generate_sample_quiz(topic: str) -> Quiz:
    base_questions = [
        {
            "q": f"Which statement best describes {topic}?",
            "opts": [
                f"A core concept in {topic}",
                "A cooking technique",
                "A musical instrument",
                "A type of weather"
            ],
            "ans": 0
        },
        {
            "q": f"What is a common beginner task in {topic}?",
            "opts": [
                "Build a small project",
                "Run a marathon",
                "Compose a symphony",
                "Paint a portrait"
            ],
            "ans": 0
        },
        {
            "q": f"Which tool might you use in {topic}?",
            "opts": [
                f"A popular {topic} tool",
                "A lawn mower",
                "A fishing rod",
                "A telescope"
            ],
            "ans": 0
        },
        {
            "q": f"What is a best practice in learning {topic}?",
            "opts": [
                "Practice consistently",
                "Avoid feedback",
                "Ignore fundamentals",
                "Cram once a year"
            ],
            "ans": 0
        },
        {
            "q": f"How do you showcase skills in {topic}?",
            "opts": [
                "Create a portfolio",
                "Keep it secret",
                "Delete your code",
                "Never share your work"
            ],
            "ans": 0
        },
    ]
    questions = [
        QuizQuestion(id=i + 1, question=item["q"], options=item["opts"], answer_index=item["ans"])  # type: ignore
        for i, item in enumerate(base_questions)
    ]
    return Quiz(topic=topic, questions=questions)


@app.get("/api/quiz", response_model=Quiz)
def get_quiz(topic: str = "Web Development"):
    return generate_sample_quiz(topic)


@app.post("/api/quiz/submit", response_model=QuizResult)
def submit_quiz(payload: QuizSubmission):
    quiz = generate_sample_quiz(payload.topic)
    if len(payload.answers) != len(quiz.questions):
        raise HTTPException(status_code=400, detail="Answers length does not match questions")

    correct = 0
    for i, q in enumerate(quiz.questions):
        try:
            if payload.answers[i] == q.answer_index:
                correct += 1
        except Exception:
            continue

    total = len(quiz.questions)
    score = int((correct / total) * 100)
    passed = score >= 60

    certificate_id: Optional[str] = None
    if passed and db is not None:
        # Persist a certificate document
        doc = {
            "name": payload.name,
            "topic": payload.topic,
            "score": score,
            "correct": correct,
            "total": total,
            "issued_at": datetime.now(timezone.utc),
        }
        try:
            certificate_id = create_document("certificate", doc)
        except Exception:
            certificate_id = None

    return QuizResult(
        topic=payload.topic,
        total=total,
        correct=correct,
        score=score,
        passed=passed,
        certificate_id=certificate_id,
    )


@app.get("/api/certificate/{cert_id}")
def get_certificate(cert_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    from bson import ObjectId

    try:
        doc = db["certificate"].find_one({"_id": ObjectId(cert_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Certificate not found")
        # Convert ObjectId and datetime
        doc["id"] = str(doc.pop("_id"))
        if isinstance(doc.get("issued_at"), datetime):
            doc["issued_at"] = doc["issued_at"].isoformat()
        return doc
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid certificate id")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
