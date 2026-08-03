"""보고서용 사실관계 생성 selector (task 13.3).

``build_report_facts``는 현재 타임라인 projection을 보고서용 문서로 결정적으로
변환한다. 타임라인의 정렬된 사건을 먼저, 시점 미상 사건을 그 다음에 한 번씩만
사용하고, 본문 끝에 데이터 기준일과 법률 안전 고지문을 붙인다. 외부 I/O, 현재
시각, 또는 법률 내용의 합성은 수행하지 않는다.
"""

from __future__ import annotations

from typing import Protocol, Tuple

from domain.ids import EventId

from data.models_common import IsoDate
from data.models_timeline import (
    RecognizedEvent,
    ReportDocument,
    TimelineProjection,
)

__all__ = ["build_report_facts", "buildReportFacts"]


class _ReportMetadata(Protocol):
    """보고서 생성에 필요한 데이터셋 메타데이터의 최소 계약."""

    as_of_date: IsoDate


def _timeline_events(
    timeline: TimelineProjection,
) -> Tuple[RecognizedEvent, ...]:
    """보고서에 사용할 화면 타임라인 순서를 반환한다.

    ``TimelineProjection``은 이미 각 partition 안에서 결정적으로 정렬되어 있다.
    화면 흐름과 동일하게 정렬된 사건을 먼저, 시점 미상 사건을 뒤에 둔다.
    """

    return timeline.ordered + timeline.unknown_time


def build_report_facts(
    timeline: TimelineProjection,
    meta: _ReportMetadata,
    notice: str,
) -> ReportDocument:
    """타임라인을 재사용 가능한 보고서용 사실관계로 만든다.

    각 이벤트 ID와 원문을 타임라인 표시 순서대로 정확히 한 줄에 한 번 포함한다.
    마지막 두 줄은 각각 데이터 기준일과 제공받은 법률 안전 고지문이다. 이 함수는
    전달된 사건을 변경하거나 새로운 사실·법률 판단을 만들지 않는다.

    Requirements: 11.14, 15.7.
    """

    events = _timeline_events(timeline)
    event_ids: Tuple[EventId, ...] = tuple(event.id for event in events)
    event_lines = tuple(
        f"[{event.id}] {event.original_text}" for event in events
    )
    body_lines = event_lines + (
        f"데이터 기준일: {meta.as_of_date}",
        notice,
    )

    return ReportDocument(
        event_ids=event_ids,
        body="\n".join(body_lines),
        as_of_date=meta.as_of_date,
        safety_notice=notice,
    )


# The design document uses this camelCase contract name. Keep it as a
# compatibility alias while Python callers use ``build_report_facts``.
buildReportFacts = build_report_facts
