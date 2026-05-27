from __future__ import annotations

from typing import Any

from app.router.text_utils import contains_any_phrase, normalize_text


PRODUCT_QUESTION_FOCUS_SIGNALS = {
    "toxicity": ["co doc", "doc voi", "an toan voi meo", "an toan voi cho", "thu cung"],
    "stock": ["con hang", "het hang", "ton kho"],
    "variant": ["size", "kich thuoc", "mau nao", "loai nao", "mau sac"],
    "image": ["hinh anh", "anh san pham", "xem anh"],
    "price": ["gia", "bao nhieu tien", "bao nhieu"],
    "highlights": ["dac diem", "noi bat", "dac biet", "uu diem", "cong dung", "mo ta", "la gi"],
    "overview": ["cay nay sao", "san pham nay sao", "cay nay the nao"],
}

TOXICITY_NEGATIVE_SIGNALS = [
    "highly toxic",
    "toxic",
    "life-threatening",
    "poison",
    "poisoning",
    "keep seeds away from children and pets",
    "keep away from pets",
]

TOXICITY_POSITIVE_SIGNALS = ["non-toxic", "safe for pets", "pet safe"]


def detect_product_question_focus(message: str, entities: dict[str, Any]) -> str:
    normalized = normalize_text(message)
    if entities.get("pet_safe") or contains_any_phrase(normalized, PRODUCT_QUESTION_FOCUS_SIGNALS["toxicity"]):
        return "toxicity"
    if contains_any_phrase(normalized, PRODUCT_QUESTION_FOCUS_SIGNALS["stock"]):
        return "stock"
    if contains_any_phrase(normalized, PRODUCT_QUESTION_FOCUS_SIGNALS["variant"]):
        return "variant"
    if contains_any_phrase(normalized, PRODUCT_QUESTION_FOCUS_SIGNALS["image"]):
        return "image"
    if contains_any_phrase(normalized, PRODUCT_QUESTION_FOCUS_SIGNALS["price"]):
        return "price"
    if contains_any_phrase(normalized, PRODUCT_QUESTION_FOCUS_SIGNALS["highlights"]):
        return "highlights"
    if contains_any_phrase(normalized, PRODUCT_QUESTION_FOCUS_SIGNALS["overview"]):
        return "overview"
    return "general"


def contains_negative_toxicity_signal(text: str) -> bool:
    return contains_any_phrase(text, TOXICITY_NEGATIVE_SIGNALS)


def contains_positive_toxicity_signal(text: str) -> bool:
    return contains_any_phrase(text, TOXICITY_POSITIVE_SIGNALS)
