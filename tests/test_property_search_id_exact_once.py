"""Property 7: matching, full-text, and statute IDs preserve exact-once sets.

The search boundary accepts fixture-derived match/reference collections.  Their
order may vary and IDs may repeat, but every valid case, statute, full-text
source, and cited-statute tag must reach its projection exactly once.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from data.fixture_repository import FixtureRepository
from data.models_query import QueryMatch
from data.validated_dataset import validate_dataset
from domain.result import Ok
from domain.mock_search import run_mock_search
from fixtures.mock_dataset import build_mock_dataset


def _repository() -> FixtureRepository:
    result = validate_dataset(build_mock_dataset())
    assert isinstance(result, Ok)
    return FixtureRepository(result.value)


# Feature: police-case-law-ai-bot, Property 7: 매칭·전문·법조문 ID의 exact-once 집합 보존
# **Validates: Requirements 3.1, 3.2, 3.7, 10.1**
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(
    case_indexes=st.lists(st.integers(min_value=0, max_value=1), max_size=20),
    statute_indexes=st.lists(st.just(0), max_size=20),
    duplicate_references=st.booleans(),
)
def test_search_preserves_valid_ids_exactly_once(
    case_indexes: list[int],
    statute_indexes: list[int],
    duplicate_references: bool,
) -> None:
    """**Validates: Requirements 3.1, 3.2, 3.7, 10.1**."""

    dataset = build_mock_dataset()
    query = next(item for item in dataset.queries if item.id == "query-arrest")
    repo = _repository()

    case_ids = tuple(query.match.case_ids[index] for index in case_indexes)
    statute_ids = tuple(
        query.match.statute_version_ids[index] for index in statute_indexes
    )
    mutated_query = replace(
        query,
        match=QueryMatch(
            case_ids=case_ids,
            statute_version_ids=statute_ids,
            response_template_id=query.match.response_template_id,
        ),
    )

    # Duplicate valid references simulate repeated source/full-text and cited
    # statute entries while retaining a valid repository target for every ID.
    if duplicate_references:
        for case_id in set(case_ids):
            case = repo.get_case(case_id)
            assert case is not None
            repo._cases_by_id[case_id] = replace(
                case,
                source_ids=case.source_ids + case.source_ids,
                applied_statutes=case.applied_statutes + case.applied_statutes,
            )

    result = run_mock_search(mutated_query, repo)

    assert isinstance(result, Ok)
    projection = result.value
    expected_case_ids = set(case_ids)
    expected_statute_ids = set(statute_ids)

    actual_case_ids = tuple(case.case_id for case in projection.cases)
    actual_statute_ids = tuple(
        statute.statute_version_id for statute in projection.statutes
    )
    assert Counter(actual_case_ids) == Counter(expected_case_ids)
    assert Counter(actual_statute_ids) == Counter(expected_statute_ids)

    expected_source_ids = set()
    for case_id in expected_case_ids:
        source_case = repo.get_case(case_id)
        assert source_case is not None
        expected_source_ids.update(source_case.source_ids)
    assert Counter(projection.direct_evidence_source_ids) == Counter(
        expected_source_ids
    )

    for case_projection in projection.cases:
        source_case = repo.get_case(case_projection.case_id)
        assert source_case is not None
        expected_tags = {
            reference.citation_label
            for reference in source_case.applied_statutes
        }
        assert Counter(case_projection.applied_statute_labels) == Counter(
            expected_tags
        )
