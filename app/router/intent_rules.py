from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WeightedRegexRule:
    label: str
    pattern: str
    weight: float
    description: str


INTENT_RULE_GROUPS: dict[str, dict[str, list[WeightedRegexRule]]] = {
    "cart_order": {
        "cart_actions": [
            WeightedRegexRule("add_to_cart", r"\bthem vao gio\b", 3.4, "User muốn thêm vào giỏ"),
            WeightedRegexRule("cart_mention", r"\bgio hang\b", 2.8, "User nhắc trực tiếp giỏ hàng"),
            WeightedRegexRule("place_order", r"\bdat hang\b", 3.0, "User muốn đặt hàng"),
            WeightedRegexRule("buy_now", r"\bmua ngay\b", 3.2, "User muốn mua ngay"),
            WeightedRegexRule("checkout", r"\bcheckout\b", 3.2, "User muốn thanh toán / checkout"),
            WeightedRegexRule("payment", r"\bthanh toan\b", 2.8, "User nhắc thanh toán"),
        ]
    },
    "product_info": {
        "price_lookup": [
            WeightedRegexRule("price_phrase", r"\bbao nhieu tien\b", 2.8, "Hỏi trực tiếp giá tiền"),
            WeightedRegexRule("price_keyword", r"\bgia\b", 1.8, "Nhắc từ khóa giá"),
        ],
        "stock_lookup": [
            WeightedRegexRule("in_stock", r"\bcon hang\b", 2.6, "Hỏi còn hàng không"),
            WeightedRegexRule("out_of_stock", r"\bhet hang\b", 2.2, "Hỏi hết hàng hay chưa"),
            WeightedRegexRule("inventory", r"\bton kho\b", 2.4, "Nhắc trực tiếp tồn kho"),
        ],
        "variant_lookup": [
            WeightedRegexRule("size", r"\bsize\b", 1.8, "Hỏi size"),
            WeightedRegexRule("dimension", r"\bkich thuoc\b", 1.8, "Hỏi kích thước"),
        ],
        "detail_lookup": [
            WeightedRegexRule("product_detail", r"\bthong tin\b", 1.4, "Muốn xem thông tin chi tiết"),
        ],
        "image_lookup": [
            WeightedRegexRule("image", r"\bhinh anh\b", 1.7, "Muốn xem hình ảnh"),
            WeightedRegexRule("product_image", r"\banh san pham\b", 2.0, "Muốn xem ảnh sản phẩm"),
        ],
        "toxicity_lookup": [
            WeightedRegexRule("toxic", r"\bco doc\b", 2.4, "Hỏi cây có độc không"),
            WeightedRegexRule("toxic_for_pet", r"\bdoc voi\b", 2.4, "Hỏi độc với mèo/chó"),
            WeightedRegexRule("pet_safety", r"\ban toan cho thu cung\b", 2.6, "Hỏi an toàn với thú cưng"),
        ],
    },
    "recommendation": {
        "advice_lookup": [
            WeightedRegexRule("advice", r"\btu van\b", 2.2, "Muốn được tư vấn"),
            WeightedRegexRule("suggest", r"\bgoi y\b", 2.0, "Muốn được gợi ý"),
            WeightedRegexRule("should_buy", r"\bnen mua\b", 2.0, "Muốn biết nên mua gì"),
            WeightedRegexRule("should_choose", r"\bnen chon\b", 2.0, "Muốn biết nên chọn gì"),
            WeightedRegexRule("choose_plant", r"\bchon cay\b", 2.0, "Muốn chọn cây"),
            WeightedRegexRule("which_plant", r"\bcay nao\b", 1.6, "Hỏi loại cây phù hợp"),
        ],
        "shopping_need": [
            WeightedRegexRule("want_plant", r"\btoi muon cay\b", 1.8, "User muốn tìm cây"),
            WeightedRegexRule("want_plant_alt", r"\bminh muon cay\b", 1.8, "User muốn tìm cây"),
            WeightedRegexRule("fit_need", r"\bphu hop\b", 1.4, "Nhấn mạnh nhu cầu phù hợp"),
            WeightedRegexRule("gift_need", r"\blam qua\b", 1.8, "Muốn cây làm quà"),
        ],
        "placement_need": [
            WeightedRegexRule("desk", r"\bde ban\b", 1.8, "Muốn cây để bàn"),
            WeightedRegexRule("living_room", r"\bphong khach\b", 1.4, "Muốn cây cho phòng khách"),
            WeightedRegexRule("bedroom", r"\bphong ngu\b", 1.4, "Muốn cây cho phòng ngủ"),
            WeightedRegexRule("office", r"\bvan phong\b", 1.4, "Muốn cây cho văn phòng"),
        ],
    },
    "plant_care": {
        "symptom_lookup": [
            WeightedRegexRule("yellow_leaves", r"\bvang la\b", 2.4, "Triệu chứng vàng lá"),
            WeightedRegexRule("root_rot", r"\bung re\b", 2.4, "Triệu chứng úng rễ"),
            WeightedRegexRule("rotting_root", r"\bthoi re\b", 2.4, "Triệu chứng thối rễ"),
            WeightedRegexRule("wilt", r"\bheo la\b", 2.2, "Triệu chứng héo lá"),
            WeightedRegexRule("leaf_spot", r"\bdom la\b", 2.2, "Triệu chứng đốm lá"),
            WeightedRegexRule("pest_disease", r"\bsau benh\b", 2.2, "Sâu bệnh"),
            WeightedRegexRule("disease", r"\bbi benh\b", 1.8, "Cây bị bệnh"),
        ],
        "care_how_to": [
            WeightedRegexRule("why", r"\btai sao\b", 1.5, "Hỏi nguyên nhân"),
            WeightedRegexRule("how_to_fix", r"\bxu ly sao\b", 2.0, "Hỏi cách xử lý"),
            WeightedRegexRule("care", r"\bcham soc\b", 1.8, "Hỏi cách chăm sóc"),
        ],
        "watering_lookup": [
            WeightedRegexRule("watering_schedule", r"\btuoi bao lau\b", 2.4, "Hỏi lịch tưới"),
            WeightedRegexRule("watering_interval", r"\bbao lau tuoi\b", 2.4, "Hỏi chu kỳ tưới"),
            WeightedRegexRule("should_water", r"\bnen tuoi\b", 1.8, "Hỏi có nên tưới không"),
        ],
    },
    "general": {
        "greeting": [
            WeightedRegexRule("hello_vi", r"\bxin chao\b", 2.8, "Chào hỏi tiếng Việt"),
            WeightedRegexRule("hello_en", r"\bhello\b", 2.5, "Chào hỏi tiếng Anh"),
            WeightedRegexRule("hi", r"\bhi\b", 2.0, "Chào hỏi ngắn"),
        ],
        "thanks": [
            WeightedRegexRule("thanks", r"\bcam on\b", 2.4, "Người dùng cảm ơn"),
        ],
    },
}

