from __future__ import annotations

from typing import Any


def build_follow_up(intent: str, result: dict[str, Any], memory: dict[str, Any] | None = None) -> tuple[str | None, list[str]]:
    if intent == "product_info":
        return build_product_follow_up(result)
    if intent == "recommendation":
        return build_recommendation_follow_up(result)
    if intent == "plant_care":
        return build_plant_care_follow_up(result)
    if intent == "general":
        return (
            "Bạn có thể hỏi tiếp về giá, tồn kho, độc tính, hoặc nhờ mình tư vấn chọn cây phù hợp hơn.",
            [
                "Cây dễ chăm dưới 400K là gì?",
                "Cây này còn hàng không?",
                "Cây này có độc với mèo không?",
            ],
        )
    if intent == "cart_order":
        return (
            "Nếu bạn muốn mua ngay, bước tiếp theo là kết nối app với giỏ hàng hoặc checkout.",
            [
                "Cây này còn hàng không?",
                "Giá cây này là bao nhiêu?",
            ],
        )
    return (
        "Bạn có thể hỏi rõ hơn tên cây, giá, tồn kho, hoặc nhu cầu tư vấn để mình hỗ trợ đúng hơn.",
        [
            "Giá cây này là bao nhiêu?",
            "Cây này còn hàng không?",
            "Tư vấn giúp tôi cây dễ chăm.",
        ],
    )


def build_product_follow_up(result: dict[str, Any]) -> tuple[str | None, list[str]]:
    metadata = result.get("metadata") or {}
    focus = metadata.get("product_focus") or "general"
    if focus == "toxicity":
        return (
            "Bạn có muốn hỏi thêm về giá, tồn kho hoặc các lựa chọn hiện có của cây này không?",
            [
                "Giá cây này là bao nhiêu?",
                "Cây này còn hàng không?",
                "Cây này có mấy loại?",
            ],
        )
    if focus == "stock":
        return (
            "Bạn có muốn biết thêm giá hiện tại hoặc độ an toàn của cây này với thú cưng không?",
            [
                "Giá cây này là bao nhiêu?",
                "Cây này có độc với mèo không?",
                "Cây này có mấy loại?",
            ],
        )
    if focus == "price":
        return (
            "Bạn có muốn xem tồn kho hiện tại hoặc hỏi thêm về độ an toàn của cây này không?",
            [
                "Cây này còn hàng không?",
                "Cây này có độc với mèo không?",
                "Cây này có mấy loại?",
            ],
        )
    if focus == "variant":
        return (
            "Bạn có muốn biết thêm giá, tồn kho hoặc độc tính của cây này không?",
            [
                "Giá cây này là bao nhiêu?",
                "Cây này còn hàng không?",
                "Cây này có độc với mèo không?",
            ],
        )
    return (
        "Bạn có muốn biết thêm giá, tồn kho, độc tính hoặc các lựa chọn hiện có của cây này không?",
        [
            "Giá cây này là bao nhiêu?",
            "Cây này còn hàng không?",
            "Cây này có độc với mèo không?",
        ],
    )


def build_recommendation_follow_up(result: dict[str, Any]) -> tuple[str | None, list[str]]:
    products = result.get("products") or []
    top_name = products[0].get("name") if products else "cây này"
    return (
        "Nếu bạn muốn, mình có thể lọc kỹ hơn theo ngân sách, mức dễ chăm, độ an toàn với thú cưng hoặc không gian đặt cây.",
        [
            "Có cây nào rẻ hơn không?",
            f"{top_name} còn hàng không?",
            f"{top_name} có độc với mèo không?",
        ],
    )


def build_plant_care_follow_up(result: dict[str, Any]) -> tuple[str | None, list[str]]:
    return (
        "Nếu bạn muốn, hãy mô tả thêm tình trạng lá, rễ, ánh sáng hoặc tần suất tưới để mình gợi ý sát hơn.",
        [
            "Lá cây bị vàng thì nên làm gì?",
            "Cây này tưới bao lâu một lần?",
            "Cây này cần nhiều ánh sáng không?",
        ],
    )
