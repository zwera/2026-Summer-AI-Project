"""Application command reducer, error snapshots, and local-export effects (task 15.2).

The reducer coordinates UI state only.  It never recalculates legal values, performs
clipboard/download I/O, or mutates fixture projections.  Case/report display values
remain selector-derived from immutable state and validated fixture projections.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Optional, Tuple, Union

from domain.enums import PoliceScenario, SummaryLevel, TraditionalCaseArea
from domain.ids import CaseId, ClaimId, SourceId
from domain.report import build_report_facts
from domain.timeline import TimelineState, UpdateEventCommand, update_timeline_event

from app.mock_rag_state import (
    MockRagState,
    RagStageError,
    advance_stage,
    fail_stage,
    initial_rag_state,
    reset_to_input,
    retry_stage,
)
from data.models_common import SourceAnchorId
from data.models_timeline import ReportDocument

__all__ = [
    "AppState", "ErrorSnapshot", "SelectionReviewState", "SourceNavigationRequest",
    "AppCommand", "AppEffect", "CopyReport", "DownloadReport", "initial_app_state",
    "app_reducer", "selected_case", "current_report",
]


@dataclass(frozen=True)
class ErrorSnapshot:
    """The exact user state retained when a mock-RAG stage fails."""

    raw_query: str
    selected_case_id: Optional[CaseId]
    summary_level: SummaryLevel
    auxiliary_filter: Optional[TraditionalCaseArea]
    selected_text: str


@dataclass(frozen=True)
class SelectionReviewState:
    selected_claim_ids: Tuple[ClaimId, ...] = ()
    selected_text: str = ""


@dataclass(frozen=True)
class SourceNavigationRequest:
    source_id: SourceId
    anchor_id: SourceAnchorId
    from_element_id: str = ""


@dataclass(frozen=True)
class AppState:
    """Immutable application state; legal projections are intentionally not copied here."""

    raw_query: str
    rag: MockRagState
    route: str = "QUERY"
    selected_case_id: Optional[CaseId] = None
    summary_level: SummaryLevel = SummaryLevel.THREE_LINE
    auxiliary_filter: Optional[TraditionalCaseArea] = None
    selected_scenario: Optional[PoliceScenario] = None
    expanded_source: Optional[SourceNavigationRequest] = None
    selection_review: SelectionReviewState = SelectionReviewState()
    timeline: Optional[TimelineState] = None
    report: Optional[ReportDocument] = None
    before_error: Optional[ErrorSnapshot] = None


@dataclass(frozen=True)
class CopyReport:
    """UI-boundary request to copy the already-generated report text locally."""

    text: str


@dataclass(frozen=True)
class DownloadReport:
    """UI-boundary request to download the already-generated report as UTF-8 text."""

    filename: str
    text: str


AppEffect = Union[CopyReport, DownloadReport]


@dataclass(frozen=True)
class SubmitQuery:
    raw: str


@dataclass(frozen=True)
class AdvanceRag:
    pass


@dataclass(frozen=True)
class RetryRag:
    pass


@dataclass(frozen=True)
class FailStage:
    error: RagStageError


@dataclass(frozen=True)
class ResetInput:
    pass


@dataclass(frozen=True)
class SelectScenario:
    scenario: PoliceScenario


@dataclass(frozen=True)
class SetAuxiliaryFilter:
    area: Optional[TraditionalCaseArea]


@dataclass(frozen=True)
class SelectCase:
    case_id: CaseId


@dataclass(frozen=True)
class SetSummaryLevel:
    level: SummaryLevel


@dataclass(frozen=True)
class ToggleSource:
    request: SourceNavigationRequest


@dataclass(frozen=True)
class ReturnFromSource:
    pass


@dataclass(frozen=True)
class SelectClaims:
    claim_ids: Tuple[ClaimId, ...]
    text: str


@dataclass(frozen=True)
class UpdateTimelineEvent:
    update: UpdateEventCommand


@dataclass(frozen=True)
class GenerateReport:
    pass


@dataclass(frozen=True)
class RequestCopyReport:
    pass


@dataclass(frozen=True)
class RequestDownloadReport:
    filename: str = "report-facts.txt"


AppCommand = Union[SubmitQuery, AdvanceRag, RetryRag, FailStage, ResetInput,
                   SelectScenario, SetAuxiliaryFilter, SelectCase, SetSummaryLevel,
                   ToggleSource, ReturnFromSource, SelectClaims, UpdateTimelineEvent,
                   GenerateReport, RequestCopyReport, RequestDownloadReport]


def initial_app_state(timeline: Optional[TimelineState] = None) -> AppState:
    return AppState(raw_query="", rag=initial_rag_state(), timeline=timeline)


def _snapshot(state: AppState) -> ErrorSnapshot:
    return ErrorSnapshot(
        raw_query=state.raw_query,
        selected_case_id=state.selected_case_id,
        summary_level=state.summary_level,
        auxiliary_filter=state.auxiliary_filter,
        selected_text=state.selection_review.selected_text,
    )


def app_reducer(
    state: AppState,
    command: AppCommand,
    *,
    report_meta: object = None,
    legal_safety_notice: Optional[str] = None,
) -> Tuple[AppState, Tuple[AppEffect, ...]]:
    """Apply one command and return immutable state plus deferred local-I/O effects.

    ``GenerateReport`` requires both report metadata and fixture safety notice; absent
    dependencies preserve state rather than synthesizing report/legal content.
    """
    if isinstance(command, SubmitQuery):
        return replace(state, raw_query=command.raw, rag=reset_to_input(state.rag),
                       route="QUERY", before_error=None, report=None), ()
    if isinstance(command, AdvanceRag):
        return replace(state, rag=advance_stage(state.rag)), ()
    if isinstance(command, FailStage):
        rag = fail_stage(state.rag, command.error)
        return (replace(state, rag=rag, before_error=_snapshot(state)) if rag != state.rag else state), ()
    if isinstance(command, RetryRag):
        rag = retry_stage(state.rag)
        return replace(state, rag=rag), ()
    if isinstance(command, ResetInput):
        return replace(state, raw_query="", rag=reset_to_input(state.rag), route="QUERY",
                       selected_case_id=None, expanded_source=None, selection_review=SelectionReviewState(),
                       report=None, before_error=None), ()
    if isinstance(command, SelectScenario):
        return replace(state, selected_scenario=command.scenario, route="SCENARIOS"), ()
    if isinstance(command, SetAuxiliaryFilter):
        return replace(state, auxiliary_filter=command.area), ()
    if isinstance(command, SelectCase):
        return replace(state, selected_case_id=command.case_id, route="CASE_DETAIL"), ()
    if isinstance(command, SetSummaryLevel):
        return replace(state, summary_level=command.level), ()
    if isinstance(command, ToggleSource):
        return replace(state, expanded_source=command.request), ()
    if isinstance(command, ReturnFromSource):
        return replace(state, expanded_source=None), ()
    if isinstance(command, SelectClaims):
        return replace(state, selection_review=SelectionReviewState(command.claim_ids, command.text)), ()
    if isinstance(command, UpdateTimelineEvent):
        if state.timeline is None:
            return state, ()
        return replace(state, timeline=update_timeline_event(state.timeline, command.update), report=None), ()
    if isinstance(command, GenerateReport):
        if state.timeline is None or report_meta is None or legal_safety_notice is None:
            return state, ()
        return replace(state, report=build_report_facts(state.timeline.projection, report_meta, legal_safety_notice), route="TIMELINE"), ()
    if isinstance(command, RequestCopyReport):
        return (state, (CopyReport(state.report.body),)) if state.report is not None else (state, ())
    if isinstance(command, RequestDownloadReport):
        return (state, (DownloadReport(command.filename, state.report.body),)) if state.report is not None else (state, ())
    return state, ()


def selected_case(state: AppState, cases_by_id: Mapping[CaseId, object]) -> Optional[object]:
    """Resolve the canonical case projection on demand without copying it into state."""
    return cases_by_id.get(state.selected_case_id) if state.selected_case_id is not None else None


def current_report(state: AppState) -> Optional[ReportDocument]:
    """Selector for the already fixture-derived report document."""
    return state.report
