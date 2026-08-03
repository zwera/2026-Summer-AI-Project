"""3줄·10줄·상세 요약 projection과 canonical·용어 설명 (task 8.1).

``design.md`` "5.5 단계별 요약" 절과 Data Models 6절 ``SummaryBundle``의 다음 규칙을
Python으로 구현한다.

- 3줄: 사건 개요 → 법원 결론 → 현장 경찰 핵심 포인트의 정확히 3개 의미 줄(요구사항 5.2).
- 10줄: 필수 8개 항목을 포함하는 정확히 10개 의미 줄(요구사항 5.3).
- 상세: 같은 필수 8개 항목을 섹션으로 제공하며 줄 수 제한은 없다(요구사항 5.4).
- 단계 변경 시 결론, 적법성, 해당 심급 인정 죄명, 해당 심급 재판 결과는 동일한 canonical
  case projection에서 읽어 일관성을 보장한다(요구사항 5.7).
- 법률 용어의 최초 현장 표현 설명에는 원래 법률 용어를 함께 표시한다(요구사항 5.6).
- 필요한 근거가 없으면 내용을 합성하지 않고 `근거 정보 없음`으로 표시한다(요구사항 5.9).

design.md는 이 계층의 함수를 별도 시그니처로 명시하지 않지만(``TieredSummary`` 컴포넌트가
클라이언트 표시를 담당), "단계 변경 시 ... 동일한 canonical case projection에서 읽어
일관성을 보장한다"는 서술은 순수 도메인 projection 함수가 필요함을 의미한다. 이 모듈의
:func:`project_summary`가 그 projection이다.

## 이 태스크(8.1)의 범위

- 3줄/10줄/상세 각 단계의 구조 계약(지정 key·순서, 필수 key 집합, 정확한 총 줄 수)을
  검증하고, 위반 시 안전하게 실패한다(``SummaryStructureError``) — design.md Error Handling
  원칙 "법률 결론보다 실패가 우선"과 일치한다. 구조 검증기(task 2.x
  ``data.validator_structural``/``data.validator_domain``)가 이미 ``ValidatedDataset``
  생성 시점에 tuple 길이·key membership·canonical 값 일치를 검사하므로, 유효한
  데이터셋에서 이 함수가 실제로 예외를 던지는 경우는 없어야 한다. 그럼에도 이 함수
  자체가 독립적으로 구조를 재확인하는 것은 Property 13("요약 단계의 구조 계약")이
  요구하는 계약을 이 projection 경계에서 직접 보장하기 위함이다.
- canonical 4필드(``canonical_conclusion``·``canonical_legality_status``·
  ``canonical_instance_charge``·``canonical_instance_outcome``)를 ``level`` 인자와
  무관하게 항상 ``bundle``의 동일한 canonical 필드에서 읽는다(요구사항 5.7).
- 각 줄/섹션의 ``text``가 ``None``이면(근거 없음, ``data.models_summary.SummaryLine``
  docstring 참조) 새 문구를 만들지 않고 ``placeholders``에서 ``key == "근거 정보 없음"``
  레코드의 문구로 치환한다(요구사항 5.9).
- ``field_term_explanations``를 해당 단계에 실제로 표시되는 key 집합으로 필터링해
  반환한다 — 3줄 요약에는 "판례 쟁점"처럼 3줄에 없는 블록의 용어 설명이 나타나지
  않아야 하기 때문이다. 필터링만 하며 legal_term·field_expression 조합 자체는
  fixture 값을 그대로 병기해 반환한다(재합성하지 않음, 요구사항 5.6).

## 이 태스크가 하지 않는 것

- ``SummaryBundle`` 자체의 생성(fixture 책임, ``fixtures/mock_dataset.py``) — 이 모듈은
  이미 만들어진 ``SummaryBundle``을 단계별로 projection할 뿐이다.
- 요약 canonical 값과 ``CaseRecord`` 대응 필드의 일치 검증(task 2.2
  ``data.validator_domain``의 ``SUMMARY_CANONICAL_*_MISMATCH`` 진단이 이미 담당).
- 클라이언트 표시 순서 재해석(요구사항 5.11, 클라이언트_웹_계층은 이 함수가 반환한 순서를
  변경·재요약·누락·추가 없이 표시해야 한다).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Sequence, Tuple

from domain.enums import LegalityStatus, SummaryLevel

from data.models_common import DisplayPolicyRecord
from data.models_source import ClaimEvidenceLink
from data.models_summary import (
    DetailedSummarySection,
    DetailedSummarySubsection,
    FieldTermExplanation,
    SummaryBundle,
    SummaryLine,
    SummarySectionKey,
)

__all__ = [
    "THREE_LINE_KEY_ORDER",
    "REQUIRED_SUMMARY_SECTION_KEYS",
    "SummaryStructureError",
    "DisplaySummaryLine",
    "DisplayDetailedSummarySection",
    "SummaryProjection",
    "project_summary",
]


THREE_LINE_KEY_ORDER: Tuple[SummarySectionKey, SummarySectionKey, SummarySectionKey] = (
    "사건 개요",
    "법원 결론",
    "현장 경찰 핵심 포인트",
)
"""요구사항 5.2: 3줄_요약이 순서대로 포함해야 하는 지정 3 key."""

REQUIRED_SUMMARY_SECTION_KEYS: FrozenSet[SummarySectionKey] = frozenset(
    {
        "사건 개요",
        "주요 사실관계",
        "판례 쟁점",
        "법원 결론",
        "적용 법조문",
        "해당 심급 인정 죄명",
        "해당 심급 재판 결과",
        "현장 경찰 핵심 포인트",
    }
)
"""요구사항 5.3, 5.4: 10줄_요약과 상세_요약이 공통으로 포함해야 하는 필수 8 key/section."""

_NO_EVIDENCE_PLACEHOLDER_KEY = "근거 정보 없음"


class SummaryStructureError(ValueError):
    """``SummaryBundle``이 요구사항 5.2~5.4의 구조 계약을 위반할 때 발생한다.

    유효한(검증기를 통과한) 데이터셋에서는 발생하지 않아야 한다 — 발생한다면 데이터셋
    검증기가 놓친 구조 위반이거나 검증 우회 호출이다. 조용히 임의로 보정하는 대신
    명시적으로 안전 실패한다.
    """


@dataclass(frozen=True)
class DisplaySummaryLine:
    """화면 표시용 :class:`~data.models_summary.SummaryLine`.

    ``text``는 원본이 ``None``이면(근거 없음) `근거 정보 없음` 표시 정책 문구로 치환된
    값이다. ``has_evidence``는 원본 ``text``가 있었는지(즉 치환이 일어나지 않았는지)를
    나타낸다.
    """

    key: SummarySectionKey
    text: str
    direct_evidence: Tuple[ClaimEvidenceLink, ...]
    has_evidence: bool


@dataclass(frozen=True)
class DisplayDetailedSummarySection(DisplaySummaryLine):
    """화면 표시용 :class:`~data.models_summary.DetailedSummarySection`."""

    subsections: Tuple[DetailedSummarySubsection, ...] = ()


@dataclass(frozen=True)
class SummaryProjection:
    """:func:`project_summary`의 반환값.

    ``level``이 ``THREE_LINE``/``TEN_LINE``이면 ``lines``에 결과가 담기고
    ``detailed_sections``는 빈 튜플이다. ``level``이 ``DETAILED``이면 반대다. 두 컬렉션이
    동시에 채워지지 않는다.

    canonical 4필드는 ``level``과 무관하게 항상 같은 ``SummaryBundle`` canonical 필드에서
    읽으므로, 같은 판례의 서로 다른 ``SummaryProjection`` 인스턴스 사이에서 항상 동일하다
    (요구사항 5.7, Correctness Property 14).
    """

    level: SummaryLevel
    canonical_conclusion: str
    canonical_legality_status: LegalityStatus
    canonical_instance_charge: str | None
    canonical_instance_outcome: str | None
    lines: Tuple[DisplaySummaryLine, ...]
    detailed_sections: Tuple[DisplayDetailedSummarySection, ...]
    field_term_explanations: Tuple[FieldTermExplanation, ...]


def _find_no_evidence_text(placeholders: Sequence[DisplayPolicyRecord]) -> str:
    for record in placeholders:
        if record.key == _NO_EVIDENCE_PLACEHOLDER_KEY:
            return record.text
    raise SummaryStructureError(
        f"placeholders에 key={_NO_EVIDENCE_PLACEHOLDER_KEY!r} 레코드가 없습니다."
    )


def _resolve_line(line: SummaryLine, no_evidence_text: str) -> DisplaySummaryLine:
    """``line.text``가 ``None``이면(요구사항 5.9) `근거 정보 없음`으로, 아니면 원본을 그대로 담는다."""

    if line.text is not None:
        return DisplaySummaryLine(
            key=line.key,
            text=line.text,
            direct_evidence=line.direct_evidence,
            has_evidence=True,
        )
    return DisplaySummaryLine(
        key=line.key,
        text=no_evidence_text,
        direct_evidence=line.direct_evidence,
        has_evidence=False,
    )


def _resolve_detailed_section(
    section: DetailedSummarySection, no_evidence_text: str
) -> DisplayDetailedSummarySection:
    resolved = _resolve_line(section, no_evidence_text)
    return DisplayDetailedSummarySection(
        key=resolved.key,
        text=resolved.text,
        direct_evidence=resolved.direct_evidence,
        has_evidence=resolved.has_evidence,
        subsections=section.subsections,
    )


def _validate_three_line(bundle: SummaryBundle) -> None:
    keys = tuple(line.key for line in bundle.three_line)
    if keys != THREE_LINE_KEY_ORDER:
        raise SummaryStructureError(
            f"three_line의 key 순서가 {THREE_LINE_KEY_ORDER!r}이어야 하나 {keys!r}임"
        )


def _validate_ten_line(bundle: SummaryBundle) -> None:
    lines = bundle.ten_line
    if len(lines) != 10:
        raise SummaryStructureError(f"ten_line은 정확히 10개여야 하나 {len(lines)}개임")
    present_keys = {line.key for line in lines}
    missing = REQUIRED_SUMMARY_SECTION_KEYS - present_keys
    if missing:
        raise SummaryStructureError(f"ten_line에 필수 key가 없음: {sorted(missing)}")


def _validate_detailed(bundle: SummaryBundle) -> None:
    sections = bundle.detailed
    present_keys = {section.key for section in sections}
    missing = REQUIRED_SUMMARY_SECTION_KEYS - present_keys
    if missing:
        raise SummaryStructureError(f"detailed에 필수 section이 없음: {sorted(missing)}")


def _filter_term_explanations(
    explanations: Sequence[FieldTermExplanation], visible_keys: FrozenSet[str]
) -> Tuple[FieldTermExplanation, ...]:
    """``visible_keys``(현재 단계에 실제로 표시되는 key 집합)에 속하는 최초 설명 위치만 남긴다.

    fixture가 이미 만든 ``(legal_term, field_expression)`` 병기 쌍은 그대로 통과시키고
    새로 합성하지 않는다(요구사항 5.6).
    """

    return tuple(
        explanation
        for explanation in explanations
        if explanation.first_occurrence_block_id in visible_keys
    )


def project_summary(
    bundle: SummaryBundle,
    level: SummaryLevel,
    placeholders: Sequence[DisplayPolicyRecord],
) -> SummaryProjection:
    """``bundle``을 ``level``에 따라 projection한다.

    ``level``과 무관하게 canonical 4필드는 항상 ``bundle``의 동일한 canonical 필드에서
    읽는다(요구사항 5.7). 구조 위반(지정 key·순서·필수 key 누락)이 있으면
    :class:`SummaryStructureError`로 안전하게 실패한다.
    """

    no_evidence_text = _find_no_evidence_text(placeholders)

    lines: Tuple[DisplaySummaryLine, ...]
    detailed_sections: Tuple[DisplayDetailedSummarySection, ...]

    if level is SummaryLevel.THREE_LINE:
        _validate_three_line(bundle)
        visible_keys: FrozenSet[str] = frozenset(THREE_LINE_KEY_ORDER)
        lines = tuple(_resolve_line(line, no_evidence_text) for line in bundle.three_line)
        detailed_sections = ()
    elif level is SummaryLevel.TEN_LINE:
        _validate_ten_line(bundle)
        visible_keys = frozenset(line.key for line in bundle.ten_line)
        lines = tuple(_resolve_line(line, no_evidence_text) for line in bundle.ten_line)
        detailed_sections = ()
    elif level is SummaryLevel.DETAILED:
        _validate_detailed(bundle)
        visible_keys = frozenset(section.key for section in bundle.detailed)
        lines = ()
        detailed_sections = tuple(
            _resolve_detailed_section(section, no_evidence_text) for section in bundle.detailed
        )
    else:  # pragma: no cover - SummaryLevel은 세 값만 선언한다.
        raise SummaryStructureError(f"알 수 없는 SummaryLevel: {level!r}")

    field_term_explanations = _filter_term_explanations(
        bundle.field_term_explanations, visible_keys
    )

    return SummaryProjection(
        level=level,
        canonical_conclusion=bundle.canonical_conclusion,
        canonical_legality_status=bundle.canonical_legality_status,
        canonical_instance_charge=bundle.canonical_instance_charge,
        canonical_instance_outcome=bundle.canonical_instance_outcome,
        lines=lines,
        detailed_sections=detailed_sections,
        field_term_explanations=field_term_explanations,
    )
