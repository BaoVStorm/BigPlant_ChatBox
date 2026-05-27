from __future__ import annotations

from typing import Any


def build_follow_up(intent: str, result: dict[str, Any], memory: dict[str, Any] | None = None) -> tuple[str | None, list[str]]:
    facet = ((result.get("metadata") or {}).get("facet") or {}).get("name")
    if intent == "product_info":
        return build_product_follow_up(result, facet)
    if intent == "recommendation":
        return build_recommendation_follow_up(result, memory, facet)
    if intent == "plant_care":
        return build_plant_care_follow_up(result, facet)
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


def build_product_follow_up(result: dict[str, Any], facet: str | None) -> tuple[str | None, list[str]]:
    metadata = result.get("metadata") or {}
    focus = facet or metadata.get("product_focus") or "general"
    if focus == "toxicity":
        return (
            "Bạn có muốn hỏi thêm về giá, tồn kho hoặc các lựa chọn hiện có của cây này không?",
            [
                "Giá cây này là bao nhiêu?",
                "Cây này còn hàng không?",
                "Cây này có mấy loại?",
            ],
        )
    if focus == "highlights":
        return (
            "Bạn có muốn biết thêm giá, tồn kho hoặc cây này có an toàn với thú cưng không?",
            [
                "Giá cây này là bao nhiêu?",
                "Cây này còn hàng không?",
                "Cây này có độc với mèo không?",
            ],
        )
    if focus == "overview":
        return (
            "Bạn có thể hỏi sâu hơn về giá, tồn kho, đặc điểm nổi bật hoặc độ an toàn của cây này.",
            [
                "Giá cây này là bao nhiêu?",
                "Cây này còn hàng không?",
                "Cây này có đặc điểm gì nổi bật?",
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


def build_recommendation_follow_up(result: dict[str, Any], memory: dict[str, Any] | None, facet: str | None) -> tuple[str | None, list[str]]:
    products = result.get("products") or []
    top_name = products[0].get("name") if products else "cây này"
    preferences = (memory or {}).get("preferences") or {}

    if facet == "generic" and not preferences.get("budget_input_amount"):
        return (
            "Mình có thể tư vấn sát hơn nếu bạn cho mình thêm khoảng ngân sách mong muốn.",
            [
                "Tôi muốn cây dưới 400K.",
                "Tôi muốn cây dưới $20.",
                "Ưu tiên cây dễ chăm cho người mới.",
            ],
        )

    return (
        "Nếu bạn muốn, mình có thể lọc kỹ hơn theo ngân sách, mức dễ chăm, độ an toàn với thú cưng hoặc không gian đặt cây.",
        [
            "Có cây nào rẻ hơn không?",
            f"{top_name} còn hàng không?",
            f"{top_name} có độc với mèo không?",
        ],
    )


def build_plant_care_follow_up(result: dict[str, Any], facet: str | None) -> tuple[str | None, list[str]]:
    if facet == "watering_schedule":
        return (
            "Nếu bạn muốn, mình có thể gợi ý thêm về ánh sáng, đất trồng hoặc dấu hiệu cần tưới của cây này.",
            [
                "Cây này cần nhiều ánh sáng không?",
                "Lá cây bị vàng thì nên làm gì?",
                "Cây này hợp trồng trong nhà không?",
            ],
        )
    return (
        "Nếu bạn muốn, hãy mô tả thêm tình trạng lá, rễ, ánh sáng hoặc tần suất tưới để mình gợi ý sát hơn.",
        [
            "Lá cây bị vàng thì nên làm gì?",
            "Cây này tưới bao lâu một lần?",
            "Cây này cần nhiều ánh sáng không?",
        ],
    )
