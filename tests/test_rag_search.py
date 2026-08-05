"""rag.search(필터/중복 제거)에 대한 단위 테스트.

Chroma는 실제 in-memory 클라이언트(``chromadb.Client()``)를 사용하지만, Gemini
임베딩 호출은 결정적 가짜 임베더로 대체해 외부 네트워크 호출 없이 검증한다.
"""
from __future__ import annotations

from typing import List, Sequence

import chromadb
import pytest

from rag.schemas import SearchHit
from rag.search import SearchFilters, dedupe_by_doc, search


class _FakeEmbedder:
    """질의 텍스트 길이만으로 결정적 2차원 벡터를 만드는 가짜 임베더(Gemini 미호출)."""

    def embed_query(self, text: str) -> List[float]:
        return [float(len(text) % 7), float(sum(ord(ch) for ch in text) % 11)]


@pytest.fixture()
def populated_collection() -> chromadb.api.models.Collection.Collection:
    client = chromadb.Client()
    collection = client.get_or_create_collection("test_search_collection")
    collection.add(
        ids=["p1", "p2", "s1"],
        embeddings=[[1.0, 2.0], [1.0, 2.0], [3.0, 4.0]],
        documents=["판례 발췌 1", "판례 발췌 2", "법령 발췌 1"],
        metadatas=[
            {"doc_type": "PRECEDENT", "doc_id": "precedent:a.md", "instance": "1심", "category": "경범죄"},
            {"doc_type": "PRECEDENT", "doc_id": "precedent:b.md", "instance": "항소심", "category": "식품"},
            {"doc_type": "STATUTE", "doc_id": "statute:c.pdf", "instance": "", "category": ""},
        ],
    )
    return collection


def test_search_without_filters_returns_all_types(populated_collection) -> None:  # type: ignore[no-untyped-def]
    hits = search(populated_collection, _FakeEmbedder(), "질의", top_k=10)
    assert {hit.doc_type for hit in hits} == {"PRECEDENT", "STATUTE"}
    assert len(hits) == 3
    assert all(isinstance(hit, SearchHit) for hit in hits)


def test_search_with_doc_type_filter_returns_only_matching_type(populated_collection) -> None:  # type: ignore[no-untyped-def]
    hits = search(
        populated_collection, _FakeEmbedder(), "질의", top_k=10, filters=SearchFilters(doc_type="STATUTE")
    )
    assert hits
    assert all(hit.doc_type == "STATUTE" for hit in hits)


def test_search_with_instance_filter_returns_only_matching_instance(populated_collection) -> None:  # type: ignore[no-untyped-def]
    hits = search(
        populated_collection, _FakeEmbedder(), "질의", top_k=10, filters=SearchFilters(instance="1심")
    )
    assert hits
    assert all(hit.metadata.get("instance") == "1심" for hit in hits)


def test_search_with_combined_filters_uses_and_semantics(populated_collection) -> None:  # type: ignore[no-untyped-def]
    hits = search(
        populated_collection,
        _FakeEmbedder(),
        "질의",
        top_k=10,
        filters=SearchFilters(doc_type="PRECEDENT", category="식품"),
    )
    assert len(hits) == 1
    assert hits[0].doc_id == "precedent:b.md"


def test_search_with_filter_matching_nothing_returns_empty(populated_collection) -> None:  # type: ignore[no-untyped-def]
    hits = search(
        populated_collection, _FakeEmbedder(), "질의", top_k=10, filters=SearchFilters(category="존재하지 않음")
    )
    assert hits == []


def _make_hit(doc_id: str, chunk_suffix: str) -> SearchHit:
    return SearchHit(
        chunk_id=f"{doc_id}#{chunk_suffix}",
        doc_id=doc_id,
        doc_type="PRECEDENT",
        text="본문",
        metadata={},
        distance=0.1,
    )


def test_dedupe_by_doc_limits_chunks_per_document() -> None:
    hits = [_make_hit("doc-a", "0"), _make_hit("doc-a", "1"), _make_hit("doc-a", "2"), _make_hit("doc-b", "0")]
    deduped = dedupe_by_doc(hits, limit_per_doc=2)
    assert [hit.chunk_id for hit in deduped] == ["doc-a#0", "doc-a#1", "doc-b#0"]


def test_dedupe_by_doc_preserves_order_and_empty_input() -> None:
    assert dedupe_by_doc([], limit_per_doc=2) == []
    hits: Sequence[SearchHit] = [_make_hit("doc-a", "0")]
    assert dedupe_by_doc(hits, limit_per_doc=1) == list(hits)
