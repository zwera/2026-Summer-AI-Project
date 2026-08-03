"""Property 14: 요약 단계 전환의 canonical 불변성 (task 8.3).

유효 fixture의 판례와 3줄/10줄/상세 요약 단계 전환 시퀀스를 생성한다. 각 전환 뒤
법원 결론, 적법성 상태, 해당 심급 인정 죄명, 해당 심급 재판 결과가 판례의 canonical
값 및 전환 전 값과 항상 같은지 확인한다.
"""

from __future__ import annotations

from typing import Tuple

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from data.models_case import CaseRecord
from data.validated_dataset import ValidatedDataset
from domain.enums import LegalityStatus, SummaryLevel
from domain.summary_projection import project_summary


# Feature: police-case-law-ai-bot, Property 14: 요약 단계 전환의 canonical 불변성
@settings(
    max_examples=100,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.data())
def test_canonical_conclusions_are_invariant_across_summary_level_transitions(
    validated_mock_dataset: ValidatedDataset,
    data: st.DataObject,
) -> None:
    """요약 단계를 임의 순서로 전환해도 canonical 결론 4필드는 변하지 않는다.

    **Validates: Requirements 5.7**
    """

    case = data.draw(
        st.sampled_from(validated_mock_dataset.cases), label="case"
    )
    transition_levels = data.draw(
        st.lists(
            st.sampled_from(tuple(SummaryLevel)), min_size=1, max_size=12
        ),
        label="summary_level_transitions",
    )
    expected = _canonical_fields(case)

    for level in transition_levels:
        projection = project_summary(
            case.summaries,
            level,
            validated_mock_dataset.display_policies.placeholders,
        )
        actual = (
            projection.canonical_conclusion,
            projection.canonical_legality_status,
            projection.canonical_instance_charge,
            projection.canonical_instance_outcome,
        )
        assert actual == expected


def _canonical_fields(
    case: CaseRecord,
) -> Tuple[str, LegalityStatus, str | None, str | None]:
    """판례 fixture에서 독립 오라클로 사용할 canonical 4필드를 읽는다."""

    summaries = case.summaries
    return (
        summaries.canonical_conclusion,
        summaries.canonical_legality_status,
        summaries.canonical_instance_charge,
        summaries.canonical_instance_outcome,
    )
