from __future__ import annotations

from typing import Any
import re

from app.chat.facets import classify_facet
from app.plant_detect.schemas import ImagePlantContext
from app.router.schemas import IntentRoute
from app.router.text_utils import contains_any_phrase, normalize_text


RECOMMENDATION_REFINEMENT_SIGNALS = [
    "re hon",
    "co loai nao re hon",
    "co loai nao khac",
    "co cay nao khac",
    "an toan voi meo",
    "an toan voi cho",
    "thu cung",
    "de cham hon",
    "it nang hon",
    "de ban hon",
    "loc them",
]


def apply_contextual_policy(
    route: IntentRoute,
    message: str,
    entities: dict[str, Any],
    memory: dict[str, Any],
    image_context: ImagePlantContext | None,
) -> IntentRoute:
    normalized = normalize_text(message or "")
    active_subject = memory.get("active_subject") or {}
    last_intent = memory.get("last_intent")

    if should_force_product_info_from_image(message, image_context):
        return IntentRoute(intent="product_info", confidence=0.8, entities=entities, source="image_context_fallback")

    if should_force_product_info_from_active_subject(route, normalized, entities, active_subject):
        entities["product_name"] = active_subject.get("product_name")
        entities["context_subject"] = True
        return IntentRoute(intent="product_info", confidence=0.68, entities=entities, source="session_context_fallback")

    if should_force_recommendation_from_memory(route, normalized, entities, memory, last_intent):
        entities["recommendation_context"] = True
        return IntentRoute(intent="recommendation", confidence=0.67, entities=entities, source="session_context_fallback")

    return route


def should_force_product_info_from_image(message: str, image_context: ImagePlantContext | None) -> bool:
    return bool(image_context and image_context.resolved_product_context and not (message or "").strip())


def should_force_product_info_from_active_subject(route: IntentRoute, normalized: str, entities: dict[str, Any], active_subject: dict[str, Any]) -> bool:
    if not active_subject or active_subject.get("subject_type") != "product":
        return False

    if route.intent == "product_info":
        return False

    product_facet = classify_facet("product_info", normalized, entities)
    return product_facet.name in {"price", "stock", "variant", "image", "toxicity", "highlights", "overview"} and len(normalized.split()) <= 10


def should_force_recommendation_from_memory(
    route: IntentRoute,
    normalized: str,
    entities: dict[str, Any],
    memory: dict[str, Any],
    last_intent: str | None,
) -> bool:
    if last_intent != "recommendation":
        return False
    if route.intent == "recommendation":
        return False
    if not (memory.get("preferences") or memory.get("last_recommendations")):
        return False
    if entities.get("product_name"):
        return False
    return contains_any_phrase(normalized, RECOMMENDATION_REFINEMENT_SIGNALS) or len(normalized.split()) <= 6


def enrich_recommendation_refinement_entities(entities: dict[str, Any], memory: dict[str, Any], normalized: str) -> dict[str, Any]:
    enriched = dict(entities)
    recommendations = memory.get("last_recommendations") or []
    if not recommendations:
        return enriched

    top = recommendations[0]
    reference_price = parse_price_text(top.get("price"))
    if contains_any_phrase(normalized, ["re hon", "loai nao re hon"]):
        enriched["recommendation_refinement"] = "cheaper_than_previous"
        enriched["reference_price_max"] = reference_price
        enriched["reference_product_id"] = top.get("product_id")
    return enriched


def parse_price_text(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None
