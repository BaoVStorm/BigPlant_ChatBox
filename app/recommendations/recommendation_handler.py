from __future__ import annotations

import json
from typing import Any

from app.embeddings.embedding_service import EmbeddingService
from app.llm.local_llm import LocalLLM
from app.llm.prompts import RECOMMENDATION_PROMPT
from app.products.product_repository import ProductRepository, care_level_matches, context_matches_filters
from app.router.schemas import IntentRoute


class RecommendationHandler:
    def __init__(
        self,
        repository: ProductRepository | None = None,
        embeddings: EmbeddingService | None = None,
        llm: LocalLLM | None = None,
    ) -> None:
        self.repository = repository or ProductRepository()
        self.embeddings = embeddings or EmbeddingService()
        self.llm = llm or LocalLLM()

    def handle(self, message: str, route: IntentRoute) -> dict[str, Any]:
        filters = dict(route.entities)
        filters.pop("product_name", None)

        products = self.repository.search_products(filters, limit=12)
        used_vector = False
        if len(products) < 3 or should_use_vector(message, filters):
            try:
                query_vector = self.embeddings.embed_text(message)
                vector_products = self.repository.vector_search_products(query_vector, filters=filters, limit=12)
                vector_contexts = self.repository.hydrate_product_contexts(vector_products, limit=12)
                vector_contexts = [context for context in vector_contexts if context_matches_filters(context, filters)]
                products = merge_products(products, vector_contexts)
                used_vector = True
            except Exception as exc:
                route.entities["vector_error"] = str(exc)

        products = rank_products(products, filters)[:3]
        if not products:
            return {
                "intent": "recommendation",
                "message": "Mình chưa tìm thấy cây phù hợp với điều kiện này trong dữ liệu hiện tại. Bạn có thể nới ngân sách, bỏ bớt điều kiện thú cưng/ánh sáng, hoặc mô tả thêm vị trí đặt cây không?",
                "products": [],
                "sources": [],
                "metadata": {"route": route.model_dump(), "filters": filters, "used_vector": used_vector},
            }

        product_cards = [build_recommendation_card(product, filters) for product in products]
        fallback_answer = build_recommendation_answer(products, filters)
        answer, llm_used = compose_recommendation_answer(self.llm, message, products, product_cards, filters, fallback_answer)

        return {
            "intent": "recommendation",
            "message": answer,
            "products": product_cards,
            "sources": build_recommendation_sources(products),
            "metadata": {"route": route.model_dump(), "filters": filters, "used_vector": used_vector, "llm_used": llm_used},
        }


def should_use_vector(message: str, filters: dict[str, Any]) -> bool:
    semantic_words = [
        "chill",
        "sang",
        "đẹp",
        "dep",
        "quà",
        "qua",
        "minimal",
        "hiện đại",
        "hien dai",
        "decor",
        "ít nắng",
        "it nang",
        "thiếu sáng",
        "thieu sang",
        "để bàn",
        "de ban",
        "phòng ngủ",
        "phong ngu",
        "phòng khách",
        "phong khach",
        "hay quên tưới",
        "quen tuoi",
    ]
    lowered = message.lower()
    return any(word in lowered for word in semantic_words) or not filters


