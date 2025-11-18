import os
from typing import Any, Dict, List, Optional
from datetime import datetime
from pymongo import MongoClient
from pymongo.collection import Collection

DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "student_career_hub")

_client: Optional[MongoClient] = None
_db = None

def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(DATABASE_URL)
    return _client

def db():
    global _db
    if _db is None:
        _db = get_client()[DATABASE_NAME]
    return _db


def get_collection(name: str) -> Collection:
    return db()[name]


def create_document(collection_name: str, data: Dict[str, Any]) -> str:
    col = get_collection(collection_name)
    now = datetime.utcnow()
    doc = {**data, "createdAt": now, "updatedAt": now}
    result = col.insert_one(doc)
    return str(result.inserted_id)


def get_documents(collection_name: str, filter_dict: Optional[Dict[str, Any]] = None, limit: int = 50) -> List[Dict[str, Any]]:
    col = get_collection(collection_name)
    cursor = col.find(filter_dict or {}).limit(limit)
    out = []
    for d in cursor:
        d["_id"] = str(d.get("_id"))
        out.append(d)
    return out
