from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional

# Primary app schemas
class YouTubeVideo(BaseModel):
    id: str
    title: str
    url: str

class Resource(BaseModel):
    name: str
    url: str
    description: Optional[str] = None

class ProjectResource(BaseModel):
    name: str
    url: str
    description: Optional[str] = None

class LearningStep(BaseModel):
    title: str
    description: str
    skillsToLearn: List[str]
    resources: List[Resource] = []
    videos: List[YouTubeVideo] = []

class LearningPlan(BaseModel):
    title: str
    description: str
    keySkills: List[str]
    learningPath: List[LearningStep]
    futurePotential: str
    projectIdeas: List[str]
    projectResources: List[ProjectResource]
    relatedRoles: Optional[List[str]] = None

class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    answerIndex: int

class CommunityVideo(BaseModel):
    title: str
    url: str
    description: Optional[str] = None

# Auth schemas
class UserCreate(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    token: str

class TokenVerifyResponse(BaseModel):
    valid: bool

