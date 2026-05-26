from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.embeddings.embedding_service import EmbeddingService, get_embedding_service
from app.llm.local_llm import LocalLLM
from app.llm.prompts import ROUTER_PROMPT
from app.router.entity_extractor import extract_entities
from app.router.intent_examples import INTENT_EXAMPLES
from app.router.intent_rules import score_intents_by_rules
from app.router.schemas import IntentRoute
from app.router.text_utils import normalize_text


class IntentRouter:
    def __init__(self, llm: LocalLLM | None = None, embeddings: EmbeddingService | None = None) -> None:
        self.llm = llm or LocalLLM()
        self.embeddings = embeddings or get_embedding_service()
        self._example_index: dict[str, list[list[float]]] | None = None

    def classify(self, message: str) -> IntentRoute:
        rule_route, rule_scores = self._classify_by_rules(message)
        if is_strong_rule_route(rule_route, rule_scores):
            return rule_route

        semantic_route, semantic_scores = self._classify_by_semantics(message, rule_route.entities, rule_scores)
        if semantic_route and is_confident_semantic_route(semantic_route, semantic_scores, rule_route):
            return semantic_route

        if self.llm.is_available:
            prompt = ROUTER_PROMPT.format(message=message)
            try:
                raw = self.llm.generate_json(prompt)
            except Exception:
                return semantic_route or rule_route

            if raw.get("intent") in {"product_info", "recommendation", "plant_care", "cart_order", "general", "unclear"}:
                entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
                entities = {**rule_route.entities, **entities}
                return IntentRoute(
                    intent=raw["intent"],
                    confidence=float(raw.get("confidence") or max((semantic_route or rule_route).confidence, 0.5)),
                    entities=entities,
                    source="local_llm",
                )

        return semantic_route or rule_route

    def _classify_by_rules(self, message: str) -> tuple[IntentRoute, dict[str, float]]:
        normalized_message = normalize_text(message)
        entities = extract_entities(normalized_message, original=message)
        scores = score_intents_by_rules(normalized_message, entities)
        best_intent, best_score, second_score = best_scores(scores)

        if best_intent == "unclear" or best_score <= 0:
            return IntentRoute(intent="unclear", confidence=0.45, entities=entities, source="heuristic_rules"), scores

        margin = best_score - second_score
        confidence = min(0.97, 0.52 + best_score * 0.1 + max(margin, 0) * 0.05)
        return IntentRoute(intent=best_intent, confidence=confidence, entities=entities, source="heuristic_rules"), scores

    def _classify_by_semantics(
        self,
        message: str,
        entities: dict[str, Any],
        rule_scores: dict[str, float],
    ) -> tuple[IntentRoute | None, dict[str, float]]:
        try:
            example_index = self._get_example_index()
            query_vector = self.embeddings.embed_text(message)
        except Exception:
            return None, {}

        semantic_scores: dict[str, float] = {}
        for intent, vectors in example_index.items():
            similarities = [cosine_similarity(query_vector, vector) for vector in vectors]
            semantic_scores[intent] = max(similarities) if similarities else 0.0

        combined_scores = dict(semantic_scores)
        for intent, score in rule_scores.items():
            if intent == "unclear":
                continue
            combined_scores[intent] = combined_scores.get(intent, 0.0) + min(score, 3.0) * 0.04

        best_intent, best_score, second_score = best_scores(combined_scores)
        if best_intent == "unclear" or best_score <= 0:
            return None, combined_scores

        margin = best_score - second_score
        confidence = min(0.95, max(0.45, best_score + margin * 0.45))
        return IntentRoute(intent=best_intent, confidence=confidence, entities=entities, source="semantic_examples"), combined_scores

    def _get_example_index(self) -> dict[str, list[list[float]]]:
        if self._example_index is not None:
            return self._example_index
        self._example_index = build_intent_example_index(self.embeddings)
        return self._example_index


def is_strong_rule_route(route: IntentRoute, scores: dict[str, float]) -> bool:
    if route.intent == "unclear":
        return False
    best_intent, best_score, second_score = best_scores(scores)
    margin = best_score - second_score
    if best_intent != route.intent:
        return False
    if best_score >= 3.0:
        return True
    return best_score >= 2.0 and margin >= 0.8


def is_confident_semantic_route(route: IntentRoute, semantic_scores: dict[str, float], rule_route: IntentRoute) -> bool:
    if route is None:
        return False
    best_intent, best_score, second_score = best_scores(semantic_scores)
    margin = best_score - second_score
    if best_intent != route.intent:
        return False
    if route.intent == rule_route.intent and rule_route.intent != "unclear":
        return True
    return best_score >= 0.63 and margin >= 0.03


def best_scores(scores: dict[str, float]) -> tuple[str, float, float]:
    ranked = sorted(((intent, score) for intent, score in scores.items() if intent != "unclear"), key=lambda item: item[1], reverse=True)
    if not ranked or ranked[0][1] <= 0:
        return "unclear", scores.get("unclear", 0.0), 0.0
    best_intent, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    return best_intent, best_score, second_score


@lru_cache(maxsize=1)
def build_intent_example_index(embeddings: EmbeddingService) -> dict[str, list[list[float]]]:
    return {intent: embeddings.embed_texts(examples) for intent, examples in INTENT_EXAMPLES.items()}


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    return float(sum(value_a * value_b for value_a, value_b in zip(vector_a, vector_b)))
