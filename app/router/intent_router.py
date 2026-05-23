from __future__ import annotations

import re
from typing import Any

from app.llm.local_llm import LocalLLM
from app.llm.prompts import ROUTER_PROMPT
from app.router.schemas import IntentRoute


class IntentRouter:
    def __init__(self, llm: LocalLLM | None = None) -> None:
        self.llm = llm or LocalLLM()

    def classify(self, message: str) -> IntentRoute:
        heuristic_route = self._classify_by_rules(message)
        if heuristic_route.confidence >= 0.82 or not self.llm.is_available:
            return heuristic_route

        prompt = ROUTER_PROMPT.format(message=message)
        try:
            raw = self.llm.generate_json(prompt)
        except Exception:
            return heuristic_route

        if raw.get("intent") not in {"product_info", "recommendation", "plant_care", "cart_order", "general", "unclear"}:
            return heuristic_route
        entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
        entities = {**heuristic_route.entities, **entities}
        return IntentRoute(
            intent=raw["intent"],
            confidence=float(raw.get("confidence") or heuristic_route.confidence or 0.5),
            entities=entities,
            source="local_llm",
        )

    def _classify_by_rules(self, message: str) -> IntentRoute:
        text = normalize_text(message)
        entities = extract_entities(text, original=message)

        if contains_any(text, ["them vao gio", "gio hang", "dat hang", "mua ngay", "checkout", "thanh toan"]):
            return IntentRoute(intent="cart_order", confidence=0.9, entities=entities)

        recommendation_markers = [
            "tu van",
            "goi y",
            "nen mua",
            "nen chon",
            "chon cay",
            "cay nao",
            "toi muon cay",
            "minh muon cay",
            "phu hop",
            "lam qua",
            "de ban",
            "phong khach",
            "phong ngu",
            "van phong",
        ]
        if contains_any(text, recommendation_markers):
            return IntentRoute(intent="recommendation", confidence=0.88, entities=entities)

        plant_care_markers = [
            "vang la",
            "ung re",
            "thoi re",
            "heo la",
            "dom la",
            "sau benh",
            "bi benh",
            "tai sao",
            "xu ly sao",
            "cham soc",
            "tuoi bao lau",
            "bao lau tuoi",
            "nen tuoi",
        ]
        if contains_any(text, plant_care_markers):
            return IntentRoute(intent="plant_care", confidence=0.86, entities=entities)

        product_markers = [
            "bao nhieu tien",
            "gia",
            "con hang",
            "het hang",
            "ton kho",
            "size",
            "kich thuoc",
            "mau nao",
            "hinh anh",
            "anh san pham",
            "co doc",
            "doc voi",
            "an toan cho thu cung",
        ]
        if contains_any(text, product_markers):
            return IntentRoute(intent="product_info", confidence=0.84, entities=entities)

        if contains_any(text, ["xin chao", "hello", "hi", "cam on"]):
            return IntentRoute(intent="general", confidence=0.8, entities=entities)

        return IntentRoute(intent="unclear", confidence=0.45, entities=entities)


def contains_any(text: str, markers: list[str]) -> bool:
    return any(marker in text for marker in markers)


def normalize_text(value: str) -> str:
    lowered = value.lower()
    replacements = {
        "à": "a",
        "á": "a",
        "ả": "a",
        "ã": "a",
        "ạ": "a",
        "ă": "a",
        "ằ": "a",
        "ắ": "a",
        "ẳ": "a",
        "ẵ": "a",
        "ặ": "a",
        "â": "a",
        "ầ": "a",
        "ấ": "a",
        "ẩ": "a",
        "ẫ": "a",
        "ậ": "a",
        "đ": "d",
        "è": "e",
        "é": "e",
        "ẻ": "e",
        "ẽ": "e",
        "ẹ": "e",
        "ê": "e",
        "ề": "e",
        "ế": "e",
        "ể": "e",
        "ễ": "e",
        "ệ": "e",
        "ì": "i",
        "í": "i",
        "ỉ": "i",
        "ĩ": "i",
        "ị": "i",
        "ò": "o",
        "ó": "o",
        "ỏ": "o",
        "õ": "o",
        "ọ": "o",
        "ô": "o",
        "ồ": "o",
        "ố": "o",
        "ổ": "o",
        "ỗ": "o",
        "ộ": "o",
        "ơ": "o",
        "ờ": "o",
        "ớ": "o",
        "ở": "o",
        "ỡ": "o",
        "ợ": "o",
        "ù": "u",
        "ú": "u",
        "ủ": "u",
        "ũ": "u",
        "ụ": "u",
        "ư": "u",
        "ừ": "u",
        "ứ": "u",
        "ử": "u",
        "ữ": "u",
        "ự": "u",
        "ỳ": "y",
        "ý": "y",
        "ỷ": "y",
        "ỹ": "y",
        "ỵ": "y",
    }
    for src, dst in replacements.items():
        lowered = lowered.replace(src, dst)
    return re.sub(r"\s+", " ", lowered).strip()


def extract_entities(text: str, original: str) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    product_name = extract_product_name(original)
    if product_name:
        entities["product_name"] = product_name

    max_price = extract_max_price(text)
    if max_price:
        entities["max_price"] = max_price

    if contains_any(text, ["de cham", "de song", "nguoi moi", "moi choi", "it cham"]):
        entities["care_level"] = "easy"
    if contains_any(text, ["hay quen tuoi", "quen tuoi", "it tuoi", "khong can tuoi nhieu", "ban ron"]):
        entities["watering_need"] = "low"
    if contains_any(text, ["it nang", "thieu sang", "it anh sang", "bong ram"]):
        entities["light_requirement"] = "low"
    if contains_any(text, ["anh sang gian tiep", "nang gian tiep"]):
        entities["light_requirement"] = "indirect"
    if "de ban" in text:
        entities["placement"] = "desk"
    elif "van phong" in text or "ban lam viec" in text:
        entities["placement"] = "office"
    elif "phong ngu" in text:
        entities["placement"] = "bedroom"
    elif "phong khach" in text:
        entities["placement"] = "living_room"
    if contains_any(text, ["meo", "cho", "thu cung"]):
        entities["pet_safe"] = True
    return entities


def extract_product_name(original: str) -> str | None:
    patterns = [
        r"(?:cây|cay)\s+(.+?)(?:\s+(?:bao nhiêu|bao nhieu|giá|gia|còn|con|hết|het|size|có|co|độc|doc)\b|[?.!,]|$)",
        r"(?:giá|gia)\s+(?:cây|cay)?\s*(.+?)(?:[?.!,]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, original, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).strip(" -_.,?!\"'")
            if 1 <= len(candidate.split()) <= 5 and not is_invalid_product_candidate(candidate):
                return candidate
    return None


def is_invalid_product_candidate(candidate: str) -> bool:
    normalized = normalize_text(candidate)
    bad_tokens = {"nay", "nao", "gi", "bi", "vao", "them", "mua", "dat", "tai sao"}
    words = set(normalized.split())
    return bool(words & bad_tokens)


def extract_max_price(text: str) -> int | None:
    match = re.search(r"(?:duoi|nho hon|toi da|<=|tam|khoang)\s*(\d+(?:[.,]\d+)?)\s*(k|nghin|ngan|trieu|m)?", text)
    if not match:
        return None
    amount = float(match.group(1).replace(",", "."))
    unit = match.group(2) or ""
    if unit in {"k", "nghin", "ngan"}:
        amount *= 1000
    elif unit in {"trieu", "m"}:
        amount *= 1_000_000
    elif amount < 1000:
        amount *= 1000
    return int(amount)
