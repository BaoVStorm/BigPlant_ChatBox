from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.config import get_settings
from app.embeddings.embedding_service import EmbeddingService, get_embedding_service
from app.llm.local_llm import LocalLLM
from app.llm.prompts import ROUTER_PROMPT
from app.router.schemas import IntentRoute


INTENT_EXAMPLES: dict[str, list[str]] = {
    "product_info": [
        "Cây monstera bao nhiêu tiền",
        "Cây aloe vera giá bao nhiêu",
        "Cây này còn hàng không",
        "Shop còn mẫu này không",
        "Sản phẩm này có mấy loại",
        "Có ảnh sản phẩm không",
        "Cây trầu bà có độc với mèo không",
        "Size medium của cây này giá bao nhiêu",
        "Cho mình xem thông tin sản phẩm này",
    ],
    "recommendation": [
        "Tôi muốn cây dễ chăm cho người mới",
        "Nên mua cây nào để bàn làm việc",
        "Phòng tôi ít nắng nên chọn cây gì",
        "Tôi muốn cây nhìn sang cho phòng khách",
        "Gợi ý cây hợp phòng ngủ",
        "Tư vấn giúp tôi một cây ít phải chăm",
        "Chọn giúp tôi cây làm quà",
        "Mình muốn tìm một cây tặng sinh nhật",
        "Cây nào hợp người bận rộn",
    ],
    "plant_care": [
        "Tại sao lá cây bị vàng",
        "Cây bị úng rễ xử lý sao",
        "Tưới cây bao lâu một lần",
        "Chăm cây này như thế nào",
        "Lá cây bị đốm nâu là sao",
        "Cây này có cần nhiều ánh sáng không",
        "Nguyên nhân cây bị héo lá",
        "Cách cứu cây sắp chết",
    ],
    "cart_order": [
        "Thêm cây này vào giỏ hàng",
        "Mua ngay sản phẩm này",
        "Đặt hàng giúp tôi",
        "Checkout đơn hàng này",
        "Thêm sản phẩm này vào giỏ",
    ],
    "general": [
        "Xin chào",
        "Alo bạn ơi",
        "Bạn là ai",
        "Bạn có thể giúp gì cho tôi",
        "Cảm ơn bạn",
        "Mình cần hỗ trợ",
        "Chào shop",
    ],
}

RULE_WEIGHTS: dict[str, list[tuple[str, float]]] = {
    "cart_order": [
        (r"\bthem vao gio\b", 3.4),
        (r"\bgio hang\b", 2.8),
        (r"\bdat hang\b", 3.0),
        (r"\bmua ngay\b", 3.2),
        (r"\bcheckout\b", 3.2),
        (r"\bthanh toan\b", 2.8),
    ],
    "product_info": [
        (r"\bbao nhieu tien\b", 2.8),
        (r"\bgia\b", 1.8),
        (r"\bcon hang\b", 2.6),
        (r"\bhet hang\b", 2.2),
        (r"\bton kho\b", 2.4),
        (r"\bsize\b", 1.8),
        (r"\bkich thuoc\b", 1.8),
        (r"\bthong tin\b", 1.4),
        (r"\bhinh anh\b", 1.7),
        (r"\banh san pham\b", 2.0),
        (r"\bco doc\b", 2.4),
        (r"\bdoc voi\b", 2.4),
        (r"\ban toan cho thu cung\b", 2.6),
    ],
    "recommendation": [
        (r"\btu van\b", 2.2),
        (r"\bgoi y\b", 2.0),
        (r"\bnen mua\b", 2.0),
        (r"\bnen chon\b", 2.0),
        (r"\bchon cay\b", 2.0),
        (r"\bcay nao\b", 1.6),
        (r"\btoi muon cay\b", 1.8),
        (r"\bminh muon cay\b", 1.8),
        (r"\bphu hop\b", 1.4),
        (r"\blam qua\b", 1.8),
        (r"\bde ban\b", 1.8),
        (r"\bphong khach\b", 1.4),
        (r"\bphong ngu\b", 1.4),
        (r"\bvan phong\b", 1.4),
    ],
    "plant_care": [
        (r"\bvang la\b", 2.4),
        (r"\bung re\b", 2.4),
        (r"\bthoi re\b", 2.4),
        (r"\bheo la\b", 2.2),
        (r"\bdom la\b", 2.2),
        (r"\bsau benh\b", 2.2),
        (r"\bbi benh\b", 1.8),
        (r"\btai sao\b", 1.5),
        (r"\bxu ly sao\b", 2.0),
        (r"\bcham soc\b", 1.8),
        (r"\btuoi bao lau\b", 2.4),
        (r"\bbao lau tuoi\b", 2.4),
        (r"\bnen tuoi\b", 1.8),
    ],
    "general": [
        (r"\bxin chao\b", 2.8),
        (r"\bhello\b", 2.5),
        (r"\bhi\b", 2.0),
        (r"\bcam on\b", 2.4),
    ],
}