ENTITY_SCORE_BOOSTS: dict[str, dict[str, float]] = {
    "recommendation": {
        "max_price": 0.7,
        "care_level": 0.9,
        "placement": 0.7,
        "watering_need": 0.6,
        "light_requirement": 0.6,
    },
    "product_info": {
        "pet_safe": 1.0,
        "product_name": 0.8,
    },
}

PRODUCT_INFO_DISAMBIGUATION_TOKENS = ["gia", "bao nhieu", "con hang", "ton kho", "doc", "hinh anh", "size"]


def score_intents_by_rules(text: str, entities: dict[str, Any]) -> dict[str, float]:
    scores = {intent: 0.0 for intent in ["product_info", "recommendation", "plant_care", "cart_order", "general", "unclear"]}
    for intent, groups in INTENT_RULE_GROUPS.items():
        for rules in groups.values():
            for rule in rules:
                if re.search(rule.pattern, text):
                    scores[intent] += rule.weight

    for intent, boosts in ENTITY_SCORE_BOOSTS.items():
        for entity_name, weight in boosts.items():
            if entities.get(entity_name):
                scores[intent] += weight

    if entities.get("product_name") and not any(token in text for token in PRODUCT_INFO_DISAMBIGUATION_TOKENS):
        scores["product_info"] -= 0.4

    if not any(score > 0 for intent, score in scores.items() if intent != "unclear"):
        scores["unclear"] = 1.0
    return scores
