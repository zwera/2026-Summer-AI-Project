"""사실관계 타임라인과 보고서 데이터 모델.

``design.md`` Data Models 11절의 ``VoiceFixture``, ``RecognizedEvent``, ``RelativeTime``,
``EventAmbiguity``, ``IssueLink``, ``TimelineProjection``, ``ReportDocument``를 정의한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Tuple

from domain.ids import EventId, QueryId, SourceId

from data.models_common import IsoDate, IsoDateTime, VoiceFixtureId


@dataclass(frozen=True)
class VoiceFixture:
    """사전_정의_음성_시연 항목. design.md Data Models 11절 ``VoiceFixture``.

    ``failure=True``이면 인식 텍스트가 없다는 뜻이며, ``LocalVoiceDemoPort``는 이 경우
    INPUT 단계를 유지하고 매칭 없이 수동 텍스트 입력 가능 상태를 유지한다(요구사항 11.18~11.20).
    """

    id: VoiceFixtureId
    label: str
    failure: bool
    recognized_text: Optional[str] = None
    query_id: Optional[QueryId] = None


@dataclass(frozen=True)
class RelativeTime:
    """상대적 시간 표현. design.md Data Models 11절 ``RelativeTime``."""

    expression: str
    anchor_event_id: Optional[EventId] = None
    offset_seconds: Optional[float] = None


@dataclass(frozen=True)
class EventAmbiguity:
    """복수 해석 가능한 시간/주체 정보. design.md Data Models 11절 ``EventAmbiguity``."""

    kind: Literal["TIME", "ACTOR", "BOTH"]
    alternatives: Tuple[str, ...]
    requires_user_confirmation: Literal[True] = True


@dataclass(frozen=True)
class IssueLink:
    """인식_사건과 판례_쟁점의 연결. design.md Data Models 11절 ``IssueLink``."""

    issue: str
    source_ids: Tuple[SourceId, ...]


@dataclass(frozen=True)
class RecognizedEvent:
    """사실관계_타임라인에 정확히 한 번 배치되는 개별 행위/사건. design.md ``RecognizedEvent``."""

    id: EventId
    original_text: str
    action: str
    original_order: int
    actor: Optional[str] = None
    explicit_time: Optional[IsoDateTime] = None
    relative_time: Optional[RelativeTime] = None
    resolved_sort_time: Optional[IsoDateTime] = None
    ambiguity: Optional[EventAmbiguity] = None
    issue_links: Tuple[IssueLink, ...] = ()


@dataclass(frozen=True)
class TimelineProjection:
    """정렬된 타임라인 projection. design.md Data Models 11절 ``TimelineProjection``.

    ``ordered``와 ``unknown_time``의 합집합에는 각 사건 ID가 정확히 한 번 있어야 한다
    (Property 33).
    """

    ordered: Tuple[RecognizedEvent, ...]
    unknown_time: Tuple[RecognizedEvent, ...]


@dataclass(frozen=True)
class ReportDocument:
    """보고서용_사실관계 문서. design.md Data Models 11절 ``ReportDocument``."""

    event_ids: Tuple[EventId, ...]
    body: str
    as_of_date: IsoDate
    safety_notice: str
