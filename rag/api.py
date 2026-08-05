"""실제 RAG 파이프라인을 노출하는 FastAPI 애플리케이션.

기존 목업 시연 서버(``web/server.py``, WSGI)와는 완전히 분리된 별도 프로세스로
동작한다. 프론트엔드(``static/app.js``)는 이 서버를 ``/api/rag/*`` 경로로 호출한다.

실행 방법(개발용):
    uvicorn rag.api:app --reload --port 8001

보안 참고: 이 서버는 사용자 인증·권한 검사를 구현하지 않은 상태로 시작한다. 로컬
개발 환경 밖(사내망 공유, 공개 배포 등)에 노출할 경우 반드시 인증/접근 제어를
추가해야 한다.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rag.config import MissingApiKeyError, RagSettings, load_settings
from rag.embedding import GeminiEmbedder
from rag.generation import LegalityReport, generate_report
from rag.index import build_index, get_chroma_client, get_collection
from rag.schemas import SearchHit
from rag.search import SearchFilters, dedupe_by_doc, search

_LOGGER = logging.getLogger(__name__)


class _AppState:
    """앱 전역에서 재사용하는 설정·클라이언트를 담는 간단한 컨테이너."""

    settings: Optional[RagSettings] = None
    embedder: Optional[GeminiEmbedder] = None
    collection = None


_state = _AppState()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """서버 시작 시 설정을 로드하고 Chroma 인덱스를 준비(또는 재사용)한다."""
    try:
        settings = load_settings(require_api_key=True)
        embedder = GeminiEmbedder(settings)
        chunk_count = build_index(settings, embedder, force_rebuild=False)
        client = get_chroma_client(settings)
        collection = get_collection(client, settings)
        _state.settings = settings
        _state.embedder = embedder
        _state.collection = collection
        _LOGGER.info("rag_api_started", extra={"chunk_count": chunk_count})
    except MissingApiKeyError as exc:
        # API 키가 없어도 서버 자체는 기동해서 명확한 오류를 반환하게 한다(수동 재설정 가능).
        _LOGGER.warning("rag_api_started_without_api_key", extra={"reason": str(exc)})
        _state.settings = None
        _state.embedder = None
        _state.collection = None
    yield


app = FastAPI(title="경찰 판례·법령 실제 RAG API", version="0.1.0", lifespan=_lifespan)

# 개발 단계에서는 기존 목업 서버(별도 포트)나 정적 파일 서버에서의 same-origin이 아닌
# 요청도 허용해야 하므로 로컬 개발 origin만 명시적으로 허용한다. 운영 배포 시에는
# 실제 배포 origin으로 좁혀야 한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _require_ready() -> None:
    if _state.settings is None or _state.embedder is None or _state.collection is None:
        raise HTTPException(
            status_code=503,
            detail="RAG 서버가 초기화되지 않았습니다. GEMINI_API_KEY 설정을 확인한 뒤 서버를 재시작하세요.",
        )


class SearchHitOut(BaseModel):
    chunk_id: str
    doc_id: str
    doc_type: Literal["PRECEDENT", "STATUTE"]
    text: str
    metadata: Dict[str, Any]
    distance: float

    @classmethod
    def from_domain(cls, hit: SearchHit) -> "SearchHitOut":
        return cls(
            chunk_id=hit.chunk_id,
            doc_id=hit.doc_id,
            doc_type=hit.doc_type,
            text=hit.text,
            metadata=hit.metadata,
            distance=hit.distance,
        )


class RagQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="현장 상황 자유 텍스트 질의")
    top_k: int = Field(default=8, ge=1, le=30)
    instance: Optional[Literal["1심", "항소심", "상고심"]] = Field(
        default=None, description="심급 필터. 지정하지 않으면 전체 심급을 검색한다."
    )
    category: Optional[str] = Field(
        default=None, description="판례 카테고리 필터(예: '경범죄', '식품', '청소년')"
    )
    include_report: bool = Field(
        default=True, description="False이면 검색 결과만 반환하고 Gemini 리포트 생성을 건너뛴다."
    )


class RagQueryResponse(BaseModel):
    query: str
    hits: List[SearchHitOut]
    report: Optional[LegalityReport] = None


@app.get("/api/rag/health")
def health() -> Dict[str, Union[str, int]]:
    """서버 초기화 상태와 인덱싱된 청크 수를 반환한다."""
    if _state.collection is None:
        return {"status": "NOT_READY", "reason": "GEMINI_API_KEY 미설정 또는 초기화 실패"}
    return {"status": "OK", "chunk_count": _state.collection.count()}


@app.post("/api/rag/query", response_model=RagQueryResponse)
def rag_query(payload: RagQueryRequest) -> RagQueryResponse:
    """질의를 검색하고(선택적으로) Gemini 적법성 리포트를 생성해 반환한다."""
    _require_ready()
    assert _state.settings is not None and _state.embedder is not None and _state.collection is not None

    filters = SearchFilters(instance=payload.instance, category=payload.category)
    raw_hits = search(
        _state.collection,
        _state.embedder,
        payload.query,
        top_k=payload.top_k,
        filters=filters,
    )
    hits = dedupe_by_doc(raw_hits, limit_per_doc=2)

    report: Optional[LegalityReport] = None
    if payload.include_report and hits:
        try:
            report = generate_report(_state.settings, payload.query, hits)
        except Exception as exc:  # noqa: BLE001 - Gemini 호출 실패는 검색 결과는 유지하고 리포트만 생략
            _LOGGER.exception("rag_report_generation_failed")
            raise HTTPException(status_code=502, detail=f"리포트 생성에 실패했습니다: {exc}") from exc

    return RagQueryResponse(
        query=payload.query,
        hits=[SearchHitOut.from_domain(hit) for hit in hits],
        report=report,
    )


@app.post("/api/rag/reindex")
def reindex(force: bool = False) -> Dict[str, Union[str, int]]:
    """인덱스를 재구축한다(원문 파일이 바뀐 경우 관리용으로 호출).

    주의: ``force=True``는 전체 재임베딩을 트리거하므로 Gemini API 비용이 발생한다.
    """
    _require_ready()
    assert _state.settings is not None and _state.embedder is not None
    count = build_index(_state.settings, _state.embedder, force_rebuild=force)
    client = get_chroma_client(_state.settings)
    _state.collection = get_collection(client, _state.settings)
    return {"status": "OK", "chunk_count": count}
