"""질의 임베딩 후 Chroma 유사도 검색 + 메타데이터 필터링.

요구사항(사용자 결정): 전체 판례를 심급 구분 없이 인덱싱해두고, 필터링(예: 1심만
보기, 카테고리별 보기)은 이 검색 단계에서 유연하게 적용한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Protocol, Sequence, cast

from chromadb.api.models.Collection import Collection

from rag.schemas import SearchHit

DocType = Literal["PRECEDENT", "STATUTE"]
CourtInstanceFilter = Literal["1심", "항소심", "상고심"]


class QueryEmbedder(Protocol):
    """``search()``가 요구하는 최소 인터페이스. ``GeminiEmbedder``와 테스트용 가짜
    임베더가 공통으로 구현한다(``GeminiEmbedder``에 대한 하드 의존을 피해 테스트를
    쉽게 한다)."""

    def embed_query(self, text: str) -> List[float]: ...


@dataclass(frozen=True)
class SearchFilters:
    """검색 단계에서 적용할 선택적 메타데이터 필터."""

    doc_type: Optional[DocType] = None
    instance: Optional[CourtInstanceFilter] = None
    """지정하면 해당 심급의 판례만 반환한다(법령 청크에는 영향 없음)."""
    category: Optional[str] = None
    """precedent 최상위 카테고리(예: '경범죄', '식품', '청소년')."""


def _build_where_clause(filters: SearchFilters) -> Optional[Dict[str, Any]]:
    clauses: List[Dict[str, Any]] = []
    if filters.doc_type is not None:
        clauses.append({"doc_type": filters.doc_type})
    if filters.instance is not None:
        clauses.append({"instance": filters.instance})
    if filters.category is not None:
        clauses.append({"category": filters.category})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def search(
    collection: Collection,
    embedder: QueryEmbedder,
    query: str,
    *,
    top_k: int = 8,
    filters: Optional[SearchFilters] = None,
) -> List[SearchHit]:
    """질의 문자열을 임베딩해 Chroma에서 유사도 검색을 수행한다."""
    query_vector = embedder.embed_query(query)
    where = _build_where_clause(filters) if filters is not None else None
    result = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    return _to_search_hits(result)


def _to_search_hits(result: Dict[str, Any]) -> List[SearchHit]:
    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    hits: List[SearchHit] = []
    for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
        metadata = metadata or {}
        doc_type = cast(Literal["PRECEDENT", "STATUTE"], metadata.get("doc_type", "PRECEDENT"))
        hits.append(
            SearchHit(
                chunk_id=chunk_id,
                doc_id=str(metadata.get("doc_id", "")),
                doc_type=doc_type,
                text=text,
                metadata=dict(metadata),
                distance=float(distance),
            )
        )
    return hits


def dedupe_by_doc(hits: Sequence[SearchHit], *, limit_per_doc: int = 2) -> List[SearchHit]:
    """같은 문서(``doc_id``)의 청크가 결과를 과도하게 점유하지 않도록 문서별 상한을 둔다."""
    counts: Dict[str, int] = {}
    deduped: List[SearchHit] = []
    for hit in hits:
        count = counts.get(hit.doc_id, 0)
        if count >= limit_per_doc:
            continue
        counts[hit.doc_id] = count + 1
        deduped.append(hit)
    return deduped
