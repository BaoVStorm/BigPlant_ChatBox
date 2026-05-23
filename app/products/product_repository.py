from __future__ import annotations

import re
from typing import Any

from bson import ObjectId
from pymongo.collection import Collection

from app.config import Settings, get_settings
from app.db.mongo import get_database, serialize_mongo


class ProductRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.db = get_database()

    @property
    def products(self) -> Collection:
        return self.db[self.settings.products_collection]

    @property
    def variants(self) -> Collection:
        return self.db[self.settings.product_variants_collection]

    @property
    def images(self) -> Collection:
        return self.db[self.settings.product_images_collection]

    def get_product_by_name(self, name: str) -> dict[str, Any] | None:
        name = name.strip()
        if not name:
            return None
        escaped = re.escape(name)
        query = {
            "is_active": {"$ne": False},
            "$or": [
                {"name": {"$regex": escaped, "$options": "i"}},
                {"slug": {"$regex": escaped.replace("\\ ", "[-_ ]"), "$options": "i"}},
                {"sku": {"$regex": escaped, "$options": "i"}},
            ],
        }
        doc = self.products.find_one(query)
        return serialize_mongo(doc) if doc else None

    def get_product_by_slug(self, slug: str) -> dict[str, Any] | None:
        doc = self.products.find_one({"slug": slug, "is_active": {"$ne": False}})
        return serialize_mongo(doc) if doc else None

    def find_product_mentioned(self, message: str) -> dict[str, Any] | None:
        lowered = message.lower()
        cursor = self.products.find({"is_active": {"$ne": False}}, {"name": 1, "slug": 1, "sku": 1}).limit(500)
        candidates = list(cursor)
        for candidate in candidates:
            name = str(candidate.get("name") or "").lower()
            slug = str(candidate.get("slug") or "").replace("-", " ").lower()
            sku = str(candidate.get("sku") or "").lower()
            if (name and name in lowered) or (slug and slug in lowered) or (sku and sku in lowered):
                doc = self.products.find_one({"_id": candidate["_id"]})
                return serialize_mongo(doc) if doc else None
        return None

    def get_product_variants(self, product_id: str) -> list[dict[str, Any]]:
        ids = object_id_or_string_values(product_id)
        query = {"product_id": {"$in": ids}, "is_active": {"$ne": False}}
        return [serialize_mongo(doc) for doc in self.variants.find(query).sort("price", 1)]

    def get_product_images(self, product_id: str) -> list[dict[str, Any]]:
        ids = object_id_or_string_values(product_id)
        query = {"product_id": {"$in": ids}, "is_active": {"$ne": False}}
        return [serialize_mongo(doc) for doc in self.images.find(query).limit(8)]

    def search_products(self, filters: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
        query = build_product_filter(filters)
        cursor = self.products.find(query).limit(limit)
        return [serialize_mongo(doc) for doc in cursor]

    def get_products_by_ids(self, product_ids: list[str], limit: int = 10) -> list[dict[str, Any]]:
        if not product_ids:
            return []
        ids: list[Any] = []
        for product_id in product_ids:
            ids.extend(object_id_or_string_values(product_id))
        docs = list(self.products.find({"_id": {"$in": ids}, "is_active": {"$ne": False}}).limit(limit))
        order = {str(product_id): index for index, product_id in enumerate(product_ids)}
        docs.sort(key=lambda doc: order.get(str(doc.get("_id")), 9999))
        return [serialize_mongo(doc) for doc in docs]

    def vector_search_products(
        self,
        query_vector: list[float],
        filters: dict[str, Any] | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        vector_stage: dict[str, Any] = {
            "index": self.settings.product_vector_index,
            "path": self.settings.product_embedding_field,
            "queryVector": query_vector,
            "numCandidates": max(limit * 10, 50),
            "limit": limit,
        }
        mongo_filter = build_vector_filter(filters or {})
        if mongo_filter:
            vector_stage["filter"] = mongo_filter

        pipeline = [
            {"$vectorSearch": vector_stage},
            {"$addFields": {"vector_score": {"$meta": "vectorSearchScore"}}},
            {"$match": {"is_active": {"$ne": False}}},
            {"$project": {self.settings.product_embedding_field: 0}},
        ]
        return [serialize_mongo(doc) for doc in self.products.aggregate(pipeline)]

    def update_product_embedding(self, product_id: str, embedding: list[float], embedding_text: str) -> None:
        values = object_id_or_string_values(product_id)
        self.products.update_one(
            {"_id": {"$in": values}},
            {"$set": {self.settings.product_embedding_field: embedding, "embedding_text": embedding_text}},
        )


def object_id_or_string_values(value: str) -> list[Any]:
    values: list[Any] = [value]
    try:
        values.insert(0, ObjectId(value))
    except Exception:
        pass
    return values


def build_product_filter(filters: dict[str, Any]) -> dict[str, Any]:
    query: dict[str, Any] = {"is_active": {"$ne": False}}
    if filters.get("max_price"):
        query["price_min"] = {"$lte": int(filters["max_price"])}
    if filters.get("care_level"):
        query["care_level"] = filters["care_level"]
    if filters.get("watering_need"):
        query["watering_need"] = filters["watering_need"]
    if filters.get("light_requirement"):
        light = filters["light_requirement"]
        query["light_requirement"] = {"$in": ["low", "indirect"]} if light == "low" else light
    if filters.get("placement"):
        query["suitable_locations"] = filters["placement"]
    if filters.get("pet_safe") is True:
        query["pet_safe"] = True
    return query


def build_vector_filter(filters: dict[str, Any]) -> dict[str, Any]:
    vector_filter: dict[str, Any] = {}
    if filters.get("care_level"):
        vector_filter["care_level"] = filters["care_level"]
    if filters.get("watering_need"):
        vector_filter["watering_need"] = filters["watering_need"]
    if filters.get("light_requirement"):
        vector_filter["light_requirement"] = filters["light_requirement"]
    if filters.get("pet_safe") is True:
        vector_filter["pet_safe"] = True
    return vector_filter
