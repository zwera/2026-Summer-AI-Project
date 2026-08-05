"""rag.index(Chroma 인덱싱)에 대한 단위 테스트.

Gemini 임베딩 호출을 결정적 가짜 임베더로 대체하고, ``RagSettings.chroma_path``를
``tmp_path``로 지정해 실제 파일시스템에 임시 인덱스를 만든 뒤 검증한다.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

import pytest

from rag.config import RagSettings
from rag.index import build_index, get_chroma_client, get_collection, reset_index


class _FakeEmbedder:
    """호출 횟수를 기록하는 결정적 가짜 임베더(Gemini 미호출)."""

    def __init__(self, settings: RagSettings) -> None:
        self._settings = settings
        self.embed_calls = 0

    def embed_texts(self, texts: Sequence[str], *, task_type: str) -> List[List[float]]:
        self.embed_calls += 1
        return [[float(len(text) % 5), float(len(text) % 3)] for text in texts]


@pytest.fixture()
def settings_with_stub_corpus(tmp_path: Path) -> RagSettings:
    precedent_root = tmp_path / "precedent" / "경범죄" / "1심 판례"
    precedent_root.mkdir(parents=True)
    (precedent_root / "2020-01-01_2020고단1.md").write_text(
        "# 사건명\n\n- **사건번호**: 2020고단1\n- **심급**: 1심\n\n## 판시사항\n\n본문 예시\n",
        encoding="utf-8",
    )
    statute_root = tmp_path / "status"
    statute_root.mkdir(parents=True)

    return RagSettings(
        gemini_api_key="unused",
        chroma_path=tmp_path / ".chroma_index_test",
        collection_name="test_index_collection",
        precedent_root=precedent_root.parent.parent,
        statute_root=statute_root,
        embedding_batch_size=4,
    )


def test_build_index_creates_collection_with_expected_chunk_count(
    settings_with_stub_corpus: RagSettings,
) -> None:
    embedder = _FakeEmbedder(settings_with_stub_corpus)
    count = build_index(settings_with_stub_corpus, embedder)  # type: ignore[arg-type]
    assert count > 0
    assert embedder.embed_calls >= 1


def test_build_index_reuses_existing_collection_without_reembedding(
    settings_with_stub_corpus: RagSettings,
) -> None:
    embedder = _FakeEmbedder(settings_with_stub_corpus)
    first_count = build_index(settings_with_stub_corpus, embedder)  # type: ignore[arg-type]
    calls_after_first_build = embedder.embed_calls

    second_count = build_index(settings_with_stub_corpus, embedder)  # type: ignore[arg-type]
    assert second_count == first_count
    # 재사용 시 재임베딩이 발생하지 않아야 한다(Gemini 호출/비용 절감).
    assert embedder.embed_calls == calls_after_first_build


def test_build_index_force_rebuild_reembeds(settings_with_stub_corpus: RagSettings) -> None:
    embedder = _FakeEmbedder(settings_with_stub_corpus)
    build_index(settings_with_stub_corpus, embedder)  # type: ignore[arg-type]
    calls_after_first_build = embedder.embed_calls

    build_index(settings_with_stub_corpus, embedder, force_rebuild=True)  # type: ignore[arg-type]
    assert embedder.embed_calls > calls_after_first_build


def test_reset_index_removes_collection_data(settings_with_stub_corpus: RagSettings) -> None:
    embedder = _FakeEmbedder(settings_with_stub_corpus)
    build_index(settings_with_stub_corpus, embedder)  # type: ignore[arg-type]

    reset_index(settings_with_stub_corpus)

    client = get_chroma_client(settings_with_stub_corpus)
    collection = get_collection(client, settings_with_stub_corpus)
    assert collection.count() == 0


def test_reset_index_is_safe_to_call_when_no_collection_exists(tmp_path: Path) -> None:
    settings = RagSettings(
        gemini_api_key="unused",
        chroma_path=tmp_path / ".chroma_index_never_created",
        collection_name="never_created_collection",
        precedent_root=tmp_path,
        statute_root=tmp_path,
    )
    reset_index(settings)  # 예외 없이 조용히 종료해야 한다.
