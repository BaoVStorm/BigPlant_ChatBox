from __future__ import annotations

import json
from typing import Any

from app.embeddings.embedding_service import EmbeddingService
from app.llm.local_llm import LocalLLM
from app.llm.prompts import RECOMMENDATION_PROMPT
from app.products.product_handler import format_price_range
from app.products.product_repository import ProductRepository
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
                vector_products = self.repository.vector_search_products(query_vector, filters=filters, limit=8)
                products = merge_products(products, vector_products)
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

        prompt = RECOMMENDATION_PROMPT.format(
            message=message,
            filters_json=json.dumps(filters, ensure_ascii=False, default=str),
            products_json=json.dumps(products, ensure_ascii=False, default=str),
        )
        answer = None
        llm_used = False
        if self.llm.is_available:
            try:
                answer = self.llm.generate(prompt)
                llm_used = True
            except Exception:
                answer = None
        if not answer:
            answer = build_recommendation_answer(products, filters)

        return {
            "intent": "recommendation",
            "message": answer,
            "products": [build_recommendation_card(product) for product in products],
            "sources": [],
            "metadata": {"route": route.model_dump(), "filters": filters, "used_vector": used_vector, "llm_used": llm_used},
        }


def should_use_vector(message: str, filters: dict[str, Any]) -> bool:
    semantic_words = ["chill", "sang", "đẹp", "dep", "quà", "qua", "minimal", "hiện đại", "hien dai", "decor"]
    lowered = message.lower()
    return any(word in lowered for word in semantic_words) or not filters


def merge_products(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for product in primary + secondary:
        product_id = str(product.get("_id"))
        if product_id not in merged:
            merged[product_id] = product
        elif product.get("vector_score") is not None:
            merged[product_id]["vector_score"] = product["vector_score"]
    return list(merged.values())


def rank_products(products: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    def score(product: dict[str, Any]) -> float:
        total = float(product.get("vector_score") or 0.0)
        if filters.get("care_level") and product.get("care_level") == filters["care_level"]:
            total += 1.0
        if filters.get("watering_need") and product.get("watering_need") == filters["watering_need"]:
            total += 1.0
        if filters.get("light_requirement") and product.get("light_requirement") in {filters["light_requirement"], "indirect"}:
            total += 1.0
        if filters.get("placement") and filters["placement"] in (product.get("suitable_locations") or []):
            total += 1.0
        if filters.get("max_price") and product.get("price_min") and int(product["price_min"]) <= int(filters["max_price"]):
            total += 1.0
        return total

    return sorted(products, key=score, reverse=True)


def build_recommendation_answer(products: list[dict[str, Any]], filters: dict[str, Any]) -> str:
    lines = ["Mình gợi ý một vài cây phù hợp nhất trong dữ liệu hiện tại:"]
    for index, product in enumerate(products[:3], start=1):
        name = product.get("name") or "Sản phẩm"
        price = format_price_range(product)
        reason = build_reason(product, filters)
        lines.append(f"{index}. {name}: {price}. {reason}")
    lines.append("Bạn muốn mình lọc thêm theo ngân sách, vị trí đặt cây hoặc mức dễ chăm không?")
    return "\n".join(lines)


def build_reason(product: dict[str, Any], filters: dict[str, Any]) -> str:
    reasons = []
    if product.get("care_level") == "easy":
        reasons.append("dễ chăm")
    if product.get("watering_need") == "low":
        reasons.append("không cần tưới nhiều")
    if product.get("light_requirement") in {"low", "indirect"}:
        reasons.append("hợp môi trường ít nắng/ánh sáng gián tiếp")
    if filters.get("placement") and filters["placement"] in (product.get("suitable_locations") or []):
        reasons.append("hợp vị trí bạn muốn đặt")
    return "Phù hợp vì " + ", ".join(reasons) + "." if reasons else "Phù hợp với nhu cầu mô tả của bạn."


def build_recommendation_card(product: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": product.get("_id"),
        "name": product.get("name"),
        "slug": product.get("slug"),
        "price": format_price_range(product),
        "price_min": product.get("price_min"),
        "price_max": product.get("price_max"),
        "care_level": product.get("care_level"),
        "light_requirement": product.get("light_requirement"),
        "watering_need": product.get("watering_need"),
        "vector_score": product.get("vector_score"),
    }
