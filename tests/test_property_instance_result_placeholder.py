"""Property 20: 해당 심급 죄명·재판 결과 누락의 독립 placeholder (task 5.7).

각 필드는 다른 필드와 독립적으로 fixture 값을 유지하거나, fixture 값이 ``None``인
경우에만 표시 정책의 ``확인되지 않음`` placeholder를 사용해야 한다.
"""

from __future__ import annotations

import dataclasses
from typing import Optional

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from data.fixture_repository import FixtureRepository
from data.validated_dataset import ValidatedDataset
from domain.mock_search import run_mock_search
from domain.result import Ok


_NULLABLE_DISPLAY_VALUE = st.one_of(
    st.none(),
    st.text(min_size=1),
)


def _expected_display_value(value: Optional[str], placeholder: str) -> str:
    """Independent field-level oracle for the null placeholder contract."""

    return placeholder if value is None else value


# Feature: police-case-law-ai-bot
# Property 20: 해당 심급 죄명·재판 결과 누락의 독립 placeholder
@settings(
    max_examples=100,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    data=st.data(),
    charge=_NULLABLE_DISPLAY_VALUE,
    outcome=_NULLABLE_DISPLAY_VALUE,
)
def test_instance_charge_and_outcome_use_independent_placeholders(
    validated_mock_dataset: ValidatedDataset,
    data: st.DataObject,
    charge: Optional[str],
    outcome: Optional[str],
) -> None:
    """**Validates: Requirements 7.7**.

    All four null/non-null combinations retain each present fixture value
    exactly and replace only the missing field with the fixture-backed
    placeholder.
    """

    query = data.draw(
        st.sampled_from(validated_mock_dataset.queries),
        label="registered_query",
    )
    case_id = data.draw(
        st.sampled_from(query.match.case_ids),
        label="matched_case_id",
    )
    repository = FixtureRepository(validated_mock_dataset)
    case = repository.get_case(case_id)
    assert case is not None
    repository._cases_by_id[case_id] = dataclasses.replace(
        case,
        instance_recognized_charge=charge,
        instance_outcome=outcome,
    )

    result = run_mock_search(query, repository)

    assert isinstance(result, Ok)
    projected_case = next(
        item for item in result.value.cases if item.case_id == case_id
    )
    placeholder = next(
        policy.text
        for policy in validated_mock_dataset.display_policies.placeholders
        if policy.key == "확인되지 않음"
    )
    expected_charge = _expected_display_value(charge, placeholder)
    assert projected_case.instance_recognized_charge == expected_charge
    assert projected_case.instance_outcome == _expected_display_value(
        outcome,
        placeholder,
    )
