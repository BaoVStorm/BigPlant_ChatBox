from __future__ import annotations

from time import perf_counter
from typing import Any

from app.knowledge.rag_handler import PlantCareRagHandler
from app.llm.local_llm import LocalLLM
from app.llm.prompts import GENERAL_PROMPT
from app.products.product_handler import ProductInfoHandler
from app.products.product_repository import ProductRepository
from app.recommendations.recommendation_handler import RecommendationHandler
from app.router.intent_router import IntentRouter, normalize_text


class ChatService:
    def __init__(self) -> None:
        self.llm = LocalLLM()
        self.router = IntentRouter(self.llm)
        self.product_repository = ProductRepository()
        self.product_handler = ProductInfoHandler(self.product_repository, self.llm)
        self.recommendation_handler = RecommendationHandler(repository=self.product_repository, llm=self.llm)
        self.rag_handler = PlantCareRagHandler(llm=self.llm)

    def handle_message(self, message: str, user_id: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        started_at = perf_counter()
        route_started_at = perf_counter()
        route = self.router.classify(message)
        route_ms = elapsed_ms(route_started_at)

        handler_started_at = perf_counter()
        if route.intent == "product_info":
            result = self.product_handler.handle(message, route)
        elif route.intent == "recommendation":
            result = self.recommendation_handler.handle(message, route)
        elif route.intent == "plant_care":
            result = self.rag_handler.handle(message, route)
        elif route.intent == "cart_order":
            result = self._handle_cart_order(route)
        elif route.intent == "general":
            result = self._handle_general(message, route)
        else:
            result = {
                "intent": "unclear",
                "message": "Bạn muốn hỏi thông tin cây cụ thể, nhờ mình tư vấn chọn cây, hay hỏi cách chăm cây?",
                "products": [],
                "sources": [],
                "metadata": {"route": route.model_dump()},
            }

        handler_ms = elapsed_ms(handler_started_at)
        result.setdefault("metadata", {})["user_id"] = user_id
        result["metadata"]["session_id"] = session_id
        result["metadata"]["timing_ms"] = {
            "route": route_ms,
            "handler": handler_ms,
            "total": elapsed_ms(started_at),
        }
        return result

    def _handle_cart_order(self, route) -> dict[str, Any]:
        return {
            "intent": "cart_order",
            "message": "Mình đã hiểu bạn muốn thao tác giỏ hàng/đặt hàng. Phần này nên nối với Cart API riêng để đảm bảo đúng sản phẩm, số lượng và giá hiện tại.",
            "products": [],
            "sources": [],
            "metadata": {"route": route.model_dump(), "status": "cart_api_not_connected"},
        }

    def _handle_general(self, message: str, route) -> dict[str, Any]:
        if should_use_deterministic_general(message):
            return {
                "intent": "general",
                "message": "Xin chào! Mình có thể giúp bạn tìm cây phù hợp, kiểm tra giá và tồn kho, hoặc trả lời câu hỏi chăm cây của BigPlant.",
                "products": [],
                "sources": [],
                "metadata": {"route": route.model_dump(), "llm_available": self.llm.is_available, "llm_used": False},
            }

        answer = None
        if self.llm.is_available:
            try:
                answer = self.llm.generate(GENERAL_PROMPT.format(message=message), max_tokens=160)
            except Exception:
                answer = None
        if not answer:
            answer = "Chào bạn, mình có thể tư vấn chọn cây, kiểm tra giá/tồn kho sản phẩm, hoặc trả lời câu hỏi chăm cây dựa trên kho kiến thức của BigPlant."
        return {
            "intent": "general",
            "message": answer,
            "products": [],
            "sources": [],
            "metadata": {"route": route.model_dump(), "llm_available": self.llm.is_available, "llm_used": bool(answer and self.llm.is_available)},
        }


def elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def should_use_deterministic_general(message: str) -> bool:
    normalized = normalize_text(message)
    greeting_markers = ["xin chao", "hello", "hi", "alo", "cam on"]
    return any(marker in normalized for marker in greeting_markers) and len(normalized.split()) <= 8
