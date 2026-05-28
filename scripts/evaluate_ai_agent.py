from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.agent.planner import AgentPlanner
from app.chat.facets import classify_facet
from app.config import get_settings
from app.db.mongo import get_database
from app.embeddings.embedding_service import EmbeddingService
from app.knowledge.knowledge_repository import KnowledgeRepository
from app.knowledge.rag_handler import filter_relevant_chunks
from app.products.product_repository import ProductRepository
from app.router.entity_extractor import extract_entities
from app.router.schemas import IntentRoute
from app.router.text_utils import normalize_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate BigPlant chatbot routing, retrieval, and grounded-agent behavior.")
    parser.add_argument("--skip-vector", action="store_true", help="Skip embedding/vector-search checks for fast local validation.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    results.extend(evaluate_entity_extraction())
    results.extend(evaluate_database_grounding())
    results.extend(evaluate_recommendation_filters())
    results.extend(evaluate_agent_planner())
    if not args.skip_vector:
        results.extend(evaluate_rag_gate())

    failed = [item for item in results if not item["passed"]]
    report = {
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "total": len(results),
        "results": results,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, default=str))
    else:
        print(f"AI agent eval: {report['passed']}/{report['total']} passed")
        for item in results:
            status = "OK" if item["passed"] else "FAIL"
            print(f"[{status}] {item['name']}: {item.get('details')}")

    return 1 if failed else 0


def evaluate_entity_extraction() -> list[dict[str, Any]]:
    cases = [
        (
            "entity_beginner_desk_low_light_budget",
            "Tư vấn cây dễ chăm để bàn ít nắng dưới 20 đô",
            {"care_level": "easy", "placement": "desk", "light_requirement": "low", "max_price": 20.0},
        ),
        (
            "entity_pet_cat",
            "Có cây nào an toàn với mèo không?",
            {"pet_safe": True, "pet_type": "cat"},
        ),
        (
            "entity_style_bedroom",
            "Tìm cây decor minimal cho phòng ngủ",
            {"placement": "bedroom", "style": "minimal"},
        ),
    ]
    results = []
    for name, message, expected in cases:
        entities = extract_entities(normalize_text(message), message)
        missing = {key: value for key, value in expected.items() if entities.get(key) != value}
        results.append(result(name, not missing, {"entities": entities, "missing": missing}))
    return results


def evaluate_database_grounding() -> list[dict[str, Any]]:
    settings = get_settings()
    db = get_database()
    products = list(db[settings.products_collection].find({"product_type": "plant"}, {"_id": 1, "plant_id": 1}).limit(1000))
    plant_ids = {str(doc["_id"]) for doc in db[settings.plants_collection].find({}, {"_id": 1})}
    bad_links = [str(item.get("_id")) for item in products if str(item.get("plant_id")) not in plant_ids]
    profile_count = db[settings.plant_profiles_collection].count_documents({})
    article_count = db[settings.knowledge_articles_collection].count_documents({})
    chunk_count = db[settings.knowledge_chunks_collection].count_documents({})
    product_embedding_count = db[settings.products_collection].count_documents({settings.product_embedding_field: {"$type": "array"}})

    repo = ProductRepository(settings=settings)
    contexts = repo.search_products({}, limit=min(len(products), 100))
    contexts_with_profile = sum(1 for item in contexts if item.get("plant_profile"))

    return [
        result("db_product_plant_links", not bad_links and len(products) >= 1, {"products": len(products), "bad_links": bad_links[:10]}),
        result("db_ai_collections_ready", profile_count >= len(products) and article_count >= len(products) and chunk_count >= len(products), {"profiles": profile_count, "articles": article_count, "chunks": chunk_count}),
        result("db_product_embeddings_ready", product_embedding_count >= len(products), {"products": len(products), "products_with_embedding": product_embedding_count}),
        result("repository_profile_hydration", contexts_with_profile == len(contexts) and len(contexts) > 0, {"contexts": len(contexts), "contexts_with_profile": contexts_with_profile}),
    ]


def evaluate_recommendation_filters() -> list[dict[str, Any]]:
    repo = ProductRepository()
    cases = [
        ("recommendation_easy_alias", {"care_level": "easy"}),
        ("recommendation_low_light", {"light_requirement": "low"}),
        ("recommendation_desk", {"placement": "desk"}),
    ]
    results = []
    for name, filters in cases:
        products = repo.search_products(filters, limit=5)
        results.append(result(name, len(products) > 0, {"filters": filters, "count": len(products), "names": product_names(products)}))
    return results


def evaluate_agent_planner() -> list[dict[str, Any]]:
    planner = AgentPlanner()
    recommendation_route = IntentRoute(intent="recommendation", confidence=0.88, entities={"placement": "desk", "light_requirement": "low"}, source="eval")
    recommendation_facet = classify_facet(recommendation_route.intent, "Tư vấn cây để bàn ít nắng", recommendation_route.entities)
    recommendation_plan = planner.plan("Tư vấn cây để bàn ít nắng", recommendation_route, recommendation_facet)
    recommendation_tools = [tool.name for tool in recommendation_plan.tools]

    product_route = IntentRoute(intent="product_info", confidence=0.8, entities={}, source="eval")
    product_facet = classify_facet(product_route.intent, "Giá cây này bao nhiêu?", product_route.entities)
    product_plan = planner.plan("Giá cây này bao nhiêu?", product_route, product_facet)

    return [
        result("planner_recommendation_tools", {"search_products", "rank_products"}.issubset(set(recommendation_tools)), {"goal": recommendation_plan.goal, "tools": recommendation_tools}),
        result("planner_product_clarification", product_plan.needs_clarification is True, product_plan.model_dump()),
    ]


def evaluate_rag_gate() -> list[dict[str, Any]]:
    settings = get_settings()
    embeddings = EmbeddingService(settings=settings)
    repository = KnowledgeRepository(settings=settings)
    cases = [
        ("rag_accept_watering_aloe", "cách tưới aloe vera", True),
        ("rag_reject_symptom_without_evidence", "cây bị vàng lá do úng nước xử lý sao", False),
        ("rag_accept_low_light", "cây nào hợp phòng thiếu sáng", True),
    ]
    results = []
    for name, query, should_accept in cases:
        vector = embeddings.embed_text(query)
        chunks = repository.vector_search_chunks(vector, limit=5)
        accepted = filter_relevant_chunks(chunks, settings.rag_min_vector_score, query)
        passed = bool(accepted) if should_accept else not accepted
        results.append(
            result(
                name,
                passed,
                {
                    "query": query,
                    "accepted": len(accepted),
                    "scores": [round(float(chunk.get("vector_score") or 0), 4) for chunk in chunks],
                    "titles": [chunk.get("title") for chunk in accepted[:2]],
                },
            )
        )
    return results


def product_names(contexts: list[dict[str, Any]]) -> list[str]:
    return [(item.get("product") or {}).get("name") for item in contexts[:3]]


def result(name: str, passed: bool, details: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "details": details}


if __name__ == "__main__":
    raise SystemExit(main())
