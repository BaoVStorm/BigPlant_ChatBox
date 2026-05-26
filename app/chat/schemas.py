from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.plant_detect.schemas import ChatImageInput


class ChatMessageRequest(BaseModel):
    message: str = Field(default="")
    user_id: str | None = None
    session_id: str | None = None
    image: ChatImageInput | None = None

    @model_validator(mode="after")
    def validate_message_or_image(self) -> "ChatMessageRequest":
        if not (self.message and self.message.strip()) and self.image is None:
            raise ValueError("Either message or image must be provided.")
        return self


class ChatMessageResponse(BaseModel):
    intent: str
    message: str
    session_id: str | None = None
    products: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    follow_up_message: str | None = None
    suggested_questions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
