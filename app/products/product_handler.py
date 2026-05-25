from __future__ import annotations

from typing import Any

from app.llm.local_llm import LocalLLM
from app.products.product_repository import ProductRepository
from app.router.schemas import IntentRoute


class ProductInfoHandler:
    def __init__(self, repository: ProductRepository | None = None, llm: LocalLLM | None = None) -> None:
        self.repository = repository or ProductRepository()
        self.llm = llm or LocalLLM()

    def handle(self, message: str, route: IntentRoute) -> dict[str, Any]:
        product_name = str(route.entities.get("product_name") or "").strip()
        product = self.repository.get_product_by_name(product_name) if product_name else None
        if not product:
            product = self.repository.find_product_mentioned(message)

        if not product:
            return {
                "intent": "product_info",
                "message": "Bạn muốn hỏi thông tin của cây nào? Mình cần tên cây để kiểm tra giá, size, tồn kho hoặc thông tin an toàn trong hệ thống.",
                "products": [],
                "sources": [],
                "metadata": {"route": route.model_dump()},
            }

        context = self.repository.get_product_full_context(product)
        if not context:
            return {
                "intent": "product_info",
                "message": "Mình tìm thấy tên cây nhưng chưa tải được dữ liệu sản phẩm chi tiết. Bạn thử lại sau nhé.",
                "products": [],
                "sources": [],
                "metadata": {"route": route.model_dump()},
            }

        answer = build_product_answer(context)
        llm_used = False

        return {
            "intent": "product_info",
            "message": answer,
            "products": [build_product_card(context)],
            "sources": [],
            "metadata": {"route": route.model_dump(), "llm_used": llm_used},
        }


def build_product_answer(context: dict[str, Any]) -> str:
    product = context.get("product") or {}
    plant = context.get("plant") or {}
    variants = context.get("variants") or []
    computed = context.get("computed") or {}

    name = product.get("name") or "Sản phẩm này"
    lines = [f"{name} hiện có giá {computed.get('price_text') or 'chưa có dữ liệu giá'}."]

    if variants:
        variant_names = ", ".join(str(variant.get("variant_name") or variant.get("variant_sku") or "biến thể") for variant in variants[:5])
        lines.append(f"Các lựa chọn hiện có: {variant_names}.")
    else:
        lines.append("Hiện chưa có dữ liệu biến thể cho sản phẩm này.")

    if computed.get("has_inventory"):
        available_qty = int(computed.get("available_qty") or 0)
        lines.append(f"Tổng tồn kho có thể bán: {available_qty}.")
    else:
        lines.append("Hiện chưa có dữ liệu tồn kho cho sản phẩm này.")

    toxicity_warning = plant.get("toxicity_warning")
    safety_notes = plant.get("safety_notes")
    if toxicity_warning or safety_notes:
        lines.append(f"Lưu ý an toàn: {toxicity_warning or safety_notes}.")

    return " ".join(lines)


def build_product_card(context: dict[str, Any]) -> dict[str, Any]:
    product = context.get("product") or {}
    category = context.get("category") or {}
    plant = context.get("plant") or {}
    computed = context.get("computed") or {}
    return {
        "id": product.get("_id"),
        "name": product.get("name"),
        "slug": product.get("slug"),
        "sku": product.get("sku"),
        "category": {"name": category.get("name"), "slug": category.get("slug")} if category else None,
        "plant": {
            "scientific_name": plant.get("scientific_name"),
            "common_name": plant.get("common_name"),
            "toxicity_warning": plant.get("toxicity_warning"),
            "safety_notes": plant.get("safety_notes"),
        }
        if plant
        else None,
        "price": computed.get("price_text"),
        "price_min": computed.get("price_min"),
        "price_max": computed.get("price_max"),
        "available_qty": computed.get("available_qty"),
        "in_stock": computed.get("in_stock"),
        "primary_image_url": computed.get("primary_image_url"),
        "variants": context.get("variants") or [],
        "images": context.get("images") or [],
    }


def format_price_range(product_or_context: dict[str, Any], variants: list[dict[str, Any]] | None = None) -> str:
    computed = product_or_context.get("computed") or {}
    if computed.get("price_text"):
        return computed["price_text"]

    variants = variants or product_or_context.get("variants") or []
    prices = [float(item["price"]) for item in variants if item.get("price") is not None]
    if not prices:
        return "chưa có dữ liệu giá"
    min_price, max_price = min(prices), max(prices)
    if float(min_price) == float(max_price):
        return format_number(min_price)
    return f"{format_number(min_price)} - {format_number(max_price)}"


def format_number(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}".replace(",", ".")
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
