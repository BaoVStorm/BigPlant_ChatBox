from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.plant_detect.schemas import ChatImageInput


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    user_id: str | None = None
    session_id: str | None = None
    image: ChatImageInput | None = None


class ChatMessageResponse(BaseModel):
    intent: str
    message: str
    products: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
