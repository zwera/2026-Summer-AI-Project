"""Property 23: 유사도 변화에 대한 판례 결론 불변성 (task 10.4).

같은 판례의 유사도 preset을 서로 다른 경고 구간의 유효 점수로 바꿔도, 검색 결과와
요약의 판례 결론 값은 fixture의 canonical 값에서 변하지 않아야 한다.
"""

from __future__ import annotations

import dataclasses

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from data.fixture_repository import FixtureRepository
from data.models_case import CaseRecord
from data.models_query import QueryFixture
from data.validated_dataset import ValidatedDataset
from domain.enums import SummaryLevel
from domain.mock_search import SearchCaseProjection, run_mock_search
from domain.result import Ok
from domain.similarity_and_difference import similarity_warning
from domain.summary_projection import project_summary


_LOW_SCORE = st.floats(
    min_value=0,
    max_value=49.999,
    allow_nan=False,
    allow_infinity=False,
)
_MID_OR_HIGH_SCORE = st.floats(
    min_value=50,
    max_value=100,
    allow_nan=False,
    allow_infinity=False,
)


def _query_with_score(
    query: QueryFixture, case: CaseRecord, score: float
) -> QueryFixture:
    """Return a query whose selected case has only its fixture score replaced."""

    presets = dict(query.similarity_by_case)
    presets[case.id] = dataclasses.replace(presets[case.id], score=score)
    return dataclasses.replace(query, similarity_by_case=presets)


def _case_projection(
    query: QueryFixture, repository: FixtureRepository, case: CaseRecord
) -> SearchCaseProjection:
    """Run the actual fixture-backed search and extract the chosen case result."""

    result = run_mock_search(query, repository)
    assert isinstance(result, Ok)
    return next(projection for projection in result.value.cases if projection.case_id == case.id)


# Feature: police-case-law-ai-bot, Property 23: 유사도 변화에 대한 판례 결론 불변성
@settings(
    max_examples=100,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.data(), low_score=_LOW_SCORE, mid_or_high_score=_MID_OR_HIGH_SCORE)
def test_case_conclusions_remain_invariant_when_similarity_preset_changes(
    validated_mock_dataset: ValidatedDataset,
    data: st.DataObject,
    low_score: float,
    mid_or_high_score: float,
) -> None:
    """**Validates: Requirements 8.11**.

    A score from the LOW warning band and one from the MEDIUM/HIGH bands are
    applied to the same query-case pair. The score and warning change, while
    legality status, court conclusion, and instance outcome remain the same
    fixture-defined canonical conclusion values.
    """

    query = data.draw(st.sampled_from(validated_mock_dataset.queries), label="query")
    case = data.draw(
        st.sampled_from(
            tuple(
                item
                for item in validated_mock_dataset.cases
                if item.id in query.match.case_ids
            )
        ),
        label="case",
    )
    repository = FixtureRepository(validated_mock_dataset)

    low_query = _query_with_score(query, case, low_score)
    mid_or_high_query = _query_with_score(query, case, mid_or_high_score)
    low_projection = _case_projection(low_query, repository, case)
    mid_or_high_projection = _case_projection(mid_or_high_query, repository, case)

    policies = validated_mock_dataset.display_policies.similarity_warnings
    assert similarity_warning(low_projection.similarity_score, policies).key == "LOW"
    assert similarity_warning(mid_or_high_projection.similarity_score, policies).key != "LOW"

    expected_outcome = case.instance_outcome
    if expected_outcome is None:
        placeholder = next(
            policy
            for policy in validated_mock_dataset.display_policies.placeholders
            if policy.key == "확인되지 않음"
        )
        expected_outcome = placeholder.text
    expected = (
        case.legality_status,
        case.summaries.canonical_conclusion,
        expected_outcome,
    )

    low_summary = project_summary(
        case.summaries,
        data.draw(
            st.sampled_from(tuple(SummaryLevel)), label="low_summary_level"
        ),
        validated_mock_dataset.display_policies.placeholders,
    )
    mid_or_high_summary = project_summary(
        case.summaries,
        data.draw(
            st.sampled_from(tuple(SummaryLevel)), label="mid_or_high_summary_level"
        ),
        validated_mock_dataset.display_policies.placeholders,
    )

    assert (
        low_projection.legality_status,
        low_summary.canonical_conclusion,
        low_projection.instance_outcome,
    ) == expected
    assert (
        mid_or_high_projection.legality_status,
        mid_or_high_summary.canonical_conclusion,
        mid_or_high_projection.instance_outcome,
    ) == expected
