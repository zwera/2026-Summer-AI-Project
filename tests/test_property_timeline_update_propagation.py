"""Property 35: 타임라인 수정의 일관된 전파 (task 13.7).

독립 참조 모델로 유효한 시간/내용 수정 명령을 적용한 뒤, 대상 사건만
교체되는지, 새 타임라인 정렬과 새 보고서가 동일한 수정값을 사용하는지 검증한다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import List, Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_common import IsoDate
from data.models_timeline import RecognizedEvent
from domain.ids import EventId
from domain.report import build_report_facts
from domain.timeline import (
    TimelineState,
    UpdateEventCommand,
    build_timeline,
    update_timeline_event,
)


_BASE_TIME = datetime(2024, 1, 1, 0, 0, 0)
_NOTICE = "테스트 법률 안전 고지"


@dataclass(frozen=True)
class _Metadata:
    as_of_date: IsoDate = "2024-01-01"


@st.composite
def _timeline_update_inputs(
    draw: st.DrawFn,
) -> Tuple[TimelineState, UpdateEventCommand]:
    """유일 ID를 가진 사건과 유효 시간·내용 수정 명령을 생성한다."""

    count = draw(st.integers(min_value=1, max_value=20))
    original_orders = draw(st.permutations(tuple(range(count))))
    events: List[RecognizedEvent] = []
    for index in range(count):
        known_time = draw(st.booleans())
        timestamp = None
        if known_time:
            timestamp = (
                _BASE_TIME
                + timedelta(seconds=draw(st.integers(0, 172800)))
            ).isoformat()
        events.append(
            RecognizedEvent(
                id=EventId(f"event-{index}"),
                original_text=f"original-text-{index}",
                action=f"action-{index}",
                actor=f"actor-{index}",
                original_order=original_orders[index],
                explicit_time=timestamp,
                resolved_sort_time=timestamp,
            )
        )

    target_index = draw(st.integers(min_value=0, max_value=count - 1))
    update_time = (
        _BASE_TIME
        + timedelta(seconds=draw(st.integers(0, 172800)))
    ).isoformat()
    command = UpdateEventCommand(
        event_id=events[target_index].id,
        original_text=draw(st.text(min_size=1, max_size=30)),
        action=draw(st.text(min_size=1, max_size=30)),
        actor=draw(st.text(min_size=1, max_size=30)),
        explicit_time=update_time,
    )
    return TimelineState(events=tuple(events)), command


def _reference_update(
    state: TimelineState, command: UpdateEventCommand
) -> Tuple[RecognizedEvent, ...]:
    """도메인 구현과 분리된 불변 map-update 참조 모델."""

    updated = []
    for event in state.events:
        if event.id != command.event_id:
            updated.append(event)
            continue
        updated.append(
            replace(
                event,
                original_text=command.original_text,
                action=command.action,
                actor=command.actor,
                explicit_time=command.explicit_time,
                resolved_sort_time=command.explicit_time,
            )
        )
    return tuple(updated)


# Feature: police-case-law-ai-bot, Property 35: 타임라인 수정의 일관된 전파
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(inputs=_timeline_update_inputs())
def test_timeline_update_propagates_consistently_to_projection_and_report(
    inputs: Tuple[TimelineState, UpdateEventCommand],
) -> None:
    """**Validates: Requirements 11.11**

    유효한 시간/내용 수정은 대상 사건의 기존 값을 교체하고, 재생성된 타임라인과
    보고서는 같은 사건·같은 수정값을 사용한다. 다른 사건은 변경되지 않는다.
    """

    state, command = inputs
    expected_events = _reference_update(state, command)

    updated_state = update_timeline_event(state, command)
    expected_projection = build_timeline(expected_events)
    report = build_report_facts(updated_state.projection, _Metadata(), _NOTICE)

    assert updated_state.events == expected_events
    assert updated_state.projection == expected_projection

    for original, updated in zip(state.events, updated_state.events):
        if original.id == command.event_id:
            assert updated.original_text == command.original_text
            assert updated.action == command.action
            assert updated.actor == command.actor
            assert updated.explicit_time == command.explicit_time
            assert updated.resolved_sort_time == command.explicit_time
        else:
            assert updated is original

    target = next(
        event for event in updated_state.events if event.id == command.event_id
    )
    displayed_events = (
        updated_state.projection.ordered
        + updated_state.projection.unknown_time
    )
    displayed_target = next(
        event for event in displayed_events if event.id == command.event_id
    )
    assert displayed_target == target
    assert f"[{target.id}] {target.original_text}" in report.body
    assert report.event_ids == tuple(event.id for event in displayed_events)
