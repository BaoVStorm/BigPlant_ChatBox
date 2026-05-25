from __future__ import annotations

from functools import lru_cache
from threading import Lock

import numpy as np

from app.config import Settings, get_settings


class EmbeddingService:
    _shared_models = {}
    _shared_lock = Lock()

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _load(self):
        model_key = (self.settings.embedding_model_name, self.settings.embedding_device)
        if model_key in self._shared_models:
            return self._shared_models[model_key]
        with self._shared_lock:
            if model_key in self._shared_models:
                return self._shared_models[model_key]
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.settings.embedding_model_name, device=self.settings.embedding_device)
            self._shared_models[model_key] = model
            return model

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
