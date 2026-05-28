from __future__ import annotations

import re
from typing import Any

from app.config import get_settings
from app.router.text_utils import contains_any_phrase, normalize_text


CARE_LEVEL_SIGNALS = {
    "easy": ["de cham", "de song", "nguoi moi", "moi choi", "it cham", "khong can cham nhieu", "low maintenance"],
    "moderate": ["cham vua", "trung binh", "co kinh nghiem mot chut"],
    "hard": ["kho cham", "can cham ky", "cau ky", "nhieu cong cham"],
}

WATERING_SIGNALS = {
    "low": ["hay quen tuoi", "quen tuoi", "it tuoi", "khong can tuoi nhieu", "ban ron", "chiu han", "drought", "it nuoc"],
    "medium": ["tuoi vua", "tuoi deu", "do am vua"],
    "high": ["ua am", "can am", "nhieu nuoc", "dat am", "tuoi nhieu", "am uot"],
}

LIGHT_SIGNALS = {
    "low": ["it nang", "thieu sang", "it anh sang", "bong ram", "anh sang yeu"],
    "indirect": ["anh sang gian tiep", "nang gian tiep", "gan cua so", "loc nang"],
    "bright": ["sang manh", "nhieu sang"],
    "full_sun": ["nang truc tiep", "full sun", "ngoai troi nang"],
}

PLACEMENT_SIGNALS = {
    "desk": ["de ban", "ban lam viec", "goc lam viec"],
    "office": ["van phong", "cong ty"],
    "bedroom": ["phong ngu"],
    "living_room": ["phong khach"],
    "balcony": ["ban cong", "cua so"],
    "outdoor": ["ngoai troi", "san vuon", "vuon"],
}

TOXICITY_PET_SIGNALS = ["mèo", "thú cưng"]
TOXICITY_PET_NORMALIZED_SIGNALS = ["thu cung"]
TOXICITY_DOG_PATTERNS = [r"\bchó\b", r"doc voi cho\b", r"an toan voi cho\b", r"nuoi cho\b"]

PRODUCT_NAME_PATTERNS = [
    r"(?:cây|cay)\s+(.+?)(?:\s+(?:bao nhiêu|bao nhieu|giá|gia|còn|con|hết|het|size|có|co|độc|doc|an toàn|an toan|hình ảnh|hinh anh)\b|[?.!,]|$)",
    r"(?:giá|gia)\s+(?:cây|cay)?\s*(.+?)(?:[?.!,]|$)",
]

INVALID_PRODUCT_NAME_TOKENS = {
    "nay",
    "nao",
    "gi",
    "bi",
    "vao",
    "them",
    "mua",
    "dat",
    "tai sao",
    "bigplant",
    "de",
    "cham",
    "duoi",
    "phong",
    "it",
    "nang",
    "sang",
    "quen",
    "tuoi",
    "ban",
    "viec",
    "minimal",
    "tang",
    "sinh",
    "nhat",
    "goc",
}


def extract_entities(text: str, original: str) -> dict[str, Any]:
    entities: dict[str, Any] = {}

    product_name = extract_product_name(original)
    if product_name:
        entities["product_name"] = product_name

    budget = extract_budget(text)
    if budget:
        entities.update(budget)

    care_level = detect_signal_value(text, CARE_LEVEL_SIGNALS)
    if care_level:
        entities["care_level"] = care_level

    watering_need = detect_signal_value(text, WATERING_SIGNALS)
    if watering_need:
        entities["watering_need"] = watering_need

    light_requirement = detect_signal_value(text, LIGHT_SIGNALS)
    if light_requirement:
        entities["light_requirement"] = light_requirement

    placement = detect_signal_value(text, PLACEMENT_SIGNALS)
    if placement:
        entities["placement"] = placement

    if mentions_pet(original, text):
        entities["pet_safe"] = True
        pet_type = detect_pet_type(original, text)
        if pet_type:
            entities["pet_type"] = pet_type

    style = detect_style(text)
    if style:
        entities["style"] = style

    if contains_any_phrase(text, ["lam qua", "qua tang", "tang sinh nhat", "tang khai truong"]):
        entities["gift_purpose"] = True

    return entities


def detect_signal_value(text: str, signal_map: dict[str, list[str]]) -> str | None:
    for value, phrases in signal_map.items():
        if contains_any_phrase(text, phrases):
            return value
    return None


