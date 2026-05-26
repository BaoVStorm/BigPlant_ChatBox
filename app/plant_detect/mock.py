from __future__ import annotations

from app.plant_detect.schemas import PlantDetectionResult


def build_mock_detection_result(label: str | None = None) -> PlantDetectionResult:
    mock_label = normalize_label(label or "aloe_vera")
    return PlantDetectionResult(
        success=True,
        source="mock",
        label=mock_label,
        scientific_name_search=mock_label,
        plant={
            "_id": None,
            "scientific_name_search": mock_label,
            "scientific_name": mock_label.replace("_", " ").title(),
            "common_name": mock_label.replace("_", " ").title(),
        },
        detect_result={"pred": {"label": mock_label, "confidence": 0.99}},
        confidence=0.99,
    )


def normalize_label(value: str) -> str:
    return "_".join(str(value or "").strip().lower().split())
