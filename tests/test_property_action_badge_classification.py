"""Property 17: 행동 배지의 만장일치·배타 분류 (task 9.3).

행동 판단 출처의 전체 집합을 독립 참조 진리표로 분류하여,
문제/적법 만장일치와 빈·충돌·모호 입력의 배타적 결과를 검증한다.
"""

from __future__ import annotations

from typing import Sequence, Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_common import CourtFinding
from data.models_risk import (
    ActionBadgeLawful,
    ActionBadgeProblem,
    ActionJudgment,
)
from domain.ids import SourceId
from domain.liability_classification import classify_action_badge


_FINDINGS: Tuple[CourtFinding, ...] = ("PROBLEM", "LAWFUL", "AMBIGUOUS")


@st.composite
def _action_judgments(draw: st.DrawFn) -> tuple[ActionJudgment, ...]:
    """Generate one action's source judgments, including duplicate sources."""

    specifications = draw(
        st.lists(
            st.tuples(
                st.sampled_from(_FINDINGS),
                st.lists(
                    st.integers(min_value=0, max_value=5),
                    min_size=1,
                    max_size=3,
                ),
            ),
            min_size=0,
            max_size=100,
        )
    )
    return tuple(
        ActionJudgment(
            action_id="property-17-action",
            action_text="속성 테스트 행동",
            court_finding=finding,
            source_ids=tuple(
                SourceId(f"property-17-source-{source_index}")
                for source_index in source_indices
            ),
        )
        for finding, source_indices in specifications
    )


def _dedupe_source_ids(
    judgments: Sequence[ActionJudgment],
) -> tuple[SourceId, ...]:
    """Return source IDs in first-occurrence order for the reference oracle."""

    seen: set[SourceId] = set()
    result: list[SourceId] = []
    for judgment in judgments:
        for source_id in judgment.source_ids:
            if source_id not in seen:
                seen.add(source_id)
                result.append(source_id)
    return tuple(result)


# Feature: police-case-law-ai-bot
# Property 17: 행동 배지의 만장일치·배타 분류
@settings(max_examples=100, derandomize=True)
@given(judgments=_action_judgments())
def test_action_badge_is_unanimous_and_exclusive(
    judgments: tuple[ActionJudgment, ...],
) -> None:
    """**Validates: Requirements 6.6, 6.7, 6.9, 6.12, 6.13**.

    Empty evidence produces no badge. Only unanimous problem or lawful evidence
    produces its respective single badge; mixed or ambiguous evidence produces
    no actionable badge and is unclassifiable.
    """

    badge = classify_action_badge(judgments)
    findings = {judgment.court_finding for judgment in judgments}

    if not judgments:
        assert badge.state == "정보_없음"
        assert not hasattr(badge, "source_ids")
    elif findings == {"PROBLEM"}:
        assert isinstance(badge, ActionBadgeProblem)
        assert badge.state == "문제_행동"
        assert badge.source_ids == _dedupe_source_ids(judgments)
    elif findings == {"LAWFUL"}:
        assert isinstance(badge, ActionBadgeLawful)
        assert badge.state == "적법_행동"
        assert badge.source_ids == _dedupe_source_ids(judgments)
    else:
        assert badge.state == "분류_불가"
        assert not hasattr(badge, "source_ids")
