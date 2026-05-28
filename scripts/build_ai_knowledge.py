from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bson import ObjectId
from pymongo import UpdateOne

from app.config import get_settings
from app.db.mongo import get_database
from app.embeddings.embedding_service import EmbeddingService
from app.knowledge.chunking import split_text


PROFILE_COLLECTION = "plant_profiles"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build AI-ready plant profiles and knowledge chunks from products/plants.")
    parser.add_argument("--write", action="store_true", help="Write generated documents to MongoDB.")
    parser.add_argument("--skip-embeddings", action="store_true", help="Do not create chunk embeddings.")
    parser.add_argument("--sample", type=int, default=3, help="Number of sample docs to print.")
    args = parser.parse_args()

    settings = get_settings()
    db = get_database()

    products = list(db[settings.products_collection].find({"product_type": "plant"}).sort("sku", 1))
    plants = list(db[settings.plants_collection].find({}))
    variants_by_product = group_by(db[settings.product_variants_collection].find({}), "product_id")
    inventory_by_variant = {str(doc.get("variant_id")): doc for doc in db[settings.variant_inventory_collection].find({})}
    images_by_product = group_by(db[settings.product_images_collection].find({}), "product_id")

    profiles = build_profiles(products, plants, variants_by_product, inventory_by_variant, images_by_product)
    articles = [build_article(profile) for profile in profiles]
    chunks = build_chunks(articles, settings.embedding_model_name, skip_embeddings=args.skip_embeddings)

    report = build_report(products, plants, profiles, articles, chunks)
    print_report(report)
    print_samples(profiles, articles, chunks, args.sample)

    if not args.write:
        print("Dry run only. Re-run with --write to upsert MongoDB collections.")
        return

    upsert_documents(db[PROFILE_COLLECTION], profiles)
    upsert_documents(db[settings.knowledge_articles_collection], articles)
    upsert_documents(db[settings.knowledge_chunks_collection], chunks)
    ensure_indexes(db, settings)
    print("Wrote MongoDB collections:", PROFILE_COLLECTION, settings.knowledge_articles_collection, settings.knowledge_chunks_collection)


