"""도메인·교차 참조 불변식 검증기 (task 2.2).

``data.validator_structural``가 구조 검증(필수 필드·enum·ISO 날짜 형식·tuple 길이·유사도
점수 범위)만 다루는 것과 달리, 이 모듈은 ``design.md`` "데이터 무결성 검증" 절의 2단계인
교차 참조·도메인 불변식 검증을 구현한다:

- ID 유일성(``CaseId``·``QueryId``·``StatuteVersionId``·``SourceId``·``ClaimId``는
  데이터셋 전체에서, ``EventId``는 하나의 ``QueryFixture`` 타임라인 내에서 유일해야 한다)
- 참조 존재(모든 ID 참조가 실제 존재하는 레코드에 해석되어야 한다)
- source→anchor 범위·체크섬(``design.md`` "체크섬은 앵커가 가리키는 부분 문자열의 빌드 시
  해시와 일치해야 한다"에 따라 ``body[start_offset:end_offset]``의 sha256 hex digest와
  ``excerpt_checksum``이 일치해야 한다)
- 표시 정책 레코드 ID 유일성(``notices``·``placeholders``·``status_labels`` 전체와
  ``similarity_warnings``는 각각 별도 네임스페이스에서 유일해야 한다)
- 유사도 경고 구간 ``[0, 100]``의 무결(gap 없음)·비중첩(overlap 없음)
- 판례 요약 canonical 값(``canonical_legality_status``·``canonical_instance_charge``·
  ``canonical_instance_outcome``)과 ``CaseRecord`` 대응 필드의 일치
- 현행법_기준 판례가 같은 질의 결과 집합 안에서 구법_기준 판례보다 낮은(더 큰 수의)
  ``searchPriority``를 갖지 않는지 확인(``design.md`` "검증기는 현행법 기준 판례의
  우선순위가 구법 기준 판례보다 낮은 순위가 되지 않도록 확인한다")
- 상대 시각(``RelativeTime.anchor_event_id``) 참조 그래프의 비순환성

이 모듈은 ``data.validator_structural``의 ``Diagnostic``/``Severity``/``has_fatal``을
재사용하며 다시 정의하지 않는다.

## 심각도 분류 원칙

``design.md`` Error Handling 2절과 이 태스크의 요구("치명 오류는 안전 실패 상태로, 결과
국한 복구 가능 오류는 진단으로 분리한다")에 따라 다음과 같이 분류한다.

- **FATAL**(데이터셋 전체를 안전하게 사용할 수 없게 만드는 구조적 손상): 전역 ID 레지스트리
  (``CaseId``·``QueryId``·``StatuteVersionId``·``SourceId``·``ClaimId``) 중복, 표시 정책
  레지스트리 중복, 유사도 경고 구간이 ``[0, 100]``을 완전히·유일하게 덮지 못함(gap/overlap).
  이런 위반은 이후 모든 조회·정렬·표시가 어느 레코드를 참조해야 하는지 자체가 모호해지므로
  레코드 하나만 격리해서는 복구할 수 없다.
- **WARNING**(개별 레코드·질의에 국한되어 레코드_격리로 복구 가능): 단일 판례의 끊긴 참조,
  단일 anchor의 범위/체크섬 오류, 단일 판례의 canonical 값 불일치, 단일 질의 타임라인의
  중복 ``EventId``·순환/끊긴 상대 시각 anchor, 단일 질의 결과 집합 안의 현행법 우선순위
  위반. 이런 위반은 해당 레코드(판례/질의/출처/응답 template/재검토 fixture/음성 fixture)만
  제외하면 나머지 데이터셋은 안전하게 계속 사용할 수 있다.

## 격리(레코드_격리) 방식

이 모듈은 진단만 생성하고, 어떤 레코드를 격리할지는 :func:`validate_domain_detailed`가
반환하는 :class:`Exclusions`에 기록한다. 격리는 위반이 발견된 **최상위 레코드**(판례,
질의, 출처, 응답 template, 재검토 fixture, 음성 fixture) 단위로만 이루어지며, 전이적
(cascading) 격리는 하지 않는다. 예를 들어 판례 A가 출처 B를 참조하고 B의 체크섬이
잘못되었다면 B만 격리되고 A는 격리되지 않는다(단, A 자체가 다른 이유로 격리 대상이면
별도로 격리된다). 이는 "레코드_격리: 유효하지 않은 목업_데이터_레코드 또는 참조만
결과에서 제외"라는 용어집 정의를 그대로 따르면서도 목업 시연 규모에서 지나치게 복잡한
전이적 격리 그래프를 만들지 않기 위한 단순화 결정이다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from domain.enums import LawBasisStatus
from domain.ids import CaseId, ClaimId, EventId, QueryId, SourceId, StatuteVersionId

from data.models_case import CaseRecord
from data.models_common import VoiceFixtureId
from data.models_dataset import MockDataset
from data.models_query import QueryFixture
from data.models_selection import SelectionReviewFixture
from data.models_source import LegalClaimBlock, ResponseTemplate, SourceRecord
from data.models_timeline import RecognizedEvent, VoiceFixture
from data.validator_structural import Diagnostic, Severity, has_fatal

__all__ = [
    "Diagnostic",
    "Severity",
    "has_fatal",
    "Exclusions",
    "validate_domain",
    "validate_domain_detailed",
]


@dataclass(frozen=True)
class Exclusions:
    """도메인 검증에서 격리(제외)하기로 결정된 최상위 레코드 ID 집합.

    :func:`data.validated_dataset.validate_dataset`이 이 정보로 "clean" 뷰에서 제외할
    레코드를 결정한다.
    """

    case_ids: FrozenSet[CaseId] = frozenset()
    query_ids: FrozenSet[QueryId] = frozenset()
    source_ids: FrozenSet[SourceId] = frozenset()
    response_template_ids: FrozenSet[str] = frozenset()
    review_fixture_response_template_ids: FrozenSet[str] = frozenset()
    voice_fixture_ids: FrozenSet[VoiceFixtureId] = frozenset()


@dataclass
class _MutableExclusions:
    """검증 도중 채우는 격리 대상 누적 집합. 완료 후 :class:`Exclusions`로 동결한다."""

    case_ids: Set[CaseId] = field(default_factory=set)
    query_ids: Set[QueryId] = field(default_factory=set)
    source_ids: Set[SourceId] = field(default_factory=set)
    response_template_ids: Set[str] = field(default_factory=set)
    review_fixture_response_template_ids: Set[str] = field(default_factory=set)
    voice_fixture_ids: Set[VoiceFixtureId] = field(default_factory=set)

    def freeze(self) -> Exclusions:
        return Exclusions(
            case_ids=frozenset(self.case_ids),
            query_ids=frozenset(self.query_ids),
            source_ids=frozenset(self.source_ids),
            response_template_ids=frozenset(self.response_template_ids),
            review_fixture_response_template_ids=frozenset(self.review_fixture_response_template_ids),
            voice_fixture_ids=frozenset(self.voice_fixture_ids),
        )


# ---------------------------------------------------------------------------
# (a) ID 유일성 + (d) 표시 정책 유일성
# ---------------------------------------------------------------------------


def _find_duplicates(values: Sequence[object]) -> List[object]:
    """``values``에서 두 번째 이상 등장하는 값을 등장 순서대로 반환한다(중복 자체를 나열)."""

    seen: Set[object] = set()
    dupes: List[object] = []
    for value in values:
        if value in seen:
            dupes.append(value)
        else:
            seen.add(value)
    return dupes


def _check_global_id_uniqueness(dataset: MockDataset, diagnostics: List[Diagnostic]) -> None:
    for case_id in _find_duplicates([c.id for c in dataset.cases]):
        diagnostics.append(
            Diagnostic(
                Severity.FATAL,
                "DUPLICATE_CASE_ID",
                "dataset.cases",
                f"dataset.cases: CaseId 중복: {case_id!r}",
            )
        )
    for query_id in _find_duplicates([q.id for q in dataset.queries]):
        diagnostics.append(
            Diagnostic(
                Severity.FATAL,
                "DUPLICATE_QUERY_ID",
                "dataset.queries",
                f"dataset.queries: QueryId 중복: {query_id!r}",
            )
        )
    for version_id in _find_duplicates([v.id for v in dataset.statute_versions]):
        diagnostics.append(
            Diagnostic(
                Severity.FATAL,
                "DUPLICATE_STATUTE_VERSION_ID",
                "dataset.statute_versions",
                f"dataset.statute_versions: StatuteVersionId 중복: {version_id!r}",
            )
        )
    for source_id in _find_duplicates([s.id for s in dataset.sources]):
        diagnostics.append(
            Diagnostic(
                Severity.FATAL,
                "DUPLICATE_SOURCE_ID",
                "dataset.sources",
                f"dataset.sources: SourceId 중복: {source_id!r}",
            )
        )

    claim_ids: List[ClaimId] = []
    for template in dataset.response_templates:
        for block in template.blocks:
            if isinstance(block, LegalClaimBlock):
                claim_ids.append(block.claim_id)
    for claim_id in _find_duplicates(claim_ids):
        diagnostics.append(
            Diagnostic(
                Severity.FATAL,
                "DUPLICATE_CLAIM_ID",
                "dataset.response_templates",
                f"dataset.response_templates: ClaimId 중복: {claim_id!r}",
            )
        )


def _check_display_policy_uniqueness(dataset: MockDataset, diagnostics: List[Diagnostic]) -> None:
    policies = dataset.display_policies
    all_ids = (
        [r.id for r in policies.notices]
        + [r.id for r in policies.placeholders]
        + [r.id for r in policies.status_labels]
    )
    for record_id in _find_duplicates(all_ids):
        diagnostics.append(
            Diagnostic(
                Severity.FATAL,
                "DUPLICATE_DISPLAY_POLICY_ID",
                "dataset.display_policies",
                f"dataset.display_policies: DisplayPolicyRecord.id 중복(notices/placeholders/"
                f"status_labels 통합 네임스페이스): {record_id!r}",
            )
        )
    similarity_ids = [r.id for r in policies.similarity_warnings]
    for record_id in _find_duplicates(similarity_ids):
        diagnostics.append(
            Diagnostic(
                Severity.FATAL,
                "DUPLICATE_SIMILARITY_WARNING_POLICY_ID",
                "dataset.display_policies.similarity_warnings",
                f"dataset.display_policies.similarity_warnings: id 중복: {record_id!r}",
            )
        )


# ---------------------------------------------------------------------------
# (e) 유사도 경고 구간 [0, 100] 무결·비중첩
# ---------------------------------------------------------------------------


def _check_similarity_warning_band_coverage(dataset: MockDataset, diagnostics: List[Diagnostic]) -> None:
    records = dataset.display_policies.similarity_warnings
    path = "dataset.display_policies.similarity_warnings"
    if not records:
        diagnostics.append(
            Diagnostic(Severity.FATAL, "SIMILARITY_WARNING_BANDS_EMPTY", path, f"{path}: 유사도 경고 구간이 하나도 없음")
        )
        return

    bands: List[Tuple[float, float, bool, str]] = []
    for record in records:
        upper: Optional[float]
        upper_inclusive: bool
        if record.max_inclusive is not None:
            upper = float(record.max_inclusive)
            upper_inclusive = True
        elif record.max_exclusive is not None:
            upper = float(record.max_exclusive)
            upper_inclusive = False
        else:
            upper = None
            upper_inclusive = False
        if upper is None:
            diagnostics.append(
                Diagnostic(
                    Severity.FATAL,
                    "SIMILARITY_WARNING_BAND_MISSING_UPPER_BOUND",
                    path,
                    f"{path}: {record.id!r} 구간에 max_inclusive/max_exclusive가 모두 없음",
                )
            )
            continue
        bands.append((float(record.min_inclusive), upper, upper_inclusive, record.id))

    if len(bands) != len(records):
        return  # 상한이 없는 구간이 있으면 순서 검사를 진행할 수 없다(이미 FATAL 보고됨).

    bands.sort(key=lambda b: b[0])

    first_lower, _, _, first_id = bands[0]
    if first_lower != 0.0:
        diagnostics.append(
            Diagnostic(
                Severity.FATAL,
                "SIMILARITY_WARNING_BAND_LOWER_BOUND_INVALID",
                path,
                f"{path}: 가장 낮은 구간({first_id!r})의 min_inclusive가 0이 아님: {first_lower!r}",
            )
        )

    last_lower, last_upper, last_upper_inclusive, last_id = bands[-1]
    if not (last_upper == 100.0 and last_upper_inclusive):
        diagnostics.append(
            Diagnostic(
                Severity.FATAL,
                "SIMILARITY_WARNING_BAND_UPPER_BOUND_INVALID",
                path,
                f"{path}: 가장 높은 구간({last_id!r})이 100을 포함해 닫혀 있지 않음 "
                f"(upper={last_upper!r}, inclusive={last_upper_inclusive!r})",
            )
        )

    for (lower_a, upper_a, upper_a_inclusive, id_a), (lower_b, _upper_b, _incl_b, id_b) in zip(
        bands, bands[1:]
    ):
        if upper_a > lower_b:
            diagnostics.append(
                Diagnostic(
                    Severity.FATAL,
                    "SIMILARITY_WARNING_BAND_OVERLAP",
                    path,
                    f"{path}: 구간 {id_a!r}(상한 {upper_a!r})과 {id_b!r}(하한 {lower_b!r})이 겹침",
                )
            )
        elif upper_a < lower_b:
            diagnostics.append(
                Diagnostic(
                    Severity.FATAL,
                    "SIMILARITY_WARNING_BAND_GAP",
                    path,
                    f"{path}: 구간 {id_a!r}(상한 {upper_a!r})과 {id_b!r}(하한 {lower_b!r}) 사이에 빈틈이 있음",
                )
            )
        elif upper_a_inclusive:
            # upper_a == lower_b이고 앞 구간이 그 값을 포함하면 두 구간 모두 그 값을 덮어 중복이다.
            diagnostics.append(
                Diagnostic(
                    Severity.FATAL,
                    "SIMILARITY_WARNING_BAND_OVERLAP",
                    path,
                    f"{path}: 구간 {id_a!r}이 경계값 {upper_a!r}을 포함해 {id_b!r}과 겹침",
                )
            )


# ---------------------------------------------------------------------------
# (c) source→anchor 범위·체크섬
# ---------------------------------------------------------------------------


def _check_source_anchors(
    source: SourceRecord, diagnostics: List[Diagnostic], excluded: _MutableExclusions
) -> None:
    body = source.body
    body_len = len(body)
    for anchor in source.anchors:
        path = f"dataset.sources[id={source.id!r}].anchors[id={anchor.id!r}]"
        start, end = anchor.start_offset, anchor.end_offset
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 0
            or end < start
            or end > body_len
        ):
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "SOURCE_ANCHOR_RANGE_OUT_OF_BOUNDS",
                    path,
                    f"{path}: anchor 범위가 본문 길이({body_len})를 벗어남 "
                    f"(start={start!r}, end={end!r})",
                )
            )
            excluded.source_ids.add(source.id)
            continue
        excerpt = body[start:end]
        expected_checksum = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        if anchor.excerpt_checksum != expected_checksum:
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "SOURCE_ANCHOR_CHECKSUM_MISMATCH",
                    path,
                    f"{path}: excerpt_checksum이 body[{start}:{end}]의 sha256 해시와 일치하지 않음",
                )
            )
            excluded.source_ids.add(source.id)


# ---------------------------------------------------------------------------
# (b) 참조 존재 + (f) canonical 값 일치: 판례
# ---------------------------------------------------------------------------


def _check_case(
    case: CaseRecord,
    *,
    source_ids_present: Set[SourceId],
    statute_version_ids_present: Set[StatuteVersionId],
    diagnostics: List[Diagnostic],
    excluded: _MutableExclusions,
) -> None:
    path = f"dataset.cases[id={case.id!r}]"
    isolate = False

    for source_id in case.source_ids:
        if source_id not in source_ids_present:
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "DANGLING_SOURCE_REFERENCE",
                    f"{path}.source_ids",
                    f"{path}.source_ids: 존재하지 않는 source_id={source_id!r}",
                )
            )
            isolate = True

    for index, applied in enumerate(case.applied_statutes):
        applied_path = f"{path}.applied_statutes[{index}]"
        if applied.source_id is not None and applied.source_id not in source_ids_present:
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "DANGLING_SOURCE_REFERENCE",
                    f"{applied_path}.source_id",
                    f"{applied_path}.source_id: 존재하지 않는 source_id={applied.source_id!r}",
                )
            )
            isolate = True
        if (
            applied.statute_version_id is not None
            and applied.statute_version_id not in statute_version_ids_present
        ):
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "DANGLING_STATUTE_VERSION_REFERENCE",
                    f"{applied_path}.statute_version_id",
                    f"{applied_path}.statute_version_id: 존재하지 않는 "
                    f"statute_version_id={applied.statute_version_id!r}",
                )
            )
            isolate = True

    if case.summaries.canonical_legality_status != case.legality_status:
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "SUMMARY_CANONICAL_LEGALITY_MISMATCH",
                f"{path}.summaries.canonical_legality_status",
                f"{path}.summaries.canonical_legality_status"
                f"({case.summaries.canonical_legality_status!r})가 legality_status"
                f"({case.legality_status!r})와 다름",
            )
        )
        isolate = True
    if case.summaries.canonical_instance_charge != case.instance_recognized_charge:
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "SUMMARY_CANONICAL_CHARGE_MISMATCH",
                f"{path}.summaries.canonical_instance_charge",
                f"{path}.summaries.canonical_instance_charge"
                f"({case.summaries.canonical_instance_charge!r})가 instance_recognized_charge"
                f"({case.instance_recognized_charge!r})와 다름",
            )
        )
        isolate = True
    if case.summaries.canonical_instance_outcome != case.instance_outcome:
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "SUMMARY_CANONICAL_OUTCOME_MISMATCH",
                f"{path}.summaries.canonical_instance_outcome",
                f"{path}.summaries.canonical_instance_outcome"
                f"({case.summaries.canonical_instance_outcome!r})가 instance_outcome"
                f"({case.instance_outcome!r})와 다름",
            )
        )
        isolate = True

    if isolate:
        excluded.case_ids.add(case.id)


# ---------------------------------------------------------------------------
# (h) 상대 시각 anchor 비순환
# ---------------------------------------------------------------------------


def _detect_relative_time_cycle(events: Sequence[RecognizedEvent]) -> Optional[Tuple[EventId, ...]]:
    """``events`` 안의 유효한 ``relative_time.anchor_event_id`` 참조 그래프에서 순환을
    찾으면 순환에 포함된 이벤트 ID 튜플을(발견 순서대로) 반환하고, 없으면 ``None``을
    반환한다.
    """

    by_id: Dict[EventId, RecognizedEvent] = {e.id: e for e in events}
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[EventId, int] = {event_id: WHITE for event_id in by_id}
    path: List[EventId] = []

    def dfs(event_id: EventId) -> Optional[Tuple[EventId, ...]]:
        color[event_id] = GRAY
        path.append(event_id)
        event = by_id[event_id]
        relative_time = event.relative_time
        if relative_time is not None and relative_time.anchor_event_id is not None:
            anchor_id = relative_time.anchor_event_id
            if anchor_id in by_id:
                anchor_color = color[anchor_id]
                if anchor_color == GRAY:
                    idx = path.index(anchor_id)
                    return tuple(path[idx:])
                if anchor_color == WHITE:
                    found = dfs(anchor_id)
                    if found is not None:
                        return found
        path.pop()
        color[event_id] = BLACK
        return None

    for event_id in by_id:
        if color[event_id] == WHITE:
            found = dfs(event_id)
            if found is not None:
                return found
    return None


# ---------------------------------------------------------------------------
# (b) 참조 존재 + (g) 현행법 우선순위 + (h) 비순환: 질의
# ---------------------------------------------------------------------------


def _check_query(
    query: QueryFixture,
    *,
    case_ids_present: Set[CaseId],
    statute_version_ids_present: Set[StatuteVersionId],
    source_ids_present: Set[SourceId],
    cases_by_id: Mapping[CaseId, CaseRecord],
    diagnostics: List[Diagnostic],
    excluded: _MutableExclusions,
) -> None:
    path = f"dataset.queries[id={query.id!r}]"
    isolate = False

    for case_id in query.match.case_ids:
        if case_id not in case_ids_present:
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "DANGLING_CASE_REFERENCE",
                    f"{path}.match.case_ids",
                    f"{path}.match.case_ids: 존재하지 않는 case_id={case_id!r}",
                )
            )
            isolate = True
    for version_id in query.match.statute_version_ids:
        if version_id not in statute_version_ids_present:
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "DANGLING_STATUTE_VERSION_REFERENCE",
                    f"{path}.match.statute_version_ids",
                    f"{path}.match.statute_version_ids: 존재하지 않는 "
                    f"statute_version_id={version_id!r}",
                )
            )
            isolate = True

    event_ids_seen: Set[EventId] = set()
    for index, event in enumerate(query.recognized_events):
        event_path = f"{path}.recognized_events[{index}][id={event.id!r}]"
        if event.id in event_ids_seen:
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "DUPLICATE_EVENT_ID",
                    event_path,
                    f"{event_path}: 하나의 질의 타임라인 내에서 EventId 중복: {event.id!r}",
                )
            )
            isolate = True
        event_ids_seen.add(event.id)

        for link_index, issue_link in enumerate(event.issue_links):
            for source_id in issue_link.source_ids:
                if source_id not in source_ids_present:
                    diagnostics.append(
                        Diagnostic(
                            Severity.WARNING,
                            "DANGLING_SOURCE_REFERENCE",
                            f"{event_path}.issue_links[{link_index}].source_ids",
                            f"{event_path}.issue_links[{link_index}].source_ids: 존재하지 않는 "
                            f"source_id={source_id!r}",
                        )
                    )
                    isolate = True

        relative_time = event.relative_time
        if (
            relative_time is not None
            and relative_time.anchor_event_id is not None
            and relative_time.anchor_event_id not in event_ids_seen
            and relative_time.anchor_event_id not in {e.id for e in query.recognized_events}
        ):
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "RELATIVE_TIME_ANCHOR_DANGLING",
                    f"{event_path}.relative_time.anchor_event_id",
                    f"{event_path}.relative_time.anchor_event_id: 존재하지 않는 "
                    f"anchor_event_id={relative_time.anchor_event_id!r}",
                )
            )
            isolate = True

    cycle = _detect_relative_time_cycle(query.recognized_events)
    if cycle is not None:
        cycle_str = " -> ".join(str(event_id) for event_id in cycle)
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "RELATIVE_TIME_ANCHOR_CYCLE",
                f"{path}.recognized_events",
                f"{path}.recognized_events: 상대 시각 anchor 순환 발견: {cycle_str}",
            )
        )
        isolate = True

    current_entries: List[Tuple[CaseId, int]] = []
    old_entries: List[Tuple[CaseId, int]] = []
    for case_id, preset in query.similarity_by_case.items():
        case = cases_by_id.get(case_id)
        if case is None:
            continue
        if case.expected_law_basis_status is LawBasisStatus.CURRENT_LAW_BASIS:
            current_entries.append((case_id, preset.search_priority))
        elif case.expected_law_basis_status is LawBasisStatus.OLD_LAW_BASIS:
            old_entries.append((case_id, preset.search_priority))
    for current_case_id, current_priority in current_entries:
        for old_case_id, old_priority in old_entries:
            if current_priority > old_priority:
                diagnostics.append(
                    Diagnostic(
                        Severity.WARNING,
                        "LAW_BASIS_PRIORITY_VIOLATION",
                        f"{path}.similarity_by_case",
                        f"{path}.similarity_by_case: 현행법_기준 판례 {current_case_id!r}"
                        f"(search_priority={current_priority!r})가 구법_기준 판례 "
                        f"{old_case_id!r}(search_priority={old_priority!r})보다 낮은 우선순위임",
                    )
                )
                isolate = True

    if isolate:
        excluded.query_ids.add(query.id)


# ---------------------------------------------------------------------------
# (b) 참조 존재: 응답 template · 선택 재검토 fixture · 음성 fixture
# ---------------------------------------------------------------------------


def _check_response_template(
    template: ResponseTemplate,
    *,
    source_ids_present: Set[SourceId],
    diagnostics: List[Diagnostic],
    excluded: _MutableExclusions,
) -> None:
    path = f"dataset.response_templates[id={template.id!r}]"
    isolate = False
    for block_index, block in enumerate(template.blocks):
        if not isinstance(block, LegalClaimBlock):
            continue
        block_path = f"{path}.blocks[{block_index}][claim_id={block.claim_id!r}]"
        for link_index, link in enumerate(block.citation_links):
            if link.source_id not in source_ids_present:
                diagnostics.append(
                    Diagnostic(
                        Severity.WARNING,
                        "DANGLING_SOURCE_REFERENCE",
                        f"{block_path}.citation_links[{link_index}].source_id",
                        f"{block_path}.citation_links[{link_index}].source_id: 존재하지 않는 "
                        f"source_id={link.source_id!r}",
                    )
                )
                isolate = True
    if isolate:
        excluded.response_template_ids.add(template.id)


def _check_selection_review_fixture(
    fixture: SelectionReviewFixture,
    *,
    source_ids_present: Set[SourceId],
    diagnostics: List[Diagnostic],
    excluded: _MutableExclusions,
) -> None:
    path = f"dataset.review_fixtures[response_template_id={fixture.response_template_id!r}]"
    isolate = False
    for claim in fixture.claims:
        claim_path = f"{path}.claims[id={claim.id!r}]"
        for link_index, link in enumerate(claim.evidence):
            if link.source_id not in source_ids_present:
                diagnostics.append(
                    Diagnostic(
                        Severity.WARNING,
                        "DANGLING_SOURCE_REFERENCE",
                        f"{claim_path}.evidence[{link_index}].source_id",
                        f"{claim_path}.evidence[{link_index}].source_id: 존재하지 않는 "
                        f"source_id={link.source_id!r}",
                    )
                )
                isolate = True
    if isolate:
        excluded.review_fixture_response_template_ids.add(fixture.response_template_id)


def _check_voice_fixture(
    voice: VoiceFixture,
    *,
    query_ids_present: Set[QueryId],
    diagnostics: List[Diagnostic],
    excluded: _MutableExclusions,
) -> None:
    if voice.query_id is not None and voice.query_id not in query_ids_present:
        path = f"dataset.voice_fixtures[id={voice.id!r}]"
        diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "DANGLING_QUERY_REFERENCE",
                f"{path}.query_id",
                f"{path}.query_id: 존재하지 않는 query_id={voice.query_id!r}",
            )
        )
        excluded.voice_fixture_ids.add(voice.id)


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def validate_domain_detailed(dataset: MockDataset) -> Tuple[Tuple[Diagnostic, ...], Exclusions]:
    """도메인·교차 참조 불변식을 검증하고 진단과 격리 대상 레코드 ID를 함께 반환한다.

    :func:`data.validated_dataset.validate_dataset`이 진단(치명 여부 판단용)과 격리 정보
    (레코드_격리 뷰 구성용)를 동시에 필요로 하므로, 두 결과를 같은 검사 로직에서 한 번에
    생성해 두 정보가 서로 어긋나지 않도록 한다.
    """

    diagnostics: List[Diagnostic] = []
    excluded = _MutableExclusions()

    _check_global_id_uniqueness(dataset, diagnostics)
    _check_display_policy_uniqueness(dataset, diagnostics)
    _check_similarity_warning_band_coverage(dataset, diagnostics)

    source_ids_present: Set[SourceId] = {s.id for s in dataset.sources}
    statute_version_ids_present: Set[StatuteVersionId] = {v.id for v in dataset.statute_versions}
    case_ids_present: Set[CaseId] = {c.id for c in dataset.cases}
    query_ids_present: Set[QueryId] = {q.id for q in dataset.queries}
    cases_by_id: Dict[CaseId, CaseRecord] = {c.id: c for c in dataset.cases}

    for source in dataset.sources:
        _check_source_anchors(source, diagnostics, excluded)

    for case in dataset.cases:
        _check_case(
            case,
            source_ids_present=source_ids_present,
            statute_version_ids_present=statute_version_ids_present,
            diagnostics=diagnostics,
            excluded=excluded,
        )

    for query in dataset.queries:
        _check_query(
            query,
            case_ids_present=case_ids_present,
            statute_version_ids_present=statute_version_ids_present,
            source_ids_present=source_ids_present,
            cases_by_id=cases_by_id,
            diagnostics=diagnostics,
            excluded=excluded,
        )

    for template in dataset.response_templates:
        _check_response_template(
            template, source_ids_present=source_ids_present, diagnostics=diagnostics, excluded=excluded
        )

    for fixture in dataset.review_fixtures:
        _check_selection_review_fixture(
            fixture, source_ids_present=source_ids_present, diagnostics=diagnostics, excluded=excluded
        )

    for voice in dataset.voice_fixtures:
        _check_voice_fixture(
            voice, query_ids_present=query_ids_present, diagnostics=diagnostics, excluded=excluded
        )

    return tuple(diagnostics), excluded.freeze()


def validate_domain(dataset: MockDataset) -> Tuple[Diagnostic, ...]:
    """도메인·교차 참조 불변식 검증 진단만 반환한다(``data.validator_structural.validate_structure``와
    동일한 형태의 진입점). 격리 대상 레코드 정보가 필요하면
    :func:`validate_domain_detailed`를 사용한다.
    """

    diagnostics, _exclusions = validate_domain_detailed(dataset)
    return diagnostics
