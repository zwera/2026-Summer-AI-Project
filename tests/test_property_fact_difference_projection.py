"""Property 21: 핵심 사실 차이 projection과 null 처리 (task 10.2).

Independently generated query-case fact-difference collections are projected
without losing or duplicating comparison items. Each nullable fact field is
resolved independently through the fixture display policy.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_common import DisplayPolicyRecord, FactDimension
from data.models_fact_difference import FactDifference
from domain.ids import SourceId
from domain.similarity_and_difference import resolve_fact_difference_display


_CONFIRMATION_NEEDED = "확인 필요"
_FACT_DIMENSIONS: tuple[FactDimension, ...] = (
    "체포 시점",
    "영장 유무",
    "동행 자발성",
    "권리 고지 여부",
    "물리력 정도",
    "증거 확보 방식",
    "기타",
)
_PLACEHOLDERS = (
    DisplayPolicyRecord(
        id="property-21-confirmation-needed",
        kind="PLACEHOLDER",
        key=_CONFIRMATION_NEEDED,
        text=_CONFIRMATION_NEEDED,
    ),
)


@st.composite
def fact_difference_collection_strategy(
    draw: st.DrawFn,
) -> tuple[FactDifference, ...]:
    """Generate a query-case comparison collection with unique item IDs.

    The collection may be empty, may include every standard dimension and
    ``기타``, and permits several distinct IDs for one dimension.
    """

    specifications = draw(
        st.lists(
            st.tuples(
                st.sampled_from(_FACT_DIMENSIONS),
                st.one_of(st.none(), st.text(min_size=1, max_size=20)),
                st.one_of(st.none(), st.text(min_size=1, max_size=20)),
                st.one_of(st.none(), st.text(min_size=1, max_size=20)),
                st.booleans(),
                st.integers(min_value=0, max_value=100),
            ),
            min_size=0,
            max_size=20,
        )
    )

    return tuple(
        FactDifference(
            id=f"property-21-difference-{index}",
            dimension=dimension,
            user_fact=user_fact,
            case_fact=case_fact,
            conclusion_impact=conclusion_impact,
            could_change_conclusion=could_change_conclusion,
            display_priority=display_priority,
            source_ids=(SourceId(f"property-21-source-{index}"),),
        )
        for index, (
            dimension,
            user_fact,
            case_fact,
            conclusion_impact,
            could_change_conclusion,
            display_priority,
        ) in enumerate(specifications)
    )


def _display_value(value: Optional[str]) -> str:
    """Independent field-level null-coalescing oracle for Property 21."""

    return _CONFIRMATION_NEEDED if value is None else value


# Feature: police-case-law-ai-bot, Property 21
# 핵심 사실 차이의 완전 projection과 null 처리
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(differences=fact_difference_collection_strategy())
def test_fact_difference_projection_is_complete_and_null_safe(
    differences: tuple[FactDifference, ...],
) -> None:
    """**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**.

    Every predefined comparison item is projected exactly once, preserves its
    dimension as an independent display item, and only replaces the nullable
    field at the missing position with the configured confirmation prompt.
    """

    projections = tuple(
        resolve_fact_difference_display(difference, _PLACEHOLDERS)
        for difference in differences
    )

    # Requirement 8.1 and 8.3: no predefined comparison item is omitted,
    # introduced, or duplicated; zero differences remain an empty section.
    assert Counter(projection.id for projection in projections) == Counter(
        difference.id for difference in differences
    )
    assert tuple(projection.dimension for projection in projections) == tuple(
        difference.dimension for difference in differences
    )

    # Requirements 8.2 and 8.4~8.6: all three fields are separate and each
    # null is resolved at only its own display position.
    for difference, projection in zip(differences, projections):
        assert projection.user_fact == _display_value(difference.user_fact)
        assert projection.case_fact == _display_value(difference.case_fact)
        assert projection.conclusion_impact == _display_value(
            difference.conclusion_impact
        )
        assert projection.id == difference.id
        assert projection.dimension == difference.dimension
