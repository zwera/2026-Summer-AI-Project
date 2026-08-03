"""Property 19: 검색 우선순위의 결정적 안정 정렬 (task 5.6).

검색 결과는 입력 순열과 무관하게 fixture의 검색 우선순위, 동순위 순서,
case ID로 결정적으로 정렬되어야 한다. 또한 현행법 기준 결과는 구법 기준 결과보다
앞에 유지되어야 하며, 같은 법령 상태 안에서는 fixture 순서 값이 그대로 적용된다.
"""

from __future__ import annotations

from typing import Sequence, Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from domain.enums import LawBasisStatus, LegalityStatus
from domain.ids import CaseId
from domain.mock_search import (
    SearchCaseProjection,
    sort_cases_deterministically,
)


_CASE_ID_ALPHABET = "abcXYZ012가나다"
_LAW_STATUSES = tuple(LawBasisStatus)


def _law_status_rank(status: LawBasisStatus) -> int:
    """Reference precedence for current, indeterminate, and old groups."""

    if status is LawBasisStatus.CURRENT_LAW_BASIS:
        return 0
    if status is LawBasisStatus.INDETERMINATE:
        return 1
    return 2


def _projection(
    case_id: str,
    status: LawBasisStatus,
    priority: int,
    tie_order: int,
) -> SearchCaseProjection:
    """Build a minimal valid result without production sorting logic."""

    return SearchCaseProjection(
        case_id=CaseId(case_id),
        case_number=case_id,
        court_name="테스트 법원",
        instance="1심",
        decision_date="2024-01-01",
        scenario_ids=(),
        legality_status=LegalityStatus.LAWFUL,
        law_basis_status=status,
        applied_statute_labels=(),
        similarity_score=50.0,
        search_priority=priority,
        tie_order=tie_order,
        instance_recognized_charge="죄명",
        instance_outcome="결과",
    )


@st.composite
def _search_case_lists(
    draw: st.DrawFn,
) -> Tuple[SearchCaseProjection, ...]:
    """Generate IDs, duplicate-capable priorities, and unique tie orders."""

    case_ids = draw(
        st.lists(
            st.text(
                alphabet=_CASE_ID_ALPHABET,
                min_size=1,
                max_size=8,
            ),
            min_size=0,
            max_size=20,
            unique=True,
        ),
        label="unique_case_ids",
    )
    statuses = draw(
        st.lists(
            st.sampled_from(_LAW_STATUSES),
            min_size=len(case_ids),
            max_size=len(case_ids),
        ),
        label="law_statuses",
    )
    priorities = draw(
        st.lists(
            st.integers(min_value=-10, max_value=10),
            min_size=len(case_ids),
            max_size=len(case_ids),
        ),
        label="search_priorities",
    )

    return tuple(
        _projection(case_id, status, priority, tie_order)
        for tie_order, (case_id, status, priority) in enumerate(
            zip(case_ids, statuses, priorities)
        )
    )


def _reference_order(
    cases: Sequence[SearchCaseProjection],
) -> Tuple[CaseId, ...]:
    """Return IDs from a comparator independent of the production function."""

    return tuple(
        case.case_id
        for case in sorted(
            cases,
            key=lambda case: (
                _law_status_rank(case.law_basis_status),
                case.search_priority,
                case.tie_order,
                str(case.case_id),
            ),
        )
    )


# Feature: police-case-law-ai-bot, Property 19: 검색 우선순위의 결정적 안정 정렬
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(data=st.data())
def test_search_priority_sort_is_deterministic_and_preserves_law_precedence(
    data: st.DataObject,
) -> None:
    """**Validates: Requirements 7.3, 7.8, 7.9, 10.9, 10.13**.

    Every generated input permutation yields the independent fixture-order
    comparator result. Current-law results precede old-law results, while
    cases sharing a law status retain their priority/tie-order/case-ID order.
    """

    cases = data.draw(_search_case_lists(), label="search_cases")
    permutation = data.draw(st.permutations(cases), label="input_permutation")

    expected_ids = _reference_order(cases)
    actual_ids = tuple(
        case.case_id for case in sort_cases_deterministically(permutation)
    )

    assert actual_ids == expected_ids
    assert actual_ids == _reference_order(permutation)

    sorted_cases = sort_cases_deterministically(permutation)
    current_indexes = [
        index
        for index, case in enumerate(sorted_cases)
        if case.law_basis_status is LawBasisStatus.CURRENT_LAW_BASIS
    ]
    old_indexes = [
        index
        for index, case in enumerate(sorted_cases)
        if case.law_basis_status is LawBasisStatus.OLD_LAW_BASIS
    ]
    if current_indexes and old_indexes:
        assert max(current_indexes) < min(old_indexes)

    for status in _LAW_STATUSES:
        same_status = [
            case for case in sorted_cases if case.law_basis_status is status
        ]
        assert [case.case_id for case in same_status] == list(
            _reference_order(
                [case for case in cases if case.law_basis_status is status]
            )
        )
