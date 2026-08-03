"""Property 5: 관계 보존 또는 모호성 차단 (task 3.3).

생성한 관계 그래프를 용어 변환 fixture에 주입해 다음 계약을 검증한다.

- actor-action, action-time, negation-target edge 집합이 순서만 달리 동일하면
  변환은 수락된다.
- edge 집합이 달라지면 ``해석 확인 필요``로 차단된다.
- 동일한 관계를 보존하는 후보가 둘 이상이면 단일 해석으로 확정할 수 없으므로
  ``해석 확인 필요``로 차단된다.

``derandomize=True``와 Hypothesis의 기본 최소 반례 축소를 함께 사용하여 실패 사례를
결정적으로 재생성하고 축소한다.
"""

from __future__ import annotations

import dataclasses
from typing import Literal, Sequence, Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_common import (
    ActionTimeEdge,
    ActorActionEdge,
    NegationTargetEdge,
    RelationEdge,
    RelationGraph,
)
from data.validated_dataset import ValidatedDataset
from domain.enums import RagStage
from domain.ids import QueryId
from domain.query_interpretation import (
    InterpretationCheckNeededQueryInterpretation,
    SupportedQueryInterpretation,
    interpret_query,
    relations_preserved,
)


@st.composite
def _relation_edges(draw: st.DrawFn) -> Tuple[RelationEdge, ...]:
    """관계 종류별 edge를 고유하게 생성한다.

    센티널 edge와의 충돌을 피하는 작은 식별자 공간을 사용해, 훼손 분기에서 edge 하나를
    추가했을 때 반드시 edge 집합이 달라지게 한다.
    """

    labels = st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",), blacklist_characters=("|",)
        ),
        min_size=1,
        max_size=4,
    ).filter(lambda value: value != "__changed__")
    edge_strategy = st.one_of(
        st.builds(
            ActorActionEdge, st.just("ACTOR_ACTION"), labels, labels
        ),
        st.builds(ActionTimeEdge, st.just("ACTION_TIME"), labels, labels),
        st.builds(
            NegationTargetEdge, st.just("NEGATION_TARGET"), labels, labels
        ),
    )
    return tuple(draw(st.lists(edge_strategy, unique=True, max_size=8)))


def _graph(edges: Sequence[RelationEdge]) -> RelationGraph:
    """edge 집합에서 관계 그래프를 만든다; 판정 대상은 edge 집합뿐이다."""

    return RelationGraph(
        actors=(), actions=(), times=(), negations=(), edges=tuple(edges)
    )


def _dataset_with_mapping(
    dataset: ValidatedDataset,
    before: RelationGraph,
    after: RelationGraph | Tuple[RelationGraph, ...],
) -> ValidatedDataset:
    """등록된 현행범체포 질의의 유일한 용어 대응만 불변 방식으로 교체한다."""

    mapping = dataset.term_mappings[0]
    replacement = dataclasses.replace(
        mapping,
        relation_graph_before=before,
        relation_graph_after=after,
    )
    return dataclasses.replace(
        dataset,
        term_mappings=(replacement,) + dataset.term_mappings[1:],
    )


# Feature: police-case-law-ai-bot, Property 5: 관계 보존 또는 모호성 차단
@settings(max_examples=100, derandomize=True, print_blob=True, deadline=None)
@given(
    edges=_relation_edges(),
    conversion=st.sampled_from(("preserved", "changed", "ambiguous")),
)
def test_relation_preservation_accepts_only_a_single_matching_graph(
    validated_mock_dataset: ValidatedDataset,
    edges: Tuple[RelationEdge, ...],
    conversion: Literal["preserved", "changed", "ambiguous"],
) -> None:
    """**Validates: Requirements 2.4, 2.8, 2.9**."""

    before = _graph(edges)
    if conversion == "preserved":
        after: RelationGraph | Tuple[RelationGraph, ...] = _graph(
            reversed(edges)
        )
    elif conversion == "changed":
        changed_edge = ActorActionEdge(
            "ACTOR_ACTION", "__changed__", "__changed__"
        )
        after = _graph((*edges, changed_edge))
    else:
        matching_candidate = _graph(reversed(edges))
        after = (matching_candidate, matching_candidate)

    dataset = _dataset_with_mapping(validated_mock_dataset, before, after)
    query = dataset.queries_by_id[QueryId("query-arrest")]
    raw = query.variants[0].raw_example
    interpretation = interpret_query(raw, dataset)

    assert interpretation.stage is RagStage.INPUT

    if conversion == "preserved":
        assert isinstance(after, RelationGraph)
        assert relations_preserved(before, after) is True
        assert isinstance(interpretation, SupportedQueryInterpretation)
        correspondence = interpretation.term_correspondences[0]
        assert correspondence.field_expression == "범행 직후 바로 잡기"
    else:
        assert isinstance(
            interpretation, InterpretationCheckNeededQueryInterpretation
        )
        expected_reason = (
            "RELATION_NOT_PRESERVED"
            if conversion == "changed"
            else "AMBIGUOUS_RELATION"
        )
        assert interpretation.reason == expected_reason
