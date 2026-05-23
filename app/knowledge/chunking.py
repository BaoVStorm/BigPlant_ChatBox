from __future__ import annotations

import re

from bs4 import BeautifulSoup


def clean_content(content: str) -> str:
    soup = BeautifulSoup(content or "", "html.parser")
    text = soup.get_text(" ")
    text = re.sub(r"[`*_>#-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    words = clean_content(text).split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = max(end - overlap, start + 1)
    return chunks
