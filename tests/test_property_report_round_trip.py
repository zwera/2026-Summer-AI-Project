"""Property 36: 보고서의 타임라인 순서 round-trip과 필수 고지 (task 13.8).

유효한 화면 타임라인의 정렬 영역과 시점 미상 영역을 독립적으로 생성한다.
보고서 selector는 두 영역을 화면 표시 순서대로 연결해 각 사건을 정확히 한 번
재사용하고, 데이터 기준일 및 법률 안전 고지문을 본문 끝에 보존해야 한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_timeline import RecognizedEvent, TimelineProjection
from domain.ids import EventId
from domain.report import build_report_facts


@dataclass(frozen=True)
class _Metadata:
    """보고서 selector가 요구하는 최소 데이터 기준일 계약."""

    as_of_date: str


_SAFE_TEXT = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters=("\x00",),
    ),
    min_size=0,
    max_size=80,
)


@st.composite
def _timeline_and_expected_events(
    draw: st.DrawFn,
) -> Tuple[TimelineProjection, Tuple[RecognizedEvent, ...]]:
    """화면의 ordered/unknown 영역과 기대 보고서 순서를 함께 생성한다."""

    event_count = draw(st.integers(min_value=0, max_value=20))
    ids = draw(
        st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
                min_size=1,
                max_size=16,
            ),
            min_size=event_count,
            max_size=event_count,
            unique=True,
        )
    )
    texts = draw(
        st.lists(_SAFE_TEXT, min_size=event_count, max_size=event_count)
    )
    ordered_count = draw(st.integers(min_value=0, max_value=event_count))

    events = tuple(
        RecognizedEvent(
            id=EventId(event_id),
            original_text=text,
            action="사건 행위",
            original_order=index,
            resolved_sort_time=(
                f"2024-01-01T00:{index:02d}:00"
                if index < ordered_count
                else None
            ),
        )
        for index, (event_id, text) in enumerate(zip(ids, texts))
    )
    return (
        TimelineProjection(
            ordered=events[:ordered_count],
            unknown_time=events[ordered_count:],
        ),
        events,
    )


# Feature: police-case-law-ai-bot, Property 36:
# 보고서의 타임라인 순서 round-trip과 필수 고지
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(
    timeline_and_events=_timeline_and_expected_events(),
    as_of_date=st.dates().map(str),
    safety_notice=st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters=("\x00",),
        ),
        min_size=1,
        max_size=160,
    ),
)
def test_report_round_trip_preserves_order_and_notices(
    timeline_and_events: Tuple[
        TimelineProjection, Tuple[RecognizedEvent, ...]
    ],
    as_of_date: str,
    safety_notice: str,
) -> None:
    """**Validates: Requirements 11.12, 11.13**

    ``event_ids`` and event-body portions preserve the complete screen timeline
    order exactly once; serialized report content retains the supplied as-of date
    and unchanged legal-safety notice for clipboard/download consumers.
    """

    timeline, expected_events = timeline_and_events
    report = build_report_facts(
        timeline, _Metadata(as_of_date), safety_notice
    )

    expected_event_ids = tuple(event.id for event in expected_events)
    expected_event_lines = tuple(
        f"[{event.id}] {event.original_text}" for event in expected_events
    )
    expected_body = "\n".join(
        expected_event_lines
        + (f"데이터 기준일: {as_of_date}", safety_notice)
    )

    assert report.event_ids == expected_event_ids
    assert len(report.event_ids) == len(set(report.event_ids))
    assert report.body == expected_body
    assert report.as_of_date == as_of_date
    assert report.safety_notice == safety_notice
    required_suffix = f"데이터 기준일: {as_of_date}\n{safety_notice}"
    assert report.body.endswith(required_suffix)
