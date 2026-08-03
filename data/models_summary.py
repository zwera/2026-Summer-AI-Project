"""단계별 판례 요약 데이터 모델.

``design.md`` Data Models 6절의 ``SummaryBundle``, ``SummaryLine``,
``DetailedSummarySection``, ``FieldTermExplanation``을 정의한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Tuple

from domain.enums import LegalityStatus

from data.models_source import ClaimEvidenceLink

SummarySectionKey = Literal[
    "사건 개요",
    "주요 사실관계",
    "판례 쟁점",
    "법원 결론",
    "적용 법조문",
    "해당 심급 인정 죄명",
    "해당 심급 재판 결과",
    "현장 경찰 핵심 포인트",
]
"""design.md Data Models 6절 ``SummarySectionKey``."""


@dataclass(frozen=True)
class SummaryLine:
    """요약의 한 의미 줄. design.md Data Models 6절 ``SummaryLine``.

    ``text``가 없으면(``None``) 근거가 없다는 뜻이며, 화면은 빈 문자열을 만들지 않고
    ``근거 정보 없음`` 표시 정책 레코드를 사용해 렌더링한다(요구사항 5.9).
    """

    key: SummarySectionKey
    text: Optional[str]
    direct_evidence: Tuple[ClaimEvidenceLink, ...]


@dataclass(frozen=True)
class DetailedSummarySubsection:
    """``DetailedSummarySection.subsections`` 항목."""

    heading: str
    text: str


@dataclass(frozen=True)
class DetailedSummarySection(SummaryLine):
    """상세_요약의 한 섹션. ``SummaryLine``을 확장해 하위 섹션을 추가로 가질 수 있다."""

    subsections: Tuple[DetailedSummarySubsection, ...] = ()


@dataclass(frozen=True)
class FieldTermExplanation:
    """법률 용어의 최초 현장 표현 설명 위치. design.md Data Models 6절."""

    legal_term: str
    field_expression: str
    first_occurrence_block_id: str


@dataclass(frozen=True)
class SummaryBundle:
    """판례 하나의 3줄·10줄·상세 요약과 canonical 값 묶음. design.md ``SummaryBundle``.

    ``canonical_conclusion``·``canonical_legality_status``·``canonical_instance_charge``·
    ``canonical_instance_outcome``은 요약_단계가 바뀌어도 값이 변하지 않는 정규_결론이며,
    ``CaseRecord``의 대응 필드와 일치해야 한다(요구사항 5.7, Property 14).
    """

    canonical_conclusion: str
    canonical_legality_status: LegalityStatus
    canonical_instance_charge: Optional[str]
    canonical_instance_outcome: Optional[str]
    three_line: Tuple[SummaryLine, SummaryLine, SummaryLine]
    ten_line: Tuple[
        SummaryLine,
        SummaryLine,
        SummaryLine,
        SummaryLine,
        SummaryLine,
        SummaryLine,
        SummaryLine,
        SummaryLine,
        SummaryLine,
        SummaryLine,
    ]
    detailed: Tuple[DetailedSummarySection, ...]
    field_term_explanations: Tuple[FieldTermExplanation, ...]
