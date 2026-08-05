"""실제 RAG 파이프라인에서 사용하는 데이터 구조.

목업 시연 계층(``data/models_case.py`` 등)의 데이터클래스와는 완전히 분리되어 있다.
이 모듈의 타입은 실제 크롤링 판례/법령 원문을 다루기 위한 것이며, 목업 fixture와는
스키마도, 목적도, 신뢰 경계도 다르다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

# 사건번호 접미사(예: "2019고단4541"의 "고단")로 판정하는 심급 분류.
# 크롤러가 저장한 판례가 실제로는 전부 지방법원급 원심(1심)에 해당하는 사건번호
# 접미사만 가지고 있음을 확인했으므로(고단/고정/고합/구단/구합/가단/가합 등),
# 심급 판정은 접미사 패턴 매칭으로 수행하고 불확실하면 "UNKNOWN"으로 남긴다.
CourtInstance = Literal["1심", "항소심", "상고심", "UNKNOWN"]

# 사건번호에서 심급을 나타내는 한글 접미사 목록. 국가법령정보센터 판례 사건번호 표기 관행에 따름.
# 형사 1심: 고단(단독)/고정(즉결심판 정식재판)/고합(합의부)
# 민사 1심: 가단(단독)/가합(합의부)/가소(소액)
# 행정 1심: 구단(단독)/구합(합의부)
# 기타 1심: 카(비송사건)
_FIRST_INSTANCE_SUFFIXES = (
    "고단", "고정", "고합", "구단", "구합", "가단", "가합", "가소", "카",
)
# 형사 항소심: 노 / 민사 항소심: 나 / 행정 항소심: 누
_APPELLATE_SUFFIXES = ("노", "나", "누")
# 형사 상고심: 도 / 민사 상고심: 다 / 행정 상고심: 두
_SUPREME_SUFFIXES = ("도", "다", "두")


@dataclass(frozen=True)
class SourceDocument:
    """인제스트 이전 단계에서 파일 하나를 읽은 원시 결과."""

    doc_id: str
    """저장소 내 파일 상대 경로 기반의 안정적 식별자."""
    doc_type: Literal["PRECEDENT", "STATUTE"]
    title: str
    file_path: str
    raw_text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PrecedentMetadata:
    case_number: str
    decision_date: Optional[str]
    court_name: str
    case_type: str
    judgment_type: str
    search_law_name: str
    instance: CourtInstance
    category: str
    """precedent/<category>/... 경로에서 유래한 최상위 카테고리(예: '경범죄', '식품', '청소년')."""


@dataclass(frozen=True)
class StatuteMetadata:
    law_name: str
    tier: Literal["법률", "시행령", "시행규칙", "UNKNOWN"]
    promulgation_number: Optional[str]
    effective_date: Optional[str]


@dataclass(frozen=True)
class Chunk:
    """임베딩·인덱싱 단위. 하나의 원문 문서는 여러 청크로 분할될 수 있다."""

    chunk_id: str
    doc_id: str
    doc_type: Literal["PRECEDENT", "STATUTE"]
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchHit:
    """Chroma 검색 결과 한 건."""

    chunk_id: str
    doc_id: str
    doc_type: Literal["PRECEDENT", "STATUTE"]
    text: str
    metadata: Dict[str, Any]
    distance: float
    """Chroma가 반환한 거리(코사인 거리 기준, 작을수록 유사)."""


def classify_instance(case_number: str) -> CourtInstance:
    """사건번호 접미사로 심급을 판정한다.

    법원 사건번호는 ``연도 + 접미사(한글) + 순번`` 형식이다(예: ``2019고단4541``).
    접미사가 확인된 1심 패턴(고단/고정/고합/구단/구합/가단/가합/가소/카)에 해당하면
    ``"1심"``을, 항소심 접미사(노/나/누)에 해당하면 ``"항소심"``을, 상고심 접미사
    (도/다/두)에 해당하면 ``"상고심"``을 반환한다. 어느 패턴에도 맞지 않으면
    추측하지 않고 ``"UNKNOWN"``을 반환한다.
    """
    import re

    match = re.search(r"\d+([가-힣]+)\d+", case_number)
    if match is None:
        return "UNKNOWN"
    suffix = match.group(1)
    if suffix in _SUPREME_SUFFIXES:
        return "상고심"
    if suffix in _APPELLATE_SUFFIXES:
        return "항소심"
    if suffix in _FIRST_INSTANCE_SUFFIXES:
        return "1심"
    return "UNKNOWN"
