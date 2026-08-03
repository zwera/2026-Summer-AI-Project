"""자연어 상황_질의 해석과 법률_검색어 대응. (task 3.1)

``design.md`` "Components and Interfaces > 핵심 포트와 함수 시그니처"의 다음 계약
의사코드를 Python으로 구현한다::

    function normalizeForFixtureMatch(raw: string, rules: NormalizationRules): NormalizedQuery;
    function interpretQuery(raw: string, dataset: ValidatedDataset): QueryInterpretation;
    function relationsPreserved(before: RelationGraph, after: RelationGraph): boolean;

이 모듈의 모든 함수는 순수 함수다 — 네트워크 I/O, 현재 시각, 난수, 로케일 의존 정렬을
쓰지 않는다(요구사항 15.3). 동일한 ``raw``와 동일한 ``ValidatedDataset``은 항상 동일한
:class:`QueryInterpretation`을 반환한다.

## 지원 질의 판정 (design.md "4. 명시적 가정과 모호성 해소" 2번)

의미 추론이나 퍼지 검색을 하지 않는다. ``QueryFixture.variants``에 등록된 문장의
결정적 정규화 결과(``QueryVariant.normalized_key``)와 정확히 일치하는 입력만 지원
질의다. 정규화는 유니코드 정규화·연속 공백 축약·허용 문장부호 처리만 수행하며, 새로운
검색어나 관계를 추론하지 않는다.

## 분기 개요 (요구사항 2.1~2.11)

1. **BLANK**: 원문이 비어 있거나 공백 문자로만 구성됨 (2.6, 2.7, 2.8) → INPUT 유지, 빈
   매칭_결과_집합.
2. **UNSUPPORTED**: 정규화 키가 어떤 ``QueryVariant.normalized_key``와도 일치하지 않음
   (2.1, 2.14, 2.15, 2.16) → INPUT 유지, 지원 경찰_직무_시나리오 목록 반환.
3. **INTERPRETATION_CHECK_NEEDED**: 일치하는 변형은 찾았지만
   (a) 연결된 ``LegalTermMapping.unsupported_fragments``에 표현이 남아 있거나(2.9),
   (b) ``relation_graph_before``/``relation_graph_after``의 edge 집합이 하나로
   일치하지 않거나 복수 해석만 있음(2.5, 2.10) → INPUT 유지, 빈 매칭_결과_집합, 원문 보존.
4. **SUPPORTED**: 위 검사를 모두 통과 → 법률_검색어 대응, 관계 그래프, 매칭_결과_집합을
   포함해 반환한다. 이 결과 자체는 ``RagStage.INPUT``에 머무른다 — ``MOCK_SEARCH``로의
   전이는 목업 RAG 오케스트레이터(task 15.1)의 책임이며 이 함수는 판정만 한다.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, FrozenSet, Literal, Mapping, Tuple, Union

from domain.enums import PoliceScenario, RagStage
from domain.ids import QueryId

from data.models_common import LegalTermMapping, RelationGraph
from data.models_query import QueryFixture, QueryMatch, QueryVariant
from data.validated_dataset import ValidatedDataset

__all__ = [
    "NormalizationRules",
    "NormalizedQuery",
    "normalize_for_fixture_match",
    "relations_preserved",
    "TermCorrespondence",
    "InterpretationCheckReason",
    "BlankQueryInterpretation",
    "UnsupportedQueryInterpretation",
    "InterpretationCheckNeededQueryInterpretation",
    "SupportedQueryInterpretation",
    "QueryInterpretation",
    "interpret_query",
]


# --------------------------------------------------------------------------
# 정규화 (design.md 4.1절 1~2번)
# --------------------------------------------------------------------------

_DEFAULT_ALLOWED_PUNCTUATION: FrozenSet[str] = frozenset(".,!?·'\"()-~:;")
"""필터링이 활성화된 정규화 규칙에서 그대로 남기는 문장부호. 유효한 데이터셋 버전이
문장부호 필터링을 요구할 때만 사용되며, 현재 fixture 버전(``v1``)에는 적용하지 않는다."""

_WHITESPACE_RUN_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class NormalizationRules:
    """``dataset.normalizationVersion``이 선언하는 비교용 정규화 규칙.

    화면에는 항상 원문(``raw``)을 그대로 표시하고, 이 규칙은 오직 fixture 대조를 위한
    비교 키 계산에만 적용한다(design.md 4.1절 2번, 요구사항 2.4).
    """

    unicode_form: Literal["NFC", "NFKC", "NFD", "NFKD"] = "NFC"
    collapse_whitespace: bool = True
    filter_disallowed_punctuation: bool = False
    """``True``이면 영숫자·공백·``allowed_punctuation``에 속하지 않는 문자를 비교 키에서
    제거한다. 현재 유일한 데이터셋 버전(``v1``)의 fixture는 이미 원문 그대로가
    ``normalized_key``이므로 기본값은 ``False``다(하위 호환성 유지)."""
    allowed_punctuation: FrozenSet[str] = _DEFAULT_ALLOWED_PUNCTUATION

    @staticmethod
    def for_dataset_version(normalization_version: str) -> "NormalizationRules":
        """``dataset.normalizationVersion`` 문자열에 대응하는 규칙을 반환한다.

        선언되지 않은 버전은 기본 규칙(NFC·공백 축약·문장부호 필터링 없음)으로 안전하게
        대체한다 — 알 수 없는 버전이라고 정규화를 건너뛰거나 예외를 던지지 않는다.
        """

        return _NORMALIZATION_RULES_BY_VERSION.get(normalization_version, NormalizationRules())


_NORMALIZATION_RULES_BY_VERSION: Mapping[str, NormalizationRules] = {
    "v1": NormalizationRules(),
}


@dataclass(frozen=True)
class NormalizedQuery:
    """:func:`normalize_for_fixture_match`의 결과. ``raw``는 변경 없이 보존된 원문이다."""

    raw: str
    normalized_key: str


def normalize_for_fixture_match(raw: str, rules: NormalizationRules) -> NormalizedQuery:
    """``raw``를 ``rules``에 따라 정규화해 fixture 대조용 키를 계산한다.

    유니코드 정규화(``rules.unicode_form``), 앞뒤 공백 제거, 연속 공백을 단일 공백으로
    축약(``rules.collapse_whitespace``)하고, 활성화된 경우에만 허용되지 않는 문장부호를
    제거한다. ``raw`` 자체는 수정하지 않고 결과에 그대로 담아 반환한다(화면에는 원문을
    표시해야 하므로).
    """

    text = unicodedata.normalize(rules.unicode_form, raw)
    text = text.strip()
    if rules.collapse_whitespace:
        text = _WHITESPACE_RUN_PATTERN.sub(" ", text)
    if rules.filter_disallowed_punctuation:
        text = "".join(
            ch
            for ch in text
            if ch.isalnum() or ch.isspace() or ch in rules.allowed_punctuation
        )
    return NormalizedQuery(raw=raw, normalized_key=text)


def _is_blank(raw: str) -> bool:
    """요구사항 2.6/2.7: 공백 문자로만 구성되거나 빈 문자열이면 참이다."""

    return len(raw.strip()) == 0


# --------------------------------------------------------------------------
# 관계 보존 (design.md 4.1절 5번, Correctness Property 5)
# --------------------------------------------------------------------------


def relations_preserved(before: RelationGraph, after: RelationGraph) -> bool:
    """``before``와 ``after``의 actor-action·action-time·negation-target edge 집합이
    (순서와 무관하게) 정확히 동일하면 ``True``를 반환한다.

    ``RelationEdge`` 세 변형(``ActorActionEdge``/``ActionTimeEdge``/``NegationTargetEdge``)은
    frozen dataclass라 판별 필드를 포함한 필드 값으로 동등성·해시가 결정되므로, 서로 다른
    edge 타입은 절대 같은 것으로 취급되지 않는다.
    """

    return frozenset(before.edges) == frozenset(after.edges)


def _relation_after_candidates(
    after: Union[RelationGraph, Tuple[RelationGraph, ...]]
) -> Tuple[RelationGraph, ...]:
    if isinstance(after, tuple):
        return after
    return (after,)


def _relation_conversion_accepted(
    before: RelationGraph, after: Union[RelationGraph, Tuple[RelationGraph, ...]]
) -> bool:
    """``after``가 단일 그래프면 :func:`relations_preserved`와 동일하게 판정한다.

    ``after``가 복수 해석(튜플)이면, ``before``와 edge 집합이 일치하는 후보가 정확히
    하나일 때만 관계가 보존된 것으로 본다. 일치 후보가 0개(보존 실패)이거나 2개 이상
    (모호함)이면 하나의 결정적 그래프로 확정할 수 없으므로 보존되지 않은 것으로 판정한다
    (design.md 4.1절 5번: "복수 해석만 있으면 입력 단계에서 중단한다").
    """

    candidates = _relation_after_candidates(after)
    matching = [c for c in candidates if relations_preserved(before, c)]
    return len(matching) == 1


# --------------------------------------------------------------------------
# 질의 해석 결과 (판별 유니온)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BlankQueryInterpretation:
    """요구사항 2.6/2.7/2.8: 공백 전용 입력. 목업_RAG_단계는 입력 상태로 유지되고
    매칭_결과_집합은 빈 집합이며, 클라이언트는 `상황 입력 요청`을 표시해야 한다."""

    raw: str
    kind: Literal["BLANK"] = "BLANK"
    stage: RagStage = RagStage.INPUT


@dataclass(frozen=True)
class UnsupportedQueryInterpretation:
    """요구사항 2.1/2.14/2.15/2.16: 지원_목업_질의 범위 밖. 매칭_결과_집합은 빈 집합이며
    ``supported_scenarios``는 클라이언트가 표시할 지원 경찰_직무_시나리오 목록이다."""

    raw: str
    supported_scenarios: Tuple[PoliceScenario, ...]
    kind: Literal["UNSUPPORTED"] = "UNSUPPORTED"
    stage: RagStage = RagStage.INPUT


InterpretationCheckReason = Literal[
    "UNMAPPED_EXPRESSION", "RELATION_NOT_PRESERVED", "AMBIGUOUS_RELATION"
]
"""`해석 확인 필요`로 분류된 원인.

