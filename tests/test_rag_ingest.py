"""rag.ingest 파싱·청크 분할 로직에 대한 단위 테스트.

임시 디렉토리에 판례 마크다운/법령 텍스트 스텁을 만들어 Gemini/Chroma 없이도
파싱 규칙을 검증한다. 저장소에 이미 있는 실제 판례/법령 데이터를 대상으로 하는
스모크 테스트도 포함한다(회귀 방지).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from rag.ingest import (
    _parse_statute_filename,
    build_all_chunks,
    chunk_precedent,
    chunk_statute,
    iter_precedent_documents,
    iter_statute_documents,
)

_PRECEDENT_MD = """# 경범죄처벌법위반

- **사건번호**: 2019고단4541
- **선고일자**: 2020-07-23
- **법원명**: 수원지법안산지원
- **사건종류**: 형사
- **판결유형**: 판결 : 확정
- **심급**: 1심
- **검색 기준 법률**: 경범죄
- **판례일련번호(ID)**: 226461
- **원문 링크**: https://example.invalid/

## 판시사항

판시사항 본문 예시입니다.

## 판결요지

판결요지 본문 예시입니다.

## 전문

전문 본문 예시입니다.
"""


@pytest.fixture()
def precedent_root(tmp_path: Path) -> Path:
    root = tmp_path / "precedent" / "경범죄" / "1심 판례"
    root.mkdir(parents=True)
    (root / "index.md").write_text("# index (제외 대상)", encoding="utf-8")
    (root / "2020-07-23_2019고단4541.md").write_text(_PRECEDENT_MD, encoding="utf-8")
    return tmp_path / "precedent"


def test_iter_precedent_documents_excludes_index_and_parses_header(precedent_root: Path) -> None:
    documents = list(iter_precedent_documents(precedent_root))
    assert len(documents) == 1
    document = documents[0]
    assert document.title == "경범죄처벌법위반"
    assert document.metadata["case_number"] == "2019고단4541"
    assert document.metadata["instance"] == "1심"
    assert document.metadata["category"] == "경범죄"
    assert document.metadata["court_name"] == "수원지법안산지원"


def test_chunk_precedent_splits_by_section_and_tags_metadata(precedent_root: Path) -> None:
    documents = list(iter_precedent_documents(precedent_root))
    chunks = chunk_precedent(documents[0])
    sections = {chunk.metadata["section"] for chunk in chunks}
    assert {"개요", "판시사항", "판결요지", "전문"} <= sections
    assert all(chunk.doc_type == "PRECEDENT" for chunk in chunks)
    assert all(chunk.metadata["case_number"] == "2019고단4541" for chunk in chunks)
    # 모든 청크는 원본 문서(doc_id)를 정확히 가리켜야 한다.
    assert all(chunk.doc_id == documents[0].doc_id for chunk in chunks)


@pytest.mark.parametrize(
    "filename,expected_law_name,expected_tier",
    [
        ("경범죄 처벌법(법률)(제14908호)(20171024).pdf", "경범죄 처벌법", "법률"),
        ("경범죄 처벌법 시행령(대통령령)(제32523호)(20220308).pdf", "경범죄 처벌법 시행령", "시행령"),
        (
            "경범죄 처벌법 시행규칙(행정안전부령)(제00298호)(20211231).pdf",
            "경범죄 처벌법 시행규칙",
            "시행규칙",
        ),
        ("식품위생법(법률)(제21065호)(20251001) (2).pdf", "식품위생법", "법률"),
    ],
)
def test_parse_statute_filename_extracts_law_name_and_tier(
    filename: str, expected_law_name: str, expected_tier: str
) -> None:
    metadata = _parse_statute_filename(filename)
    assert metadata.law_name == expected_law_name
    assert metadata.tier == expected_tier
    assert metadata.effective_date is not None and len(metadata.effective_date) == 10


def test_parse_statute_filename_falls_back_to_unknown_for_unrecognized_pattern() -> None:
    metadata = _parse_statute_filename("이상한파일명.pdf")
    assert metadata.tier == "UNKNOWN"
    assert metadata.effective_date is None


def test_chunk_statute_splits_by_article_heading() -> None:
    class _FakeDoc:
        def __init__(self) -> None:
            self.doc_id = "statute:test.pdf"
            self.doc_type = "STATUTE"
            self.title = "테스트법"
            self.raw_text = (
                "제1조(목적) 이 법은 목적을 정한다.\n"
                "제2조(정의) 이 법에서 용어를 정의한다."
            )
            self.metadata = {"law_name": "테스트법", "tier": "법률"}

    document = _FakeDoc()
    chunks = chunk_statute(document)  # type: ignore[arg-type]
    articles = [chunk.metadata["article"] for chunk in chunks]
    assert "제1조(목적)" in articles
    assert "제2조(정의)" in articles
    assert all(chunk.doc_type == "STATUTE" for chunk in chunks)


def test_chunk_statute_without_article_headings_falls_back_to_length_split() -> None:
    class _FakeDoc:
        def __init__(self) -> None:
            self.doc_id = "statute:no-articles.pdf"
            self.doc_type = "STATUTE"
            self.title = "조문 없는 문서"
            self.raw_text = "조문 헤딩이 전혀 없는 임의의 텍스트입니다."
            self.metadata = {"law_name": "조문 없는 문서", "tier": "UNKNOWN"}

    document = _FakeDoc()
    chunks = chunk_statute(document)  # type: ignore[arg-type]
    assert len(chunks) == 1
    assert chunks[0].metadata["article"] == ""


# ---------------------------------------------------------------------------
# 실제 저장소 데이터(precedent/, status/세부법령/)를 대상으로 하는 스모크 테스트.
# Gemini/Chroma를 호출하지 않으며, 파일이 없으면 건너뛴다(빈 결과를 오류로 취급하지 않음).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REAL_PRECEDENT_ROOT = _REPO_ROOT / "precedent"
_REAL_STATUTE_ROOT = _REPO_ROOT / "status" / "세부법령"


@pytest.mark.skipif(not _REAL_PRECEDENT_ROOT.is_dir(), reason="실제 판례 데이터 폴더가 없음")
def test_real_precedent_corpus_produces_chunks_with_known_categories() -> None:
    documents = list(iter_precedent_documents(_REAL_PRECEDENT_ROOT))
    assert documents, "precedent/ 아래에서 최소 1개 문서를 읽어야 한다"
    categories = {document.metadata["category"] for document in documents}
    # 현재 저장소에는 최소 이 세 카테고리가 존재해야 한다(회귀 방지).
    assert {"경범죄", "식품", "청소년"} <= categories


@pytest.mark.skipif(not _REAL_STATUTE_ROOT.is_dir(), reason="실제 법령 PDF 폴더가 없음")
def test_real_statute_corpus_parses_all_pdfs_without_unknown_tier() -> None:
    documents = list(iter_statute_documents(_REAL_STATUTE_ROOT))
    assert documents, "status/세부법령/ 아래에서 최소 1개 PDF를 읽어야 한다"
    for document in documents:
        assert document.metadata["tier"] != "UNKNOWN", document.file_path
        assert not document.raw_text.startswith("[PDF_PARSE_ERROR]"), document.file_path


@pytest.mark.skipif(
    not (_REAL_PRECEDENT_ROOT.is_dir() and _REAL_STATUTE_ROOT.is_dir()),
    reason="실제 판례/법령 데이터 폴더가 없음",
)
def test_build_all_chunks_on_real_corpus_returns_both_doc_types() -> None:
    chunks = build_all_chunks(_REAL_PRECEDENT_ROOT, _REAL_STATUTE_ROOT)
    doc_types = {chunk.doc_type for chunk in chunks}
    assert doc_types == {"PRECEDENT", "STATUTE"}
    assert all(chunk.text.strip() for chunk in chunks), "빈 텍스트 청크가 있으면 안 된다"
