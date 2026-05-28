from __future__ import annotations

import json
from typing import Any

from app.config import get_settings
from app.embeddings.embedding_service import EmbeddingService
from app.knowledge.knowledge_repository import KnowledgeRepository
from app.llm.local_llm import LocalLLM
from app.llm.prompts import RAG_PROMPT
from app.router.schemas import IntentRoute
from app.router.text_utils import normalize_text


class PlantCareRagHandler:
    def __init__(
        self,
        repository: KnowledgeRepository | None = None,
        embeddings: EmbeddingService | None = None,
        llm: LocalLLM | None = None,
    ) -> None:
        self.repository = repository or KnowledgeRepository()
        self.embeddings = embeddings or EmbeddingService()
        self.llm = llm or LocalLLM()

    def handle(self, message: str, route: IntentRoute) -> dict[str, Any]:
        try:
            query_vector = self.embeddings.embed_text(message)
            chunks = self.repository.vector_search_chunks(query_vector, filters=build_filters(route), limit=5)
        except Exception as exc:
            return {
                "intent": "plant_care",
                "message": "Mình chưa thể tìm trong kho kiến thức lúc này. Bạn kiểm tra lại cấu hình embedding/vector search hoặc thử lại sau.",
                "products": [],
                "sources": [],
                "metadata": {"route": route.model_dump(), "error": str(exc)},
            }

        min_score = get_settings().rag_min_vector_score
        chunks = filter_relevant_chunks(chunks, min_score, message)
        if not chunks:
            return {
                "intent": "plant_care",
                "message": "Mình chưa có đủ thông tin đáng tin trong tài liệu hiện tại để trả lời câu này. Bạn có thể mô tả rõ tên cây, triệu chứng, ánh sáng và tần suất tưới không?",
                "products": [],
                "sources": [],
                "metadata": {"route": route.model_dump(), "min_vector_score": min_score, "retrieval_rejected": True},
            }

        context = build_context(chunks)
        sources = build_sources(chunks)
        prompt = RAG_PROMPT.format(
            message=message,
            context=context,
            sources=json.dumps(sources, ensure_ascii=False, default=str),
        )

        answer = None
        llm_used = False
        llm_enabled = getattr(getattr(self.llm, "settings", None), "llm_use_for_rag", False)
        if llm_enabled and self.llm.is_available:
            try:
                answer = self.llm.generate(prompt)
                llm_used = True
            except Exception:
                answer = None
        if not answer:
            answer = build_context_based_answer(chunks)

        return {
            "intent": "plant_care",
            "message": answer,
            "products": [],
            "sources": sources,
            "metadata": {"route": route.model_dump(), "llm_used": llm_used, "min_vector_score": get_settings().rag_min_vector_score},
        }


def filter_relevant_chunks(chunks: list[dict[str, Any]], min_score: float, query: str) -> list[dict[str, Any]]:
    relevant = []
    for chunk in chunks:
        score = chunk.get("vector_score")
        if score is not None and float(score) < min_score:
            continue
        if not chunk_has_query_evidence(chunk, query):
            continue
        relevant.append(chunk)
    return relevant


def chunk_has_query_evidence(chunk: dict[str, Any], query: str) -> bool:
    required_groups = query_evidence_groups(query)
    if not required_groups:
        return True
    metadata = chunk.get("metadata") or {}
    haystack = normalize_text(" ".join([str(chunk.get("title") or ""), str(chunk.get("content") or ""), str(metadata)]))
    return all(any(term in haystack for term in terms) for terms in required_groups)


def query_evidence_groups(query: str) -> list[set[str]]:
    text = normalize_text(query)
    groups: list[set[str]] = []
    if any(term in text for term in ["tuoi", "nuoc", "watering"]):
        groups.append({"tuoi", "nuoc", "watering", "water", "moisture"})
    if any(term in text for term in ["anh sang", "nang", "thieu sang", "it nang", "light", "shade"]):
        groups.append({"anh sang", "nang", "light", "shade", "low_to_indirect", "bright_indirect", "bright_outdoor"})
    if any(term in text for term in ["vang la", "la vang", "yellow leaf", "yellow leaves", "chlorosis"]):
        groups.append({"vang la", "la vang", "yellow leaf", "yellow leaves", "chlorosis"})
    if any(term in text for term in ["ung nuoc", "thoi re", "ngap nuoc", "root rot", "overwater", "waterlogged"]):
        groups.append({"ung nuoc", "thoi re", "ngap nuoc", "root rot", "overwater", "overwatering", "waterlogged"})
    if any(term in text for term in ["sau", "nam", "benh", "fungus", "pest", "disease"]):
        groups.append({"sau", "nam", "benh", "fungus", "pest", "disease"})
    return groups


def build_filters(route: IntentRoute) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if route.entities.get("topic"):
        filters["topic"] = route.entities["topic"]
    if route.entities.get("plant_slug"):
        filters["plant_slug"] = route.entities["plant_slug"]
    return filters


def build_context(chunks: list[dict[str, Any]]) -> str:
    lines = []
    for index, chunk in enumerate(chunks, start=1):
        title = chunk.get("title") or "Tài liệu"
        content = chunk.get("content") or ""
        lines.append(f"[{index}] {title}\n{content}")
    return "\n\n".join(lines)


def build_sources(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources = []
    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        sources.append(
            {
                "title": chunk.get("title"),
                "slug": metadata.get("slug"),
                "score": chunk.get("vector_score"),
                "source_type": metadata.get("source_type"),
            }
        )
    return sources


def build_context_based_answer(chunks: list[dict[str, Any]]) -> str:
    first = chunks[0]
    content = str(first.get("content") or "")[:900]
    title = first.get("title") or "tài liệu liên quan"
    return f"Theo {title}, thông tin liên quan là: {content}"