- ``UNMAPPED_EXPRESSION``: 요구사항 2.9. 핵심 사실은 대응하지만 하나 이상의 표현이
  ``LegalTermMapping.unsupported_fragments``에 남아 있다.
- ``RELATION_NOT_PRESERVED``: 요구사항 2.10. 변환 전후 관계 그래프의 edge 집합이 하나로
  일치하지 않는다.
- ``AMBIGUOUS_RELATION``: 요구사항 2.10. ``relation_graph_after``가 복수 해석이며 그중
  ``relation_graph_before``와 일치하는 후보가 정확히 하나로 결정되지 않는다.
"""


@dataclass(frozen=True)
class InterpretationCheckNeededQueryInterpretation:
    """요구사항 2.9/2.10/2.11/2.12/2.13: `해석 확인 필요`. 목업_RAG_단계는 입력 상태로
    유지되고 매칭_결과_집합은 빈 집합이며, 원문과 원인을 함께 보존해 클라이언트가 원문
    표현과 해석 확인 요청을 표시할 수 있게 한다."""

    raw: str
    reason: InterpretationCheckReason
    unmapped_fragments: Tuple[str, ...] = ()
    kind: Literal["INTERPRETATION_CHECK_NEEDED"] = "INTERPRETATION_CHECK_NEEDED"
    stage: RagStage = RagStage.INPUT


@dataclass(frozen=True)
class TermCorrespondence:
    """요구사항 2.3/2.4: 경찰_현장_표현 ↔ 법률_검색어 대응 쌍 하나. 클라이언트는 이
    대응을 재해석 없이 그대로 표시해야 한다(요구사항 2.18)."""

    term_mapping_id: str
    field_expression: str
    legal_search_terms: Tuple[str, ...]


@dataclass(frozen=True)
class SupportedQueryInterpretation:
    """요구사항 2.1/2.2/2.3/2.5: 지원_목업_질의로 수락된 해석 결과.

    ``match``는 ``QueryFixture.match``를 그대로 담은 매칭_결과_집합이며,
    ``relation_graph``는 이 질의의 canonical 관계 그래프다. 이 결과 자체는 여전히
    ``RagStage.INPUT``이다 — ``MOCK_SEARCH``로 실제로 전이하는 것은 목업 RAG
    오케스트레이터(task 15.1)의 책임이다.
    """

    raw: str
    query_id: QueryId
    variant_id: str
    term_correspondences: Tuple[TermCorrespondence, ...]
    relation_graph: RelationGraph
    match: QueryMatch
    kind: Literal["SUPPORTED"] = "SUPPORTED"
    stage: RagStage = RagStage.INPUT


QueryInterpretation = Union[
    BlankQueryInterpretation,
    UnsupportedQueryInterpretation,
    InterpretationCheckNeededQueryInterpretation,
    SupportedQueryInterpretation,
]
"""``interpret_query``의 판별 유니온 반환 타입. ``kind`` 필드로 네 변형을 구분한다."""


# --------------------------------------------------------------------------
# 인덱스 구성 (순수 조회, 부트 시 캐시하지 않고 매번 결정적으로 재계산)
# --------------------------------------------------------------------------


def _build_variant_index(
    dataset: ValidatedDataset,
) -> Mapping[str, Tuple[QueryFixture, QueryVariant]]:
    """``normalized_key`` → ``(QueryFixture, QueryVariant)`` 조회 인덱스.

    ``dataset.queries``와 각 ``query.variants``는 고정된 순서의 tuple이므로, 동일
    ``normalized_key``가 중복 등록된 경우에도(데이터셋 검증기가 걸러내야 할 상황이지만)
    이 인덱스 구성은 항상 동일한 순서로 순회해 결정적으로 동일한 결과를 만든다.
    """

    index: Dict[str, Tuple[QueryFixture, QueryVariant]] = {}
    for query in dataset.queries:
        for variant in query.variants:
            index[variant.normalized_key] = (query, variant)
    return index


def _build_term_mapping_index(dataset: ValidatedDataset) -> Mapping[str, LegalTermMapping]:
    """``LegalTermMapping.id`` → ``LegalTermMapping`` 조회 인덱스."""

    return {mapping.id: mapping for mapping in dataset.term_mappings}


# --------------------------------------------------------------------------
# 최상위 해석 함수
# --------------------------------------------------------------------------


def interpret_query(raw: str, dataset: ValidatedDataset) -> QueryInterpretation:
    """``raw`` 상황_질의를 ``dataset``에 대해 해석한다.

    순수 함수다: 동일한 ``raw``와 동일한 ``dataset``에 대해 항상 동일한
    :class:`QueryInterpretation`을 반환한다(요구사항 2.17, 15.3). 반환값은 항상
    ``RagStage.INPUT``에 머무른다 — 실제 단계 전이는 이 함수의 책임이 아니다.
    """

    if _is_blank(raw):
        return BlankQueryInterpretation(raw=raw)

    rules = NormalizationRules.for_dataset_version(dataset.normalization_version)
    normalized = normalize_for_fixture_match(raw, rules)

    variant_index = _build_variant_index(dataset)
    matched = variant_index.get(normalized.normalized_key)
    if matched is None:
        supported_scenarios = tuple(scenario.id for scenario in dataset.scenarios)
        return UnsupportedQueryInterpretation(raw=raw, supported_scenarios=supported_scenarios)

    query, variant = matched
    term_mapping_index = _build_term_mapping_index(dataset)
    resolved_mappings = tuple(
        term_mapping_index[mapping_id]
        for mapping_id in query.term_mapping_ids
        if mapping_id in term_mapping_index
    )

    unmapped_fragments = tuple(
        fragment
        for mapping in resolved_mappings
        for fragment in mapping.unsupported_fragments
    )
    if unmapped_fragments:
        return InterpretationCheckNeededQueryInterpretation(
            raw=raw,
            reason="UNMAPPED_EXPRESSION",
            unmapped_fragments=unmapped_fragments,
        )

    for mapping in resolved_mappings:
        if not _relation_conversion_accepted(mapping.relation_graph_before, mapping.relation_graph_after):
            candidates = _relation_after_candidates(mapping.relation_graph_after)
            reason: InterpretationCheckReason = (
                "AMBIGUOUS_RELATION" if len(candidates) > 1 else "RELATION_NOT_PRESERVED"
            )
            return InterpretationCheckNeededQueryInterpretation(raw=raw, reason=reason)

    term_correspondences = tuple(
        TermCorrespondence(
            term_mapping_id=mapping.id,
            field_expression=mapping.field_expression,
            legal_search_terms=mapping.legal_search_terms,
        )
        for mapping in resolved_mappings
    )

    return SupportedQueryInterpretation(
        raw=raw,
        query_id=query.id,
        variant_id=variant.id,
        term_correspondences=term_correspondences,
        relation_graph=query.canonical_relations,
        match=query.match,
    )