class IntentRouter:
    def __init__(self, llm: LocalLLM | None = None, embeddings: EmbeddingService | None = None) -> None:
        self.llm = llm or LocalLLM()
        self.embeddings = embeddings or get_embedding_service()
        self._example_index: dict[str, list[list[float]]] | None = None

    def classify(self, message: str) -> IntentRoute:
        rule_route, rule_scores = self._classify_by_rules(message)
        if is_strong_rule_route(rule_route, rule_scores):
            return rule_route

        semantic_route, semantic_scores = self._classify_by_semantics(message, rule_route.entities, rule_scores)
        if semantic_route and is_confident_semantic_route(semantic_route, semantic_scores, rule_route):
            return semantic_route

        if self.llm.is_available:
            prompt = ROUTER_PROMPT.format(message=message)
            try:
                raw = self.llm.generate_json(prompt)
            except Exception:
                return semantic_route or rule_route

            if raw.get("intent") in {"product_info", "recommendation", "plant_care", "cart_order", "general", "unclear"}:
                entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
                entities = {**rule_route.entities, **entities}
                return IntentRoute(
                    intent=raw["intent"],
                    confidence=float(raw.get("confidence") or max((semantic_route or rule_route).confidence, 0.5)),
                    entities=entities,
                    source="local_llm",
                )

        return semantic_route or rule_route

    def _classify_by_rules(self, message: str) -> tuple[IntentRoute, dict[str, float]]:
        text = normalize_text(message)
        entities = extract_entities(text, original=message)
        scores = score_intents_by_rules(text, entities)
        best_intent, best_score, second_score = best_scores(scores)

        if best_intent == "unclear" or best_score <= 0:
            return IntentRoute(intent="unclear", confidence=0.45, entities=entities, source="heuristic_rules"), scores

        margin = best_score - second_score
        confidence = min(0.97, 0.52 + best_score * 0.1 + max(margin, 0) * 0.05)
        return IntentRoute(intent=best_intent, confidence=confidence, entities=entities, source="heuristic_rules"), scores

    def _classify_by_semantics(
        self,
        message: str,
        entities: dict[str, Any],
        rule_scores: dict[str, float],
    ) -> tuple[IntentRoute | None, dict[str, float]]:
        try:
            index = self._get_example_index()
            query_vector = self.embeddings.embed_text(message)
        except Exception:
            return None, {}

        semantic_scores: dict[str, float] = {}
        for intent, vectors in index.items():
            similarities = [cosine_similarity(query_vector, vector) for vector in vectors]
            semantic_scores[intent] = max(similarities) if similarities else 0.0

        combined_scores = dict(semantic_scores)
        for intent, score in rule_scores.items():
            if intent == "unclear":
                continue
            combined_scores[intent] = combined_scores.get(intent, 0.0) + min(score, 3.0) * 0.04

        best_intent, best_score, second_score = best_scores(combined_scores)
        if best_intent == "unclear" or best_score <= 0:
            return None, combined_scores

        margin = best_score - second_score
        confidence = min(0.95, max(0.45, best_score + margin * 0.45))
        return IntentRoute(intent=best_intent, confidence=confidence, entities=entities, source="semantic_examples"), combined_scores

    def _get_example_index(self) -> dict[str, list[list[float]]]:
        if self._example_index is not None:
            return self._example_index
        self._example_index = build_intent_example_index(self.embeddings)
        return self._example_index


