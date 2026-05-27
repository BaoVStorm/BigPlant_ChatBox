from __future__ import annotations

from app.llm.local_llm import LocalLLM
from app.plant_detect.schemas import ImagePlantContext
from app.products.product_repository import ProductRepository
from app.products.question_focus import (
    contains_negative_toxicity_signal,
    contains_positive_toxicity_signal,
    detect_product_question_focus,
)
from app.router.schemas import IntentRoute


class ProductInfoHandler:
    def __init__(self, repository: ProductRepository | None = None, llm: LocalLLM | None = None) -> None:
        self.repository = repository or ProductRepository()
        self.llm = llm or LocalLLM()

    def handle(
        self,
        message: str,
        route: IntentRoute,
        image_context: ImagePlantContext | None = None,
        memory: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        product_name = str(route.entities.get("product_name") or "").strip()
        context = image_context.resolved_product_context if image_context and image_context.resolved_product_context else None

        if not context and memory and (active_subject := memory.get("active_subject")):
            if active_subject.get("subject_type") == "product" and active_subject.get("product_id"):
                context = self.repository.get_product_full_context(active_subject.get("product_id"))

        product = self.repository.get_product_by_name(product_name) if product_name and not context else None
        if not product and not context:
            product = self.repository.find_product_mentioned(message)

        if not product and not context:
            return {
                "intent": "product_info",
                "message": "Bạn muốn hỏi thông tin của cây nào? Mình cần tên cây để kiểm tra giá, size, tồn kho hoặc thông tin an toàn trong hệ thống.",
                "products": [],
                "sources": [],
                "metadata": {"route": route.model_dump()},
            }

        if not context:
            context = self.repository.get_product_full_context(product)
        if not context:
            return {
                "intent": "product_info",
                "message": "Mình tìm thấy tên cây nhưng chưa tải được dữ liệu sản phẩm chi tiết. Bạn thử lại sau nhé.",
                "products": [],
                "sources": [],
                "metadata": {"route": route.model_dump()},
            }

        focus = detect_product_question_focus(message, route.entities)
        answer = build_product_answer(context, message, route.entities)
        llm_used = False

        return {
            "intent": "product_info",
            "message": answer,
            "products": [build_product_card(context)],
            "sources": [],
            "metadata": {
                "route": route.model_dump(),
                "llm_used": llm_used,
                "image_assisted": bool(image_context and image_context.resolved_product_context),
                "product_focus": focus,
                "context_assisted": bool(memory and memory.get("active_subject") and not image_context),
            },
        }


def build_product_answer(context: dict[str, Any], message: str, entities: dict[str, Any]) -> str:
    product = context.get("product") or {}
    plant = context.get("plant") or {}
    variants = context.get("variants") or []
    computed = context.get("computed") or {}
    focus = detect_product_question_focus(message, entities)

    name = product.get("name") or "Sản phẩm này"

    if focus == "toxicity":
        return build_toxicity_answer(name, plant)
    if focus == "highlights":
        return build_highlights_answer(name, product, plant, computed)

    lines = []
    if focus in {"price", "stock", "variant", "image", "general"}:
        lines.append(f"{name} hiện có giá {computed.get('price_text') or 'chưa có dữ liệu giá'}.")

    if variants and focus in {"variant", "general", "price"}:
        variant_names = ", ".join(str(variant.get("variant_name") or variant.get("variant_sku") or "biến thể") for variant in variants[:5])
        lines.append(f"Các lựa chọn hiện có: {variant_names}.")
    elif not variants and focus in {"variant", "general", "price"}:
        lines.append("Hiện chưa có dữ liệu biến thể cho sản phẩm này.")

    if computed.get("has_inventory") and focus in {"stock", "general", "price"}:
        available_qty = int(computed.get("available_qty") or 0)
        lines.append(f"Tổng tồn kho có thể bán: {available_qty}.")
    elif focus in {"stock", "general", "price"}:
        lines.append("Hiện chưa có dữ liệu tồn kho cho sản phẩm này.")

    toxicity_warning = plant.get("toxicity_warning")
    safety_notes = plant.get("safety_notes")
    if (toxicity_warning or safety_notes) and focus == "general":
        lines.append(f"Lưu ý an toàn: {toxicity_warning or safety_notes}.")

    return " ".join(lines)


def build_highlights_answer(name: str, product: dict[str, Any], plant: dict[str, Any], computed: dict[str, Any]) -> str:
    parts = [f"{name} có một vài điểm nổi bật trong dữ liệu hiện tại."]

    short_description = str(product.get("short_description") or "").strip()
    if short_description:
        parts.append(short_description)

    plant_description = str(plant.get("description") or "").strip()
    if plant_description:
        parts.append(plant_description.split(".")[0].strip() + ".")

    advantages = str(plant.get("advantages") or "").strip()
    if advantages:
        parts.append("Ưu điểm nổi bật: " + advantages.split(".")[0].strip() + ".")

    if computed.get("price_text"):
        parts.append(f"Giá hiện tại đang ở mức {computed.get('price_text')}.")

    return " ".join(part for part in parts if part)


def build_toxicity_answer(name: str, plant: dict[str, Any]) -> str:
    toxicity_warning = str(plant.get("toxicity_warning") or "").strip()
    safety_notes = str(plant.get("safety_notes") or "").strip()
    toxicity_text = f"{toxicity_warning} {safety_notes}".strip().lower()

    if not toxicity_warning and not safety_notes:
        return f"Mình chưa có dữ liệu độc tính hoặc độ an toàn với thú cưng của {name} trong hệ thống hiện tại."

    if contains_negative_toxicity_signal(toxicity_text):
        return f"Theo dữ liệu cây nền trong hệ thống, {name} có cảnh báo độc tính và không nên xem là an toàn cho mèo/chó hoặc thú cưng. Lưu ý: {toxicity_warning or safety_notes}"

    if contains_positive_toxicity_signal(toxicity_text):
        return f"Theo dữ liệu hiện tại trong hệ thống, {name} không có cảnh báo độc tính rõ ràng và có thể xem là tương đối an toàn cho thú cưng."

    return f"Theo dữ liệu cây nền trong hệ thống, {name} có ghi chú an toàn nhưng chưa đủ để khẳng định là hoàn toàn an toàn cho mèo/chó. Lưu ý: {toxicity_warning or safety_notes}"


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
    from app.config import get_settings

    settings = get_settings()
    if settings.catalog_price_currency.upper() == "USD":
        return f"{float(value):.2f} USD"
    if float(value).is_integer():
        number = f"{int(value):,}".replace(",", ".")
    else:
        number = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{number} VND"
