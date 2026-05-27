from __future__ import annotations

from typing import Any

from app.embeddings.embedding_service import EmbeddingService
from app.llm.local_llm import LocalLLM
from app.products.product_repository import ProductRepository, context_matches_filters
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

        products = self.repository.search_products(filters, limit=8)
        used_vector = False
        if len(products) < 3 or should_use_vector(message, filters):
            try:
                query_vector = self.embeddings.embed_text(message)
                vector_products = self.repository.vector_search_products(query_vector, filters=filters, limit=10)
                vector_contexts = self.repository.hydrate_product_contexts(vector_products, limit=10)
                vector_contexts = [context for context in vector_contexts if context_matches_filters(context, filters)]
                products = merge_products(products, vector_contexts)
                used_vector = True
            except Exception as exc:
                route.entities["vector_error"] = str(exc)

        products = rank_products(products, filters)[:3]
        if not products:
            return {
                "intent": "recommendation",
                "message": "Mình chưa tìm thấy cây phù hợp với điều kiện này trong dữ liệu hiện tại. Bạn có thể nới ngân sách hoặc mô tả thêm vị trí đặt cây không?",
                "products": [],
                "sources": [],
                "metadata": {"route": route.model_dump(), "filters": filters, "used_vector": used_vector},
            }

        product_cards = [build_recommendation_card(product, filters) for product in products]
        answer = build_recommendation_answer(products, filters)
        llm_used = False

        return {
            "intent": "recommendation",
            "message": answer,
            "products": product_cards,
            "sources": [],
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
    unsupported_hard_filters = {"watering_need", "light_requirement", "placement", "pet_safe"}
    lowered = message.lower()
    return any(word in lowered for word in semantic_words) or bool(unsupported_hard_filters & set(filters)) or not filters


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
        total = float(context.get("vector_score") or 0.0)
        if computed.get("in_stock"):
            total += 1.0
        if filters.get("care_level") and normalize_text(product.get("care_level")) == normalize_text(filters["care_level"]):
            total += 1.3
        if filters.get("max_price") and computed.get("price_min") is not None and float(computed["price_min"]) <= float(filters["max_price"]):
            total += 1.2
        if filters.get("recommendation_refinement") == "cheaper_than_previous" and computed.get("price_min") is not None:
            total += max(0.0, 1.5 - float(computed["price_min"]) / 20)
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
    lines.append("Bạn muốn mình lọc thêm theo ngân sách, mức dễ chăm hoặc tình trạng còn hàng không?")
    return "\n".join(lines)


def build_reason(context: dict[str, Any], filters: dict[str, Any]) -> str:
    product = context.get("product") or {}
    computed = context.get("computed") or {}
    plant = context.get("plant") or {}
    reasons = []
    if product.get("care_level") == "easy":
        reasons.append("dễ chăm")
    if computed.get("in_stock"):
        reasons.append("đang có hàng")
    if filters.get("max_price") and computed.get("price_min") is not None:
        reasons.append("phù hợp ngân sách")
    if plant.get("advantages"):
        reasons.append("có mô tả/ưu điểm cây trong dữ liệu")
    if context.get("vector_score") is not None:
        reasons.append("phù hợp với nhu cầu mô tả theo tìm kiếm ngữ nghĩa")
    return "Phù hợp vì " + ", ".join(reasons) + "." if reasons else "Phù hợp với nhu cầu mô tả của bạn."


def build_recommendation_card(context: dict[str, Any], filters: dict[str, Any]) -> dict[str, Any]:
    product = context.get("product") or {}
    category = context.get("category") or {}
    plant = context.get("plant") or {}
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
        "price": computed.get("price_text"),
        "price_min": computed.get("price_min"),
        "price_max": computed.get("price_max"),
        "available_qty": computed.get("available_qty"),
        "in_stock": computed.get("in_stock"),
        "primary_image_url": computed.get("primary_image_url"),
        "vector_score": context.get("vector_score"),
        "reason": build_reason(context, filters),
    }


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()
