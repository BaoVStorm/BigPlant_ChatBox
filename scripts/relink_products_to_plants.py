from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pymongo import UpdateOne

from app.config import get_settings
from app.db.mongo import get_mongo_client


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild products so each plant product links 1:1 to plants.")
    parser.add_argument("--write", action="store_true", help="Write updates to MongoDB.")
    parser.add_argument("--backup", action="store_true", help="Create backup collections before write.")
    parser.add_argument("--sample", type=int, default=10)
    args = parser.parse_args()

    settings = get_settings()
    db = get_mongo_client()[settings.mongo_db_name]

    products = list(db[settings.products_collection].find({"product_type": "plant"}).sort("sku", 1))
    plants = list(db[settings.plants_collection].find({}).sort("_id", 1))
    if len(products) != len(plants):
        raise RuntimeError(f"Expected 1:1 counts but got products={len(products)} plants={len(plants)}")

    mappings = []
    product_updates = []
    variant_updates = []
    image_updates = []
    now = datetime.now(timezone.utc)

    for position, (product, plant) in enumerate(zip(products, plants), start=1):
        common = primary_common_name(plant.get("common_name")) or plant.get("scientific_name")
        scientific = str(plant.get("scientific_name") or "").strip()
        product_name = f"{common} ({scientific})" if common and scientific and common.lower() != scientific.lower() else scientific
        slug = unique_slug(product_name, position)
        short_description = build_short_description(plant)
        description = build_product_description(plant)
        care_level = infer_care_level(plant)

        current_scientific = scientific_from_product_name(product.get("name"))
        current_common = common_from_product_name(product.get("name"))
        changed = {
            "name": product.get("name") != product_name,
            "plant_id": str(product.get("plant_id")) != str(plant.get("_id")),
            "scientific_name": normalize(current_scientific) != normalize(scientific),
            "common_name": normalize(current_common) != normalize(common),
        }
        mappings.append(
            {
                "position": position,
                "sku": product.get("sku"),
                "product_id": str(product.get("_id")),
                "old_name": product.get("name"),
                "new_name": product_name,
                "old_plant_id": str(product.get("plant_id")) if product.get("plant_id") else None,
                "new_plant_id": str(plant.get("_id")),
                "plant_scientific_name": scientific,
                "changed": changed,
            }
        )
        product_updates.append(
            UpdateOne(
                {"_id": product["_id"]},
                {
                    "$set": {
                        "plant_id": plant["_id"],
                        "name": product_name,
                        "slug": slug,
                        "short_description": short_description,
                        "description": description,
                        "care_level": care_level,
                        "updated_at": now,
                    }
                },
            )
        )

        variants = list(db[settings.product_variants_collection].find({"product_id": product["_id"]}).sort([("is_default", -1), ("price", 1)]))
        for variant in variants:
            attrs = dict(variant.get("attributes") or {})
            attrs["plant_name"] = common
            attrs["scientific_name"] = scientific
            attrs.setdefault("pot_type", "Nursery pot")
            variant_updates.append(
                UpdateOne(
                    {"_id": variant["_id"]},
                    {"$set": {"attributes": attrs, "updated_at": now}},
                )
            )

        images = list(db[settings.product_images_collection].find({"product_id": product["_id"]}).sort([("sort_order", 1)]))
        for image in images:
            variant = variants[0] if variants else None
            size = ((variant or {}).get("attributes") or {}).get("size") or "Default"
            sort_order = int(image.get("sort_order") or 0)
            image_updates.append(
                UpdateOne(
                    {"_id": image["_id"]},
                    {
                        "$set": {
                            "variant_id": (variant or {}).get("_id") or image.get("variant_id"),
                            "alt_text": f"{product_name} - {size} - ảnh {sort_order + 1}",
                        }
                    },
                )
            )

    changed_count = sum(1 for item in mappings if any(item["changed"].values()))
    print({"products": len(products), "plants": len(plants), "changed_products": changed_count})
    print("SAMPLES")
    for item in mappings[: args.sample]:
        print(item)
    print("LAST_SAMPLES")
    for item in mappings[-min(args.sample, len(mappings)) :]:
        print(item)

    if not args.write:
        print("Dry run only. Re-run with --write --backup to update MongoDB.")
        return

    if args.backup:
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        backup_collection(db, settings.products_collection, f"{settings.products_collection}_backup_before_relink_{timestamp}")
        backup_collection(db, settings.product_variants_collection, f"{settings.product_variants_collection}_backup_before_relink_{timestamp}")
        backup_collection(db, settings.product_images_collection, f"{settings.product_images_collection}_backup_before_relink_{timestamp}")

    if product_updates:
        db[settings.products_collection].bulk_write(product_updates, ordered=False)
    if variant_updates:
        db[settings.product_variants_collection].bulk_write(variant_updates, ordered=False)
    if image_updates:
        db[settings.product_images_collection].bulk_write(image_updates, ordered=False)
    print({"updated_products": len(product_updates), "updated_variants": len(variant_updates), "updated_images": len(image_updates)})


def backup_collection(db: Any, source: str, target: str) -> None:
    if target in db.list_collection_names():
        db[target].drop()
    db[source].aggregate([{"$match": {}}, {"$out": target}])
    print({"backup": target, "count": db[target].estimated_document_count()})


def primary_common_name(value: Any) -> str:
    return str(value or "").split(";")[0].strip()


def scientific_from_product_name(value: Any) -> str | None:
    match = re.search(r"\(([^()]+)\)\s*$", str(value or ""))
    return match.group(1).strip() if match else None


def common_from_product_name(value: Any) -> str:
    return re.sub(r"\s*\([^()]+\)\s*$", "", str(value or "")).strip()


def normalize(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def slugify(value: Any) -> str:
    return "-".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def unique_slug(product_name: str, position: int) -> str:
    return f"{slugify(product_name)}-plt{position:03d}"


def first_sentence(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", text)[0].strip()
    if len(sentence) <= limit:
        return sentence
    return sentence[: limit - 3].rstrip() + "..."


def build_short_description(plant: dict[str, Any]) -> str:
    return first_sentence(plant.get("uses"), 180) or first_sentence(plant.get("description"), 180) or f"Live plant: {plant.get('scientific_name')}"


def build_product_description(plant: dict[str, Any]) -> str:
    parts = [plant.get("description"), plant.get("uses"), plant.get("advantages")]
    text = "\n\n".join(str(part).strip() for part in parts if str(part or "").strip())
    return text or f"Live plant record for {plant.get('scientific_name')}."


def infer_care_level(plant: dict[str, Any]) -> str:
    text = " ".join(str(plant.get(key) or "") for key in ["description", "uses", "advantages", "safety_notes", "toxicity_warning"]).lower()
    if any(token in text for token in ["orchid", "wetland", "marsh", "consistently moist", "humid", "climbing", "vine"]):
        return "Hard"
    if any(token in text for token in ["hardy", "food", "cultivated", "common", "ornamental", "tree", "shrub"]):
        return "Moderate"
    return "Moderate"


if __name__ == "__main__":
    main()
