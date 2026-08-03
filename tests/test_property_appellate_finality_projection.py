"""Property 37: 상급심·확정 정보의 총 projection과 무합성 (task 11.6).

사전 정의된 상급심 결정과 확정 상태를 생성해, projection이 필드를 재계산하거나
결측 상급심/확정 정보를 합성하지 않는지 검증한다.
"""

from __future__ import annotations

from typing import Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_case import AppellateDecision, AppellateInformation
from domain.appellate_projection import (
    project_appellate_information,
    project_finality_badge,
)
from domain.ids import SourceId


@st.composite
def _appellate_decisions(
    draw: st.DrawFn,
) -> Tuple[AppellateDecision, ...]:
    """0개 이상 상급심 결정을 유효한 fixture 형태로 생성한다.

    생성 순서는 projection이 보존해야 하는 사전 정의 표시 순서이며, 항소심/상고심과
    원심 유지/변경의 모든 조합을 포함한다.
    """

    specifications = draw(
        st.lists(
            st.tuples(
                st.sampled_from(("항소심", "상고심")),
                st.sampled_from(("유지", "변경")),
                st.text(min_size=1, max_size=20),
                st.text(min_size=1, max_size=20),
                st.dates().map(lambda date: date.isoformat()),
                st.lists(
                    st.text(min_size=1, max_size=16),
                    max_size=3,
                ).map(tuple),
            ),
            max_size=5,
        )
    )
    return tuple(
        AppellateDecision(
            case_number=f"property-37-{index}",
            instance=instance,
            court_name=court_name,
            decision_date=decision_date,
            outcome=outcome,
            relation_to_lower_instance=relation_to_lower_instance,
            source_ids=tuple(SourceId(source_id) for source_id in source_ids),
        )
        for index, (
            instance,
            relation_to_lower_instance,
            court_name,
            outcome,
            decision_date,
            source_ids,
        ) in enumerate(specifications)
    )


@st.composite
def _appellate_information(draw: st.DrawFn) -> AppellateInformation:
    """상태-결정 배열 불변식을 지키는 상급심 정보를 생성한다."""

    state = draw(st.sampled_from(("PRESENT", "정보_없음")))
    decisions = draw(_appellate_decisions()) if state == "PRESENT" else ()
    return AppellateInformation(state=state, decisions=decisions)


# Feature: police-case-law-ai-bot, Property 37: 상급심·확정 정보의 총 projection과 무합성
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(
    appellate=_appellate_information(),
    finality=st.sampled_from(("확정", "미확정", "정보_없음")),
)
def test_appellate_and_finality_projection_is_total_and_does_not_invent_values(
    appellate: AppellateInformation,
    finality: str,
) -> None:
    """**Validates: Requirements 12.6, 12.7, 12.8, 12.9, 12.11, 12.12**.

    PRESENT 상태에서는 각 사전 정의 결정의 사건번호·심급·선고일·결과 등 모든 필드와
    순서를 그대로 유지한다. 정보_없음 상태는 어떤 상세 결정을 만들지 않으며, 확정 상태는
    확정/미확정 중 정확히 하나의 배지 또는 정보_없음일 때 배지 0개만 허용한다.
    """

    appellate_projection = project_appellate_information(appellate)

    assert appellate_projection.state == appellate.state
    if appellate.state == "정보_없음":
        assert appellate.decisions == ()
        assert appellate_projection.decisions == ()
    else:
        assert len(appellate_projection.decisions) == len(appellate.decisions)
        for expected, actual in zip(
            appellate.decisions, appellate_projection.decisions
        ):
            assert actual.case_number == expected.case_number
            assert actual.instance == expected.instance
            assert actual.court_name == expected.court_name
            assert actual.decision_date == expected.decision_date
            assert actual.outcome == expected.outcome
            assert (
                actual.relation_to_lower_instance
                == expected.relation_to_lower_instance
            )
            assert actual.source_ids == expected.source_ids

    finality_badge = project_finality_badge(finality)  # type: ignore[arg-type]
    if finality == "정보_없음":
        assert finality_badge is None
    else:
        assert finality_badge is not None
        assert finality_badge.finality == finality
