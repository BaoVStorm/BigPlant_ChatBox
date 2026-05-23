from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Intent = Literal["product_info", "recommendation", "plant_care", "cart_order", "general", "unclear"]


class IntentRoute(BaseModel):
    intent: Intent = "unclear"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    entities: dict[str, Any] = Field(default_factory=dict)
    source: str = "heuristic"
