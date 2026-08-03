"""Property 22: 유사도 경고 구간 분할과 결정적 차이 우선 (task 10.3).

유효한 유사도 점수는 정확히 하나의 사전 정의 경고 구간으로 분류되어야 한다.
높은 유사도 구간에서 결론을 바꿀 수 있는 사실 차이가 있으면, 그 차이는 점수보다
앞선 경고 항목으로 표시되어야 한다.
"""

from __future__ import annotations

from typing import Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_fact_difference import FactDifference
from domain.similarity_and_difference import (
    order_fact_differences,
    similarity_warning,
)
from fixtures.mock_dataset import build_mock_dataset


_POLICIES = build_mock_dataset().display_policies.similarity_warnings


@st.composite
def _fact_differences(draw: st.DrawFn) -> Tuple[FactDifference, ...]:
    """결정적·비결정적 차이와 우선순위가 섞인 유효 차이 목록을 만든다."""

    specifications = draw(
        st.lists(
            st.tuples(
                st.booleans(),
                st.integers(min_value=-100, max_value=100),
            ),
            max_size=20,
        )
    )
    return tuple(
        FactDifference(
            id=f"property-22-difference-{index}",
            dimension="체포 시점",
            user_fact="사용자 사실",
            case_fact="판례 사실",
            conclusion_impact="결론 영향",
            could_change_conclusion=could_change_conclusion,
            display_priority=display_priority,
            source_ids=(),
        )
        for index, (could_change_conclusion, display_priority) in enumerate(
            specifications
        )
    )


def _expected_warning(score: float) -> tuple[str, str]:
    """설계에 명시된 세 경계 구간의 독립 참조 오라클이다."""

    if score < 50:
        return ("LOW", "낮은 유사도 — 결론 근거로 사용 금지")
    if score < 80:
        return ("MEDIUM", "중간 유사도 — 직접 적용 전 사실관계 재검토 필요")
    return ("HIGH", "높은 유사도 — 핵심 차이 확인 필요")


# Feature: police-case-law-ai-bot, Property 22: 유사도 경고 구간 분할과 결정적 차이 우선
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(
    score=st.floats(
        min_value=0,
        max_value=100,
        allow_nan=False,
        allow_infinity=False,
    ),
    differences=_fact_differences(),
)
def test_similarity_warning_bands_and_decisive_differences_take_priority(
    score: float,
    differences: Tuple[FactDifference, ...],
) -> None:
    """**Validates: Requirements 8.7, 8.8, 8.9, 8.10**.

    Each valid score selects exactly the fixed LOW/MEDIUM/HIGH warning dictated
    by the three non-overlapping bands. Fact differences are ordered with all
    conclusion-changing entries before non-decisive entries; specifically, this
    remains true for every high-similarity result.
    """

    warning = similarity_warning(score, _POLICIES)
    expected_key, expected_text = _expected_warning(score)

    assert warning.key == expected_key
    assert warning.text == expected_text

    ordered = order_fact_differences(score, differences)
    expected_order = tuple(
        sorted(
            differences,
            key=lambda difference: (
                0 if difference.could_change_conclusion else 1,
                difference.display_priority,
                difference.id,
            ),
        )
    )
    assert ordered == expected_order

    if score >= 80 and any(
        difference.could_change_conclusion for difference in differences
    ):
        first_non_decisive_index = next(
            (
                index
                for index, difference in enumerate(ordered)
                if not difference.could_change_conclusion
            ),
            len(ordered),
        )
        assert all(
            difference.could_change_conclusion
            for difference in ordered[:first_non_decisive_index]
        )
        assert all(
            not difference.could_change_conclusion
            for difference in ordered[first_non_decisive_index:]
        )
