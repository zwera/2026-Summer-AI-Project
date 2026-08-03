"""Property 38: 출처 왕복의 사용자 상태 보존 (task 15.5).

검증된 목업 fixture에서 지원 질의, 그 질의 결과의 판례 및 해당 판례 출처를
생성한다. 출처를 열었다가 복귀해도 상황 질의, 선택 판례, 요약 단계, 보조
필터라는 사용자 상태가 왕복 전과 깊은 동등성을 유지하는지 검증한다.
"""

from __future__ import annotations

from typing import Optional, Tuple

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.app_reducer import (
    ReturnFromSource,
    SelectCase,
    SetAuxiliaryFilter,
    SetSummaryLevel,
    SourceNavigationRequest,
    SubmitQuery,
    ToggleSource,
    app_reducer,
    initial_app_state,
)
from data.models_query import QueryFixture
from data.validated_dataset import ValidatedDataset
from domain.enums import SummaryLevel, TraditionalCaseArea
from domain.ids import CaseId


def _query_case_source_choices(
    dataset: ValidatedDataset,
) -> Tuple[Tuple[QueryFixture, CaseId, str, str], ...]:
    """지원 질의에서 도달 가능한 판례와 유효 출처 앵커 조합만 만든다."""

    choices = []
    for query in dataset.queries:
        for case_id in query.match.case_ids:
            case = dataset.cases_by_id[case_id]
            for source_id in case.source_ids:
                source = dataset.sources_by_id[source_id]
                for anchor in source.anchors:
                    choices.append((query, case_id, source.id, anchor.id))
    return tuple(choices)


# Feature: police-case-law-ai-bot, Property 38: 출처 왕복의 사용자 상태 보존
@settings(
    max_examples=100,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.data())
def test_source_round_trip_preserves_state(
    validated_mock_dataset: ValidatedDataset,
    data: st.DataObject,
) -> None:
    """**Validates: Requirements 13.3**

    Opening a valid source and returning from it clears only the transient source
    navigation state; the specified query, selected case, summary level, and
    optional auxiliary filter stay unchanged.
    """

    query, case_id, source_id, anchor_id = data.draw(
        st.sampled_from(
            _query_case_source_choices(validated_mock_dataset)
        ),
        label="query_case_source",
    )
    summary_level = data.draw(
        st.sampled_from(tuple(SummaryLevel)),
        label="summary_level",
    )
    auxiliary_filter: Optional[TraditionalCaseArea] = data.draw(
        st.one_of(
            st.none(),
            st.sampled_from(tuple(TraditionalCaseArea)),
        ),
        label="auxiliary_filter",
    )

    state = initial_app_state()
    for command in (
        SubmitQuery(query.variants[0].raw_example),
        SelectCase(case_id),
        SetSummaryLevel(summary_level),
        SetAuxiliaryFilter(auxiliary_filter),
    ):
        state, effects = app_reducer(state, command)
        assert effects == ()

    before_round_trip = (
        state.raw_query,
        state.selected_case_id,
        state.summary_level,
        state.auxiliary_filter,
    )
    opened, effects = app_reducer(
        state,
        ToggleSource(SourceNavigationRequest(source_id, anchor_id)),
    )
    returned, effects_after_return = app_reducer(opened, ReturnFromSource())

    assert effects == ()
    assert effects_after_return == ()
    assert opened.expanded_source is not None
    assert returned.expanded_source is None
    assert (
        returned.raw_query,
        returned.selected_case_id,
        returned.summary_level,
        returned.auxiliary_filter,
    ) == before_round_trip
