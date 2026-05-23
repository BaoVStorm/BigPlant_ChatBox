from __future__ import annotations

from typing import Any


def build_product_embedding_text(product: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Tên cây: {product.get('name') or ''}.",
            f"Mô tả ngắn: {product.get('short_description') or ''}.",
            f"Mô tả: {product.get('description') or ''}.",
            f"Mức chăm sóc: {product.get('care_level') or 'unknown'}.",
            f"Ánh sáng: {product.get('light_requirement') or 'unknown'}.",
            f"Nhu cầu tưới nước: {product.get('watering_need') or 'unknown'}.",
            f"Độ ẩm: {product.get('humidity_need') or 'unknown'}.",
            f"Trong nhà/ngoài trời: {product.get('indoor_outdoor') or 'unknown'}.",
            f"An toàn cho thú cưng: {pet_safe_text(product.get('pet_safe'))}.",
            f"Phù hợp đặt ở: {join_values(product.get('suitable_locations'))}.",
            f"Phù hợp cho: {join_values(product.get('suitable_for'))}.",
            f"Tags: {join_values(product.get('tags'))}.",
            f"Hướng dẫn chăm sóc: {product.get('care_guide') or {}}.",
        ]
    )


def join_values(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value or "")


def pet_safe_text(value: Any) -> str:
    if value is True:
        return "có"
    if value is False:
        return "không"
    return "không rõ"