def build_profiles(
    products: list[dict[str, Any]],
    plants: list[dict[str, Any]],
    variants_by_product: dict[str, list[dict[str, Any]]],
    inventory_by_variant: dict[str, dict[str, Any]],
    images_by_product: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    now = now_utc()
    plant_by_id = {str(plant.get("_id")): plant for plant in plants}
    plant_by_search = {normalize_search(plant.get("scientific_name")): plant for plant in plants if plant.get("scientific_name")}
    products_by_search: dict[str, list[dict[str, Any]]] = {}
    product_context_by_id: dict[str, dict[str, Any]] = {}

    for product in products:
        product_id = str(product["_id"])
        variants = variants_by_product.get(product_id, [])
        product_context = {
            "product": product,
            "variants": variants,
            "inventory": [inventory_by_variant.get(str(variant.get("_id"))) for variant in variants],
            "images": images_by_product.get(product_id, []),
        }
        product_context_by_id[product_id] = product_context

        scientific_name = product_scientific_name(product, variants)
        search_key = normalize_search(scientific_name or product.get("name"))
        products_by_search.setdefault(search_key, []).append(product_context)

    profiles_by_key: dict[str, dict[str, Any]] = {}
    matched_plant_ids: set[str] = set()

    for search_key, contexts in products_by_search.items():
        resolved_plant = plant_by_search.get(search_key)
        if resolved_plant:
            matched_plant_ids.add(str(resolved_plant["_id"]))

        primary_context = contexts[0]
        primary_product = primary_context["product"]
        profile = build_profile_doc(
            profile_key=search_key,
            product_contexts=contexts,
            plant=resolved_plant,
            product_plant_id_doc=plant_by_id.get(str(primary_product.get("plant_id"))),
            now=now,
        )
        profiles_by_key[search_key] = profile

    for plant in plants:
        plant_id = str(plant["_id"])
        if plant_id in matched_plant_ids:
            continue
        search_key = normalize_search(plant.get("scientific_name"))
        if search_key in profiles_by_key:
            continue
        profiles_by_key[search_key] = build_profile_doc(
            profile_key=search_key,
            product_contexts=[],
            plant=plant,
            product_plant_id_doc=None,
            now=now,
        )

    return sorted(profiles_by_key.values(), key=lambda item: item["scientific_name_search"])


def build_profile_doc(
    profile_key: str,
    product_contexts: list[dict[str, Any]],
    plant: dict[str, Any] | None,
    product_plant_id_doc: dict[str, Any] | None,
    now: datetime,
) -> dict[str, Any]:
    products = [context["product"] for context in product_contexts]
    primary_product = products[0] if products else None
    variants = [variant for context in product_contexts for variant in context["variants"]]
    inventories = [item for context in product_contexts for item in context["inventory"] if item]
    images = [image for context in product_contexts for image in context["images"]]

    scientific_name = (
        plant.get("scientific_name")
        if plant
        else product_scientific_name(primary_product or {}, variants)
        or title_from_search(profile_key)
    )
    common_name = plant.get("common_name") if plant else common_name_from_product(primary_product)
    text = combined_text(plant, primary_product)
    product_link_status = link_status(primary_product, plant, product_plant_id_doc)
    care_profile = infer_care_profile(text, primary_product, plant)
    safety_profile = infer_safety_profile(text, plant)
    recommendation_profile = infer_recommendation_profile(text, primary_product, care_profile, safety_profile)
    product_summary = build_product_summary(products, variants, inventories, images)
    data_quality = build_data_quality(product_link_status, plant, primary_product, care_profile, safety_profile)

    profile_id = f"plant_profile:{profile_key}"
    return {
        "_id": profile_id,
        "profile_key": profile_key,
        "scientific_name": scientific_name,
        "scientific_name_search": profile_key,
        "common_name": common_name,
        "plant_id": plant.get("_id") if plant else None,
        "product_ids": [product["_id"] for product in products],
        "primary_product_id": primary_product.get("_id") if primary_product else None,
        "product_skus": [product.get("sku") for product in products if product.get("sku")],
        "link_status": product_link_status,
        "taxonomy": build_taxonomy(plant),
        "care_profile": care_profile,
        "safety_profile": safety_profile,
        "recommendation_profile": recommendation_profile,
        "product_summary": product_summary,
        "source_facts": build_source_facts(plant, primary_product),
        "data_quality": data_quality,
        "created_at": now,
        "updated_at": now,
    }


def build_article(profile: dict[str, Any]) -> dict[str, Any]:
    now = now_utc()
    topics = article_topics(profile)
    slug = slugify(profile["scientific_name"])
    article_id = f"plant_article:{profile['scientific_name_search']}"
    content = build_article_content(profile)
    return {
        "_id": article_id,
        "profile_id": profile["_id"],
        "plant_id": profile.get("plant_id"),
        "product_ids": profile.get("product_ids") or [],
        "title": f"{profile['scientific_name']} AI care and safety profile",
        "slug": slug,
        "content": content,
        "topics": topics,
        "related_plants": [profile["scientific_name_search"], slug],
        "source_type": "generated_from_bigplant_products_and_plants",
        "source_facts": profile.get("source_facts"),
        "data_quality": profile.get("data_quality"),
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }


def build_chunks(articles: list[dict[str, Any]], embedding_model_name: str, skip_embeddings: bool) -> list[dict[str, Any]]:
    now = now_utc()
    chunk_inputs: list[tuple[dict[str, Any], int, str]] = []
    for article in articles:
        for index, content in enumerate(split_text(article["content"], chunk_size=420, overlap=60)):
            chunk_inputs.append((article, index, content))

    embeddings: list[list[float] | None]
    if skip_embeddings:
        embeddings = [None] * len(chunk_inputs)
    else:
        service = EmbeddingService()
        texts = [content for _, _, content in chunk_inputs]
        embeddings = service.embed_texts(texts) if texts else []

    chunks: list[dict[str, Any]] = []
    for (article, index, content), embedding in zip(chunk_inputs, embeddings):
        article_id = article["_id"]
        chunk_id = stable_chunk_id(article_id, index)
        doc = {
            "_id": chunk_id,
            "article_id": article_id,
            "chunk_index": index,
            "title": article["title"],
            "content": content,
            "embedding_model": embedding_model_name if embedding is not None else None,
            "metadata": {
                "profile_id": article["profile_id"],
                "plant_id": article.get("plant_id"),
                "product_ids": article.get("product_ids") or [],
                "topics": article.get("topics") or [],
                "related_plants": article.get("related_plants") or [],
                "source_type": article.get("source_type"),
                "slug": article.get("slug"),
            },
            "created_at": now,
            "updated_at": now,
        }
        if embedding is not None:
            doc["embedding"] = embedding
        chunks.append(doc)
    return chunks


def infer_care_profile(text: str, product: dict[str, Any] | None, plant: dict[str, Any] | None) -> dict[str, Any]:
    lowered = text.lower()
    care_level_raw = (product or {}).get("care_level")
    care_level = normalize_care_level(care_level_raw)

    light_requirement, light_confidence, light_evidence = infer_light(lowered)
    watering_need, watering_confidence, watering_evidence = infer_watering(lowered)
    soil_type, soil_confidence, soil_evidence = infer_soil(lowered)
    humidity_need, humidity_confidence, humidity_evidence = infer_humidity(lowered)
    placement_tags = infer_placement_tags(lowered, product)
    indoor_score = infer_indoor_score(lowered, placement_tags)

    care_summary = summarize_care(care_level, light_requirement, watering_need, soil_type, humidity_need)
    return {
        "care_level": care_level,
        "care_level_source": "products.care_level" if care_level_raw else "inferred_default",
        "light_requirement": light_requirement,
        "watering_need": watering_need,
        "soil_type": soil_type,
        "humidity_need": humidity_need,
        "indoor_score": indoor_score,
        "placement_tags": placement_tags,
        "beginner_friendly": care_level == "easy",
        "container_friendly": bool(any(token in lowered for token in ["container", "pot", "planter", "houseplant", "windows"])),
        "care_summary": care_summary,
        "evidence": {
            "light": light_evidence,
            "watering": watering_evidence,
            "soil": soil_evidence,
            "humidity": humidity_evidence,
        },
        "confidence": round(avg([light_confidence, watering_confidence, soil_confidence, humidity_confidence, 0.9 if care_level_raw else 0.45]), 2),
    }


def infer_safety_profile(text: str, plant: dict[str, Any] | None) -> dict[str, Any]:
    lowered = text.lower()
    severe_patterns = [
        "highly toxic",
        "life-threatening",
        "fatal",
        "poison",
        "abrin",
        "cardiac glycoside",
        "human poisoning",
        "livestock poisoning",
        "cyanide",
    ]
    moderate_patterns = ["potentially toxic", "toxic if ingested", "toxicity concern", "not recommended for self-medication", "safety concern"]
    mild_patterns = ["irritant", "skin irritation", "allergy", "caution"]
    safe_patterns = ["non-toxic", "safe for pets", "pet safe"]

    if has_any(lowered, severe_patterns):
        toxicity_level = "severe"
        pet_safe = False
        child_safe = False
        confidence = 0.92
    elif has_any(lowered, moderate_patterns):
        toxicity_level = "moderate"
        pet_safe = False
        child_safe = False
        confidence = 0.76
    elif has_any(lowered, mild_patterns):
        toxicity_level = "mild"
        pet_safe = "unknown"
        child_safe = "unknown"
        confidence = 0.62
    elif has_any(lowered, safe_patterns):
        toxicity_level = "none"
        pet_safe = True
        child_safe = True
        confidence = 0.72
    else:
        toxicity_level = "unknown"
        pet_safe = "unknown"
        child_safe = "unknown"
        confidence = 0.4

    edible_context = infer_edible_context(lowered)
    medicinal_policy = "do_not_present_as_treatment" if has_any(lowered, ["traditional medicine", "medicinal", "clinical", "self-medication"]) else "not_applicable"
    summary = summarize_safety(toxicity_level, pet_safe, edible_context, medicinal_policy, plant)
    return {
        "toxicity_level": toxicity_level,
        "pet_safe": pet_safe,
        "child_safe": child_safe,
        "edible_context": edible_context,
        "medicinal_claim_policy": medicinal_policy,
        "safety_summary": summary,
        "confidence": confidence,
        "evidence": {
            "toxicity_warning": (plant or {}).get("toxicity_warning"),
            "safety_notes": (plant or {}).get("safety_notes"),
            "evidence_level": (plant or {}).get("evidence_level"),
        },
    }


def infer_recommendation_profile(
    text: str,
    product: dict[str, Any] | None,
    care_profile: dict[str, Any],
    safety_profile: dict[str, Any],
) -> dict[str, Any]:
    lowered = text.lower()
    use_cases: list[str] = []
    style_tags: list[str] = []
    avoid_if: list[str] = []
    good_if: list[str] = []

    add_if(use_cases, "houseplant", has_any(lowered, ["houseplant", "indoor", "room", "windows"]))
    add_if(use_cases, "culinary_herb", has_any(lowered, ["culinary", "kitchen", "edible", "fruit", "food", "tea", "aromatic herb"]))
    add_if(use_cases, "ornamental", has_any(lowered, ["ornamental", "flowers", "foliage", "display", "decor"]))
    add_if(use_cases, "medicinal_study_collection", has_any(lowered, ["traditional medicine", "medicinal", "ethnobotanical"]))
    add_if(use_cases, "pollinator_garden", has_any(lowered, ["pollinator", "flowers", "garden beds"]))
    add_if(use_cases, "water_edge", has_any(lowered, ["wetland", "water-edge", "pond", "marsh"]))

    add_if(style_tags, "aromatic", has_any(lowered, ["aromatic", "fragrant", "scent"]))
    add_if(style_tags, "flowering", has_any(lowered, ["flowers", "flowering", "blooms"]))
    add_if(style_tags, "foliage", has_any(lowered, ["leaves", "foliage", "fan-shaped", "rosette"]))
    add_if(style_tags, "succulent", has_any(lowered, ["succulent", "fleshy"]))
    add_if(style_tags, "tree_or_shrub", has_any(lowered, ["tree", "shrub"]))
    add_if(style_tags, "tropical", has_any(lowered, ["tropical", "warm", "humid"]))
    add_if(style_tags, "compact", has_any(lowered, ["compact", "small", "desk", "planter"]))

    if safety_profile["pet_safe"] is False:
        avoid_if.append("homes_with_pets_or_small_children")
    if care_profile["light_requirement"] in {"full_sun", "bright_outdoor"}:
        avoid_if.append("low_light_rooms")
    if care_profile["watering_need"] == "low":
        avoid_if.append("users_who_tend_to_overwater")
    if care_profile["watering_need"] == "high":
        avoid_if.append("users_who_forget_watering")

    if care_profile["beginner_friendly"]:
        good_if.append("beginner_or_low_maintenance_preference")
    if care_profile["indoor_score"] >= 0.65:
        good_if.append("indoor_or_desk_display")
    if care_profile["watering_need"] == "low":
        good_if.append("busy_user_or_infrequent_watering")
    if care_profile["light_requirement"] == "low_to_indirect":
        good_if.append("limited_direct_sunlight")

    return {
        "use_cases": sorted(set(use_cases)) or ["general_plant_collection"],
        "style_tags": sorted(set(style_tags)) or ["general"],
        "good_if": sorted(set(good_if)),
        "avoid_if": sorted(set(avoid_if)),
        "recommendation_summary": summarize_recommendation(product, care_profile, safety_profile),
    }


def infer_light(text: str) -> tuple[str, float, list[str]]:
    rules = [
        ("low_to_indirect", 0.88, ["low light", "low-light", "shade tolerant", "indirect light only"], ["low light", "low-light", "shade"]),
        ("bright_indirect", 0.86, ["bright indirect light", "filtered light", "sunny window"], ["bright indirect", "filtered light", "sunny window"]),
        ("full_sun", 0.88, ["full sun", "bright sun", "sun-loving"], ["full sun", "bright sun", "sun-loving"]),
        ("bright_outdoor", 0.82, ["bright outdoor light", "outdoor light"], ["bright outdoor", "outdoor"]),
        ("partial_shade", 0.76, ["protection from harsh afternoon sun", "partial shade"], ["afternoon sun", "partial shade"]),
    ]
    return infer_from_rules(text, rules, "unknown", 0.35)


def infer_watering(text: str) -> tuple[str, float, list[str]]:
    rules = [
        ("high", 0.86, ["consistently moist", "regular moisture", "steady moisture", "wetland", "water-edge"], ["consistently moist", "regular moisture", "steady moisture", "wetland", "water-edge"]),
        ("low", 0.86, ["drought-tolerant", "infrequent watering", "dry between watering", "avoid overwatering"], ["drought-tolerant", "infrequent watering", "dry between watering", "avoid overwatering"]),
        ("medium", 0.7, ["moderate watering", "moderately moist", "regular watering"], ["moderate watering", "moderately moist", "regular watering"]),
    ]
    return infer_from_rules(text, rules, "medium", 0.45)


def infer_soil(text: str) -> tuple[str, float, list[str]]:
    rules = [
        ("fast_draining", 0.86, ["fast-draining soil", "well-drained soil", "excellent drainage", "lean soil"], ["fast-draining", "well-drained", "excellent drainage", "lean soil"]),
        ("moist_rich", 0.78, ["rich soil", "moderately moist soil", "steady moisture"], ["rich soil", "moderately moist", "steady moisture"]),
        ("wet_or_water_edge", 0.86, ["wetland", "water-edge", "marsh", "pond edge"], ["wetland", "water-edge", "marsh", "pond edge"]),
    ]
    return infer_from_rules(text, rules, "standard_potting_mix", 0.4)


def infer_humidity(text: str) -> tuple[str, float, list[str]]:
    rules = [
        ("high", 0.82, ["humid conditions", "tropical", "warm humid"], ["humid", "tropical"]),
        ("low_to_medium", 0.74, ["dry climates", "mediterranean", "airflow"], ["dry climates", "mediterranean", "airflow"]),
    ]
    return infer_from_rules(text, rules, "medium", 0.42)


def infer_from_rules(
    text: str,
    rules: list[tuple[str, float, list[str], list[str]]],
    default: str,
    default_confidence: float,
) -> tuple[str, float, list[str]]:
    for value, confidence, evidence_terms, patterns in rules:
        matched = [term for term in evidence_terms if term in text]
        if matched or has_any(text, patterns):
            return value, confidence, matched or patterns[:1]
    return default, default_confidence, []


def infer_placement_tags(text: str, product: dict[str, Any] | None) -> list[str]:
    tags: list[str] = []
    add_if(tags, "desk", has_any(text, ["desk", "small planter", "compact"]))
    add_if(tags, "office", has_any(text, ["office", "low-light", "houseplant"]))
    add_if(tags, "living_room", has_any(text, ["houseplant", "decor", "display", "foliage"]))
    add_if(tags, "kitchen", has_any(text, ["culinary", "kitchen", "herb", "edible"]))
    add_if(tags, "balcony", has_any(text, ["container", "pot", "planter", "sunny window"]))
    add_if(tags, "outdoor_garden", has_any(text, ["outdoor", "garden", "full sun", "tree", "shrub"]))
    add_if(tags, "water_edge", has_any(text, ["wetland", "water-edge", "pond", "marsh"]))
    if not tags and (product or {}).get("product_type") == "plant":
        tags.append("general_plant_collection")
    return sorted(set(tags))


def infer_indoor_score(text: str, placement_tags: list[str]) -> float:
    score = 0.45
    if has_any(text, ["houseplant", "indoor", "desk", "office", "low-light", "indirect light"]):
        score += 0.35
    if has_any(text, ["full sun", "outdoor", "tree", "large shrub", "water-edge", "garden beds"]):
        score -= 0.25
    if "kitchen" in placement_tags or "balcony" in placement_tags:
        score += 0.1
    return max(0.0, min(1.0, round(score, 2)))


def infer_edible_context(text: str) -> str:
    if has_any(text, ["culinary", "edible", "food", "fruit", "tea", "kitchen herb", "staple crop"]):
        return "food_or_culinary_context_present"
    if has_any(text, ["medicinal", "traditional medicine", "self-medication"]):
        return "medicinal_context_only_not_food_safety"
    return "not_established"


def link_status(product: dict[str, Any] | None, plant: dict[str, Any] | None, product_plant_id_doc: dict[str, Any] | None) -> dict[str, Any]:
    if not product and plant:
        return {"status": "plant_only_no_product", "confidence": 1.0}
    if not product:
        return {"status": "unknown", "confidence": 0.0}

    expected = normalize_search(product_scientific_name(product, []))
    actual = normalize_search((plant or {}).get("scientific_name"))
    product_plant_actual = normalize_search((product_plant_id_doc or {}).get("scientific_name"))
    current_plant_id = product.get("plant_id")

    if plant and expected == actual and str(plant.get("_id")) == str(current_plant_id):
        return {"status": "verified_product_plant_id", "confidence": 1.0}
    if plant and expected == actual:
        return {
            "status": "corrected_by_scientific_name",
            "confidence": 0.95,
            "product_plant_id": current_plant_id,
            "product_plant_id_scientific_name": (product_plant_id_doc or {}).get("scientific_name"),
            "resolved_plant_id": plant.get("_id"),
        }
    return {
        "status": "product_only_no_matching_plant_record",
        "confidence": 0.78,
        "product_plant_id": current_plant_id,
        "product_plant_id_scientific_name": (product_plant_id_doc or {}).get("scientific_name"),
    }


def build_product_summary(
    products: list[dict[str, Any]],
    variants: list[dict[str, Any]],
    inventories: list[dict[str, Any]],
    images: list[dict[str, Any]],
) -> dict[str, Any]:
    prices = [float(variant["price"]) for variant in variants if variant.get("price") is not None]
    available = sum(int(item.get("available_qty") or 0) for item in inventories)
    sizes = sorted({str((variant.get("attributes") or {}).get("size")) for variant in variants if (variant.get("attributes") or {}).get("size")})
    return {
        "names": [product.get("name") for product in products],
        "slugs": [product.get("slug") for product in products if product.get("slug")],
        "care_levels": sorted({str(product.get("care_level")) for product in products if product.get("care_level")}),
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "available_qty": available,
        "in_stock": available > 0 if inventories else None,
        "variant_sizes": sizes,
        "image_count": len(images),
        "has_image_url": any(bool(image.get("image_url")) for image in images),
    }


def build_taxonomy(plant: dict[str, Any] | None) -> dict[str, Any]:
    if not plant:
        return {}
    return {
        "family": plant.get("family"),
        "taxonomic_order": plant.get("taxonomic_order"),
        "genus": plant.get("genus"),
        "species": plant.get("species"),
        "taxonomic_status": plant.get("taxonomic_status"),
    }


def build_source_facts(plant: dict[str, Any] | None, product: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "product": {
            "name": (product or {}).get("name"),
            "short_description": (product or {}).get("short_description"),
            "description": (product or {}).get("description"),
            "care_level": (product or {}).get("care_level"),
        },
        "plant": {
            "scientific_name": (plant or {}).get("scientific_name"),
            "common_name": (plant or {}).get("common_name"),
            "description": (plant or {}).get("description"),
            "uses": (plant or {}).get("uses"),
            "advantages": (plant or {}).get("advantages"),
            "toxicity_warning": (plant or {}).get("toxicity_warning"),
            "safety_notes": (plant or {}).get("safety_notes"),
            "evidence_level": (plant or {}).get("evidence_level"),
            "source": (plant or {}).get("source"),
        },
    }


def build_data_quality(
    link_status_doc: dict[str, Any],
    plant: dict[str, Any] | None,
    product: dict[str, Any] | None,
    care_profile: dict[str, Any],
    safety_profile: dict[str, Any],
) -> dict[str, Any]:
    missing = []
    if not plant:
        missing.append("verified_plants_record")
    if not product:
        missing.append("linked_product_record")
    if care_profile["light_requirement"] == "unknown":
        missing.append("explicit_light_requirement")
    if safety_profile["toxicity_level"] == "unknown":
        missing.append("explicit_toxicity_classification")
    confidence = avg(
        [
            float(link_status_doc.get("confidence") or 0.0),
            float(care_profile.get("confidence") or 0.0),
            float(safety_profile.get("confidence") or 0.0),
            0.9 if plant else 0.55,
            0.9 if product else 0.65,
        ]
    )
    return {
        "confidence": round(confidence, 2),
        "missing_fields": sorted(set(missing)),
        "needs_review": bool(missing) or link_status_doc.get("status") != "verified_product_plant_id",
        "generation_method": "deterministic_extraction_from_bigplant_products_and_plants",
        "notes": [
            "Plant IDs are only assigned when the product scientific name exactly matches plants.scientific_name.",
            "Care fields are conservative structured inferences from existing product/plant text.",
            "Safety fields preserve source warnings and avoid medicinal dosage or treatment advice.",
        ],
    }


def article_topics(profile: dict[str, Any]) -> list[str]:
    topics = {"plant_profile", "care", "recommendation"}
    safety = profile.get("safety_profile") or {}
    care = profile.get("care_profile") or {}
    if safety.get("toxicity_level") in {"mild", "moderate", "severe"}:
        topics.add("toxicity")
        topics.add("pet_safety")
    if care.get("watering_need") and care.get("watering_need") != "unknown":
        topics.add("watering")
    if care.get("light_requirement") and care.get("light_requirement") != "unknown":
        topics.add("light")
    if (profile.get("recommendation_profile") or {}).get("use_cases"):
        topics.add("shopping_recommendation")
    return sorted(topics)


def build_article_content(profile: dict[str, Any]) -> str:
    care = profile.get("care_profile") or {}
    safety = profile.get("safety_profile") or {}
    rec = profile.get("recommendation_profile") or {}
    product = profile.get("product_summary") or {}
    source = profile.get("source_facts") or {}
    plant_source = source.get("plant") or {}
    product_source = source.get("product") or {}
    quality = profile.get("data_quality") or {}

    parts = [
        f"Plant profile: {profile.get('scientific_name')}.",
        f"Common names: {profile.get('common_name') or 'not recorded'}.",
        f"Link status: {(profile.get('link_status') or {}).get('status')}.",
        f"Care level: {care.get('care_level')}. Light requirement: {care.get('light_requirement')}. Watering need: {care.get('watering_need')}. Soil type: {care.get('soil_type')}. Humidity need: {care.get('humidity_need')}.",
        f"Care summary: {care.get('care_summary')}.",
        f"Recommended placements: {', '.join(care.get('placement_tags') or []) or 'not determined'}. Indoor score: {care.get('indoor_score')}.",
        f"Safety: toxicity level is {safety.get('toxicity_level')}; pet safe is {safety.get('pet_safe')}; child safe is {safety.get('child_safe')}. {safety.get('safety_summary')}",
        f"Recommendation fit: {rec.get('recommendation_summary')} Good if: {', '.join(rec.get('good_if') or []) or 'general use'}. Avoid if: {', '.join(rec.get('avoid_if') or []) or 'no specific avoid rule recorded'}.",
        f"Product facts: names={', '.join(product.get('names') or []) or 'none'}; price_min={product.get('price_min')}; price_max={product.get('price_max')}; available_qty={product.get('available_qty')}; sizes={', '.join(product.get('variant_sizes') or []) or 'none'}.",
        f"Product description basis: {product_source.get('description') or product_source.get('short_description') or 'not available'}.",
        f"Plant description basis: {plant_source.get('description') or 'not available'}.",
        f"Traditional uses basis: {plant_source.get('uses') or 'not available'}.",
        f"Advantages basis: {plant_source.get('advantages') or 'not available'}.",
        f"Toxicity warning basis: {plant_source.get('toxicity_warning') or 'not available'}.",
        f"Safety notes basis: {plant_source.get('safety_notes') or 'not available'}.",
        f"Evidence level: {plant_source.get('evidence_level') or 'not available'}.",
        f"Data quality confidence: {quality.get('confidence')}. Needs review: {quality.get('needs_review')}. Missing fields: {', '.join(quality.get('missing_fields') or []) or 'none'}.",
    ]
    return "\n\n".join(clean_spaces(part) for part in parts if part)


def summarize_care(care_level: str, light: str, watering: str, soil: str, humidity: str) -> str:
    return f"{care_level} care profile with {light} light, {watering} watering, {soil} soil, and {humidity} humidity needs."


def summarize_safety(
    toxicity_level: str,
    pet_safe: bool | str,
    edible_context: str,
    medicinal_policy: str,
    plant: dict[str, Any] | None,
) -> str:
    if toxicity_level == "severe":
        return "Treat this plant as unsafe around pets and children; do not suggest ingestion or self-medication."
    if toxicity_level == "moderate":
        return "Use caution around pets and children and avoid presenting medicinal use as safe."
    if toxicity_level == "mild":
        return "Safety is not fully established; mention possible irritation or sensitivity when relevant."
    if toxicity_level == "none":
        return "No explicit toxicity warning was detected in the available source text."
    if plant:
        return "Safety is not explicit enough for a strong claim; answer conservatively from source notes."
    return "No verified plant safety record is linked; avoid pet-safe or medicinal claims."


def summarize_recommendation(product: dict[str, Any] | None, care: dict[str, Any], safety: dict[str, Any]) -> str:
    name = (product or {}).get("name") or "This plant"
    return (
        f"{name} is best recommended when user constraints match {care.get('light_requirement')} light, "
        f"{care.get('watering_need')} watering, and safety tolerance of {safety.get('toxicity_level')} toxicity."
    )


def product_scientific_name(product: dict[str, Any], variants: list[dict[str, Any]]) -> str | None:
    match = re.search(r"\(([^()]+)\)\s*$", str(product.get("name") or ""))
    if match:
        return match.group(1).strip()
    for variant in variants:
        scientific = (variant.get("attributes") or {}).get("scientific_name")
        if scientific:
            return str(scientific).strip()
    return None


def common_name_from_product(product: dict[str, Any] | None) -> str | None:
    if not product:
        return None
    name = str(product.get("name") or "")
    return re.sub(r"\s*\([^()]+\)\s*$", "", name).strip() or None


def normalize_search(value: Any) -> str:
    return "_".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def normalize_care_level(value: Any) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"easy", "moderate", "hard"}:
        return lowered
    return "unknown"


