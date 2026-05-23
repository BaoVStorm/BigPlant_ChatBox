from __future__ import annotations

import json
from typing import Any

from app.embeddings.embedding_service import EmbeddingService
from app.knowledge.knowledge_repository import KnowledgeRepository
from app.llm.local_llm import LocalLLM
from app.llm.prompts import RAG_PROMPT
from app.router.schemas import IntentRoute


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

        if not chunks:
            return {
                "intent": "plant_care",
                "message": "Mình chưa có đủ thông tin trong tài liệu hiện tại. Bạn có thể mô tả thêm tình trạng cây hoặc gửi ảnh nếu app có hỗ trợ.",
                "products": [],
                "sources": [],
                "metadata": {"route": route.model_dump()},
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
        if self.llm.is_available:
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
            "metadata": {"route": route.model_dump(), "llm_used": llm_used},
        }


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
