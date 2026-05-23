from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.embeddings.embedding_service import EmbeddingService
from app.products.product_repository import ProductRepository
from app.recommendations.product_embedding import build_product_embedding_text


def main() -> None:
    repository = ProductRepository()
    embeddings = EmbeddingService()
    products = repository.search_products({}, limit=10_000)
    updated = 0
    for product in products:
        text = build_product_embedding_text(product)
        vector = embeddings.embed_text(text)
        repository.update_product_embedding(str(product["_id"]), vector, text)
        updated += 1
        print(f"embedded product {updated}: {product.get('name')}")
    print({"updated_products": updated})


if __name__ == "__main__":
    main()
