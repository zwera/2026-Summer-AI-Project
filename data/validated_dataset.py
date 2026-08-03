"""불투명 ``ValidatedDataset`` 타입과 그 유일한 생성 경로 ``validate_dataset`` (task 2.2).

``design.md``: "``ValidatedDataset``은 ``MockDataset``을 구조 검증하고 모든 교차 참조와
도메인 불변식을 확인한 뒤에만 생성할 수 있는 불투명 타입이다. UI는 원본 JSON에 접근하지
않는다."

이 모듈은 두 검증 단계를 순서대로 실행한다:

1. :func:`data.validator_structural.validate_structure` — 필수 필드·enum·ISO 날짜·tuple
   길이·유사도 범위(task 2.1).
2. :func:`data.validator_domain.validate_domain_detailed` — ID 유일성·참조 존재·
   source→anchor 체크섬·표시 정책 유일성·유사도 경고 구간 무결/비중첩·canonical 값 일치·
   현행법 우선순위·상대 시각 비순환(task 2.2).

두 단계에서 나온 진단을 합쳐 :data:`FATAL` 진단이 하나라도 있으면 ``ValidatedDataset``을
전혀 생성하지 않고 ``Err``로 안전 실패한다. ``FATAL``이 없으면(``WARNING``만 있거나 진단이
전혀 없으면) ``ValidatedDataset``을 생성하되, ``WARNING``이 가리키는 레코드는 아래
"레코드 격리 전략" 절의 규칙에 따라 노출되는 "clean" 컬렉션에서 제외한다.

## 레코드 격리 전략

용어집의 "레코드_격리": "유효하지 않은 목업_데이터_레코드 또는 참조만 결과에서 제외하고,
유효한 다른 레코드와 오류 발생 전 화면 상태를 유지"를 다음과 같이 구현한다.

- **격리 단위**: 판례(``CaseRecord``)·질의(``QueryFixture``)·출처(``SourceRecord``)·
  응답 template(``ResponseTemplate``)·선택 재검토 fixture(``SelectionReviewFixture``,
  ``response_template_id``로 식별)·음성 fixture(``VoiceFixture``) 각각 최상위 레코드
  하나 단위로 격리한다. 필드 하나만 지우는 부분 격리는 하지 않는다 — 목업 시연 규모에서
  근거_데이터 신뢰성을 유지하려면 레코드 전체를 감춰야 안전하기 때문이다.
- **격리 판단 근거**: (1) :mod:`data.validator_domain`이 검사 도중 직접 판정한
  :class:`~data.validator_domain.Exclusions`(ID 기반), (2)
  :mod:`data.validator_structural`가 낸 ``WARNING``의 ``path``에서 유도한 최상위 컬렉션
  인덱스(``dataset.<collection>[<index>]`` 접두사 매칭). 구조 검증기는 개별 필드 경로만
  보고하므로, 이 모듈이 인덱스를 실제 컬렉션에 대조해 어떤 레코드가 영향을 받는지
  확인한다.
- **전이적(cascading) 격리는 하지 않는다**: 판례 A가 격리된 출처 B를 참조해도 A 자체가
  다른 이유로 격리 대상이 아니면 A는 그대로 노출된다. 참조 유효성의 최종 확인은 이 값을
  소비하는 이후 태스크(예: 검색·인용 조립)가 ``ValidatedDataset``의 clean 컬렉션을 기준으로
  다시 수행해야 한다. 이는 목업 시연 규모에서 다단계 전이적 격리 그래프를 만들지 않기 위한
  의도적 단순화다.
- 법조문(``StatuteRecord``)과 법조문 버전(``StatuteVersion``)은 이 태스크의 도메인 불변식
  목록(a~h)에 별도 레코드 단위 격리 대상으로 명시되지 않았으므로 격리하지 않는다. 이들을
  잘못 참조하는 판례/질의는 이미 ``DANGLING_STATUTE_VERSION_REFERENCE`` 위반으로 그 판례/
  질의가 격리된다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping, Pattern, Set, Tuple

from domain.ids import CaseId, QueryId, SourceId
from domain.result import Err, Ok, Result

from data.models_case import CaseRecord
from data.models_common import LegalTermMapping, MockDisplayPolicies, ScenarioDefinition, VoiceFixtureId
from data.models_dataset import MockDataset
from data.models_query import QueryFixture
from data.models_selection import SelectionReviewFixture
from data.models_source import ResponseTemplate, SourceRecord
from data.models_statute import StatuteRecord, StatuteVersion
from data.models_timeline import VoiceFixture
from data.validator_domain import Diagnostic, has_fatal, validate_domain_detailed
from data.validator_structural import validate_structure

__all__ = ["ValidatedDataset", "validate_dataset"]


_CONSTRUCTION_TOKEN = object()
"""``ValidatedDataset``이 :func:`validate_dataset` 밖에서 직접 생성되지 않도록 막는
모듈 전용 sentinel. 이 모듈 밖에서는 접근·재현할 수 없으므로 다른 코드가 같은 값을 만들어
검증을 우회할 수 없다."""


def _index_prefixed_pattern(collection: str) -> Pattern[str]:
    return re.compile(rf"^dataset\.{re.escape(collection)}\[(\d+)\]")


_CASE_PATH_PATTERN = _index_prefixed_pattern("cases")
_QUERY_PATH_PATTERN = _index_prefixed_pattern("queries")
_SOURCE_PATH_PATTERN = _index_prefixed_pattern("sources")
_RESPONSE_TEMPLATE_PATH_PATTERN = _index_prefixed_pattern("response_templates")
_REVIEW_FIXTURE_PATH_PATTERN = _index_prefixed_pattern("review_fixtures")
_VOICE_FIXTURE_PATH_PATTERN = _index_prefixed_pattern("voice_fixtures")


def _structural_warning_indices(diagnostics: Tuple[Diagnostic, ...], pattern: Pattern[str]) -> Set[int]:
    indices: Set[int] = set()
    for diagnostic in diagnostics:
        match = pattern.match(diagnostic.path)
        if match is not None:
            indices.add(int(match.group(1)))
    return indices


@dataclass(frozen=True)
class ValidatedDataset:
    """구조·교차 참조·도메인 불변식 검증을 통과한 불투명 데이터셋.

    :func:`validate_dataset`를 통해서만 생성할 수 있다. 모든 컬렉션은 격리된(유효하지
    않다고 판정된 레코드를 제외한) 뷰다. ``diagnostics``에는 격리를 유발한 ``WARNING``
    진단이 그대로 보존되어, 소비하는 코드가 어떤 레코드가 왜 빠졌는지 추적할 수 있다.
    """

    _construction_token: object = field(repr=False, compare=False)

    schema_version: str
    dataset_id: str
    dataset_version: str
    normalization_version: str
    as_of_date: str
    target_coverage_label: str
    implemented_coverage_label: str
    legal_safety_notice: str
    instance_caution_notice: str
    no_realtime_sync_label: str
    scenarios: Tuple[ScenarioDefinition, ...]
    term_mappings: Tuple[LegalTermMapping, ...]
    statutes: Tuple[StatuteRecord, ...]
    statute_versions: Tuple[StatuteVersion, ...]
    display_policies: MockDisplayPolicies

    cases: Tuple[CaseRecord, ...]
    queries: Tuple[QueryFixture, ...]
    sources: Tuple[SourceRecord, ...]
    response_templates: Tuple[ResponseTemplate, ...]
    review_fixtures: Tuple[SelectionReviewFixture, ...]
    voice_fixtures: Tuple[VoiceFixture, ...]

    diagnostics: Tuple[Diagnostic, ...]
    """생성 당시 존재했던 ``WARNING`` 진단 전체(격리 원인 포함). ``FATAL``은 결코 여기
    담기지 않는다 — ``FATAL``이 있으면 :func:`validate_dataset`가 ``Err``를 반환하고
    ``ValidatedDataset``을 만들지 않는다."""

    def __post_init__(self) -> None:
        if self._construction_token is not _CONSTRUCTION_TOKEN:
            raise RuntimeError(
                "ValidatedDataset은 data.validated_dataset.validate_dataset()을 통해서만 "
                "생성할 수 있다."
            )

    @property
    def cases_by_id(self) -> Mapping[CaseId, CaseRecord]:
        """clean 판례 컬렉션의 ID 조회 인덱스(캐시 없이 매번 재계산)."""

        return {case.id: case for case in self.cases}

    @property
    def sources_by_id(self) -> Mapping[SourceId, SourceRecord]:
        """clean 출처 컬렉션의 ID 조회 인덱스(캐시 없이 매번 재계산)."""

        return {source.id: source for source in self.sources}

    @property
    def queries_by_id(self) -> Mapping[QueryId, QueryFixture]:
        """clean 질의 컬렉션의 ID 조회 인덱스(캐시 없이 매번 재계산)."""

        return {query.id: query for query in self.queries}


def validate_dataset(raw: MockDataset) -> "Result[ValidatedDataset, Tuple[Diagnostic, ...]]":
    """``raw``를 구조·도메인 검증한 뒤 통과하면 ``Ok(ValidatedDataset)``, 치명 오류가 있으면
    ``Err(diagnostics)``를 반환한다.

    치명(``FATAL``) 진단이 하나라도 있으면 ``ValidatedDataset`` 인스턴스를 전혀 생성하지
    않고 안전 실패한다(모듈 docstring "레코드 격리 전략" 참조). ``WARNING``만 있으면 해당
    레코드를 격리한 clean 뷰로 ``ValidatedDataset``을 생성한다.
    """

    structural_diagnostics = validate_structure(raw)
    domain_diagnostics, domain_exclusions = validate_domain_detailed(raw)
    all_diagnostics = structural_diagnostics + domain_diagnostics

    if has_fatal(all_diagnostics):
        return Err(all_diagnostics)

    excluded_case_ids: Set[CaseId] = set(domain_exclusions.case_ids) | {
        raw.cases[i].id for i in _structural_warning_indices(structural_diagnostics, _CASE_PATH_PATTERN)
    }
    excluded_query_ids: Set[QueryId] = set(domain_exclusions.query_ids) | {
        raw.queries[i].id
        for i in _structural_warning_indices(structural_diagnostics, _QUERY_PATH_PATTERN)
    }
    excluded_source_ids: Set[SourceId] = set(domain_exclusions.source_ids) | {
        raw.sources[i].id
        for i in _structural_warning_indices(structural_diagnostics, _SOURCE_PATH_PATTERN)
    }
    excluded_response_template_ids: Set[str] = set(domain_exclusions.response_template_ids) | {
        raw.response_templates[i].id
        for i in _structural_warning_indices(structural_diagnostics, _RESPONSE_TEMPLATE_PATH_PATTERN)
    }
    excluded_review_fixture_ids: Set[str] = set(
        domain_exclusions.review_fixture_response_template_ids
    ) | {
        raw.review_fixtures[i].response_template_id
        for i in _structural_warning_indices(structural_diagnostics, _REVIEW_FIXTURE_PATH_PATTERN)
    }
    excluded_voice_fixture_ids: Set[VoiceFixtureId] = set(domain_exclusions.voice_fixture_ids) | {
        raw.voice_fixtures[i].id
        for i in _structural_warning_indices(structural_diagnostics, _VOICE_FIXTURE_PATH_PATTERN)
    }

    clean_cases = tuple(c for c in raw.cases if c.id not in excluded_case_ids)
    clean_queries = tuple(q for q in raw.queries if q.id not in excluded_query_ids)
    clean_sources = tuple(s for s in raw.sources if s.id not in excluded_source_ids)
    clean_response_templates = tuple(
        t for t in raw.response_templates if t.id not in excluded_response_template_ids
    )
    clean_review_fixtures = tuple(
        f for f in raw.review_fixtures if f.response_template_id not in excluded_review_fixture_ids
    )
    clean_voice_fixtures = tuple(v for v in raw.voice_fixtures if v.id not in excluded_voice_fixture_ids)

    warning_diagnostics = tuple(all_diagnostics)  # has_fatal이 False이므로 전부 WARNING이다.

    validated = ValidatedDataset(
        _construction_token=_CONSTRUCTION_TOKEN,
        schema_version=raw.schema_version,
        dataset_id=raw.dataset_id,
        dataset_version=raw.dataset_version,
        normalization_version=raw.normalization_version,
        as_of_date=raw.as_of_date,
        target_coverage_label=raw.target_coverage_label,
        implemented_coverage_label=raw.implemented_coverage_label,
        legal_safety_notice=raw.legal_safety_notice,
        instance_caution_notice=raw.instance_caution_notice,
        no_realtime_sync_label=raw.no_realtime_sync_label,
        scenarios=raw.scenarios,
        term_mappings=raw.term_mappings,
        statutes=raw.statutes,
        statute_versions=raw.statute_versions,
        display_policies=raw.display_policies,
        cases=clean_cases,
        queries=clean_queries,
        sources=clean_sources,
        response_templates=clean_response_templates,
        review_fixtures=clean_review_fixtures,
        voice_fixtures=clean_voice_fixtures,
        diagnostics=warning_diagnostics,
    )
    return Ok(validated)
