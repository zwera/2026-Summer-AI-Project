"""결정적 타임라인 구성·수정과 쟁점 projection (task 13.2).

``design.md`` "핵심 포트와 함수 시그니처"의 다음 계약을 구현한다::

    function buildTimeline(
      events: readonly RecognizedEvent[]
    ): TimelineProjection;

    function updateTimelineEvent(
      state: TimelineState,
      command: UpdateEventCommand
    ): TimelineState;

그리고 "4.8 타임라인과 보고서" 절의 규칙을 구현한다.

1. 명시 시각 이벤트를 ISO 시각 오름차순으로 정렬한다.
2. 기준 이벤트가 유효한 상대 시각은 fixture의 해석된 정렬 키를 사용한다.
3. 같은 시각은 ``originalOrder``를 유지한다.
4. 시점 미상 이벤트는 원문과 함께 별도 영역에서 원래 순서로 둔다.
5. 복수 시간/주체 해석은 후보를 보존하고 `사용자 확인 필요`로 둔다.
6. 이벤트 수정은 불변 업데이트로 timeline과 report selector에 동시에 반영한다.

## 이 태스크(13.2)의 범위와 :func:`build_timeline`의 정렬 키

design.md 4.8절 2번 규칙("기준 이벤트가 유효한 상대 시각은 fixture의 해석된 정렬 키를
사용한다")은 상대 시각 anchor 해석(체인 순회, 오프셋 누적) 자체를 이 함수의 책임으로 두지
않는다. ``data.models_timeline.RecognizedEvent.resolved_sort_time``이 이미 그 "해석된
정렬 키"다 — 명시 시각이든 유효하게 해석된 상대 시각이든, 정렬 가능한 이벤트는 fixture가
이미 계산해 둔 ``resolved_sort_time``(ISO 날짜/시간 문자열)을 갖는다. 따라서
:func:`build_timeline`은:

- ``resolved_sort_time is not None``인 이벤트만 ``ordered``에 넣고
  ``(resolved_sort_time, original_order)`` 오름차순으로 정렬한다. 두 번째 키
  ``original_order``는 요구사항 11.7("동일한 시점을 가지면 ... 사용자 설명에 나타난 행위
  순서를 유지한다")을 입력 배열의 나열 순서와 무관하게(입력이 어떤 순서로 주어지든) 항상
  같은 결과로 강제한다.
- ``resolved_sort_time is None``인 이벤트는 시점을 판단할 수 없는 것으로 보아
  ``unknown_time``에 넣고 ``original_order`` 오름차순으로만 정렬한다(요구사항 11.8, 원문과
  함께 별도 영역에서 원래 순서 유지).
- 두 영역은 서로소이며(``resolved_sort_time``의 유무로 배타적으로 나뉨) 합집합에는 입력의
  각 이벤트가 정확히 한 번 나타난다(요구사항 11.9, Property 33 exact-once partition).
- ``ambiguity``(``EventAmbiguity``, 요구사항 11.12)는 그룹 배정과 무관하게 이벤트 필드
  그대로 통과시킨다 — 모호 이벤트도 (그 ``resolved_sort_time``이 있으면) 정상적으로
  ``ordered``에, 없으면 ``unknown_time``에 들어가되 후보와 `사용자 확인 필요` 표시는
  ``RecognizedEvent.ambiguity`` 필드 자체에 그대로 보존된다. 이 함수는 그 필드를 지우거나
  새로 만들지 않는다.

## :func:`update_timeline_event`와 "timeline·report selector에 동시 반영"

design.md는 이벤트 수정을 "불변 업데이트로 timeline과 report selector에 동시에 반영한다"고
서술한다. 이 모듈은 :class:`TimelineState`를 이벤트 튜플의 불변 컨테이너로 두고,
:attr:`TimelineState.projection`을 **저장하지 않는 selector**(호출마다
:func:`build_timeline`을 다시 실행하는 property)로 둔다. 따라서
:func:`update_timeline_event`가 반환한 새 ``TimelineState``에서 ``.projection``을
읽거나, task 13.3의 ``buildReportFacts``가 그 최신 ``TimelineState``를 입력으로
받으면, 두 selector 모두 자동으로 같은 수정값을
반영한다 — 별도의 캐시된 projection이나 report 사본을 이 모듈이 직접 갱신할 필요가 없다
(요구사항 11.13, Property 35). ``buildReportFacts`` 자체의 구현은 task 13.3의 책임이다.

``UpdateEventCommand``의 각 필드는 ``None``이면 "변경 없음"을 뜻한다(design.md가 이
명령의 필드를 구체적으로 명세하지 않으므로, 이 모듈은 요구사항 11.13이 요구하는 "시간
또는 내용"의 최소 편집 표면 — 시간(``explicit_time``), 행위(``action``), 주체(``actor``),
원문(``original_text``) — 만 옮긴다). ``explicit_time``이 주어지면 그 값을
``resolved_sort_time``에도 그대로 반영한다 — 사용자가 명시 시각을 입력하면 그 값이 곧
"해석된 정렬 키"이므로 별도 anchor 해석이 필요 없고, 이는 "시점 미상 → 명시 시각" 편집이
:func:`build_timeline`의 그룹 배정에 즉시 반영되게 한다(design.md 4.8절 2번 규칙, Property
35 경계 사례).

## 쟁점 또는 `연결 쟁점 없음` (요구사항 11.10, 11.11, Property 34)

:func:`project_event_issues`는 ``RecognizedEvent.issue_links``가 비어 있으면 정확히 하나의
`연결 쟁점 없음` 표시를, 비어 있지 않으면 각 ``IssueLink``(쟁점과 사전 연결된 판례·법조문
``sourceIds``)를 누락 없이 그대로 옮긴다. 새 출처를 만들거나 필터링하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Sequence, Tuple

from domain.ids import EventId

from data.models_common import IsoDateTime
from data.models_timeline import IssueLink, RecognizedEvent, TimelineProjection

__all__ = [
    "NO_ISSUE_LINKED_LABEL",
    "build_timeline",
    "EventIssueProjection",
    "project_event_issues",
    "UpdateEventCommand",
    "TimelineState",
    "UnknownEventIdError",
    "update_timeline_event",
]


NO_ISSUE_LINKED_LABEL = "연결 쟁점 없음"
"""요구사항 11.10의 고정 문구. ``RecognizedEvent.issue_links``가 비어 있을 때 표시한다."""


def build_timeline(events: Sequence[RecognizedEvent]) -> TimelineProjection:
    """``events``를 결정적으로 정렬·partition해 :class:`TimelineProjection`을 만든다.

    ``resolved_sort_time``이 있는 이벤트는
    ``(resolved_sort_time, original_order)`` 오름차순으로 ``ordered``에, 없는
    이벤트는 ``original_order`` 오름차순으로 ``unknown_time``에 배치한다. 두
    영역의 합집합에는 입력의 각 이벤트가 정확히 한 번 존재한다(요구사항
    11.5~11.9, Property 33). 입력 리스트의 순서와 무관하게 항상 같은 결과를
    낸다.
    """

    ordered_events = tuple(
        sorted(
            (
                event
                for event in events
                if event.resolved_sort_time is not None
            ),
            key=lambda event: (event.resolved_sort_time, event.original_order),
        )
    )
    unknown_events = tuple(
        sorted(
            (event for event in events if event.resolved_sort_time is None),
            key=lambda event: event.original_order,
        )
    )
    return TimelineProjection(
        ordered=ordered_events, unknown_time=unknown_events
    )


@dataclass(frozen=True)
class EventIssueProjection:
    """인식_사건 하나의 쟁점 표시 projection. 요구사항 11.10, 11.11.

    ``issues``가 비어 있지 않으면 ``no_issue_label``은 ``None``이고, 비어 있으면
    ``issues``도 빈 튜플이며 ``no_issue_label``이 :data:`NO_ISSUE_LINKED_LABEL`이다. 두
    상태가 동시에 나타나지 않는다.
    """

    event_id: EventId
    issues: Tuple[IssueLink, ...]
    no_issue_label: Optional[str]


def project_event_issues(event: RecognizedEvent) -> EventIssueProjection:
    """``event.issue_links``를 그대로 옮기거나(비어 있지 않으면) `연결 쟁점 없음`으로
    바꾼다(비어 있으면). 쟁점에 사전 연결된 ``sourceIds``는 누락·필터링 없이 그대로
    보존한다(요구사항 11.11, Property 34).
    """

    if event.issue_links:
        return EventIssueProjection(
            event_id=event.id, issues=event.issue_links, no_issue_label=None
        )
    return EventIssueProjection(
        event_id=event.id, issues=(), no_issue_label=NO_ISSUE_LINKED_LABEL
    )


@dataclass(frozen=True)
class UpdateEventCommand:
    """인식_사건 수정 명령. design.md ``UpdateEventCommand``(요구사항 11.13).

    각 필드는 ``None``이면 "변경 없음"을 뜻한다. ``explicit_time``이 주어지면
    ``resolved_sort_time``도 같은 값으로 갱신된다(모듈 docstring 참조).
    """

    event_id: EventId
    action: Optional[str] = None
    actor: Optional[str] = None
    original_text: Optional[str] = None
    explicit_time: Optional[IsoDateTime] = None


class UnknownEventIdError(ValueError):
    """``command.event_id``가 ``state.events``에 존재하지 않을 때 발생한다.

    존재하지 않는 이벤트를 조용히 무시하거나 새로 만들지 않고 명시적으로 안전 실패한다
    (Property 35 경계 사례 "존재하지 않는 ID는 오류").
    """


@dataclass(frozen=True)
class TimelineState:
    """현재 사실관계_타임라인의 인식_사건 전체. design.md ``TimelineState``.

    ``projection``은 저장된 캐시가 아니라 매 호출마다 :func:`build_timeline`을 다시 실행하는
    selector다 — 이벤트가 수정된 뒤에도 별도 동기화 없이 항상 최신 ``events``를 반영한다
    (모듈 docstring "timeline·report selector에 동시 반영" 참조).
    """

    events: Tuple[RecognizedEvent, ...]

    @property
    def projection(self) -> TimelineProjection:
        return build_timeline(self.events)


def update_timeline_event(
    state: TimelineState, command: UpdateEventCommand
) -> TimelineState:
    """``command.event_id``가 가리키는 이벤트만 불변 업데이트로 교체한 새 ``TimelineState``를
    반환한다.

    ``command``에서 ``None``이 아닌 필드만 해당 이벤트에 교체 반영하고, 다른 이벤트는
    그대로 유지한다(요구사항 11.13, Property 35). ``event_id``가 존재하지 않으면
    :class:`UnknownEventIdError`를 발생시킨다.
    """

    updated_events = []
    found = False
    for event in state.events:
        if event.id != command.event_id:
            updated_events.append(event)
            continue
        found = True
        changes: dict = {}
        if command.action is not None:
            changes["action"] = command.action
        if command.actor is not None:
            changes["actor"] = command.actor
        if command.original_text is not None:
            changes["original_text"] = command.original_text
        if command.explicit_time is not None:
            changes["explicit_time"] = command.explicit_time
            changes["resolved_sort_time"] = command.explicit_time
        updated_events.append(replace(event, **changes) if changes else event)

    if not found:
        raise UnknownEventIdError(
            f"존재하지 않는 event_id에 대한 수정 요청: {command.event_id!r}"
        )

    return TimelineState(events=tuple(updated_events))