def extract_product_name(original: str) -> str | None:
    for pattern in PRODUCT_NAME_PATTERNS:
        match = re.search(pattern, original, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(1).strip(" -_.,?!\"'")
        if 1 <= len(candidate.split()) <= 5 and not is_invalid_product_candidate(candidate):
            return candidate
    return None


def is_invalid_product_candidate(candidate: str) -> bool:
    normalized = normalize_text(candidate)
    words = set(normalized.split())
    has_invalid_token = bool(words & INVALID_PRODUCT_NAME_TOKENS)
    looks_like_budget = bool(re.search(r"\b\d+(k|m|trieu|nghin|ngan)?\b", normalized))
    return has_invalid_token or looks_like_budget


def mentions_pet(original: str, normalized: str) -> bool:
    original_lower = original.lower()
    if any(signal in original_lower for signal in TOXICITY_PET_SIGNALS):
        return True
    if contains_any_phrase(normalized, TOXICITY_PET_NORMALIZED_SIGNALS):
        return True
    return any(re.search(pattern, original_lower) or re.search(pattern, normalized) for pattern in TOXICITY_DOG_PATTERNS)


def detect_pet_type(original: str, normalized: str) -> str | None:
    original_lower = original.lower()
    if "mèo" in original_lower or "meo" in normalized:
        return "cat"
    if "chó" in original_lower or "cho" in normalized:
        return "dog"
    if "thu cung" in normalized:
        return "pet"
    return None


def detect_style(text: str) -> str | None:
    if contains_any_phrase(text, ["minimal", "toi gian", "hien dai"]):
        return "minimal"
    if contains_any_phrase(text, ["sang", "cao cap", "luxury"]):
        return "elegant"
    if contains_any_phrase(text, ["chill", "xanh mat", "thu gian"]):
        return "relaxing"
    if contains_any_phrase(text, ["decor", "trang tri", "dep"]):
        return "decorative"
    return None


def extract_budget(text: str) -> dict[str, Any] | None:
    settings = get_settings()

    prefixed_usd = re.search(r"(?:duoi|nho hon|toi da|<=|tam|khoang)?\s*\$\s*(\d+(?:[.,]\d+)?)", text)
    if prefixed_usd:
        original_amount = float(prefixed_usd.group(1).replace(",", "."))
        normalized_amount = convert_amount_to_catalog(original_amount, "USD", settings.catalog_price_currency, settings.vnd_per_usd)
        return build_budget_entities(original_amount, "USD", normalized_amount, settings.catalog_price_currency)

    usd_match = re.search(r"(?:duoi|nho hon|toi da|<=|tam|khoang)?\s*(\d+(?:[.,]\d+)?)\s*(usd|dollar|dollars|do la|do-la)", text)
    if usd_match:
        original_amount = float(usd_match.group(1).replace(",", "."))
        normalized_amount = convert_amount_to_catalog(original_amount, "USD", settings.catalog_price_currency, settings.vnd_per_usd)
        return build_budget_entities(original_amount, "USD", normalized_amount, settings.catalog_price_currency)

    vnd_match = re.search(r"(?:duoi|nho hon|toi da|<=|tam|khoang)?\s*(\d+(?:[.,]\d+)?)\s*(k|nghin|ngan|trieu|m|vnd|dong|đ|d)\b", text)
    if vnd_match:
        original_amount = float(vnd_match.group(1).replace(",", "."))
        unit = vnd_match.group(2)
        if unit in {"k", "nghin", "ngan"}:
            original_amount *= 1000
        elif unit in {"trieu", "m"}:
            original_amount *= 1_000_000
        normalized_amount = convert_amount_to_catalog(original_amount, "VND", settings.catalog_price_currency, settings.vnd_per_usd)
        return build_budget_entities(original_amount, "VND", normalized_amount, settings.catalog_price_currency)

    plain_match = re.search(r"(?:duoi|nho hon|toi da|<=|tam|khoang)\s*(\d+(?:[.,]\d+)?)\b", text)
    if plain_match:
        original_amount = float(plain_match.group(1).replace(",", "."))
        currency = settings.catalog_price_currency.upper()
        return build_budget_entities(original_amount, currency, original_amount, currency)

    return None


def build_budget_entities(original_amount: float, input_currency: str, normalized_amount: float, catalog_currency: str) -> dict[str, Any]:
    return {
        "max_price": round(normalized_amount, 4),
        "budget_input_currency": input_currency,
        "budget_input_amount": round(original_amount, 4),
        "budget_catalog_currency": catalog_currency.upper(),
    }


def convert_amount_to_catalog(amount: float, input_currency: str, catalog_currency: str, vnd_per_usd: float) -> float:
    input_currency = input_currency.upper()
    catalog_currency = catalog_currency.upper()
    if input_currency == catalog_currency:
        return amount
    if input_currency == "VND" and catalog_currency == "USD":
        return amount / vnd_per_usd
    if input_currency == "USD" and catalog_currency == "VND":
        return amount * vnd_per_usd
    return amount
