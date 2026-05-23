from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.collection import Collection

from app.config import Settings, get_settings
from app.db.mongo import get_database, serialize_mongo


class KnowledgeRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.db = get_database()

    @property
    def articles(self) -> Collection:
        return self.db[self.settings.knowledge_articles_collection]

    @property
    def chunks(self) -> Collection:
        return self.db[self.settings.knowledge_chunks_collection]

    def get_active_articles(self) -> list[dict[str, Any]]:
        cursor = self.articles.find({"is_active": {"$ne": False}})
        return [serialize_mongo(doc) for doc in cursor]

    def delete_chunks_for_article(self, article_id: str) -> None:
        self.chunks.delete_many({"article_id": {"$in": object_id_or_string_values(article_id)}})

    def upsert_chunk(
        self,
        article: dict[str, Any],
        chunk_index: int,
        content: str,
        embedding: list[float],
        embedding_model: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        article_id = article.get("_id")
        article_values = object_id_or_string_values(str(article_id))
        doc = {
            "article_id": article_values[0],
            "chunk_index": chunk_index,
            "title": article.get("title"),
            "content": content,
            "embedding_model": embedding_model,
            self.settings.knowledge_embedding_field: embedding,
            "metadata": {
                "topics": article.get("topics") or [],
                "related_plants": article.get("related_plants") or [],
                "source_type": article.get("source_type") or "article",
                "slug": article.get("slug"),
            },
            "updated_at": now,
        }
        self.chunks.update_one(
            {"article_id": {"$in": article_values}, "chunk_index": chunk_index},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    def vector_search_chunks(
        self,
        query_vector: list[float],
        filters: dict[str, Any] | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        vector_stage: dict[str, Any] = {
            "index": self.settings.knowledge_vector_index,
            "path": self.settings.knowledge_embedding_field,
            "queryVector": query_vector,
            "numCandidates": max(limit * 10, 50),
            "limit": limit,
        }
        mongo_filter = build_knowledge_filter(filters or {})
        if mongo_filter:
            vector_stage["filter"] = mongo_filter

        pipeline = [
            {"$vectorSearch": vector_stage},
            {"$addFields": {"vector_score": {"$meta": "vectorSearchScore"}}},
            {"$project": {self.settings.knowledge_embedding_field: 0}},
        ]
        return [serialize_mongo(doc) for doc in self.chunks.aggregate(pipeline)]


def object_id_or_string_values(value: str) -> list[Any]:
    values: list[Any] = [value]
    try:
        values.insert(0, ObjectId(value))
    except Exception:
        pass
    return values


def build_knowledge_filter(filters: dict[str, Any]) -> dict[str, Any]:
    mongo_filter: dict[str, Any] = {}
    if filters.get("topic"):
        mongo_filter["metadata.topics"] = filters["topic"]
    if filters.get("plant_slug"):
        mongo_filter["metadata.related_plants"] = filters["plant_slug"]
    return mongo_filter
