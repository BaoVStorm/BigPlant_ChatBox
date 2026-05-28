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
        contexts = self.get_products_full_contexts([product_or_id], limit=1)
        return contexts[0] if contexts else None

    def get_products_full_contexts(self, products_or_ids: list[dict[str, Any] | str], limit: int | None = None) -> list[dict[str, Any]]:
        products = self._get_raw_products(products_or_ids)
        if limit is not None:
            products = products[:limit]
        if not products:
            return []

        product_ids = [product.get("_id") for product in products if product.get("_id") is not None]
        product_values = expanded_object_values(product_ids)
        category_values = expanded_object_values(product.get("category_id") for product in products if product.get("category_id") is not None)
        plant_values = expanded_object_values(product.get("plant_id") for product in products if product.get("plant_id") is not None)

        variants = list(self.variants.find({"product_id": {"$in": product_values}, "is_active": {"$ne": False}}).sort([("is_default", -1), ("price", 1)]))
        variants_by_product = group_by_field(variants, "product_id")
        variant_ids = [variant.get("_id") for variant in variants if variant.get("_id") is not None]
        variant_values = expanded_object_values(variant_ids)
        variant_to_product_id = {str(variant.get("_id")): str(variant.get("product_id")) for variant in variants if variant.get("_id") is not None}

        inventories = list(self.inventory.find({"variant_id": {"$in": variant_values}})) if variant_values else []
        inventory_by_variant_id = {str(inventory.get("variant_id")): inventory for inventory in inventories}

        categories = list(self.categories.find({"_id": {"$in": category_values}})) if category_values else []
        category_by_id = first_by_id(categories)

        plants = list(self.plants.find({"_id": {"$in": plant_values}})) if plant_values else []
        plant_by_id = first_by_id(plants)

        profiles = self._get_raw_profiles_for_batch(plant_values, product_values)
        profile_by_plant_id, profile_by_product_id = index_profiles(profiles)

        image_query: dict[str, Any] = {"$or": [{"product_id": {"$in": product_values}}]}
        if variant_values:
            image_query["$or"].append({"variant_id": {"$in": variant_values}})
        images = list(self.images.find(image_query).sort([("is_primary", -1), ("sort_order", 1)]).limit(max(len(products) * 12, 12)))
        images_by_product: dict[str, list[dict[str, Any]]] = {}
        for image in images:
            product_key = str(image.get("product_id") or "")
            if not product_key and image.get("variant_id") is not None:
                product_key = variant_to_product_id.get(str(image.get("variant_id")), "")
            if product_key:
                images_by_product.setdefault(product_key, []).append(image)

        contexts: list[dict[str, Any]] = []
        for product in products:
            product_id = product.get("_id")
            product_key = str(product_id)
            product_variants = variants_by_product.get(product_key, [])
            variants_with_inventory = attach_inventory_from_map(product_variants, inventory_by_variant_id)
            product_images = images_by_product.get(product_key, [])[:12]
            category = category_by_id.get(str(product.get("category_id")))
            plant = plant_by_id.get(str(product.get("plant_id")))
            profile = profile_by_plant_id.get(str(product.get("plant_id"))) or profile_by_product_id.get(product_key)
            computed = compute_product_values(variants_with_inventory, product_images)

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
                "images": serialize_mongo(product_images),
                "computed": computed,
            }
            if product.get("vector_score") is not None:
                context["vector_score"] = product["vector_score"]
            contexts.append(context)
        return contexts

    def get_product_variants(self, product_id: str) -> list[dict[str, Any]]:
        variants = self._get_raw_variants(product_id)
        inventories = self._get_raw_inventories([variant.get("_id") for variant in variants])
        return serialize_mongo(attach_inventory(variants, inventories))

    def get_product_images(self, product_id: str) -> list[dict[str, Any]]:
        return serialize_mongo(self._get_raw_images(product_id, []))

    def search_products(self, filters: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
        query = self._plant_product_query(build_product_filter(filters))
        products = list(self.products.find(query).limit(max(limit * 20, 200)))
        contexts: list[dict[str, Any]] = []
        for context in self.get_products_full_contexts(products):
            if context_matches_filters(context, filters):
                contexts.append(context)
            if len(contexts) >= limit:
                break
        return contexts

    def get_products_by_ids(self, product_ids: list[str], limit: int = 10) -> list[dict[str, Any]]:
        if not product_ids:
            return []
        ids = expanded_object_values(product_ids)
        docs = list(self.products.find(self._plant_product_query({"_id": {"$in": ids}})).limit(limit))
        order = {str(product_id): index for index, product_id in enumerate(product_ids)}
        docs.sort(key=lambda doc: order.get(str(doc.get("_id")), 9999))
        return self.get_products_full_contexts(docs, limit=limit)

    def hydrate_product_contexts(self, products: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
        return self.get_products_full_contexts(products[:limit], limit=limit)

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
        products = self._get_raw_products([product_or_id])
        return products[0] if products else None

    def _get_raw_products(self, products_or_ids: list[dict[str, Any] | str]) -> list[dict[str, Any]]:
        raw_by_id: dict[str, dict[str, Any]] = {}
        requested: list[dict[str, Any] | str] = []
        ids_to_fetch: list[Any] = []

        for item in products_or_ids:
            requested.append(item)
            if isinstance(item, dict):
                product_id = item.get("_id")
                if product_id is None:
                    continue
                if item.get("name") and item.get("plant_id") is not None:
                    raw_by_id[str(product_id)] = dict(item)
                else:
                    ids_to_fetch.append(product_id)
            else:
                ids_to_fetch.append(item)

        if ids_to_fetch:
            for raw in self.products.find({"_id": {"$in": expanded_object_values(ids_to_fetch)}}):
                raw_by_id[str(raw.get("_id"))] = raw

        result: list[dict[str, Any]] = []
        for item in requested:
            if isinstance(item, dict):
                product_id = item.get("_id")
                raw = raw_by_id.get(str(product_id)) if product_id is not None else item
                if raw:
                    raw = dict(raw)
                    if item.get("vector_score") is not None:
                        raw["vector_score"] = item["vector_score"]
                    result.append(raw)
            else:
                raw = raw_by_id.get(str(item))
                if raw:
                    result.append(raw)
        return result

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
        profiles = self._get_raw_profiles_for_batch(object_id_or_string_values(plant_id), object_id_or_string_values(product_id))
        return profiles[0] if profiles else None

    def _get_raw_profiles_for_batch(self, plant_values: list[Any], product_values: list[Any]) -> list[dict[str, Any]]:
        clauses = []
        if plant_values:
            clauses.append({"plant_id": {"$in": plant_values}})
        if product_values:
            clauses.append({"primary_product_id": {"$in": product_values}})
            clauses.append({"product_ids": {"$in": product_values}})
        if not clauses:
            return []
        return list(self.profiles.find({"$or": clauses}))

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


def expanded_object_values(values: Any) -> list[Any]:
    expanded: list[Any] = []
    for value in values or []:
        expanded.extend(object_id_or_string_values(value))
    return dedupe_values(expanded)


def dedupe_values(values: list[Any]) -> list[Any]:
    result = []
    seen = set()
    for value in values:
        marker = (type(value).__name__, str(value))
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


def group_by_field(docs: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for doc in docs:
        value = doc.get(field)
        if value is not None:
            grouped.setdefault(str(value), []).append(doc)
    return grouped


def first_by_id(docs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(doc.get("_id")): doc for doc in docs if doc.get("_id") is not None}


def index_profiles(profiles: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_plant_id: dict[str, dict[str, Any]] = {}
    by_product_id: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        if profile.get("plant_id") is not None:
            by_plant_id[str(profile.get("plant_id"))] = profile
        if profile.get("primary_product_id") is not None:
            by_product_id[str(profile.get("primary_product_id"))] = profile
        for product_id in profile.get("product_ids") or []:
            by_product_id[str(product_id)] = profile
    return by_plant_id, by_product_id


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
    return attach_inventory_from_map(variants, inventory_by_variant_id)


def attach_inventory_from_map(variants: list[dict[str, Any]], inventory_by_variant_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
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
