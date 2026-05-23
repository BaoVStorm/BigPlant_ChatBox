from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.knowledge.ingest import KnowledgeIngestService


def main() -> None:
    result = KnowledgeIngestService().ingest_all_articles()
    print(result)


if __name__ == "__main__":
    main()