def is_strong_rule_route(route: IntentRoute, scores: dict[str, float]) -> bool:
    if route.intent == "unclear":
        return False
    best_intent, best_score, second_score = best_scores(scores)
    margin = best_score - second_score
    if best_intent != route.intent:
        return False
    if best_score >= 3.0:
        return True
    return best_score >= 2.0 and margin >= 0.8


def is_confident_semantic_route(
    route: IntentRoute,
    semantic_scores: dict[str, float],
    rule_route: IntentRoute,
) -> bool:
    if route is None:
        return False
    best_intent, best_score, second_score = best_scores(semantic_scores)
    margin = best_score - second_score
    if best_intent != route.intent:
        return False
    if route.intent == rule_route.intent and rule_route.intent != "unclear":
        return True
    return best_score >= 0.63 and margin >= 0.03


def score_intents_by_rules(text: str, entities: dict[str, Any]) -> dict[str, float]:
    scores = {intent: 0.0 for intent in ["product_info", "recommendation", "plant_care", "cart_order", "general", "unclear"]}
    for intent, rules in RULE_WEIGHTS.items():
        for pattern, weight in rules:
            if re.search(pattern, text):
                scores[intent] += weight

    if entities.get("max_price"):
        scores["recommendation"] += 0.7
    if entities.get("care_level"):
        scores["recommendation"] += 0.9
    if entities.get("placement"):
        scores["recommendation"] += 0.7
    if entities.get("watering_need"):
        scores["recommendation"] += 0.6
    if entities.get("light_requirement"):
        scores["recommendation"] += 0.6
    if entities.get("pet_safe"):
        scores["product_info"] += 1.0
    if entities.get("product_name"):
        scores["product_info"] += 0.8

    if entities.get("product_name") and not any(token in text for token in ["gia", "bao nhieu", "con hang", "ton kho", "doc", "hinh anh", "size"]):
        scores["product_info"] -= 0.4

    if not any(score > 0 for intent, score in scores.items() if intent != "unclear"):
        scores["unclear"] = 1.0
    return scores


def best_scores(scores: dict[str, float]) -> tuple[str, float, float]:
    ranked = sorted(((intent, score) for intent, score in scores.items() if intent != "unclear"), key=lambda item: item[1], reverse=True)
    if not ranked or ranked[0][1] <= 0:
        return "unclear", scores.get("unclear", 0.0), 0.0
    best_intent, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    return best_intent, best_score, second_score


@lru_cache(maxsize=1)
def build_intent_example_index(embeddings: EmbeddingService) -> dict[str, list[list[float]]]:
    index: dict[str, list[list[float]]] = {}
    for intent, examples in INTENT_EXAMPLES.items():
        index[intent] = embeddings.embed_texts(examples)
    return index


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    return float(sum(a * b for a, b in zip(vector_a, vector_b)))


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

    budget = extract_budget(text)
    if budget:
        entities.update(budget)

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
    if mentions_pet(original, text):
        entities["pet_safe"] = True
    return entities


def extract_product_name(original: str) -> str | None:
    patterns = [
        r"(?:cây|cay)\s+(.+?)(?:\s+(?:bao nhiêu|bao nhieu|giá|gia|còn|con|hết|het|size|có|co|độc|doc|an toàn|an toan|hình ảnh|hinh anh)\b|[?.!,]|$)",
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
    bad_tokens = {
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
    words = set(normalized.split())
    return bool(words & bad_tokens) or bool(re.search(r"\b\d+(k|m|trieu|nghin|ngan)?\b", normalized))


def mentions_pet(original: str, normalized: str) -> bool:
    original_lower = original.lower()
    if "mèo" in original_lower or "thú cưng" in original_lower or "thu cung" in normalized:
        return True
    pet_dog_patterns = [r"\bchó\b", r"doc voi cho\b", r"an toan voi cho\b", r"nuoi cho\b"]
    return any(re.search(pattern, original_lower) or re.search(pattern, normalized) for pattern in pet_dog_patterns)


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


def contains_any(text: str, markers: list[str]) -> bool:
    return any(marker in text for marker in markers)
