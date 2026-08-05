"""
Part 1 + Part 2: 판례 검색(RAG) 서비스.

실무 용어 보정(term_mapping) -> bge-m3 질의 임베딩 -> ChromaDB 벡터 검색
순서로 처리한다. 리랭커는 사용하지 않고, ChromaDB가 반환하는 코사인 거리를
그대로 유사도(%)로 변환해 정렬 기준으로 사용한다.

판례는 build_index.py에서 "digest"(제목+판시사항+판결요지)와 "full_text"
청크로 나눠 인덱싱되어 있으므로, 같은 판례(precedent_id)의 여러 조각이
검색될 수 있다. 이 서비스는 판례 단위로 중복을 제거해 가장 유사도가 높은
조각의 점수를 대표값으로 사용한다.
"""
from __future__ import annotations

from app.models.schemas import PrecedentHit
from app.services.chroma_service import get_precedent_collection
from app.services.embedding_service import embed_query
from app.taxonomy import LAW_AREA_DEFAULT_CATEGORY
from app.term_mapping import normalize_query


# ChromaDB 컬렉션은 hnsw:space="cosine"으로 생성되어 있어, distance는
# 코사인 거리(0=완전히 동일, 2=완전히 반대)이다.
# similarity(%) = (1 - distance/2) * 100 로 0~100%에 대략 대응시킨다.
def _distance_to_similarity(distance: float) -> float:
    similarity = (1.0 - distance / 2.0) * 100.0
    return max(0.0, min(100.0, round(similarity, 1)))


def _snippet(document: str, metadata: dict, max_len: int = 160) -> str:
    text = metadata.get("content") or document or ""
    text = text.strip().replace("\n", " ")
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def search_precedents(
    query: str, category: str | None = None, top_k: int = 5
) -> tuple[str, list[PrecedentHit]]:
    """질의를 보정하고 벡터 검색을 수행해 판례 단위로 중복 제거된 결과를 반환.

    반환값: (보정된 질의문, PrecedentHit 목록)
    """
    normalized = normalize_query(query)
    query_vec = embed_query(normalized)

    collection = get_precedent_collection()

    where = None
    if category:
        where = {"job_category": category}

    # 판례 단위 중복 제거를 감안해 top_k보다 넉넉히 후보를 가져온다.
    fetch_n = max(top_k * 4, 20)
    result = collection.query(
        query_embeddings=[query_vec.tolist()],
        n_results=fetch_n,
        where=where,
    )

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    best_by_precedent: dict[str, PrecedentHit] = {}
    for doc, meta, distance in zip(documents, metadatas, distances):
        precedent_id = meta.get("precedent_id", "")
        if not precedent_id:
            continue
        similarity = _distance_to_similarity(distance)

        existing = best_by_precedent.get(precedent_id)
        if existing is not None and existing.similarity >= similarity:
            continue

        law_area = meta.get("law_area", "")
        job_category = meta.get("job_category") or (
            LAW_AREA_DEFAULT_CATEGORY.get(law_area, "uncategorized")
        )

        best_by_precedent[precedent_id] = PrecedentHit(
            id=precedent_id,
            title=meta.get("title", ""),
            case_no=meta.get("case_no", ""),
            date=meta.get("date", ""),
            court=meta.get("court", ""),
            category=job_category,
            is_lawful_example=None,
            similarity=similarity,
            summary_snippet=_snippet(doc, meta),
            source_path=meta.get("source_file", ""),
            source_link=meta.get("source_link", ""),
        )

    hits = sorted(
        best_by_precedent.values(), key=lambda h: h.similarity, reverse=True
    )
    return normalized, hits[:top_k]
