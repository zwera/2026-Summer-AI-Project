"""판례 마크다운과 법령 PDF를 읽어 청크로 변환하는 인제스트 파이프라인.

Gemini/Chroma 호출 없이 순수 파일 파싱·분할만 수행하므로 API 키 없이도 단독으로
테스트할 수 있다.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Literal, Tuple, cast

import pypdf

from rag.schemas import (
    Chunk,
    CourtInstance,
    PrecedentMetadata,
    SourceDocument,
    StatuteMetadata,
    classify_instance,
)

_PRECEDENT_FIELD_PATTERN = re.compile(r"^- \*\*([^*]+)\*\*:\s*(.*)$")
_ARTICLE_HEADING_PATTERN = re.compile(r"(제\d+조(?:의\d+)?\([^)]*\))")


def _relative_doc_id(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def iter_precedent_documents(precedent_root: Path) -> Iterator[SourceDocument]:
    """``precedent/<카테고리>/<하위폴더>/*.md``(index.md 제외)를 순회하며 읽는다."""
    if not precedent_root.is_dir():
        return
    for md_path in sorted(precedent_root.rglob("*.md")):
        if md_path.name == "index.md":
            continue
        raw_text = md_path.read_text(encoding="utf-8")
        category = _infer_category(precedent_root, md_path)
        metadata = _parse_precedent_header(raw_text, category=category)
        title_match = re.search(r"^#\s*(.+)$", raw_text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else md_path.stem
        yield SourceDocument(
            doc_id=f"precedent:{_relative_doc_id(precedent_root, md_path)}",
            doc_type="PRECEDENT",
            title=title,
            file_path=str(md_path),
            raw_text=raw_text,
            metadata=_precedent_metadata_dict(metadata),
        )


def _infer_category(precedent_root: Path, md_path: Path) -> str:
    """``precedent/<카테고리>/...`` 경로에서 최상위 카테고리 이름을 얻는다."""
    relative = md_path.relative_to(precedent_root)
    return relative.parts[0] if relative.parts else "UNKNOWN"


def _parse_precedent_header(raw_text: str, *, category: str) -> PrecedentMetadata:
    fields: Dict[str, str] = {}
    for line in raw_text.splitlines():
        match = _PRECEDENT_FIELD_PATTERN.match(line.strip())
        if match:
            key, value = match.group(1).strip(), match.group(2).strip()
            fields[key] = value

    case_number = fields.get("사건번호", "")
    declared_instance = fields.get("심급", "")
    instance: CourtInstance
    if declared_instance in ("1심", "항소심", "상고심"):
        instance = cast(Literal["1심", "항소심", "상고심"], declared_instance)
    else:
        instance = classify_instance(case_number)

    return PrecedentMetadata(
        case_number=case_number,
        decision_date=fields.get("선고일자") or None,
        court_name=fields.get("법원명", ""),
        case_type=fields.get("사건종류", ""),
        judgment_type=fields.get("판결유형", ""),
        search_law_name=fields.get("검색 기준 법률", ""),
        instance=instance,
        category=category,
    )


def _precedent_metadata_dict(metadata: PrecedentMetadata) -> Dict[str, Any]:
    return {
        "case_number": metadata.case_number,
        "decision_date": metadata.decision_date or "",
        "court_name": metadata.court_name,
        "case_type": metadata.case_type,
        "judgment_type": metadata.judgment_type,
        "search_law_name": metadata.search_law_name,
        "instance": metadata.instance,
        "category": metadata.category,
    }


# 실제 파일명 형식: "<법령명>(<공포기관 유형>)(<공포번호>)(<시행일 YYYYMMDD>).pdf"
# 예: "식품위생법 시행령(대통령령)(제35811호)(20251001).pdf",
#     "경범죄 처벌법(법률)(제14908호)(20171024).pdf".
# "시행령"/"시행규칙" 여부는 첫 괄호(공포기관 유형)가 아니라 법령명 자체에 포함되어 있으므로
# 법령명 문자열로 tier를 판정한다.
_PDF_FILENAME_PATTERN = re.compile(
    r"^(?P<law_name>[^(（]+)\((?P<issuing_body>[^)]+)\)\((?P<promulgation_number>[^)]+)\)\((?P<date>\d{8})\)"
)


def iter_statute_documents(statute_root: Path) -> Iterator[SourceDocument]:
    """``status/세부법령/*.pdf``를 읽어 텍스트를 추출한다."""
    if not statute_root.is_dir():
        return
    for pdf_path in sorted(statute_root.glob("*.pdf")):
        try:
            reader = pypdf.PdfReader(str(pdf_path))
            full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:  # noqa: BLE001 - 개별 PDF 파싱 실패는 건너뛰고 계속 진행
            full_text = f"[PDF_PARSE_ERROR] {pdf_path.name}: {exc}"
        metadata = _parse_statute_filename(pdf_path.name)
        yield SourceDocument(
            doc_id=f"statute:{pdf_path.name}",
            doc_type="STATUTE",
            title=metadata.law_name,
            file_path=str(pdf_path),
            raw_text=full_text,
            metadata=_statute_metadata_dict(metadata),
        )


def _parse_statute_filename(filename: str) -> StatuteMetadata:
    match = _PDF_FILENAME_PATTERN.match(filename)
    if match is None:
        return StatuteMetadata(
            law_name=filename.rsplit(".pdf", 1)[0],
            tier="UNKNOWN",
            promulgation_number=None,
            effective_date=None,
        )
    law_name = match.group("law_name").strip()
    tier: Literal["법률", "시행령", "시행규칙", "UNKNOWN"]
    if "시행규칙" in law_name:
        tier = "시행규칙"
    elif "시행령" in law_name:
        tier = "시행령"
    else:
        # 공포기관 유형(예: '법률', '대통령령', '총리령', '행정안전부령')과 무관하게, 법령명에
        # 시행령/시행규칙 표기가 없으면 최상위 법률로 간주한다.
        tier = "법률"
    date_raw = match.group("date")
    effective_date = f"{date_raw[0:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
    return StatuteMetadata(
        law_name=law_name,
        tier=tier,
        promulgation_number=match.group("promulgation_number"),
        effective_date=effective_date,
    )


def _statute_metadata_dict(metadata: StatuteMetadata) -> Dict[str, Any]:
    return {
        "law_name": metadata.law_name,
        "tier": metadata.tier,
        "promulgation_number": metadata.promulgation_number or "",
        "effective_date": metadata.effective_date or "",
    }


# 청크 하나가 지나치게 길어 Gemini 임베딩 토큰 한도(8192 토큰)를 넘지 않도록 문자 수
# 기준으로 넉넉히 잘라준다(한국어 법률 텍스트 기준 대략적인 안전 여유치).
_MAX_CHUNK_CHARS = 2000
_CHUNK_OVERLAP_CHARS = 200


def chunk_precedent(document: SourceDocument) -> List[Chunk]:
    """판례 문서를 판시사항/판결요지/참조조문/전문 섹션 단위로 분할한다."""
    sections = _split_markdown_sections(document.raw_text)
    chunks: List[Chunk] = []
    for section_index, (heading, body) in enumerate(sections):
        text = body.strip()
        if not text:
            continue
        for part_index, part in enumerate(_split_long_text(text)):
            chunk_id = f"{document.doc_id}#s{section_index}-{part_index}"
            chunk_metadata: Dict[str, Any] = dict(document.metadata)
            chunk_metadata["doc_id"] = document.doc_id
            chunk_metadata["title"] = document.title
            chunk_metadata["section"] = heading
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    doc_id=document.doc_id,
                    doc_type="PRECEDENT",
                    text=f"[{document.title}] {heading}\n{part}",
                    metadata=chunk_metadata,
                )
            )
    return chunks


def _split_markdown_sections(raw_text: str) -> List[Tuple[str, str]]:
    """``## 제목`` 헤딩 기준으로 (제목, 본문) 쌍 목록을 만든다. 헤딩 이전 헤더 블록은 '개요'로 묶는다."""
    lines = raw_text.splitlines()
    sections: List[Tuple[str, str]] = []
    current_heading = "개요"
    current_lines: List[str] = []
    for line in lines:
        heading_match = re.match(r"^##\s+(.+)$", line.strip())
        if heading_match:
            sections.append((current_heading, "\n".join(current_lines)))
            current_heading = heading_match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    sections.append((current_heading, "\n".join(current_lines)))
    return sections


def chunk_statute(document: SourceDocument) -> List[Chunk]:
    """법령 PDF 텍스트를 조문(``제N조(...)``) 단위로 분할한다."""
    matches = list(_ARTICLE_HEADING_PATTERN.finditer(document.raw_text))
    chunks: List[Chunk] = []
    if not matches:
        # 조문 헤딩을 찾지 못하면(예: 파싱 실패) 문서 전체를 길이 기준으로만 분할한다.
        for part_index, part in enumerate(_split_long_text(document.raw_text)):
            chunk_metadata: Dict[str, Any] = dict(document.metadata)
            chunk_metadata["doc_id"] = document.doc_id
            chunk_metadata["title"] = document.title
            chunk_metadata["article"] = ""
            chunks.append(
                Chunk(
                    chunk_id=f"{document.doc_id}#p{part_index}",
                    doc_id=document.doc_id,
                    doc_type="STATUTE",
                    text=part,
                    metadata=chunk_metadata,
                )
            )
        return chunks

    boundaries = [match.start() for match in matches] + [len(document.raw_text)]
    for article_index, match in enumerate(matches):
        article_heading = match.group(1)
        body = document.raw_text[boundaries[article_index] : boundaries[article_index + 1]].strip()
        for part_index, part in enumerate(_split_long_text(body)):
            article_chunk_metadata: Dict[str, Any] = dict(document.metadata)
            article_chunk_metadata["doc_id"] = document.doc_id
            article_chunk_metadata["title"] = document.title
            article_chunk_metadata["article"] = article_heading
            chunks.append(
                Chunk(
                    chunk_id=f"{document.doc_id}#a{article_index}-{part_index}",
                    doc_id=document.doc_id,
                    doc_type="STATUTE",
                    text=f"[{document.title}] {part}",
                    metadata=article_chunk_metadata,
                )
            )
    return chunks


def _split_long_text(text: str) -> List[str]:
    """긴 텍스트를 겹침을 두고 문자 수 기준으로 분할한다."""
    if len(text) <= _MAX_CHUNK_CHARS:
        return [text]
    parts: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + _MAX_CHUNK_CHARS, len(text))
        parts.append(text[start:end])
        if end == len(text):
            break
        start = end - _CHUNK_OVERLAP_CHARS
    return parts


def build_all_chunks(precedent_root: Path, statute_root: Path) -> List[Chunk]:
    """전체 판례·법령 문서를 읽어 청크 목록을 만든다(임베딩 이전 단계)."""
    chunks: List[Chunk] = []
    for document in iter_precedent_documents(precedent_root):
        chunks.extend(chunk_precedent(document))
    for document in iter_statute_documents(statute_root):
        chunks.extend(chunk_statute(document))
    return chunks
