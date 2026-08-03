"""구조 검증기 (task 2.1).

``design.md`` "데이터 무결성 검증" 절은 검증을 두 단계로 나눈다::

    1. 구조 검증: 필수 필드, enum, 날짜 형식, tuple 길이, 점수 범위를 스키마로 검사한다.
    2. 도메인/교차 참조 검증: ID 유일성·참조 존재, 체크섬, canonical 값 일치 등 순수
       validator로 검사한다.

이 모듈은 **1단계(구조 검증)만** 구현한다. ID 유일성, 참조 존재, source anchor
체크섬, canonical 값 일치, 현행법 우선순위 배정, 순환 참조 등 교차 참조·도메인
불변식 검증과 불투명 ``ValidatedDataset`` 생성은 task 2.2(``data.validator_domain`` 등)의
책임이며 이 모듈에서 다루지 않는다.

이 모듈이 검사하는 범위:

- 필수 필드 존재(런타임에 주입된 빈 문자열/None처럼 dataclass 생성 시점 타입 검사로
  걸러지지 않는 값)
- enum·``Literal`` 필드가 허용된 값 집합에 속하는지(JSON 등 신뢰되지 않은 원본에서
  주입되었을 때 dataclass 타입 힌트만으로는 걸러지지 않는 값)
- ISO 날짜(``YYYY-MM-DD``)·ISO 날짜시간 형식
- ``SummaryBundle.three_line``/``ten_line`` tuple 길이(정확히 3개/10개)와 각 줄의
  ``key``가 유효한 ``SummarySectionKey``인지
- ``SimilarityPreset.score``가 유한 숫자이고 ``[0, 100]`` 범위인지

각 :class:`Diagnostic`은 ``severity``(``FATAL``/``WARNING``), 위반을 식별할 수 있는
안정적인 ``code``, 위반이 발견된 위치를 가리키는 ``path``, 사람이 읽을 수 있는
``message``를 담는다. ``severity``는 이 모듈이 이미 판단할 수 있는 정보(데이터셋
루트의 핵심 인덱스·안전 고지 관련 필드는 ``FATAL``, 개별 판례·질의·출처 레코드에
국한된 위반은 결과 격리로 복구 가능한 ``WARNING``)만 반영하며, task 2.2는 이 진단을
소비해 최종 치명/복구 가능 분류와 ``ValidatedDataset`` 생성 여부를 결정한다.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Optional, Sequence, Tuple

from data.models_case import AppellateDecision, AppellateInformation, CaseRecord, RelatedInstanceRef
from data.models_common import DisplayPolicyRecord, MockDisplayPolicies, SimilarityWarningPolicyRecord
from data.models_dataset import MockDataset
from data.models_query import QueryFixture, QueryVariant, SimilarityPreset
from data.models_risk import ActionJudgment
from data.models_selection import SelectionReviewFixture
from data.models_source import ResponseTemplate, SourceRecord
from data.models_statute import StatuteRecord, StatuteVersion
from data.models_summary import DetailedSummarySection, SummaryBundle, SummaryLine
from data.models_timeline import RecognizedEvent, VoiceFixture


class Severity(str, Enum):
    """진단의 심각도.

    ``FATAL``은 데이터셋 핵심 인덱스나 안전 고지 자체가 잘못되어 전체 흐름을 안전
    실패시켜야 하는 위반, ``WARNING``은 개별 레코드에 국한되어 레코드_격리로 복구
    가능한 위반을 나타낸다(``design.md`` Error Handling 2절).
    """

    FATAL = "FATAL"
    WARNING = "WARNING"


@dataclass(frozen=True)
class Diagnostic:
    """구조 검증에서 발견한 위반 하나."""

    severity: Severity
    code: str
    path: str
    message: str


def has_fatal(diagnostics: Sequence[Diagnostic]) -> bool:
    """``diagnostics``에 ``FATAL`` 진단이 하나 이상 있는지 반환한다."""

    return any(d.severity is Severity.FATAL for d in diagnostics)


# ---------------------------------------------------------------------------
# 허용 값 집합. ``domain.enums``의 str Enum과 달리 ``data.models_common``의
# ``Literal`` 타입은 런타임에 값을 강제하지 않으므로, 신뢰되지 않은 원본에서 값이
# 슬쩍 들어왔을 때도 잡아낼 수 있도록 이 모듈에서 명시적 집합으로 다시 선언한다.
# ---------------------------------------------------------------------------

_INSTANCE_VALUES = {"1심", "항소심", "상고심"}
_APPELLATE_INSTANCE_VALUES = {"항소심", "상고심"}
_INSTANCE_RELATION_VALUES = {"하급심", "상급심"}
_RELATION_TO_LOWER_INSTANCE_VALUES = {"유지", "변경"}
_FINALITY_VALUES = {"확정", "미확정", "정보_없음"}
_APPELLATE_STATE_VALUES = {"PRESENT", "정보_없음"}
_COURT_FINDING_VALUES = {"PROBLEM", "LAWFUL", "AMBIGUOUS"}
_LEGALITY_STATUS_VALUES = {"적법", "위법", "판단_혼재"}
_LAW_BASIS_STATUS_VALUES = {"현행법_기준", "구법_기준", "법령_상태_판별불가"}
_TRADITIONAL_CASE_AREA_VALUES = {"형사", "민사", "행정"}
_DISPLAY_POLICY_KIND_VALUES = {"NOTICE", "PLACEHOLDER", "STATUS_LABEL"}
_SIMILARITY_WARNING_KEY_VALUES = {"HIGH", "MEDIUM", "LOW"}
_INPUT_MODE_VALUES = {"TEXT", "VOICE_FIXTURE"}
_SOURCE_OWNER_TYPE_VALUES = {"CASE", "STATUTE"}
_SOURCE_KIND_VALUES = {"JUDGMENT_EXCERPT", "STATUTE_TEXT"}
_CLAIM_EVIDENCE_PURPOSE_VALUES = {"DECISION", "REFERENCE"}
_CLAIM_EVIDENCE_RELATION_VALUES = {"SUPPORTS", "CONTRADICTS", "RELATED"}
_CLAIM_EVIDENCE_COVERAGE_VALUES = {"FULL", "PARTIAL", "NONE"}
_RESPONSE_BLOCK_TYPE_VALUES = {"TEXT", "LEGAL_CLAIM"}
_EVENT_AMBIGUITY_KIND_VALUES = {"TIME", "ACTOR", "BOTH"}
_FACT_DIMENSION_VALUES = {
    "체포 시점",
    "영장 유무",
    "동행 자발성",
    "권리 고지 여부",
    "물리력 정도",
    "증거 확보 방식",
    "기타",
}
_SUMMARY_SECTION_KEY_VALUES = {
    "사건 개요",
    "주요 사실관계",
    "판례 쟁점",
    "법원 결론",
    "적용 법조문",
    "해당 심급 인정 죄명",
    "해당 심급 재판 결과",
    "현장 경찰 핵심 포인트",
}
_TARGET_COVERAGE_LABEL_VALUE = "공개적으로 확인 가능한 제1심·항소심·상고심 판례"
_IMPLEMENTED_COVERAGE_LABEL_VALUE = "사전에 정의된 목업 전체 심급 판례 샘플"


def _is_nonempty_str(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_valid_iso_date(value: str) -> bool:
    """``value``가 실제 존재하는 날짜를 나타내는 ``YYYY-MM-DD`` 문자열인지 확인한다.

    ``datetime.date.fromisoformat``은 Python 3.9에서 정확히 ``YYYY-MM-DD`` 형식만
    허용하고 그 외 형식(월/일 생략, 확장 형식 등)은 ``ValueError``를 낸다.
    """

    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_valid_iso_datetime(value: str) -> bool:
    """``value``가 ISO 8601 날짜시간 문자열인지 확인한다.

    Python 3.9의 ``datetime.datetime.fromisoformat``은 ``Z`` 접미사를 지원하지 않으므로
    ``Z``로 끝나는 값은 ``+00:00``으로 바꿔서 검사한다.
    """

    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return True


def _check_iso_date_field(
    value: Optional[str], path: str, diagnostics: List[Diagnostic], *, required: bool = False
) -> None:
    if value is None:
        if required:
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "REQUIRED_FIELD_MISSING",
                    path,
                    f"{path}: 필수 ISO 날짜 필드가 없음",
                )
            )
        return
    if not isinstance(value, str) or not _is_valid_iso_date(value):
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "INVALID_ISO_DATE",
                path,
                f"{path}: ISO 날짜(YYYY-MM-DD) 형식이 아님: {value!r}",
            )
        )


def _check_iso_datetime_field(
    value: Optional[str], path: str, diagnostics: List[Diagnostic]
) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not _is_valid_iso_datetime(value):
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "INVALID_ISO_DATETIME",
                path,
                f"{path}: ISO 날짜시간 형식이 아님: {value!r}",
            )
        )


def _check_enum_membership(
    value: object, allowed: Iterable[str], path: str, code: str, diagnostics: List[Diagnostic]
) -> None:
    allowed_set = allowed if isinstance(allowed, set) else set(allowed)
    if value not in allowed_set:
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                code,
                path,
                f"{path}: 허용되지 않은 값 {value!r} (허용: {sorted(allowed_set)})",
            )
        )


def _check_required_nonempty_str(
    value: object, path: str, diagnostics: List[Diagnostic], *, severity: Severity = Severity.WARNING
) -> None:
    if not _is_nonempty_str(value):
        diagnostics.append(
            Diagnostic(
                severity,
                "REQUIRED_FIELD_EMPTY",
                path,
                f"{path}: 필수 문자열 필드가 비어 있거나 없음",
            )
        )


def _check_similarity_score(score: object, path: str, diagnostics: List[Diagnostic]) -> None:
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(float(score)):
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "SIMILARITY_SCORE_INVALID",
                path,
                f"{path}: 유사도_점수가 유한 숫자가 아님: {score!r}",
            )
        )
        return
    if not (0 <= float(score) <= 100):
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "SIMILARITY_SCORE_OUT_OF_RANGE",
                path,
                f"{path}: 유사도_점수가 [0, 100] 범위를 벗어남: {score!r}",
            )
        )


# ---------------------------------------------------------------------------
# 개별 레코드 유형별 구조 검증
# ---------------------------------------------------------------------------


def _validate_summary_line(line: SummaryLine, path: str, diagnostics: List[Diagnostic]) -> None:
    _check_enum_membership(
        line.key, _SUMMARY_SECTION_KEY_VALUES, f"{path}.key", "INVALID_SUMMARY_SECTION_KEY", diagnostics
    )


def _validate_summary_bundle(bundle: SummaryBundle, path: str, diagnostics: List[Diagnostic]) -> None:
    _check_enum_membership(
        bundle.canonical_legality_status.value
        if hasattr(bundle.canonical_legality_status, "value")
        else bundle.canonical_legality_status,
        _LEGALITY_STATUS_VALUES,
        f"{path}.canonical_legality_status",
        "INVALID_LEGALITY_STATUS",
        diagnostics,
    )

    three_line: Sequence[SummaryLine] = bundle.three_line
    if len(three_line) != 3:
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "SUMMARY_THREE_LINE_LENGTH_MISMATCH",
                f"{path}.three_line",
                f"{path}.three_line: 정확히 3개여야 하나 {len(three_line)}개임",
            )
        )
    for index, line in enumerate(three_line):
        _validate_summary_line(line, f"{path}.three_line[{index}]", diagnostics)

    ten_line: Sequence[SummaryLine] = bundle.ten_line
    if len(ten_line) != 10:
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "SUMMARY_TEN_LINE_LENGTH_MISMATCH",
                f"{path}.ten_line",
                f"{path}.ten_line: 정확히 10개여야 하나 {len(ten_line)}개임",
            )
        )
    for index, line in enumerate(ten_line):
        _validate_summary_line(line, f"{path}.ten_line[{index}]", diagnostics)

    detailed: Sequence[DetailedSummarySection] = bundle.detailed
    for index, section in enumerate(detailed):
        _validate_summary_line(section, f"{path}.detailed[{index}]", diagnostics)


def _validate_appellate_decision(
    decision: AppellateDecision, path: str, diagnostics: List[Diagnostic]
) -> None:
    _check_required_nonempty_str(decision.case_number, f"{path}.case_number", diagnostics)
    _check_enum_membership(
        decision.instance, _APPELLATE_INSTANCE_VALUES, f"{path}.instance", "INVALID_APPELLATE_INSTANCE", diagnostics
    )
    _check_iso_date_field(decision.decision_date, f"{path}.decision_date", diagnostics, required=True)
    _check_enum_membership(
        decision.relation_to_lower_instance,
        _RELATION_TO_LOWER_INSTANCE_VALUES,
        f"{path}.relation_to_lower_instance",
        "INVALID_RELATION_TO_LOWER_INSTANCE",
        diagnostics,
    )


def _validate_appellate_information(
    info: AppellateInformation, path: str, diagnostics: List[Diagnostic]
) -> None:
    _check_enum_membership(
        info.state, _APPELLATE_STATE_VALUES, f"{path}.state", "INVALID_APPELLATE_STATE", diagnostics
    )
    for index, decision in enumerate(info.decisions):
        _validate_appellate_decision(decision, f"{path}.decisions[{index}]", diagnostics)


def _validate_related_instance_ref(
    ref: RelatedInstanceRef, path: str, diagnostics: List[Diagnostic]
) -> None:
    _check_enum_membership(
        ref.instance, _INSTANCE_VALUES, f"{path}.instance", "INVALID_INSTANCE", diagnostics
    )
    _check_enum_membership(
        ref.relation, _INSTANCE_RELATION_VALUES, f"{path}.relation", "INVALID_INSTANCE_RELATION", diagnostics
    )


def _validate_action_judgment(
    judgment: ActionJudgment, path: str, diagnostics: List[Diagnostic]
) -> None:
    _check_required_nonempty_str(judgment.action_id, f"{path}.action_id", diagnostics)
    _check_enum_membership(
        judgment.court_finding, _COURT_FINDING_VALUES, f"{path}.court_finding", "INVALID_COURT_FINDING", diagnostics
    )


def _validate_case(case: CaseRecord, path: str, diagnostics: List[Diagnostic]) -> None:
    _check_required_nonempty_str(case.id, f"{path}.id", diagnostics)
    _check_required_nonempty_str(case.court_name, f"{path}.court_name", diagnostics)
    _check_enum_membership(
        case.instance, _INSTANCE_VALUES, f"{path}.instance", "INVALID_INSTANCE", diagnostics
    )
    _check_required_nonempty_str(case.case_number, f"{path}.case_number", diagnostics)
    _check_iso_date_field(case.decision_date, f"{path}.decision_date", diagnostics, required=True)
    _check_enum_membership(
        case.legality_status.value if hasattr(case.legality_status, "value") else case.legality_status,
        _LEGALITY_STATUS_VALUES,
        f"{path}.legality_status",
        "INVALID_LEGALITY_STATUS",
        diagnostics,
    )
    _check_enum_membership(
        case.expected_law_basis_status.value
        if hasattr(case.expected_law_basis_status, "value")
        else case.expected_law_basis_status,
        _LAW_BASIS_STATUS_VALUES,
        f"{path}.expected_law_basis_status",
        "INVALID_LAW_BASIS_STATUS",
        diagnostics,
    )
    _check_enum_membership(
        case.finality, _FINALITY_VALUES, f"{path}.finality", "INVALID_FINALITY", diagnostics
    )
    if case.traditional_areas is not None:
        for index, area in enumerate(case.traditional_areas):
            _check_enum_membership(
                area,
                _TRADITIONAL_CASE_AREA_VALUES,
                f"{path}.traditional_areas[{index}]",
                "INVALID_TRADITIONAL_CASE_AREA",
                diagnostics,
            )
    for index, judgment in enumerate(case.action_judgments):
        _validate_action_judgment(judgment, f"{path}.action_judgments[{index}]", diagnostics)
    for index, ref in enumerate(case.related_instances):
        _validate_related_instance_ref(ref, f"{path}.related_instances[{index}]", diagnostics)
    _validate_appellate_information(case.appellate, f"{path}.appellate", diagnostics)
    _validate_summary_bundle(case.summaries, f"{path}.summaries", diagnostics)
    for query_id, differences in case.fact_differences_by_query.items():
        for index, difference in enumerate(differences):
            _check_enum_membership(
                difference.dimension,
                _FACT_DIMENSION_VALUES,
                f"{path}.fact_differences_by_query[{query_id}][{index}].dimension",
                "INVALID_FACT_DIMENSION",
                diagnostics,
            )


def _validate_statute_version(
    version: StatuteVersion, path: str, diagnostics: List[Diagnostic]
) -> None:
    _check_required_nonempty_str(version.id, f"{path}.id", diagnostics)
    _check_required_nonempty_str(version.article, f"{path}.article", diagnostics)
    _check_iso_date_field(version.revision_date, f"{path}.revision_date", diagnostics)
    _check_iso_date_field(version.effective_date, f"{path}.effective_date", diagnostics)


def _validate_statute_record(record: StatuteRecord, path: str, diagnostics: List[Diagnostic]) -> None:
    _check_required_nonempty_str(record.id, f"{path}.id", diagnostics)
    _check_required_nonempty_str(record.law_name, f"{path}.law_name", diagnostics)


def _validate_source(source: SourceRecord, path: str, diagnostics: List[Diagnostic]) -> None:
    _check_required_nonempty_str(source.id, f"{path}.id", diagnostics)
    _check_enum_membership(
        source.owner.type, _SOURCE_OWNER_TYPE_VALUES, f"{path}.owner.type", "INVALID_SOURCE_OWNER_TYPE", diagnostics
    )
    _check_enum_membership(
        source.source_kind, _SOURCE_KIND_VALUES, f"{path}.source_kind", "INVALID_SOURCE_KIND", diagnostics
    )
    for index, anchor in enumerate(source.anchors):
        anchor_path = f"{path}.anchors[{index}]"
        if not isinstance(anchor.start_offset, int) or not isinstance(anchor.end_offset, int):
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "SOURCE_ANCHOR_OFFSET_NOT_INT",
                    anchor_path,
                    f"{anchor_path}: start_offset/end_offset가 정수가 아님",
                )
            )
        elif anchor.start_offset < 0 or anchor.end_offset < anchor.start_offset:
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "SOURCE_ANCHOR_OFFSET_INVALID",
                    anchor_path,
                    f"{anchor_path}: offset 범위가 유효하지 않음 "
                    f"(start={anchor.start_offset}, end={anchor.end_offset})",
                )
            )
        _check_required_nonempty_str(anchor.excerpt_checksum, f"{anchor_path}.excerpt_checksum", diagnostics)


def _validate_query_variant(variant: QueryVariant, path: str, diagnostics: List[Diagnostic]) -> None:
    _check_required_nonempty_str(variant.id, f"{path}.id", diagnostics)
    _check_required_nonempty_str(variant.raw_example, f"{path}.raw_example", diagnostics)
    _check_required_nonempty_str(variant.normalized_key, f"{path}.normalized_key", diagnostics)
    _check_enum_membership(
        variant.input_mode, _INPUT_MODE_VALUES, f"{path}.input_mode", "INVALID_INPUT_MODE", diagnostics
    )


def _validate_recognized_event(event: RecognizedEvent, path: str, diagnostics: List[Diagnostic]) -> None:
    _check_required_nonempty_str(event.id, f"{path}.id", diagnostics)
    _check_iso_datetime_field(event.explicit_time, f"{path}.explicit_time", diagnostics)
    _check_iso_datetime_field(event.resolved_sort_time, f"{path}.resolved_sort_time", diagnostics)
    if event.ambiguity is not None:
        _check_enum_membership(
            event.ambiguity.kind,
            _EVENT_AMBIGUITY_KIND_VALUES,
            f"{path}.ambiguity.kind",
            "INVALID_EVENT_AMBIGUITY_KIND",
            diagnostics,
        )


def _validate_query_fixture(query: QueryFixture, path: str, diagnostics: List[Diagnostic]) -> None:
    _check_required_nonempty_str(query.id, f"{path}.id", diagnostics)
    _check_required_nonempty_str(query.core_fact_set_id, f"{path}.core_fact_set_id", diagnostics)
    for index, variant in enumerate(query.variants):
        _validate_query_variant(variant, f"{path}.variants[{index}]", diagnostics)
    for index, event in enumerate(query.recognized_events):
        _validate_recognized_event(event, f"{path}.recognized_events[{index}]", diagnostics)
    for dimension in query.fact_values:
        _check_enum_membership(
            dimension,
            _FACT_DIMENSION_VALUES,
            f"{path}.fact_values[{dimension!r}]",
            "INVALID_FACT_DIMENSION",
            diagnostics,
        )
    for case_id, preset in query.similarity_by_case.items():
        _validate_similarity_preset(preset, f"{path}.similarity_by_case[{case_id}]", diagnostics)


def _validate_similarity_preset(
    preset: SimilarityPreset, path: str, diagnostics: List[Diagnostic]
) -> None:
    _check_similarity_score(preset.score, f"{path}.score", diagnostics)
    if not isinstance(preset.search_priority, int) or isinstance(preset.search_priority, bool):
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "SEARCH_PRIORITY_NOT_INT",
                f"{path}.search_priority",
                f"{path}.search_priority: 정수가 아님: {preset.search_priority!r}",
            )
        )
    if not isinstance(preset.tie_order, int) or isinstance(preset.tie_order, bool):
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "TIE_ORDER_NOT_INT",
                f"{path}.tie_order",
                f"{path}.tie_order: 정수가 아님: {preset.tie_order!r}",
            )
        )


def _validate_response_template(
    template: ResponseTemplate, path: str, diagnostics: List[Diagnostic]
) -> None:
    _check_required_nonempty_str(template.id, f"{path}.id", diagnostics)
    for index, block in enumerate(template.blocks):
        block_path = f"{path}.blocks[{index}]"
        _check_enum_membership(
            block.type, _RESPONSE_BLOCK_TYPE_VALUES, f"{block_path}.type", "INVALID_RESPONSE_BLOCK_TYPE", diagnostics
        )
        if block.type == "LEGAL_CLAIM":
            _check_required_nonempty_str(block.claim_id, f"{block_path}.claim_id", diagnostics)
            for link_index, link in enumerate(block.citation_links):
                _validate_claim_evidence_link(link, f"{block_path}.citation_links[{link_index}]", diagnostics)


def _validate_claim_evidence_link(link: object, path: str, diagnostics: List[Diagnostic]) -> None:
    _check_enum_membership(
        getattr(link, "purpose", None),
        _CLAIM_EVIDENCE_PURPOSE_VALUES,
        f"{path}.purpose",
        "INVALID_CLAIM_EVIDENCE_PURPOSE",
        diagnostics,
    )
    _check_enum_membership(
        getattr(link, "relation", None),
        _CLAIM_EVIDENCE_RELATION_VALUES,
        f"{path}.relation",
        "INVALID_CLAIM_EVIDENCE_RELATION",
        diagnostics,
    )
    _check_enum_membership(
        getattr(link, "coverage", None),
        _CLAIM_EVIDENCE_COVERAGE_VALUES,
        f"{path}.coverage",
        "INVALID_CLAIM_EVIDENCE_COVERAGE",
        diagnostics,
    )


def _validate_selection_review_fixture(
    fixture: SelectionReviewFixture, path: str, diagnostics: List[Diagnostic]
) -> None:
    _check_required_nonempty_str(fixture.response_template_id, f"{path}.response_template_id", diagnostics)
    for index, claim in enumerate(fixture.claims):
        claim_path = f"{path}.claims[{index}]"
        _check_required_nonempty_str(claim.id, f"{claim_path}.id", diagnostics)
        for link_index, link in enumerate(claim.evidence):
            _validate_claim_evidence_link(link, f"{claim_path}.evidence[{link_index}]", diagnostics)


def _validate_voice_fixture(voice: VoiceFixture, path: str, diagnostics: List[Diagnostic]) -> None:
    _check_required_nonempty_str(voice.id, f"{path}.id", diagnostics)
    _check_required_nonempty_str(voice.label, f"{path}.label", diagnostics)


def _validate_display_policy_record(
    record: DisplayPolicyRecord, path: str, diagnostics: List[Diagnostic]
) -> None:
    _check_required_nonempty_str(record.id, f"{path}.id", diagnostics)
    _check_enum_membership(
        record.kind, _DISPLAY_POLICY_KIND_VALUES, f"{path}.kind", "INVALID_DISPLAY_POLICY_KIND", diagnostics
    )
    _check_required_nonempty_str(record.key, f"{path}.key", diagnostics)


def _validate_similarity_warning_policy_record(
    record: SimilarityWarningPolicyRecord, path: str, diagnostics: List[Diagnostic]
) -> None:
    _check_required_nonempty_str(record.id, f"{path}.id", diagnostics)
    _check_enum_membership(
        record.key, _SIMILARITY_WARNING_KEY_VALUES, f"{path}.key", "INVALID_SIMILARITY_WARNING_KEY", diagnostics
    )
    for field_name, value in (
        ("min_inclusive", record.min_inclusive),
        ("max_inclusive", record.max_inclusive),
        ("max_exclusive", record.max_exclusive),
    ):
        if value is None:
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "SIMILARITY_WARNING_BOUND_NOT_FINITE",
                    f"{path}.{field_name}",
                    f"{path}.{field_name}: 유한 숫자가 아님: {value!r}",
                )
            )


def _validate_display_policies(
    policies: MockDisplayPolicies, path: str, diagnostics: List[Diagnostic]
) -> None:
    for index, notice_record in enumerate(policies.notices):
        _validate_display_policy_record(notice_record, f"{path}.notices[{index}]", diagnostics)
    for index, placeholder_record in enumerate(policies.placeholders):
        _validate_display_policy_record(
            placeholder_record, f"{path}.placeholders[{index}]", diagnostics
        )
    for index, status_record in enumerate(policies.status_labels):
        _validate_display_policy_record(
            status_record, f"{path}.status_labels[{index}]", diagnostics
        )
    for index, warning_record in enumerate(policies.similarity_warnings):
        _validate_similarity_warning_policy_record(
            warning_record, f"{path}.similarity_warnings[{index}]", diagnostics
        )


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def validate_structure(dataset: MockDataset) -> Tuple[Diagnostic, ...]:
    """``dataset``에 구조 검증(필수 필드·enum·ISO 날짜·tuple 길이·유사도 범위)을 적용한다.

    반환된 진단이 비어 있으면 구조적으로 유효하다는 뜻이다. ``FATAL`` 진단이 하나라도
    있으면(:func:`has_fatal`) 데이터셋 핵심 인덱스 또는 안전 고지 자체가 손상되었다는
    뜻이므로 task 2.2는 ``ValidatedDataset``을 생성하지 않고 안전 실패해야 한다.
    ``WARNING``만 있으면 해당 레코드만 격리하고 나머지는 계속 검증/사용할 수 있다.

    이 함수는 ID 유일성, 참조 존재, source anchor 체크섬, canonical 값 일치 등 교차
    참조·도메인 불변식을 검사하지 않는다(task 2.2 책임).
    """

    diagnostics: List[Diagnostic] = []

    # --- 데이터셋 루트: 핵심 인덱스·안전 고지 관련 필수 필드는 FATAL로 분류한다. ---
    _check_required_nonempty_str(
        dataset.schema_version, "dataset.schema_version", diagnostics, severity=Severity.FATAL
    )
    _check_required_nonempty_str(
        dataset.dataset_id, "dataset.dataset_id", diagnostics, severity=Severity.FATAL
    )
    _check_required_nonempty_str(
        dataset.dataset_version, "dataset.dataset_version", diagnostics, severity=Severity.FATAL
    )
    _check_required_nonempty_str(
        dataset.normalization_version, "dataset.normalization_version", diagnostics, severity=Severity.FATAL
    )
    if not isinstance(dataset.as_of_date, str) or not _is_valid_iso_date(dataset.as_of_date):
        diagnostics.append(
            Diagnostic(
                Severity.FATAL,
                "INVALID_ISO_DATE",
                "dataset.as_of_date",
                f"dataset.as_of_date: ISO 날짜(YYYY-MM-DD) 형식이 아님: {dataset.as_of_date!r}",
            )
        )
    if dataset.target_coverage_label != _TARGET_COVERAGE_LABEL_VALUE:
        diagnostics.append(
            Diagnostic(
                Severity.FATAL,
                "INVALID_TARGET_COVERAGE_LABEL",
                "dataset.target_coverage_label",
                f"dataset.target_coverage_label: 고정 문구와 다름: {dataset.target_coverage_label!r}",
            )
        )
    if dataset.implemented_coverage_label != _IMPLEMENTED_COVERAGE_LABEL_VALUE:
        diagnostics.append(
            Diagnostic(
                Severity.FATAL,
                "INVALID_IMPLEMENTED_COVERAGE_LABEL",
                "dataset.implemented_coverage_label",
                f"dataset.implemented_coverage_label: 고정 문구와 다름: "
                f"{dataset.implemented_coverage_label!r}",
            )
        )
    _check_required_nonempty_str(
        dataset.legal_safety_notice, "dataset.legal_safety_notice", diagnostics, severity=Severity.FATAL
    )
    _check_required_nonempty_str(
        dataset.instance_caution_notice, "dataset.instance_caution_notice", diagnostics, severity=Severity.FATAL
    )
    _check_required_nonempty_str(
        dataset.no_realtime_sync_label, "dataset.no_realtime_sync_label", diagnostics, severity=Severity.FATAL
    )

    # --- 레코드 컬렉션: 개별 레코드에 국한된 위반은 WARNING(레코드_격리 가능)으로 분류한다. ---
    for index, case in enumerate(dataset.cases):
        _validate_case(case, f"dataset.cases[{index}]", diagnostics)
    for index, statute in enumerate(dataset.statutes):
        _validate_statute_record(statute, f"dataset.statutes[{index}]", diagnostics)
    for index, version in enumerate(dataset.statute_versions):
        _validate_statute_version(version, f"dataset.statute_versions[{index}]", diagnostics)
    for index, source in enumerate(dataset.sources):
        _validate_source(source, f"dataset.sources[{index}]", diagnostics)
    for index, query in enumerate(dataset.queries):
        _validate_query_fixture(query, f"dataset.queries[{index}]", diagnostics)
    for index, template in enumerate(dataset.response_templates):
        _validate_response_template(template, f"dataset.response_templates[{index}]", diagnostics)
    for index, fixture in enumerate(dataset.review_fixtures):
        _validate_selection_review_fixture(fixture, f"dataset.review_fixtures[{index}]", diagnostics)
    for index, voice in enumerate(dataset.voice_fixtures):
        _validate_voice_fixture(voice, f"dataset.voice_fixtures[{index}]", diagnostics)

    _validate_display_policies(dataset.display_policies, "dataset.display_policies", diagnostics)

    return tuple(diagnostics)
