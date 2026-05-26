from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException

from app.chat.chat_service import ChatService
from app.chat.schemas import ChatMessageRequest, ChatMessageResponse


router = APIRouter(prefix="/chat", tags=["chat"])


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    return ChatService()


@router.post("/message", response_model=ChatMessageResponse)
def chat_message(payload: ChatMessageRequest) -> ChatMessageResponse:
    try:
        service = get_chat_service()
        result = service.handle_message(payload.message, user_id=payload.user_id, session_id=payload.session_id, image=payload.image)
        return ChatMessageResponse(**result)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
