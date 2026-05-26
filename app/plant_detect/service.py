from __future__ import annotations

from app.plant_detect.client import BigPlantPlantDetectClient
from app.plant_detect.schemas import ChatImageInput, ImagePlantContext
from app.products.product_repository import ProductRepository, object_id_or_string_values


class PlantDetectService:
    def __init__(
        self,
        client: BigPlantPlantDetectClient | None = None,
        repository: ProductRepository | None = None,
    ) -> None:
        self.client = client or BigPlantPlantDetectClient()
        self.repository = repository or ProductRepository()

    def resolve_image_context(self, image: ChatImageInput) -> ImagePlantContext:
        detection = self.client.detect(image)
        resolved_product = None
        resolved_context = None

        if detection.success:
            resolved_product = self.repository.get_product_by_detected_plant(
                label=detection.label,
                scientific_name_search=detection.scientific_name_search,
                plant=detection.plant,
            )
            if resolved_product:
                resolved_context = self.repository.get_product_full_context(resolved_product)

        return ImagePlantContext(
            image_provided=True,
            detection=detection,
            resolved_product=resolved_product,
            resolved_product_context=resolved_context,
        )
