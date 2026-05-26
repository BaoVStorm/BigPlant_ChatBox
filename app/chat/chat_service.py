from __future__ import annotations

from time import perf_counter
from typing import Any

from app.chat.context_service import ChatContextService
from app.chat.follow_up import build_follow_up
from app.knowledge.rag_handler import PlantCareRagHandler
from app.llm.local_llm import LocalLLM
from app.llm.prompts import GENERAL_PROMPT
from app.plant_detect.schemas import ChatImageInput, ImagePlantContext
from app.plant_detect.service import PlantDetectService
from app.products.product_handler import ProductInfoHandler
from app.products.product_repository import ProductRepository
from app.recommendations.recommendation_handler import RecommendationHandler
from app.router.intent_router import IntentRouter, normalize_text
from app.router.schemas import IntentRoute


class ChatService:
    def __init__(self) -> None:
        self.llm = LocalLLM()
        self.router = IntentRouter(self.llm)
        self.product_repository = ProductRepository()
        self.context_service = ChatContextService()
        self.plant_detect_service = PlantDetectService(repository=self.product_repository)
        self.product_handler = ProductInfoHandler(self.product_repository, self.llm)
        self.recommendation_handler = RecommendationHandler(repository=self.product_repository, llm=self.llm)
        self.rag_handler = PlantCareRagHandler(llm=self.llm)

    def handle_message(
        self,
        message: str,
        user_id: str | None = None,
        session_id: str | None = None,
        image: ChatImageInput | None = None,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        session = self.context_service.ensure_session(user_id, session_id)
        resolved_session_id = str(session.get("_id"))
        memory = self.context_service.load_memory(session)
        image_context = self._resolve_image_context(image)

        route_started_at = perf_counter()
        route = self.router.classify(message)
        route = self._augment_route_with_context(route, image_context, memory, message)
        route_ms = elapsed_ms(route_started_at)

        handler_started_at = perf_counter()
        if route.intent == "product_info":
            result = self.product_handler.handle(message, route, image_context=image_context, memory=memory)
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
        follow_up_message, suggested_questions = build_follow_up(result.get("intent", route.intent), result, memory)
        result["follow_up_message"] = follow_up_message
        result["suggested_questions"] = suggested_questions
        result["session_id"] = resolved_session_id
        result.setdefault("metadata", {})["user_id"] = user_id
        result["metadata"]["session_id"] = resolved_session_id
        if image_context:
            result["metadata"]["image_detection"] = image_context.model_dump()
        result["metadata"]["timing_ms"] = {
            "route": route_ms,
            "handler": handler_ms,
            "total": elapsed_ms(started_at),
        }
        self.context_service.persist_turn(resolved_session_id, user_id, message, result, image_context=image_context)
        return result

    def _resolve_image_context(self, image: ChatImageInput | None) -> ImagePlantContext | None:
        if not image:
            return None
        return self.plant_detect_service.resolve_image_context(image)

    def _augment_route_with_context(
        self,
        route: IntentRoute,
        image_context: ImagePlantContext | None,
        memory: dict[str, Any],
        message: str,
    ) -> IntentRoute:
        entities = dict(route.entities)

        if memory and not entities.get("product_name"):
            active_subject = memory.get("active_subject") or {}
            if active_subject.get("subject_type") == "product" and route.intent in {"product_info", "plant_care", "unclear"}:
                entities["product_name"] = active_subject.get("product_name")
                entities["context_subject"] = True

            if active_subject.get("subject_type") == "product" and route.intent == "general" and should_reinterpret_general_as_image_product_info(message):
                entities["product_name"] = active_subject.get("product_name")
                entities["context_subject"] = True
                return IntentRoute(intent="product_info", confidence=0.64, entities=entities, source="session_context_fallback")

        if not image_context:
            route.entities = entities
            return route

        if image_context.resolved_name and not entities.get("product_name"):
            entities["product_name"] = image_context.resolved_name
        entities["image_provided"] = True
        if image_context.detection.label:
            entities["detected_label"] = image_context.detection.label
        if image_context.detection.confidence is not None:
            entities["detected_confidence"] = image_context.detection.confidence

        if not (message or "").strip() and image_context.resolved_product_context:
            return IntentRoute(intent="product_info", confidence=0.8, entities=entities, source="image_context_fallback")

        if route.intent == "unclear" and image_context.resolved_product_context:
            return IntentRoute(intent="product_info", confidence=0.7, entities=entities, source="image_context_fallback")

        if route.intent == "general" and image_context.resolved_product_context and should_reinterpret_general_as_image_product_info(message):
            return IntentRoute(intent="product_info", confidence=0.66, entities=entities, source="image_context_fallback")

        route.entities = entities
        return route

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


def should_reinterpret_general_as_image_product_info(message: str) -> bool:
    normalized = normalize_text(message)
    if should_use_deterministic_general(message):
        return False
    image_anaphora = ["cay nay", "san pham nay", "nay sao", "nay co", "nay bao nhieu", "nay con"]
    return any(phrase in normalized for phrase in image_anaphora) or len(normalized.split()) <= 5
