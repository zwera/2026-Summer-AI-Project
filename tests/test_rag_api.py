"""rag.api(FastAPI 앱)에 대한 단위 테스트.

앱의 ``lifespan``이 실제로 Gemini API를 호출하지 않도록, ``GEMINI_API_KEY``가
없는 상태(초기화 실패)와 내부 상태(``_state``)를 직접 주입한 상태(성공) 두 가지를
검증한다. 실제 네트워크 호출은 어떤 테스트에서도 발생하지 않는다.
"""
from __future__ import annotations

from typing import Any, Iterator, List

import chromadb
import pytest
from fastapi.testclient import TestClient

import rag.api as rag_api
from rag.generation import LegalityReport


@pytest.fixture(autouse=True)
def _reset_state_after_each_test() -> Iterator[None]:
    """각 테스트가 ``rag_api._state``를 오염시키지 않도록 종료 후 초기화한다."""
    yield
    rag_api._state.settings = None
    rag_api._state.embedder = None
    rag_api._state.collection = None


def test_health_reports_not_ready_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with TestClient(rag_api.app) as client:
        response = client.get("/api/rag/health")
        assert response.status_code == 200
        assert response.json()["status"] == "NOT_READY"


def test_query_returns_503_when_not_initialized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with TestClient(rag_api.app) as client:
        response = client.post("/api/rag/query", json={"query": "테스트 질의"})
        assert response.status_code == 503


def test_query_request_validation_rejects_empty_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with TestClient(rag_api.app) as client:
        response = client.post("/api/rag/query", json={"query": ""})
        assert response.status_code == 422


class _FakeEmbedder:
    """Gemini를 호출하지 않는 결정적 가짜 임베더. rag.index._add_chunks_in_batches와
    동일한 ``_settings.embedding_batch_size`` 접근 패턴을 지원한다."""

    def __init__(self) -> None:
        from rag.config import RagSettings
        from pathlib import Path

        self._settings = RagSettings(
            gemini_api_key="unused", chroma_path=Path("unused"), precedent_root=Path("unused"),
            statute_root=Path("unused"),
        )

    def embed_query(self, text: str) -> List[float]:
        return [float(len(text) % 5), float(len(text) % 3)]


def _install_ready_state_with_one_hit() -> None:
    """API 준비 완료 상태를 흉내 내되, Chroma는 실제 in-memory 클라이언트를 쓰고
    Gemini 호출은 하지 않는다(질의 검색까지만 확인, 리포트 생성은 별도 테스트에서 monkeypatch)."""
    from pathlib import Path
    from rag.config import RagSettings

    client = chromadb.Client()
    collection = client.get_or_create_collection("test_rag_api_collection")
    collection.add(
        ids=["p1"],
        embeddings=[[1.0, 2.0]],
        documents=["판례 발췌"],
        metadatas=[{"doc_type": "PRECEDENT", "doc_id": "precedent:a.md", "case_number": "2019고단4541"}],
    )
    rag_api._state.settings = RagSettings(
        gemini_api_key="unused", chroma_path=Path("unused"), precedent_root=Path("unused"),
        statute_root=Path("unused"),
    )
    rag_api._state.embedder = _FakeEmbedder()  # type: ignore[assignment]
    rag_api._state.collection = collection


def test_query_without_report_returns_search_hits_only() -> None:
    # lifespan(startup)이 GEMINI_API_KEY 부재로 _state를 초기화하므로, TestClient
    # 컨텍스트에 "진입한 뒤"에 준비 상태를 주입해야 한다(진입 전에 주입하면 덮어써짐).
    with TestClient(rag_api.app) as client:
        _install_ready_state_with_one_hit()
        response = client.post(
            "/api/rag/query", json={"query": "질의", "top_k": 5, "include_report": False}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["report"] is None
    assert len(body["hits"]) == 1
    assert body["hits"][0]["doc_type"] == "PRECEDENT"


def test_query_with_report_calls_generate_report_and_returns_it(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_generate_report(settings: Any, query: str, hits: Any, *, client: Any = None) -> LegalityReport:
        return LegalityReport(
            overall_assessment="적법",
            key_risks=[],
            reasoning="테스트 근거",
            cited_precedents=[],
            timeline=[],
        )

    monkeypatch.setattr(rag_api, "generate_report", _fake_generate_report)

    with TestClient(rag_api.app) as client:
        _install_ready_state_with_one_hit()
        response = client.post(
            "/api/rag/query", json={"query": "질의", "top_k": 5, "include_report": True}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["report"]["overall_assessment"] == "적법"


def test_query_with_no_hits_skips_report_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """검색 결과가 비어 있으면 include_report=True여도 Gemini를 호출하지 않는다."""
    from pathlib import Path
    from rag.config import RagSettings

    client_db = chromadb.Client()
    empty_collection = client_db.get_or_create_collection("test_rag_api_empty_collection")
    called = {"count": 0}

    def _fail_if_called(*args: Any, **kwargs: Any) -> LegalityReport:
        called["count"] += 1
        raise AssertionError("빈 검색 결과에서는 generate_report가 호출되면 안 된다")

    monkeypatch.setattr(rag_api, "generate_report", _fail_if_called)

    with TestClient(rag_api.app) as client:
        rag_api._state.settings = RagSettings(
            gemini_api_key="unused", chroma_path=Path("unused"), precedent_root=Path("unused"),
            statute_root=Path("unused"),
        )
        rag_api._state.embedder = _FakeEmbedder()  # type: ignore[assignment]
        rag_api._state.collection = empty_collection
        response = client.post(
            "/api/rag/query", json={"query": "질의", "top_k": 5, "include_report": True}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["hits"] == []
    assert body["report"] is None
    assert called["count"] == 0


def test_query_report_generation_failure_returns_502(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args: Any, **kwargs: Any) -> LegalityReport:
        raise RuntimeError("Gemini 호출 실패 시뮬레이션")

    monkeypatch.setattr(rag_api, "generate_report", _raise)

    with TestClient(rag_api.app) as client:
        _install_ready_state_with_one_hit()
        response = client.post(
            "/api/rag/query", json={"query": "질의", "top_k": 5, "include_report": True}
        )
    assert response.status_code == 502
