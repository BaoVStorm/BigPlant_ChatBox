from __future__ import annotations

import json
from typing import Any

from app.llm.local_llm import LocalLLM
from app.llm.prompts import PRODUCT_INFO_PROMPT
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
                "message": "Bạn muốn hỏi thông tin của cây nào? Mình cần tên cây để kiểm tra giá, size và tồn kho trong hệ thống.",
                "products": [],
                "sources": [],
                "metadata": {"route": route.model_dump()},
            }

        product_id = str(product.get("_id"))
        variants = self.repository.get_product_variants(product_id)
        images = self.repository.get_product_images(product_id)

        prompt = PRODUCT_INFO_PROMPT.format(
            message=message,
            product_json=json.dumps(product, ensure_ascii=False, default=str),
            variants_json=json.dumps(variants, ensure_ascii=False, default=str),
            images_json=json.dumps(images, ensure_ascii=False, default=str),
        )

        answer = None
        llm_used = False
        if self.llm.is_available:
            try:
                answer = self.llm.generate(prompt)
                llm_used = True
            except Exception:
                answer = None
        if not answer:
            answer = build_product_answer(product, variants)

        return {
            "intent": "product_info",
            "message": answer,
            "products": [build_product_card(product, variants, images)],
            "sources": [],
            "metadata": {"route": route.model_dump(), "llm_used": llm_used},
        }


def build_product_answer(product: dict[str, Any], variants: list[dict[str, Any]]) -> str:
    name = product.get("name") or "Sản phẩm này"
    price = format_price_range(product, variants)
    stock = sum(int(variant.get("stock") or 0) for variant in variants)
    lines = [f"{name} hiện có giá {price}."]
    if variants:
        sizes = ", ".join(str(variant.get("size") or variant.get("sku") or "variant") for variant in variants[:5])
        lines.append(f"Các lựa chọn hiện có: {sizes}.")
        lines.append(f"Tổng tồn kho theo biến thể: {stock}.")
    else:
        lines.append("Hiện chưa có dữ liệu biến thể/tồn kho cho sản phẩm này.")
    if "pet_safe" in product:
        lines.append("Sản phẩm này an toàn cho thú cưng." if product.get("pet_safe") else "Sản phẩm này không được đánh dấu là an toàn cho thú cưng.")
    return " ".join(lines)


def build_product_card(product: dict[str, Any], variants: list[dict[str, Any]], images: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": product.get("_id"),
        "name": product.get("name"),
        "slug": product.get("slug"),
        "price": format_price_range(product, variants),
        "price_min": product.get("price_min"),
        "price_max": product.get("price_max"),
        "variants": variants,
        "images": images,
    }


def format_price_range(product: dict[str, Any], variants: list[dict[str, Any]] | None = None) -> str:
    variants = variants or []
    prices = [int(item["price"]) for item in variants if item.get("price") is not None]
    if prices:
        min_price, max_price = min(prices), max(prices)
    else:
        min_price = product.get("price_min")
        max_price = product.get("price_max") or product.get("price_min")
    if min_price is None:
        return "chưa có dữ liệu giá"
    if max_price is None or int(min_price) == int(max_price):
        return f"{int(min_price):,}đ".replace(",", ".")
    return f"{int(min_price):,}đ - {int(max_price):,}đ".replace(",", ".")
