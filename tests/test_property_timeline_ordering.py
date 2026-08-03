"""Property 33: 타임라인의 결정적 정렬·partition·exact-once (task 13.5).

독립 생성기는 명시 시각, 앞선 사건을 기준으로 한 비순환 상대 시각, 시점
미상 및 TIME/ACTOR/BOTH 모호성을 함께 만든다. 오라클은 구현과 별개로 상대
시각을 해석하고 ``(resolved time, original order)`` 및 ``original order`` 정렬을
계산해 ``build_timeline``의 결과를 확인한다.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import List, Optional, Sequence, Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_timeline import EventAmbiguity, RecognizedEvent, RelativeTime
from domain.ids import EventId
from domain.timeline import build_timeline


_BASE_TIME = datetime(2024, 1, 1, 0, 0, 0)


@st.composite
def _recognized_event_inputs(
    draw: st.DrawFn,
) -> Tuple[Tuple[RecognizedEvent, ...], Tuple[Optional[str], ...]]:
    """비순환 relative anchor를 포함한 유효 사건과 독립 참조 정렬 키를 생성한다."""

    count = draw(st.integers(min_value=0, max_value=25))
    original_orders = draw(st.permutations(tuple(range(count))))
    events: List[RecognizedEvent] = []
    resolved_times: List[Optional[str]] = []

    for index in range(count):
        kind = draw(st.sampled_from(("explicit", "relative", "unknown")))
        ambiguity_kind = draw(
            st.one_of(
                st.none(),
                st.sampled_from(("TIME", "ACTOR", "BOTH")),
            )
        )
        ambiguity = (
            None
            if ambiguity_kind is None
            else EventAmbiguity(
                kind=ambiguity_kind,
                alternatives=(
                    f"candidate-{index}-a",
                    f"candidate-{index}-b",
                ),
            )
        )
        event_id = EventId(f"event-{index}")
        original_order = original_orders[index]

        if kind == "explicit":
            offset_seconds = draw(st.integers(min_value=0, max_value=172800))
            resolved = (
                _BASE_TIME + timedelta(seconds=offset_seconds)
            ).isoformat()
            event = RecognizedEvent(
                id=event_id,
                original_text=f"event {index} original text",
                action=f"action-{index}",
                original_order=original_order,
                explicit_time=resolved,
                resolved_sort_time=resolved,
                ambiguity=ambiguity,
            )
        elif kind == "relative" and any(
            resolved is not None for resolved in resolved_times
        ):
            resolved_anchor_indices = [
                prior_index
                for prior_index, resolved in enumerate(resolved_times)
                if resolved is not None
            ]
            anchor_index = draw(st.sampled_from(resolved_anchor_indices))
            offset_seconds = draw(st.integers(min_value=-3600, max_value=3600))
            anchor_time = datetime.fromisoformat(
                resolved_times[anchor_index] or ""
            )
            resolved = (
                anchor_time + timedelta(seconds=offset_seconds)
            ).isoformat()
            event = RecognizedEvent(
                id=event_id,
                original_text=f"event {index} original text",
                action=f"action-{index}",
                original_order=original_order,
                relative_time=RelativeTime(
                    expression=f"anchor {offset_seconds:+d} seconds",
                    anchor_event_id=EventId(f"event-{anchor_index}"),
                    offset_seconds=float(offset_seconds),
                ),
                resolved_sort_time=resolved,
                ambiguity=ambiguity,
            )
        else:
            event = RecognizedEvent(
                id=event_id,
                original_text=f"event {index} original text",
                action=f"action-{index}",
                original_order=original_order,
                ambiguity=ambiguity,
            )
            resolved = None

        events.append(event)
        resolved_times.append(resolved)

    return tuple(events), tuple(resolved_times)


def _reference_partitions(
    events: Sequence[RecognizedEvent],
) -> Tuple[Tuple[RecognizedEvent, ...], Tuple[RecognizedEvent, ...]]:
    """구현과 독립된 명세 오라클로 두 타임라인 영역을 계산한다."""

    known = [event for event in events if event.resolved_sort_time is not None]
    unknown = [event for event in events if event.resolved_sort_time is None]
    ordered = tuple(
        sorted(
            known,
            key=lambda event: (
                event.resolved_sort_time,
                event.original_order,
            ),
        )
    )
    unknown_time = tuple(
        sorted(unknown, key=lambda event: event.original_order)
    )
    return ordered, unknown_time


# Feature: police-case-law-ai-bot, Property 33:
# 타임라인의 결정적 정렬·partition·exact-once
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(data=st.data())
def test_timeline_deterministic_order_partition_and_exact_once(
    data: st.DataObject,
) -> None:
    """**Validates: Requirements 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.10**

    명시/해결 시각과 유효한 상대 시각은 시각순(동률은 원문 순서)으로, 시점
    미상은 별도 원문 순서로 정렬한다. 모든 사건은 정확히 한 번 포함되며
    모호성 후보와 사용자 확인 상태는 보존된다.
    """

    events, resolved_times = data.draw(
        _recognized_event_inputs(),
        label="events",
    )
    permuted_events = data.draw(
        st.permutations(events),
        label="input_permutation",
    )

    projection = build_timeline(permuted_events)
    expected_ordered, expected_unknown = _reference_partitions(events)

    assert projection.ordered == expected_ordered
    assert projection.unknown_time == expected_unknown

    output_events = projection.ordered + projection.unknown_time
    input_ids = [event.id for event in events]
    output_ids = [event.id for event in output_events]
    assert Counter(output_ids) == Counter(input_ids)
    assert len(output_ids) == len(set(output_ids))
    assert set(event.id for event in projection.ordered).isdisjoint(
        event.id for event in projection.unknown_time
    )

    expected_resolved_by_id = {
        event.id: resolved
        for event, resolved in zip(events, resolved_times)
    }
    for event in projection.ordered:
        assert expected_resolved_by_id[event.id] == event.resolved_sort_time
        if event.relative_time is not None:
            assert event.relative_time.anchor_event_id is not None
            assert event.relative_time.offset_seconds is not None
    for event in projection.unknown_time:
        assert event.resolved_sort_time is None
        assert event.original_text

    original_by_id = {event.id: event for event in events}
    for event in output_events:
        original = original_by_id[event.id]
        assert event.ambiguity == original.ambiguity
        if event.ambiguity is not None:
            assert (
                event.ambiguity.alternatives
                == original.ambiguity.alternatives
            )
            assert event.ambiguity.requires_user_confirmation is True
