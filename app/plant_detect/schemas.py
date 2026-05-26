from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatImageInput(BaseModel):
    data_url: str | None = None
    base64: str | None = None
    url: str | None = None
    filename: str | None = None
    content_type: str | None = None
    mock_label: str | None = None


class PlantDetectionResult(BaseModel):
    success: bool = True
    source: str
    label: str | None = None
    scientific_name_search: str | None = None
    plant: dict[str, Any] | None = None
    detect_result: dict[str, Any] | None = None
    confidence: float | None = None
    error: str | None = None


class ImagePlantContext(BaseModel):
    image_provided: bool = True
    detection: PlantDetectionResult
    resolved_product: dict[str, Any] | None = None
    resolved_product_context: dict[str, Any] | None = None

    @property
    def resolved_name(self) -> str | None:
        if self.resolved_product:
            return str(self.resolved_product.get("name") or "") or None
        if self.detection.plant:
            return str(
                self.detection.plant.get("scientific_name")
                or self.detection.plant.get("common_name")
                or self.detection.label
                or ""
            ) or None
        return self.detection.label
