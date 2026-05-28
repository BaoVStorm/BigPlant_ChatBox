from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from bson import ObjectId
from bson.decimal128 import Decimal128
from pymongo.collection import Collection

from app.config import Settings, get_settings
from app.db.mongo import get_database, serialize_mongo


class ProductRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.db = get_database()
        self._plant_category_ids: list[Any] | None = None

    @property
    def products(self) -> Collection:
        return self.db[self.settings.products_collection]

    @property
    def categories(self) -> Collection:
        return self.db[self.settings.product_categories_collection]

    @property
    def variants(self) -> Collection:
        return self.db[self.settings.product_variants_collection]

    @property
    def inventory(self) -> Collection:
        return self.db[self.settings.variant_inventory_collection]

    @property
    def images(self) -> Collection:
        return self.db[self.settings.product_images_collection]

    @property
    def plants(self) -> Collection:
        return self.db[self.settings.plants_collection]

    @property
    def profiles(self) -> Collection:
        return self.db[self.settings.plant_profiles_collection]

    def get_product_by_name(self, name: str) -> dict[str, Any] | None:
        name = name.strip()
        if not name:
            return None
        escaped = re.escape(name)
        query = self._plant_product_query(
            {
                "$or": [
                    {"name": {"$regex": escaped, "$options": "i"}},
                    {"slug": {"$regex": escaped.replace("\\ ", "[-_ ]"), "$options": "i"}},
                    {"sku": {"$regex": escaped, "$options": "i"}},
                ]
            }
        )
        doc = self.products.find_one(query)
        if not doc:
            plant = self.plants.find_one(
                {
                    "$or": [
                        {"scientific_name": {"$regex": escaped, "$options": "i"}},
                        {"scientific_name_search": {"$regex": escaped.replace("\\ ", "[_ -]?"), "$options": "i"}},
                        {"common_name": {"$regex": escaped, "$options": "i"}},
                    ]
                },
                {"_id": 1},
            )
            if plant:
                doc = self.products.find_one(self._plant_product_query({"plant_id": {"$in": object_id_or_string_values(plant.get("_id"))}}))
        return serialize_mongo(doc) if doc else None

    def get_product_by_slug(self, slug: str) -> dict[str, Any] | None:
        doc = self.products.find_one(self._plant_product_query({"slug": slug}))
        return serialize_mongo(doc) if doc else None

    def get_product_by_detected_plant(
        self,
        label: str | None = None,
        scientific_name_search: str | None = None,
        plant: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if plant and plant.get("_id"):
            doc = self.products.find_one(self._plant_product_query({"plant_id": {"$in": object_id_or_string_values(plant.get("_id"))}}))
            if doc:
                return serialize_mongo(doc)

        if scientific_name_search:
            raw_plant = self.plants.find_one({"scientific_name_search": scientific_name_search}, {"_id": 1})
            if raw_plant:
                doc = self.products.find_one(self._plant_product_query({"plant_id": {"$in": object_id_or_string_values(raw_plant.get("_id"))}}))
                if doc:
                    return serialize_mongo(doc)

        for candidate in [
            label,
            scientific_name_search.replace("_", " ") if scientific_name_search else None,
            plant.get("scientific_name") if plant else None,
            plant.get("common_name") if plant else None,
        ]:
            if candidate:
                product = self.get_product_by_name(str(candidate))
                if product:
                    return product
        return None

    def find_product_mentioned(self, message: str) -> dict[str, Any] | None:
        lowered = message.lower()
        cursor = self.products.find(self._plant_product_query(), {"name": 1, "slug": 1, "sku": 1}).limit(700)
        for candidate in cursor:
            name = str(candidate.get("name") or "").lower()
            slug = str(candidate.get("slug") or "").replace("-", " ").lower()
            sku = str(candidate.get("sku") or "").lower()
            if (name and name in lowered) or (slug and slug in lowered) or (sku and sku in lowered):
                doc = self.products.find_one({"_id": candidate["_id"]})
                return serialize_mongo(doc) if doc else None
        return None

    def get_product_full_context(self, product_or_id: dict[str, Any] | str) -> dict[str, Any] | None:
        product = self._get_raw_product(product_or_id)
        if not product:
            return None

        product_id = product.get("_id")
        variants = self._get_raw_variants(product_id)
        inventories = self._get_raw_inventories([variant.get("_id") for variant in variants])
        variants_with_inventory = attach_inventory(variants, inventories)
        category = self._get_raw_by_id(self.categories, product.get("category_id"))
        plant = self._get_raw_by_id(self.plants, product.get("plant_id"))
        images = self._get_raw_images(product_id, [variant.get("_id") for variant in variants])
        profile = self._get_raw_profile(product.get("plant_id"), product_id)
        computed = compute_product_values(variants_with_inventory, images)

        context = {
            "_id": str(product_id),
            "name": product.get("name"),
            "slug": product.get("slug"),
            "sku": product.get("sku"),
            "care_level": product.get("care_level"),
            "rating_avg": product.get("rating_avg"),
            "rating_count": product.get("rating_count"),
            "product": serialize_mongo(product),
            "category": serialize_mongo(category) if category else None,
            "plant": serialize_mongo(plant) if plant else None,
            "plant_profile": serialize_mongo(profile) if profile else None,
            "variants": serialize_mongo(variants_with_inventory),
            "images": serialize_mongo(images),
            "computed": computed,
        }
        if isinstance(product_or_id, dict) and product_or_id.get("vector_score") is not None:
            context["vector_score"] = product_or_id["vector_score"]
        return context

    def get_product_variants(self, product_id: str) -> list[dict[str, Any]]:
        variants = self._get_raw_variants(product_id)
        inventories = self._get_raw_inventories([variant.get("_id") for variant in variants])
        return serialize_mongo(attach_inventory(variants, inventories))

    def get_product_images(self, product_id: str) -> list[dict[str, Any]]:
        return serialize_mongo(self._get_raw_images(product_id, []))

    def search_products(self, filters: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
        query = self._plant_product_query(build_product_filter(filters))
        cursor = self.products.find(query).limit(max(limit * 20, 200))
        contexts: list[dict[str, Any]] = []
        for product in cursor:
            context = self.get_product_full_context(product)
            if context and context_matches_filters(context, filters):
                contexts.append(context)
            if len(contexts) >= limit:
                break
        return contexts

    def get_products_by_ids(self, product_ids: list[str], limit: int = 10) -> list[dict[str, Any]]:
        if not product_ids:
            return []
        ids: list[Any] = []
        for product_id in product_ids:
            ids.extend(object_id_or_string_values(product_id))
        docs = list(self.products.find(self._plant_product_query({"_id": {"$in": ids}})).limit(limit))
        order = {str(product_id): index for index, product_id in enumerate(product_ids)}
        docs.sort(key=lambda doc: order.get(str(doc.get("_id")), 9999))
        return [context for doc in docs if (context := self.get_product_full_context(doc))]

    def hydrate_product_contexts(self, products: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
        contexts: list[dict[str, Any]] = []
        for product in products:
            context = self.get_product_full_context(product)
            if context:
                contexts.append(context)
            if len(contexts) >= limit:
                break
        return contexts

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
            {"$match": self._plant_product_match_stage()},
            {"$project": {self.settings.product_embedding_field: 0}},
        ]
        return [serialize_mongo(doc) for doc in self.products.aggregate(pipeline)]

    def update_product_embedding(self, product_id: str, embedding: list[float], embedding_text: str) -> None:
        values = object_id_or_string_values(product_id)
        self.products.update_one(
            {"_id": {"$in": values}},
            {"$set": {self.settings.product_embedding_field: embedding, "embedding_text": embedding_text}},
        )

    def _get_raw_product(self, product_or_id: dict[str, Any] | str) -> dict[str, Any] | None:
        if isinstance(product_or_id, dict):
            product_id = product_or_id.get("_id")
            if product_id:
                raw = self.products.find_one({"_id": {"$in": object_id_or_string_values(product_id)}})
                if raw:
                    if product_or_id.get("vector_score") is not None:
                        raw["vector_score"] = product_or_id["vector_score"]
                    return raw
            return product_or_id
        return self.products.find_one({"_id": {"$in": object_id_or_string_values(product_or_id)}})

    def _get_raw_variants(self, product_id: Any) -> list[dict[str, Any]]:
        query = {"product_id": {"$in": object_id_or_string_values(product_id)}, "is_active": {"$ne": False}}
        return list(self.variants.find(query).sort([("is_default", -1), ("price", 1)]))

    def _get_raw_inventories(self, variant_ids: list[Any]) -> list[dict[str, Any]]:
        ids: list[Any] = []
        for variant_id in variant_ids:
            ids.extend(object_id_or_string_values(variant_id))
        if not ids:
            return []
        return list(self.inventory.find({"variant_id": {"$in": ids}}))

    def _get_raw_images(self, product_id: Any, variant_ids: list[Any]) -> list[dict[str, Any]]:
        product_ids = object_id_or_string_values(product_id)
        all_variant_ids: list[Any] = []
        for variant_id in variant_ids:
            all_variant_ids.extend(object_id_or_string_values(variant_id))
        query: dict[str, Any] = {"$or": [{"product_id": {"$in": product_ids}}]}
        if all_variant_ids:
            query["$or"].append({"variant_id": {"$in": all_variant_ids}})
        return list(self.images.find(query).sort([("is_primary", -1), ("sort_order", 1)]).limit(12))

    def _get_raw_by_id(self, collection: Collection, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        return collection.find_one({"_id": {"$in": object_id_or_string_values(value)}})

    def _get_raw_profile(self, plant_id: Any, product_id: Any) -> dict[str, Any] | None:
        query = {"$or": []}
        plant_values = object_id_or_string_values(plant_id)
        if plant_values:
            query["$or"].append({"plant_id": {"$in": plant_values}})
        product_values = object_id_or_string_values(product_id)
        if product_values:
            query["$or"].append({"primary_product_id": {"$in": product_values}})
            query["$or"].append({"product_ids": {"$in": product_values}})
        if not query["$or"]:
            return None
        return self.profiles.find_one(query)

    def _plant_product_query(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        clauses = [{"is_active": {"$ne": False}}, self._plant_constraint()]
        if extra:
            clauses.append(extra)
        return {"$and": clauses}

    def _plant_product_match_stage(self) -> dict[str, Any]:
        return self._plant_product_query()

    def _plant_constraint(self) -> dict[str, Any]:
        category_ids = self.get_plant_category_ids()
        plant_conditions: list[dict[str, Any]] = [{"product_type": "plant"}]
        if category_ids:
            plant_conditions.append({"category_id": {"$in": category_ids}})
        return {"$or": plant_conditions}

    def get_plant_category_ids(self) -> list[Any]:
        if self._plant_category_ids is not None:
            return self._plant_category_ids

        root_query = {
            "is_active": {"$ne": False},
            "$or": [
                {"name": {"$regex": r"^(cây|cay)$", "$options": "i"}},
                {"slug": {"$regex": r"^(cay|plant|plants)$", "$options": "i"}},
            ],
        }
        roots = list(self.categories.find(root_query, {"_id": 1}))
        category_ids = [category["_id"] for category in roots]
        seen = {str(category_id) for category_id in category_ids}
        frontier = list(category_ids)

        while frontier:
            parent_values: list[Any] = []
            for category_id in frontier:
                parent_values.extend(object_id_or_string_values(category_id))
            children = list(self.categories.find({"parent_id": {"$in": parent_values}, "is_active": {"$ne": False}}, {"_id": 1}))
            frontier = []
            for child in children:
                child_id = child["_id"]
                if str(child_id) not in seen:
                    seen.add(str(child_id))
                    category_ids.append(child_id)
                    frontier.append(child_id)

        expanded: list[Any] = []
        for category_id in category_ids:
            expanded.extend(object_id_or_string_values(category_id))
        self._plant_category_ids = expanded
        return expanded


def object_id_or_string_values(value: Any) -> list[Any]:
    if value is None:
        return []
    values: list[Any] = []
    if isinstance(value, ObjectId):
        values.append(value)
        values.append(str(value))
        return values
    values.append(value)
    try:
        object_id = ObjectId(str(value))
        if object_id not in values:
            values.insert(0, object_id)
    except Exception:
        pass
    return values


def build_product_filter(filters: dict[str, Any]) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if filters.get("care_level"):
        care_levels = sorted(care_level_aliases(filters["care_level"]))
        if care_levels:
            pattern = "^(" + "|".join(re.escape(value) for value in care_levels) + ")$"
            query["care_level"] = {"$regex": pattern, "$options": "i"}
    return query


def build_vector_filter(filters: dict[str, Any]) -> dict[str, Any]:
    return {}


def attach_inventory(variants: list[dict[str, Any]], inventories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inventory_by_variant_id = {str(inventory.get("variant_id")): inventory for inventory in inventories}
    result = []
    for variant in variants:
        item = dict(variant)
        item["inventory"] = inventory_by_variant_id.get(str(variant.get("_id")))
        result.append(item)
    return result


def compute_product_values(variants: list[dict[str, Any]], images: list[dict[str, Any]]) -> dict[str, Any]:
    prices = [to_float(variant.get("price")) for variant in variants if variant.get("price") is not None]
    prices = [price for price in prices if price is not None]
    available_qty = 0
    has_inventory = False
    for variant in variants:
        inventory = variant.get("inventory") or {}
        if inventory:
            has_inventory = True
        available_qty += int(inventory.get("available_qty") or 0)

    primary_image = next((image for image in images if image.get("is_primary") is True), images[0] if images else None)
    price_min = min(prices) if prices else None
    price_max = max(prices) if prices else None
    return {
        "price_min": price_min,
        "price_max": price_max,
        "price_text": format_price_range_values(price_min, price_max),
        "available_qty": available_qty,
        "has_inventory": has_inventory,
        "in_stock": available_qty > 0,
        "variant_count": len(variants),
        "primary_image_url": normalize_image_url(primary_image.get("image_url") if primary_image else None),
    }


def context_matches_filters(context: dict[str, Any], filters: dict[str, Any]) -> bool:
    computed = context.get("computed") or {}
    product = context.get("product") or {}
    profile = context.get("plant_profile") or {}
    care_profile = profile.get("care_profile") or {}
    safety_profile = profile.get("safety_profile") or {}
    product_id = str(product.get("_id") or "")
    if filters.get("max_price"):
        price_min = computed.get("price_min")
        if price_min is None or float(price_min) > float(filters["max_price"]):
            return False
    if filters.get("reference_price_max") is not None:
        price_min = computed.get("price_min")
        if price_min is None or float(price_min) >= float(filters["reference_price_max"]):
            return False
    if filters.get("reference_product_id") and product_id == str(filters["reference_product_id"]):
        return False
    if filters.get("care_level") and not care_level_matches(product.get("care_level") or care_profile.get("care_level"), filters.get("care_level")):
        return False
    if filters.get("watering_need") and not profile_value_matches(care_profile.get("watering_need"), filters.get("watering_need")):
        return False
    if filters.get("light_requirement") and not light_matches(care_profile.get("light_requirement"), filters.get("light_requirement")):
        return False
    if filters.get("placement") and not placement_matches(care_profile.get("placement_tags"), filters.get("placement")):
        return False
    if filters.get("pet_safe") is True and safety_profile.get("pet_safe") is not True:
        return False
    if filters.get("in_stock") is True and not computed.get("in_stock"):
        return False
    return True


def care_level_matches(actual: Any, expected: Any) -> bool:
    actual_text = normalize_text(actual)
    return bool(actual_text and actual_text in care_level_aliases(expected))


def care_level_aliases(expected: Any) -> set[str]:
    expected_text = normalize_text(expected)
    if expected_text in {"easy", "de", "de cham", "low", "low maintenance"}:
        return {"easy", "low", "moderate"}
    if expected_text in {"moderate", "medium", "trung binh"}:
        return {"moderate", "medium", "easy", "low"}
    if expected_text in {"hard", "difficult", "advanced", "kho", "kho cham"}:
        return {"hard", "difficult", "advanced"}
    return {expected_text} if expected_text else set()


def profile_value_matches(actual: Any, expected: Any) -> bool:
    if actual is None or expected is None:
        return False
    return normalize_text(actual) == normalize_text(expected)


def light_matches(actual: Any, expected: Any) -> bool:
    actual_text = normalize_text(actual)
    expected_text = normalize_text(expected)
    if not actual_text or actual_text == "unknown":
        return False
    if expected_text in {"low", "it nang", "thieu sang"}:
        return actual_text in {"low_to_indirect", "low", "partial_shade"}
    if expected_text in {"indirect", "gian tiep"}:
        return actual_text in {"low_to_indirect", "bright_indirect", "partial_shade"}
    if expected_text in {"bright", "full_sun", "sun"}:
        return actual_text in {"bright_indirect", "full_sun", "bright_outdoor"}
    return actual_text == expected_text


def placement_matches(actual: Any, expected: Any) -> bool:
    if not isinstance(actual, list):
        return False
    normalized_tags = {normalize_text(item) for item in actual}
    expected_text = normalize_text(expected)
    aliases = {
        "desk": {"desk", "office", "living_room"},
        "office": {"office", "desk", "living_room"},
        "bedroom": {"bedroom", "living_room", "office"},
        "living_room": {"living_room", "office", "balcony"},
        "balcony": {"balcony", "outdoor_garden"},
        "outdoor": {"outdoor_garden", "balcony", "water_edge"},
    }
    return bool(normalized_tags & aliases.get(expected_text, {expected_text}))


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal128):
        return float(value.to_decimal())
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_price_range_values(price_min: float | None, price_max: float | None) -> str:
    if price_min is None:
        return "chưa có dữ liệu giá"
    if price_max is None or float(price_min) == float(price_max):
        return format_price_number(price_min)
    return f"{format_price_number(price_min)} - {format_price_number(price_max)}"


def format_price_number(value: float) -> str:
    settings = get_settings()
    currency = settings.catalog_price_currency.upper()
    if currency == "USD":
        return f"{float(value):.2f} USD"
    if float(value).is_integer():
        number = f"{int(value):,}".replace(",", ".")
    else:
        number = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{number} VND"


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_image_url(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