def merge_products(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for product in primary + secondary:
        product_id = str(product.get("_id") or (product.get("product") or {}).get("_id"))
        if product_id not in merged:
            merged[product_id] = product
        elif product.get("vector_score") is not None:
            merged[product_id]["vector_score"] = product["vector_score"]
    return list(merged.values())


def rank_products(products: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    def score(context: dict[str, Any]) -> float:
        product = context.get("product") or {}
        computed = context.get("computed") or {}
        profile = context.get("plant_profile") or {}
        care_profile = profile.get("care_profile") or {}
        safety_profile = profile.get("safety_profile") or {}
        recommendation_profile = profile.get("recommendation_profile") or {}
        total = float(context.get("vector_score") or 0.0)
        if computed.get("in_stock"):
            total += 1.0
        if filters.get("care_level") and care_level_matches(product.get("care_level") or care_profile.get("care_level"), filters["care_level"]):
            total += 1.4
        if filters.get("watering_need") and normalize_text(care_profile.get("watering_need")) == normalize_text(filters["watering_need"]):
            total += 1.1
        if filters.get("light_requirement") and light_rank_match(care_profile.get("light_requirement"), filters.get("light_requirement")):
            total += 1.1
        if filters.get("placement") and placement_rank_match(care_profile.get("placement_tags"), filters.get("placement")):
            total += 1.0
        if filters.get("pet_safe") is True and safety_profile.get("pet_safe") is True:
            total += 1.4
        if filters.get("max_price") and computed.get("price_min") is not None and float(computed["price_min"]) <= float(filters["max_price"]):
            total += 1.2
        if filters.get("recommendation_refinement") == "cheaper_than_previous" and computed.get("price_min") is not None:
            total += max(0.0, 1.5 - float(computed["price_min"]) / 20)
        if recommendation_profile.get("good_if"):
            total += min(len(recommendation_profile.get("good_if") or []), 3) * 0.2
        if product.get("rating_avg"):
            total += min(float(product.get("rating_avg") or 0), 5.0) / 10
        return total

    return sorted(products, key=score, reverse=True)


def build_recommendation_answer(products: list[dict[str, Any]], filters: dict[str, Any]) -> str:
    lines = ["Mình gợi ý một vài cây phù hợp nhất trong dữ liệu hiện tại:"]
    for index, context in enumerate(products[:3], start=1):
        product = context.get("product") or {}
        computed = context.get("computed") or {}
        name = product.get("name") or "Sản phẩm"
        price = computed.get("price_text") or "chưa có dữ liệu giá"
        reason = build_reason(context, filters)
        lines.append(f"{index}. {name}: {price}. {reason}")
    lines.append("Bạn muốn mình lọc thêm theo ngân sách, ánh sáng, mức tưới hoặc độ an toàn với thú cưng không?")
    return "\n".join(lines)


def compose_recommendation_answer(
    llm: LocalLLM,
    message: str,
    products: list[dict[str, Any]],
    product_cards: list[dict[str, Any]],
    filters: dict[str, Any],
    fallback_answer: str,
) -> tuple[str, bool]:
    if not llm.is_available:
        return fallback_answer, False
    try:
        prompt = RECOMMENDATION_PROMPT.format(
            message=message,
            filters_json=json.dumps(filters, ensure_ascii=False, default=str),
            products_json=json.dumps([compact_recommendation_context(item, card) for item, card in zip(products, product_cards)], ensure_ascii=False, default=str),
        )
        answer = sanitize_llm_answer(llm.generate(prompt, max_tokens=420))
        return answer or fallback_answer, bool(answer)
    except Exception:
        return fallback_answer, False


def compact_recommendation_context(context: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    profile = context.get("plant_profile") or {}
    plant = context.get("plant") or {}
    return {
        "card": card,
        "plant": {
            "scientific_name": plant.get("scientific_name"),
            "common_name": plant.get("common_name"),
            "advantages": plant.get("advantages"),
            "toxicity_warning": plant.get("toxicity_warning"),
            "safety_notes": plant.get("safety_notes"),
        },
        "care_profile": profile.get("care_profile"),
        "safety_profile": profile.get("safety_profile"),
        "recommendation_profile": profile.get("recommendation_profile"),
    }


def build_reason(context: dict[str, Any], filters: dict[str, Any]) -> str:
    product = context.get("product") or {}
    computed = context.get("computed") or {}
    plant = context.get("plant") or {}
    profile = context.get("plant_profile") or {}
    care_profile = profile.get("care_profile") or {}
    safety_profile = profile.get("safety_profile") or {}
    reasons = []
    if normalize_text(product.get("care_level") or care_profile.get("care_level")) == "easy":
        reasons.append("dễ chăm")
    if computed.get("in_stock"):
        reasons.append("đang có hàng")
    if filters.get("max_price") and computed.get("price_min") is not None:
        reasons.append("phù hợp ngân sách")
    if filters.get("watering_need") and normalize_text(care_profile.get("watering_need")) == normalize_text(filters.get("watering_need")):
        reasons.append(f"nhu cầu tưới {care_profile.get('watering_need')}")
    if filters.get("light_requirement") and light_rank_match(care_profile.get("light_requirement"), filters.get("light_requirement")):
        reasons.append(f"hợp điều kiện ánh sáng {care_profile.get('light_requirement')}")
    if filters.get("placement") and placement_rank_match(care_profile.get("placement_tags"), filters.get("placement")):
        reasons.append("phù hợp vị trí đặt cây")
    if filters.get("pet_safe") and safety_profile.get("pet_safe") is True:
        reasons.append("an toàn hơn cho thú cưng theo hồ sơ hiện có")
    if plant.get("advantages"):
        reasons.append("có ưu điểm cây trong dữ liệu nền")
    if context.get("vector_score") is not None:
        reasons.append("khớp ngữ nghĩa với nhu cầu mô tả")
    return "Phù hợp vì " + ", ".join(reasons) + "." if reasons else "Phù hợp với nhu cầu mô tả của bạn."


def build_recommendation_card(context: dict[str, Any], filters: dict[str, Any]) -> dict[str, Any]:
    product = context.get("product") or {}
    category = context.get("category") or {}
    plant = context.get("plant") or {}
    profile = context.get("plant_profile") or {}
    computed = context.get("computed") or {}
    return {
        "id": product.get("_id"),
        "name": product.get("name"),
        "slug": product.get("slug"),
        "short_description": product.get("short_description"),
        "care_level": product.get("care_level"),
        "category_name": category.get("name") if category else None,
        "plant_common_name": plant.get("common_name") if plant else None,
        "plant_scientific_name": plant.get("scientific_name") if plant else None,
        "care_profile": profile.get("care_profile") if profile else None,
        "safety_profile": profile.get("safety_profile") if profile else None,
        "recommendation_profile": profile.get("recommendation_profile") if profile else None,
        "price": computed.get("price_text"),
        "price_min": computed.get("price_min"),
        "price_max": computed.get("price_max"),
        "available_qty": computed.get("available_qty"),
        "in_stock": computed.get("in_stock"),
        "primary_image_url": computed.get("primary_image_url"),
        "vector_score": context.get("vector_score"),
        "reason": build_reason(context, filters),
    }


def build_recommendation_sources(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources = []
    for context in products:
        profile = context.get("plant_profile") or {}
        plant = context.get("plant") or {}
        if profile:
            sources.append(
                {
                    "title": profile.get("scientific_name") or plant.get("scientific_name"),
                    "source_type": "plant_profile",
                    "profile_id": profile.get("_id"),
                    "plant_id": profile.get("plant_id"),
                    "confidence": (profile.get("data_quality") or {}).get("confidence"),
                }
            )
    return sources


def light_rank_match(actual: Any, expected: Any) -> bool:
    actual_text = normalize_text(actual)
    expected_text = normalize_text(expected)
    if expected_text == "low":
        return actual_text in {"low_to_indirect", "low", "partial_shade"}
    if expected_text == "indirect":
        return actual_text in {"low_to_indirect", "bright_indirect", "partial_shade"}
    return actual_text == expected_text


def placement_rank_match(actual: Any, expected: Any) -> bool:
    if not isinstance(actual, list):
        return False
    tags = {normalize_text(item) for item in actual}
    expected_text = normalize_text(expected)
    aliases = {
        "desk": {"desk", "office", "living_room"},
        "office": {"office", "desk", "living_room"},
        "bedroom": {"bedroom", "living_room", "office"},
        "living_room": {"living_room", "office", "balcony"},
        "balcony": {"balcony", "outdoor_garden"},
        "outdoor": {"outdoor_garden", "balcony", "water_edge"},
    }
    return bool(tags & aliases.get(expected_text, {expected_text}))


def sanitize_llm_answer(answer: str | None) -> str | None:
    text = str(answer or "").strip()
    if not text:
        return None
    for marker in ["User:", "Người dùng:", "Assistant:"]:
        if marker in text:
            text = text.split(marker, 1)[0].strip()
    return text or None


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()
