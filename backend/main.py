import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

from database import create_document, get_documents, db
from schemas import (
    UserCreate, UserLogin, TokenResponse, TokenVerifyResponse,
    LearningPlan, LearningStep, Resource, YouTubeVideo, ProjectResource, QuizQuestion
)

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
JWT_ALG = "HS256"
TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Student Career Hub API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility

def create_token(payload: Dict[str, Any]) -> str:
    to_encode = {**payload, "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)}
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALG)


def verify_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# Auth Endpoints
@app.post("/api/auth/signup", response_model=TokenResponse)
async def signup(body: UserCreate):
    users = db()["user"]
    if users.find_one({"email": body.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = pwd_context.hash(body.password)
    doc = {
        "firstName": body.firstName,
        "lastName": body.lastName,
        "email": body.email,
        "password": hashed,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    users.insert_one(doc)
    token = create_token({"sub": body.email})
    return TokenResponse(token=token)


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(body: UserLogin):
    users = db()["user"]
    u = users.find_one({"email": body.email})
    if not u or not pwd_context.verify(body.password, u.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({"sub": u["email"]})
    return TokenResponse(token=token)


class VerifyBody(BaseModel):
    token: str

@app.post("/api/auth/verify", response_model=TokenVerifyResponse)
async def verify(body: VerifyBody):
    try:
        verify_token(body.token)
        return TokenVerifyResponse(valid=True)
    except HTTPException:
        return TokenVerifyResponse(valid=False)


# Simple protected dependency
async def auth_dependency(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    return verify_token(token)


# Gemini proxies (structure only; no frontend dependency on SDK)
from google.generativeai import GenerativeModel, configure

API_KEY = os.getenv("API_KEY")
if API_KEY:
    configure(api_key=API_KEY)


def build_learning_plan_stub(query: str) -> LearningPlan:
    # Fallback structured example if API key missing
    return LearningPlan(
        title=f"Learning plan for {query}",
        description="A curated journey to master the topic.",
        keySkills=["Fundamentals", "Projects", "Interview"],
        learningPath=[
            LearningStep(
                title="Basics",
                description="Learn the foundations.",
                skillsToLearn=["Syntax", "Tools"],
                resources=[Resource(name="Official Docs", url="https://example.com")],
                videos=[YouTubeVideo(id="dQw4w9WgXcQ", title="Intro", url="https://youtube.com/watch?v=dQw4w9WgXcQ")],
            ),
            LearningStep(
                title="Build",
                description="Create sample projects.",
                skillsToLearn=["Project setup", "Testing"],
                resources=[Resource(name="Guide", url="https://example.com/guide")],
                videos=[],
            ),
        ],
        futurePotential="High demand across industries.",
        projectIdeas=["Clone a website", "Data pipeline"],
        projectResources=[ProjectResource(name="Starter Repo", url="https://github.com/", description="Kickstart")],
        relatedRoles=["Engineer", "Analyst"],
    )


@app.post("/api/gemini/learning-plan", response_model=LearningPlan)
async def learning_plan(payload: Dict[str, str], user=Depends(auth_dependency)):
    query = payload.get("query", "")
    if not API_KEY:
        return build_learning_plan_stub(query)
    # With API, still enforce structure by post-processing if needed
    model = GenerativeModel("gemini-1.5-pro")
    prompt = (
        "Return a JSON matching this schema: "
        "LearningPlan{title,description,keySkills[],learningPath[LearningStep{title,description,skillsToLearn[],resources[Resource{name,url,description?}],videos[YouTubeVideo{id,title,url}]}],futurePotential,projectIdeas[],projectResources[ProjectResource{name,url,description?}],relatedRoles?}. "
        f"Topic: {query}"
    )
    res = model.generate_content(prompt)
    text = res.text or "{}"
    import json
    try:
        data = json.loads(text)
        return LearningPlan(**data)
    except Exception:
        return build_learning_plan_stub(query)


@app.post("/api/gemini/chat")
async def chat(payload: Dict[str, Any], user=Depends(auth_dependency)):
    message = payload.get("message", "")
    history = payload.get("history", [])
    if not API_KEY:
        return {"reply": f"Echo: {message}", "history": history + [{"role": "model", "text": f"Echo: {message}"}]}
    model = GenerativeModel("gemini-1.5-pro")
    res = model.generate_content(message)
    return {"reply": res.text}


@app.post("/api/gemini/quiz")
async def quiz(payload: Dict[str, Any], user=Depends(auth_dependency)):
    topic = payload.get("topic", "")
    if not API_KEY:
        return {"questions": [
            {"question": f"What is {topic}?", "options": ["A", "B", "C", "D"], "answerIndex": 1}
        ]}
    model = GenerativeModel("gemini-1.5-pro")
    res = model.generate_content(f"Create 5 MCQs about {topic} as JSON")
    import json
    try:
        return json.loads(res.text or "{}")
    except Exception:
        return {"questions": []}


@app.post("/api/gemini/related-roles")
async def related_roles(payload: Dict[str, Any], user=Depends(auth_dependency)):
    query = payload.get("query", "")
    if not API_KEY:
        return {"roles": ["Software Engineer", "ML Engineer", "Data Analyst"]}
    model = GenerativeModel("gemini-1.5-pro")
    res = model.generate_content(f"List related roles for {query} as JSON array under 'roles'")
    import json
    try:
        return json.loads(res.text or "{}")
    except Exception:
        return {"roles": []}


# Community videos simple persistence
@app.post("/api/community/videos")
async def add_video(payload: Dict[str, str], user=Depends(auth_dependency)):
    title = payload.get("title", "Untitled")
    url = payload.get("url", "")
    description = payload.get("description", "")
    vid = {"title": title, "url": url, "description": description}
    create_document("communityvideo", vid)
    return {"ok": True}


@app.get("/api/community/videos")
async def list_videos(limit: int = 50):
    return {"items": get_documents("communityvideo", limit=limit)}


@app.get("/test")
async def test():
    # verify DB connection
    db().list_collection_names()
    return {"ok": True}
