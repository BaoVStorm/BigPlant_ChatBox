from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.plant_detect.schemas import ImagePlantContext
from app.router.text_utils import contains_any_phrase, normalize_text


@dataclass(frozen=True)
class FacetResult:
    name: str
    confidence: float
    source: str = "rule"


PRODUCT_INFO_FACET_SIGNALS = {
    "toxicity": ["co doc", "doc voi", "an toan voi meo", "an toan voi cho", "thu cung"],
    "stock": ["con hang", "het hang", "ton kho"],
    "price": ["gia", "bao nhieu tien", "bao nhieu"],
    "variant": ["size", "kich thuoc", "mau nao", "loai nao", "mau sac", "lua chon"],
    "image": ["hinh anh", "anh san pham", "xem anh", "xem hinh"],
    "highlights": ["dac diem", "noi bat", "dac biet", "uu diem", "cong dung", "mo ta", "la gi"],
    "overview": ["cay nay sao", "san pham nay sao", "cay nay the nao"],
}

RECOMMENDATION_FACET_SIGNALS = {
    "budget": ["duoi", "toi da", "khoang", "$", "usd", "vnd", "trieu", "k"],
    "beginner": ["de cham", "nguoi moi", "moi choi", "it cham"],
    "placement": ["de ban", "phong khach", "phong ngu", "van phong", "ban lam viec"],
    "light": ["it nang", "thieu sang", "anh sang gian tiep"],
    "watering": ["hay quen tuoi", "it tuoi", "ban ron"],
    "gift": ["lam qua", "tang sinh nhat", "qua tang"],
    "style": ["chill", "sang", "dep", "minimal", "hien dai", "decor"],
}

PLANT_CARE_FACET_SIGNALS = {
    "symptom": ["vang la", "ung re", "thoi re", "heo la", "dom la", "sau benh", "bi benh"],
    "watering_schedule": ["tuoi bao lau", "bao lau tuoi", "nen tuoi"],
    "light_care": ["nhieu anh sang", "it nang", "thieu sang", "anh sang gian tiep"],
    "generic_care": ["cham soc", "xu ly sao", "tai sao"],
}


def classify_facet(
    intent: str,
    message: str,
    entities: dict[str, Any],
    image_context: ImagePlantContext | None = None,
    memory: dict[str, Any] | None = None,
) -> FacetResult:
    normalized = normalize_text(message or "")

    if intent == "product_info":
        return classify_product_info_facet(normalized, entities, image_context)
    if intent == "recommendation":
        return classify_recommendation_facet(normalized, entities, memory)
    if intent == "plant_care":
        return classify_plant_care_facet(normalized)
    if intent == "cart_order":
        return FacetResult(name="cart_action", confidence=0.95)
    if intent == "general":
        return FacetResult(name="greeting" if is_short_greeting(normalized) else "general_chat", confidence=0.8)
    return FacetResult(name="unknown", confidence=0.4)


def classify_product_info_facet(normalized: str, entities: dict[str, Any], image_context: ImagePlantContext | None) -> FacetResult:
    if entities.get("pet_safe") or contains_any_phrase(normalized, PRODUCT_INFO_FACET_SIGNALS["toxicity"]):
        return FacetResult(name="toxicity", confidence=0.96)
    if contains_any_phrase(normalized, PRODUCT_INFO_FACET_SIGNALS["stock"]):
        return FacetResult(name="stock", confidence=0.93)
    if contains_any_phrase(normalized, PRODUCT_INFO_FACET_SIGNALS["price"]):
        return FacetResult(name="price", confidence=0.93)
    if contains_any_phrase(normalized, PRODUCT_INFO_FACET_SIGNALS["variant"]):
        return FacetResult(name="variant", confidence=0.9)
    if contains_any_phrase(normalized, PRODUCT_INFO_FACET_SIGNALS["image"]):
        return FacetResult(name="image", confidence=0.9)
    if contains_any_phrase(normalized, PRODUCT_INFO_FACET_SIGNALS["highlights"]):
        return FacetResult(name="highlights", confidence=0.86)
    if (not normalized and image_context) or contains_any_phrase(normalized, PRODUCT_INFO_FACET_SIGNALS["overview"]):
        return FacetResult(name="overview", confidence=0.82)
    return FacetResult(name="general", confidence=0.72)


def classify_recommendation_facet(normalized: str, entities: dict[str, Any], memory: dict[str, Any] | None) -> FacetResult:
    if entities.get("budget_input_amount") or contains_any_phrase(normalized, RECOMMENDATION_FACET_SIGNALS["budget"]):
        return FacetResult(name="budget_filtered", confidence=0.85)
    if entities.get("care_level") or contains_any_phrase(normalized, RECOMMENDATION_FACET_SIGNALS["beginner"]):
        return FacetResult(name="beginner_friendly", confidence=0.83)
    if entities.get("placement") or contains_any_phrase(normalized, RECOMMENDATION_FACET_SIGNALS["placement"]):
        return FacetResult(name="placement_based", confidence=0.82)
    if entities.get("light_requirement") or contains_any_phrase(normalized, RECOMMENDATION_FACET_SIGNALS["light"]):
        return FacetResult(name="light_based", confidence=0.8)
    if entities.get("watering_need") or contains_any_phrase(normalized, RECOMMENDATION_FACET_SIGNALS["watering"]):
        return FacetResult(name="watering_based", confidence=0.8)
    if contains_any_phrase(normalized, RECOMMENDATION_FACET_SIGNALS["gift"]):
        return FacetResult(name="gift_based", confidence=0.8)
    if contains_any_phrase(normalized, RECOMMENDATION_FACET_SIGNALS["style"]):
        return FacetResult(name="style_based", confidence=0.78)
    if memory and (memory.get("preferences") or {}).get("budget_input_amount"):
        return FacetResult(name="memory_refined", confidence=0.7, source="memory")
    return FacetResult(name="generic", confidence=0.65)


def classify_plant_care_facet(normalized: str) -> FacetResult:
    if contains_any_phrase(normalized, PLANT_CARE_FACET_SIGNALS["symptom"]):
        return FacetResult(name="symptom_diagnosis", confidence=0.9)
    if contains_any_phrase(normalized, PLANT_CARE_FACET_SIGNALS["watering_schedule"]):
        return FacetResult(name="watering_schedule", confidence=0.88)
    if contains_any_phrase(normalized, PLANT_CARE_FACET_SIGNALS["light_care"]):
        return FacetResult(name="light_care", confidence=0.82)
    if contains_any_phrase(normalized, PLANT_CARE_FACET_SIGNALS["generic_care"]):
        return FacetResult(name="generic_care", confidence=0.78)
    return FacetResult(name="generic_care", confidence=0.65)


def is_short_greeting(normalized: str) -> bool:
    greeting_markers = ["xin chao", "hello", "hi", "alo", "cam on"]
    return any(marker in normalized for marker in greeting_markers) and len(normalized.split()) <= 8
