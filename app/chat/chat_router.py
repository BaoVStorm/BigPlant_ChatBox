from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.chat.chat_service import ChatService
from app.chat.schemas import ChatMessageRequest, ChatMessageResponse


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
def chat_message(payload: ChatMessageRequest) -> ChatMessageResponse:
    try:
        service = ChatService()
        result = service.handle_message(payload.message, user_id=payload.user_id, session_id=payload.session_id)
        return ChatMessageResponse(**result)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
