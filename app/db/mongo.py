from __future__ import annotations

from functools import lru_cache
from typing import Any

from bson import ObjectId
from pymongo import MongoClient
from pymongo.database import Database

from app.config import get_settings


def serialize_mongo(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [serialize_mongo(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_mongo(item) for key, item in value.items()}
    return value


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    settings = get_settings()
    if not settings.mongo_uri:
        raise RuntimeError("MONGO_URI is not configured. Create .env from .env.example first.")
    return MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=7000)


def get_database() -> Database:
    settings = get_settings()
    return get_mongo_client()[settings.mongo_db_name]
