"""
긴 텍스트(판례 전문 등)를 임베딩하기 좋은 크기로 나누는 유틸리티.

문단(빈 줄) 경계를 우선적으로 존중하면서, chunk_size를 초과하면 강제로 자른다.
"""
from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > chunk_size:
            # 문단 자체가 너무 길면 문자 단위로 강제 분할
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(para):
                end = start + chunk_size
                chunks.append(para[start:end])
                start = end - overlap if end - overlap > start else end
            continue

        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) > chunk_size:
            chunks.append(current)
            current = para
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks
