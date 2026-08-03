"""``domain.timeline`` 단위 테스트 (task 13.2).

요구사항 11.4~11.13을 검증한다.

- ``build_timeline``이 명시/해결 시각 이벤트를 오름차순으로, 동률은 원래 순서로,
  시점 미상 이벤트는 별도 영역에서 원래 순서로 배치하고, 두 영역이 exact-once
  partition을 이루는지(11.5~11.9).
- 모호성(``ambiguity``)이 그대로 보존되는지(11.12).
- ``project_event_issues``가 쟁점 유무에 따라 `연결 쟁점 없음` 또는 쟁점·출처를
  그대로 옮기는지(11.10, 11.11).
- ``update_timeline_event``가 대상 이벤트만 불변 교체하고 나머지는 그대로 두며,
  존재하지 않는 ID에는 안전하게 실패하는지(11.13).
"""

from __future__ import annotations

import pytest

from domain.ids import EventId, SourceId
from domain.timeline import (
    NO_ISSUE_LINKED_LABEL,
    TimelineState,
    UnknownEventIdError,
    UpdateEventCommand,
    build_timeline,
    project_event_issues,
    update_timeline_event,
)
from data.models_timeline import EventAmbiguity, IssueLink, RecognizedEvent


def _event(
    id_: str,
    original_order: int,
    resolved_sort_time=None,
    action: str = "행위",
    ambiguity=None,
    issue_links=(),
) -> RecognizedEvent:
    return RecognizedEvent(
        id=EventId(id_),
        original_text=f"{id_} 원문",
        action=action,
        original_order=original_order,
        resolved_sort_time=resolved_sort_time,
        ambiguity=ambiguity,
        issue_links=issue_links,
    )


class TestBuildTimeline:
    def test_explicit_time_events_sorted_ascending(self) -> None:
        e1 = _event("e1", 0, resolved_sort_time="2024-01-01T02:11:00")
        e2 = _event("e2", 1, resolved_sort_time="2024-01-01T02:10:00")

        projection = build_timeline([e1, e2])

        assert [e.id for e in projection.ordered] == ["e2", "e1"]
        assert projection.unknown_time == ()

    def test_tied_time_preserves_original_order(self) -> None:
        same_time = "2024-01-01T02:10:00"
        e1 = _event("e1", 2, resolved_sort_time=same_time)
        e2 = _event("e2", 0, resolved_sort_time=same_time)
        e3 = _event("e3", 1, resolved_sort_time=same_time)

        projection = build_timeline([e1, e2, e3])

        assert [e.id for e in projection.ordered] == ["e2", "e3", "e1"]

    def test_unknown_time_events_kept_separate_by_original_order(
        self,
    ) -> None:
        known = _event(
            "known", 0, resolved_sort_time="2024-01-01T00:00:00"
        )
        unknown_a = _event("unknown-a", 3)
        unknown_b = _event("unknown-b", 1)

        projection = build_timeline([known, unknown_a, unknown_b])

        assert [e.id for e in projection.ordered] == ["known"]
        assert [e.id for e in projection.unknown_time] == [
            "unknown-b",
            "unknown-a",
        ]

    def test_two_areas_are_exact_once_partition_any_input_order(
        self,
    ) -> None:
        events = [
            _event("a", 0, resolved_sort_time="2024-01-01T01:00:00"),
            _event("b", 1),
            _event("c", 2, resolved_sort_time="2024-01-01T00:00:00"),
            _event("d", 3),
        ]

        projection = build_timeline(events)
        all_ids = [e.id for e in projection.ordered] + [
            e.id for e in projection.unknown_time
        ]

        assert sorted(all_ids) == sorted(e.id for e in events)
        assert len(all_ids) == len(set(all_ids)) == 4

    def test_input_permutation_does_not_change_result(self) -> None:
        events = [
            _event("a", 0, resolved_sort_time="2024-01-01T01:00:00"),
            _event("b", 1),
            _event("c", 2, resolved_sort_time="2024-01-01T00:00:00"),
        ]

        forward = build_timeline(events)
        backward = build_timeline(list(reversed(events)))

        assert forward.ordered == backward.ordered
        assert forward.unknown_time == backward.unknown_time

    def test_all_unknown_time_yields_empty_ordered(self) -> None:
        events = [_event("a", 1), _event("b", 0)]

        projection = build_timeline(events)

        assert projection.ordered == ()
        assert [e.id for e in projection.unknown_time] == ["b", "a"]

    def test_empty_input_returns_empty_partitions(self) -> None:
        projection = build_timeline([])

        assert projection.ordered == ()
        assert projection.unknown_time == ()

    def test_ambiguity_is_preserved_unchanged(self) -> None:
        ambiguity = EventAmbiguity(
            kind="TIME", alternatives=("02:10", "14:10")
        )
        event = _event(
            "ambiguous",
            0,
            resolved_sort_time="2024-01-01T02:10:00",
            ambiguity=ambiguity,
        )

        projection = build_timeline([event])

        assert projection.ordered[0].ambiguity is ambiguity
        assert (
            projection.ordered[0].ambiguity.requires_user_confirmation
            is True
        )


class TestProjectEventIssues:
    def test_empty_issue_links_yields_no_issue_linked_label(self) -> None:
        event = _event("e1", 0, issue_links=())

        projection = project_event_issues(event)

        assert projection.issues == ()
        assert projection.no_issue_label == NO_ISSUE_LINKED_LABEL

    def test_nonempty_issue_links_passed_through_with_sources(
        self,
    ) -> None:
        link = IssueLink(
            issue="영장주의 예외",
            source_ids=(SourceId("source-1"), SourceId("source-2")),
        )
        event = _event("e1", 0, issue_links=(link,))

        projection = project_event_issues(event)

        assert projection.issues == (link,)
        assert projection.no_issue_label is None

    def test_multiple_issues_all_preserved(self) -> None:
        link_a = IssueLink(issue="현행범 요건", source_ids=(SourceId("s-a"),))
        link_b = IssueLink(issue="영장주의 예외", source_ids=(SourceId("s-b"),))
        event = _event("e1", 0, issue_links=(link_a, link_b))

        projection = project_event_issues(event)

        assert projection.issues == (link_a, link_b)
        assert projection.no_issue_label is None


class TestUpdateTimelineEvent:
    def test_updates_only_target_event_action(self) -> None:
        e1 = _event("e1", 0, action="원래 행위")
        e2 = _event("e2", 1, action="다른 행위")
        state = TimelineState(events=(e1, e2))

        new_state = update_timeline_event(
            state,
            UpdateEventCommand(event_id=EventId("e1"), action="수정된 행위"),
        )

        assert new_state.events[0].action == "수정된 행위"
        assert new_state.events[1] is e2

    def test_original_state_is_not_mutated(self) -> None:
        e1 = _event("e1", 0, action="원래 행위")
        state = TimelineState(events=(e1,))

        update_timeline_event(
            state,
            UpdateEventCommand(event_id=EventId("e1"), action="수정된 행위"),
        )

        assert state.events[0].action == "원래 행위"

    def test_explicit_time_update_also_updates_resolved_sort_time(
        self,
    ) -> None:
        e1 = _event("e1", 0, resolved_sort_time="2024-01-01T00:00:00")
        state = TimelineState(events=(e1,))

        new_state = update_timeline_event(
            state,
            UpdateEventCommand(
                event_id=EventId("e1"),
                explicit_time="2024-01-01T05:00:00",
            ),
        )

        assert new_state.events[0].explicit_time == "2024-01-01T05:00:00"
        assert (
            new_state.events[0].resolved_sort_time
            == "2024-01-01T05:00:00"
        )

    def test_unknown_time_event_becomes_known_and_reflected(self) -> None:
        e1 = _event("e1", 0)  # 시점 미상
        state = TimelineState(events=(e1,))
        assert state.projection.unknown_time == (e1,)

        new_state = update_timeline_event(
            state,
            UpdateEventCommand(
                event_id=EventId("e1"),
                explicit_time="2024-01-01T00:00:00",
            ),
        )

        assert new_state.projection.unknown_time == ()
        assert [e.id for e in new_state.projection.ordered] == ["e1"]

    def test_report_facing_projection_reflects_update_immediately(
        self,
    ) -> None:
        e1 = _event(
            "e1",
            0,
            action="원래 행위",
            resolved_sort_time="2024-01-01T00:00:00",
        )
        state = TimelineState(events=(e1,))

        new_state = update_timeline_event(
            state,
            UpdateEventCommand(event_id=EventId("e1"), action="수정된 행위"),
        )

        assert new_state.projection.ordered[0].action == "수정된 행위"

    def test_unknown_event_id_raises(self) -> None:
        state = TimelineState(events=(_event("e1", 0),))

        with pytest.raises(UnknownEventIdError):
            update_timeline_event(
                state,
                UpdateEventCommand(
                    event_id=EventId("does-not-exist"), action="x"
                ),
            )

    def test_no_fields_provided_leaves_event_unchanged(self) -> None:
        e1 = _event("e1", 0, action="원래 행위")
        state = TimelineState(events=(e1,))

        new_state = update_timeline_event(
            state, UpdateEventCommand(event_id=EventId("e1"))
        )

        assert new_state.events[0] == e1
