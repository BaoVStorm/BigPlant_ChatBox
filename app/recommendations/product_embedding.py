from __future__ import annotations

from typing import Any


def build_product_embedding_text(context: dict[str, Any]) -> str:
    product = context.get("product") or context
    category = context.get("category") or {}
    plant = context.get("plant") or {}
    profile = context.get("plant_profile") or {}
    care_profile = profile.get("care_profile") or {}
    safety_profile = profile.get("safety_profile") or {}
    recommendation_profile = profile.get("recommendation_profile") or {}
    variants = context.get("variants") or []

    return "\n".join(
        [
            f"Tên sản phẩm: {product.get('name') or ''}.",
            f"SKU: {product.get('sku') or ''}.",
            f"Loại sản phẩm: {product.get('product_type') or ''}.",
            f"Danh mục: {category.get('name') or ''}.",
            f"Mô tả ngắn: {product.get('short_description') or ''}.",
            f"Mô tả sản phẩm: {product.get('description') or ''}.",
            f"Mức chăm sóc: {product.get('care_level') or 'unknown'}.",
            f"Tên khoa học: {plant.get('scientific_name') or ''}.",
            f"Tên thường gọi: {plant.get('common_name') or ''}.",
            f"Họ thực vật: {plant.get('family') or ''}.",
            f"Chi/loài: {plant.get('genus') or ''} {plant.get('species') or ''}.",
            f"Mô tả cây: {plant.get('description') or ''}.",
            f"Công dụng: {plant.get('uses') or ''}.",
            f"Ưu điểm: {plant.get('advantages') or ''}.",
            f"Cảnh báo độc tính: {plant.get('toxicity_warning') or ''}.",
            f"Ghi chú an toàn: {plant.get('safety_notes') or ''}.",
            f"Mức bằng chứng: {plant.get('evidence_level') or ''}.",
            f"Nhu cầu ánh sáng: {care_profile.get('light_requirement') or ''}.",
            f"Nhu cầu tưới: {care_profile.get('watering_need') or ''}.",
            f"Vị trí phù hợp: {', '.join(care_profile.get('placement_tags') or [])}.",
            f"Độ an toàn thú cưng: {safety_profile.get('pet_safe')}.",
            f"Mức độc tính: {safety_profile.get('toxicity_level') or ''}.",
            f"Trường hợp phù hợp: {', '.join(recommendation_profile.get('good_if') or [])}.",
            f"Nên tránh nếu: {', '.join(recommendation_profile.get('avoid_if') or [])}.",
            f"Biến thể: {build_variant_text(variants)}.",
        ]
    )


def build_variant_text(variants: list[dict[str, Any]]) -> str:
    values = []
    for variant in variants:
        values.append(
            " ".join(
                [
                    str(variant.get("variant_name") or ""),
                    str(variant.get("variant_sku") or ""),
                    stringify_attributes(variant.get("attributes")),
                ]
            ).strip()
        )
    return "; ".join(value for value in values if value)


def stringify_attributes(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}: {item}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value or "")
