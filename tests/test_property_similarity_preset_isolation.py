"""Property 18: 유사도 preset 보존과 잘못된 값 격리 (task 5.5).

유효한 query-case 유사도 preset은 검색 projection에 재계산 없이 그대로 표시되어야
한다. 누락, 비숫자, 비유한 또는 범위 밖 score는 해당 판례만 격리하고, 같은 검색의
나머지 유효 판례 및 ``유사도 데이터 오류`` 진단은 유지되어야 한다.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Union, cast

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from data.fixture_repository import FixtureRepository
from data.models_query import QueryFixture
from data.validated_dataset import ValidatedDataset
from domain.mock_search import run_mock_search
from domain.result import Ok


_ValidScore = Union[int, float]
_InvalidScore = Union[None, str, float]

_VALID_SCORES = st.one_of(
    st.sampled_from((0, -0.0, 50, 100)),
    st.integers(min_value=0, max_value=100),
    st.floats(
        min_value=0,
        max_value=100,
        allow_nan=False,
        allow_infinity=False,
    ),
)
_INVALID_SCORES = st.one_of(
    st.none(),
    st.text(),
    st.sampled_from((float("nan"), float("inf"), float("-inf"))),
    st.floats(max_value=-0.000_001, allow_nan=False, allow_infinity=False),
    st.floats(min_value=100.000_001, allow_nan=False, allow_infinity=False),
)


def _query_with_score(
    query: QueryFixture, case_index: int, score: _ValidScore | _InvalidScore
) -> QueryFixture:
    """Return a query with only one selected case's score fixture changed."""

    case_id = query.match.case_ids[case_index]
    presets = dict(query.similarity_by_case)
    if score is None:
        del presets[case_id]
    else:
        presets[case_id] = dataclasses.replace(
            presets[case_id], score=cast(Any, score)
        )
    return dataclasses.replace(query, similarity_by_case=presets)


def _is_valid_score(score: _ValidScore | _InvalidScore) -> bool:
    """Independent reference oracle for Property 18's valid score domain."""

    return (
        isinstance(score, (int, float))
        and not isinstance(score, bool)
        and math.isfinite(score)
        and 0 <= score <= 100
    )


# Feature: police-case-law-ai-bot, Property 18: 유사도 preset 보존과 잘못된 값 격리
@settings(
    max_examples=100,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.data(), score=st.one_of(_VALID_SCORES, _INVALID_SCORES))
def test_similarity_preset_is_preserved_or_case_locally_isolated(
    validated_mock_dataset: ValidatedDataset,
    data: st.DataObject,
    score: _ValidScore | _InvalidScore,
) -> None:
    """**Validates: Requirements 7.1, 7.2, 7.10, 7.11**.

    Valid finite scores in ``[0, 100]`` remain identical in the matching case
    projection. Every other generated value excludes only its selected case,
    preserves all valid sibling cases, and emits the fixture-backed similarity
    data-error diagnostic.
    """

    query = data.draw(
        st.sampled_from(
            tuple(
                item
                for item in validated_mock_dataset.queries
                if len(item.match.case_ids) >= 2
            )
        ),
        label="query_with_sibling_cases",
    )
    case_index = data.draw(
        st.integers(min_value=0, max_value=len(query.match.case_ids) - 1),
        label="mutated_case_index",
    )
    case_id = query.match.case_ids[case_index]
    expected_sibling_ids = {
        sibling_id
        for sibling_id in query.match.case_ids
        if sibling_id != case_id
    }

    result = run_mock_search(
        _query_with_score(query, case_index, score),
        FixtureRepository(validated_mock_dataset),
    )

    assert isinstance(result, Ok)
    projection = result.value
    projected_cases = {item.case_id: item for item in projection.cases}

    if _is_valid_score(score):
        assert case_id in projected_cases
        assert projected_cases[case_id].similarity_score == score
        assert projection.case_data_errors == ()
        return

    assert case_id not in projected_cases
    assert expected_sibling_ids <= set(projected_cases)
    assert len(projection.case_data_errors) == 1
    error = projection.case_data_errors[0]
    assert error.case_id == case_id
    assert error.policy_record_id == "status-similarity-data-error"
    assert error.message == "유사도 데이터 오류"
