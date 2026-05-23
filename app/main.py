from __future__ import annotations

from fastapi import FastAPI

from app.chat.chat_router import router as chat_router
from app.config import get_settings


app = FastAPI(title="BigPlant Local RAG Chatbot", version="0.1.0")
app.include_router(chat_router, prefix="/api")


@app.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "mongo_db": settings.mongo_db_name,
        "llm_model_exists": settings.resolved_llm_model_path.exists(),
        "llm_model_path": str(settings.resolved_llm_model_path),
        "embedding_model": settings.embedding_model_name,
    }
