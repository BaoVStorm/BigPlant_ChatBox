from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mongo_uri: str = Field(default="", alias="MONGO_URI")
    mongo_db_name: str = Field(default="bigplant", alias="MONGO_DB_NAME")

    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    llm_model_path: str = Field(default="./models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf", alias="LLM_MODEL_PATH")
    llm_context_size: int = Field(default=4096, alias="LLM_CONTEXT_SIZE")
    llm_gpu_layers: int = Field(default=-1, alias="LLM_GPU_LAYERS")
    llm_max_tokens: int = Field(default=768, alias="LLM_MAX_TOKENS")
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    llm_prompt_format: str = Field(default="auto", alias="LLM_PROMPT_FORMAT")

    embedding_model_name: str = Field(default="./models/embeddings/bge-m3", alias="EMBEDDING_MODEL_NAME")
    embedding_device: str = Field(default="cuda", alias="EMBEDDING_DEVICE")

    product_vector_index: str = Field(default="product_vector_index", alias="PRODUCT_VECTOR_INDEX")
    knowledge_vector_index: str = Field(default="knowledge_vector_index", alias="KNOWLEDGE_VECTOR_INDEX")
    product_embedding_field: str = Field(default="embedding", alias="PRODUCT_EMBEDDING_FIELD")
    knowledge_embedding_field: str = Field(default="embedding", alias="KNOWLEDGE_EMBEDDING_FIELD")

    products_collection: str = Field(default="products", alias="PRODUCTS_COLLECTION")
    product_categories_collection: str = Field(default="product_categories", alias="PRODUCT_CATEGORIES_COLLECTION")
    product_variants_collection: str = Field(default="product_variants", alias="PRODUCT_VARIANTS_COLLECTION")
    product_images_collection: str = Field(default="product_images", alias="PRODUCT_IMAGES_COLLECTION")
    variant_inventory_collection: str = Field(default="variant_inventory", alias="VARIANT_INVENTORY_COLLECTION")
    plants_collection: str = Field(default="plants", alias="PLANTS_COLLECTION")
    knowledge_articles_collection: str = Field(default="plant_knowledge_articles", alias="KNOWLEDGE_ARTICLES_COLLECTION")
    knowledge_chunks_collection: str = Field(default="knowledge_chunks", alias="KNOWLEDGE_CHUNKS_COLLECTION")

    @property
    def resolved_llm_model_path(self) -> Path:
        return Path(self.llm_model_path).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
