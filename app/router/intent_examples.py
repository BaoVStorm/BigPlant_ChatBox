from __future__ import annotations


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
