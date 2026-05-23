from __future__ import annotations

from app.embeddings.embedding_service import EmbeddingService
from app.knowledge.chunking import split_text
from app.knowledge.knowledge_repository import KnowledgeRepository


class KnowledgeIngestService:
    def __init__(
        self,
        repository: KnowledgeRepository | None = None,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self.repository = repository or KnowledgeRepository()
        self.embeddings = embeddings or EmbeddingService()

    def ingest_all_articles(self) -> dict[str, int]:
        articles = self.repository.get_active_articles()
        article_count = 0
        chunk_count = 0
        for article in articles:
            content = str(article.get("content") or "")
            chunks = split_text(content)
            if not chunks:
                continue
            self.repository.delete_chunks_for_article(str(article["_id"]))
            vectors = self.embeddings.embed_texts(chunks)
            for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
                self.repository.upsert_chunk(
                    article=article,
                    chunk_index=index,
                    content=chunk,
                    embedding=vector,
                    embedding_model=self.embeddings.settings.embedding_model_name,
                )
                chunk_count += 1
            article_count += 1
        return {"articles": article_count, "chunks": chunk_count}
