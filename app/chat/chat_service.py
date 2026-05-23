from __future__ import annotations

from typing import Any

from app.knowledge.rag_handler import PlantCareRagHandler
from app.llm.local_llm import LocalLLM
from app.llm.prompts import GENERAL_PROMPT
from app.products.product_handler import ProductInfoHandler
from app.products.product_repository import ProductRepository
from app.recommendations.recommendation_handler import RecommendationHandler
from app.router.intent_router import IntentRouter


class ChatService:
    def __init__(self) -> None:
        self.llm = LocalLLM()
        self.router = IntentRouter(self.llm)
        self.product_repository = ProductRepository()
        self.product_handler = ProductInfoHandler(self.product_repository, self.llm)
        self.recommendation_handler = RecommendationHandler(repository=self.product_repository, llm=self.llm)
        self.rag_handler = PlantCareRagHandler(llm=self.llm)

    def handle_message(self, message: str, user_id: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        route = self.router.classify(message)

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

        result.setdefault("metadata", {})["user_id"] = user_id
        result["metadata"]["session_id"] = session_id
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
            "metadata": {"route": route.model_dump(), "llm_available": self.llm.is_available},
        }
