from __future__ import annotations

from functools import lru_cache

import numpy as np

from app.config import Settings, get_settings


class EmbeddingService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self.settings.embedding_model_name, device=self.settings.embedding_device)
        return self._model

    def embed_text(self, text: str) -> list[float]:
        model = self._load()
        vector = model.encode(text, normalize_embeddings=True)
        if isinstance(vector, np.ndarray):
            return vector.astype(float).tolist()
        return [float(item) for item in vector]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(texts, normalize_embeddings=True)
        return [[float(item) for item in vector] for vector in vectors]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