def title_from_search(value: str) -> str:
    return " ".join(part.capitalize() for part in str(value or "").split("_"))


def slugify(value: Any) -> str:
    return "-".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def combined_text(plant: dict[str, Any] | None, product: dict[str, Any] | None) -> str:
    values = []
    for source in [product or {}, plant or {}]:
        for key in ["name", "short_description", "description", "uses", "advantages", "toxicity_warning", "safety_notes", "evidence_level"]:
            if source.get(key):
                values.append(str(source[key]))
    return "\n".join(values)


def group_by(cursor: Any, field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for doc in cursor:
        grouped.setdefault(str(doc.get(field)), []).append(doc)
    return grouped


def has_any(text: str, patterns: list[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def add_if(items: list[str], value: str, condition: bool) -> None:
    if condition:
        items.append(value)


def avg(values: list[float]) -> float:
    cleaned = [float(value) for value in values if value is not None]
    return sum(cleaned) / len(cleaned) if cleaned else 0.0


def clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def stable_chunk_id(article_id: str, index: int) -> str:
    digest = hashlib.sha1(f"{article_id}:{index}".encode("utf-8")).hexdigest()[:24]
    return f"knowledge_chunk:{digest}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def upsert_documents(collection: Any, docs: list[dict[str, Any]]) -> None:
    if not docs:
        return
    operations = [UpdateOne({"_id": doc["_id"]}, {"$set": doc}, upsert=True) for doc in docs]
    collection.bulk_write(operations, ordered=False)


def ensure_indexes(db: Any, settings: Any) -> None:
    db[PROFILE_COLLECTION].create_index("plant_id")
    db[PROFILE_COLLECTION].create_index("primary_product_id")
    db[PROFILE_COLLECTION].create_index("scientific_name_search", unique=True)
    db[PROFILE_COLLECTION].create_index("link_status.status")
    db[settings.knowledge_articles_collection].create_index("slug", unique=True)
    db[settings.knowledge_articles_collection].create_index("plant_id")
    db[settings.knowledge_articles_collection].create_index("product_ids")
    db[settings.knowledge_chunks_collection].create_index([("article_id", 1), ("chunk_index", 1)], unique=True)
    db[settings.knowledge_chunks_collection].create_index("metadata.topics")
    db[settings.knowledge_chunks_collection].create_index("metadata.related_plants")


def build_report(
    products: list[dict[str, Any]],
    plants: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    missing_counts: dict[str, int] = {}
    for profile in profiles:
        status = (profile.get("link_status") or {}).get("status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        for item in (profile.get("data_quality") or {}).get("missing_fields") or []:
            missing_counts[item] = missing_counts.get(item, 0) + 1
    return {
        "source_products": len(products),
        "source_plants": len(plants),
        "profiles": len(profiles),
        "articles": len(articles),
        "chunks": len(chunks),
        "link_status_counts": status_counts,
        "missing_field_counts": missing_counts,
        "chunks_with_embedding": sum(1 for chunk in chunks if chunk.get("embedding")),
    }


def print_report(report: dict[str, Any]) -> None:
    print("=== AI KNOWLEDGE BUILD REPORT ===")
    for key, value in report.items():
        print(f"{key}: {value}")


def print_samples(profiles: list[dict[str, Any]], articles: list[dict[str, Any]], chunks: list[dict[str, Any]], sample: int) -> None:
    print("=== PROFILE SAMPLES ===")
    for doc in profiles[:sample]:
        print(
            {
                "_id": doc["_id"],
                "scientific_name": doc["scientific_name"],
                "plant_id": str(doc.get("plant_id")) if doc.get("plant_id") else None,
                "primary_product_id": str(doc.get("primary_product_id")) if doc.get("primary_product_id") else None,
                "link_status": doc["link_status"],
                "care_profile": doc["care_profile"],
                "safety_profile": {
                    "toxicity_level": doc["safety_profile"]["toxicity_level"],
                    "pet_safe": doc["safety_profile"]["pet_safe"],
                    "confidence": doc["safety_profile"]["confidence"],
                },
                "data_quality": doc["data_quality"],
            }
        )
    print("=== ARTICLE SAMPLE IDS ===")
    for doc in articles[:sample]:
        print({"_id": doc["_id"], "title": doc["title"], "topics": doc["topics"], "content_preview": doc["content"][:220]})
    print("=== CHUNK SAMPLE IDS ===")
    for doc in chunks[:sample]:
        print({"_id": doc["_id"], "article_id": doc["article_id"], "has_embedding": bool(doc.get("embedding")), "content_preview": doc["content"][:160]})


if __name__ == "__main__":
    main()
