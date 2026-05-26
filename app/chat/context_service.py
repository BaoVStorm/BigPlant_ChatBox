from __future__ import annotations

import uuid
from typing import Any

from app.chat.context_repository import ChatContextRepository
from app.plant_detect.schemas import ImagePlantContext


class ChatContextService:
    def __init__(self, repository: ChatContextRepository | None = None) -> None:
        self.repository = repository or ChatContextRepository()

    def ensure_session(self, user_id: str | None, session_id: str | None) -> dict[str, Any]:
        resolved_session_id = session_id or f"session_{uuid.uuid4().hex}"
        session = self.repository.ensure_session(resolved_session_id, user_id)
        session.setdefault("memory", {})
        return session

    def load_memory(self, session: dict[str, Any]) -> dict[str, Any]:
        return dict(session.get("memory") or {})

    def persist_turn(
        self,
        session_id: str,
        user_id: str | None,
        user_message: str,
        assistant_result: dict[str, Any],
        image_context: ImagePlantContext | None = None,
    ) -> None:
        self.repository.append_message(
            session_id,
            user_id,
            "user",
            user_message,
            extra={
                "image_detection": image_context.model_dump() if image_context else None,
            },
        )
        self.repository.append_message(
            session_id,
            user_id,
            "assistant",
            assistant_result.get("message") or "",
            extra={
                "intent": assistant_result.get("intent"),
                "products": assistant_result.get("products") or [],
                "follow_up_message": assistant_result.get("follow_up_message"),
                "suggested_questions": assistant_result.get("suggested_questions") or [],
            },
        )

        updates = {
            "last_user_message": user_message,
            "last_assistant_message": assistant_result.get("message"),
            "last_intent": assistant_result.get("intent"),
        }

        active_subject = determine_active_subject(assistant_result, image_context)
        if active_subject:
            updates["active_subject"] = active_subject

        if image_context:
            updates["last_image_detection"] = image_context.model_dump()

        self.repository.update_session_memory(session_id, updates)


def determine_active_subject(assistant_result: dict[str, Any], image_context: ImagePlantContext | None) -> dict[str, Any] | None:
    if image_context and image_context.resolved_product_context:
        context = image_context.resolved_product_context
        product = context.get("product") or {}
        plant = context.get("plant") or {}
        return {
            "subject_type": "product",
            "product_id": product.get("_id"),
            "product_name": product.get("name"),
            "plant_id": plant.get("_id"),
            "plant_scientific_name": plant.get("scientific_name"),
            "source": "image_detection",
        }

    products = assistant_result.get("products") or []
    if products:
        first = products[0]
        plant = first.get("plant") or {}
        return {
            "subject_type": "product",
            "product_id": first.get("id"),
            "product_name": first.get("name"),
            "plant_id": plant.get("_id"),
            "plant_scientific_name": plant.get("scientific_name"),
            "source": assistant_result.get("intent"),
        }
    return None
