"""Unit coverage for task 15.2 application command reducer."""
from __future__ import annotations

from app.app_reducer import (
    CopyReport, FailStage, RequestCopyReport, RequestDownloadReport, ReturnFromSource,
    SelectCase, SelectClaims, SetAuxiliaryFilter, SetSummaryLevel, SourceNavigationRequest,
    ToggleSource, app_reducer, initial_app_state, selected_case,
)
from app.mock_rag_state import RagStageError, advance_stage
from domain.enums import RagStage, SummaryLevel, TraditionalCaseArea
from domain.ids import CaseId, SourceId
from data.models_common import SourceAnchorId
from data.models_timeline import ReportDocument


def test_failure_preserves_complete_error_snapshot_and_marks_stage_failed() -> None:
    case_id = CaseId("case-1")
    source = SourceNavigationRequest(SourceId("source-1"), SourceAnchorId("anchor-1"))
    state = initial_app_state()
    for command in (
        SelectCase(case_id), SetSummaryLevel(SummaryLevel.DETAILED),
        SetAuxiliaryFilter(TraditionalCaseArea.CIVIL), SelectClaims((), "selected text"),
        ToggleSource(source),
    ):
        state, _ = app_reducer(state, command)
    state = state.__class__(**{**state.__dict__, "raw_query": "현장 상황"})
    state = state.__class__(**{**state.__dict__, "rag": advance_stage(state.rag)})

    next_state, effects = app_reducer(state, FailStage(RagStageError(
        "MOCK_DATA_INSUFFICIENT", RagStage.MOCK_SEARCH, True
    )))

    assert effects == ()
    assert next_state.before_error is not None
    assert next_state.before_error.raw_query == "현장 상황"
    assert next_state.before_error.selected_case_id == case_id
    assert next_state.before_error.summary_level is SummaryLevel.DETAILED
    assert next_state.before_error.auxiliary_filter is TraditionalCaseArea.CIVIL
    assert next_state.before_error.selected_text == "selected text"
    assert next_state.expanded_source == source
    assert next_state.rag.error is not None
    assert next_state.rag.error.stage is RagStage.MOCK_SEARCH


def test_source_return_preserves_navigation_context_and_case_selector_is_canonical() -> None:
    case_id = CaseId("case-1")
    state, _ = app_reducer(initial_app_state(), SelectCase(case_id))
    state, _ = app_reducer(state, SetSummaryLevel(SummaryLevel.TEN_LINE))
    state, _ = app_reducer(state, SetAuxiliaryFilter(TraditionalCaseArea.CRIMINAL))
    state, _ = app_reducer(state, ToggleSource(SourceNavigationRequest(SourceId("s"), SourceAnchorId("a"))))
    returned, _ = app_reducer(state, ReturnFromSource())

    assert returned.expanded_source is None
    assert (returned.selected_case_id, returned.summary_level, returned.auxiliary_filter) == (
        case_id, SummaryLevel.TEN_LINE, TraditionalCaseArea.CRIMINAL
    )
    canonical_case = object()
    assert selected_case(returned, {case_id: canonical_case}) is canonical_case


def test_copy_and_download_are_effect_commands_and_do_not_change_state() -> None:
    report = ReportDocument((), "facts\nnotice", "2025-01-01", "notice")
    state = initial_app_state().__class__(**{**initial_app_state().__dict__, "report": report})

    copied, copy_effects = app_reducer(state, RequestCopyReport())
    downloaded, download_effects = app_reducer(state, RequestDownloadReport("facts.txt"))

    assert copied is state and copy_effects == (CopyReport(report.body),)
    assert downloaded is state
    assert len(download_effects) == 1
    assert download_effects[0].filename == "facts.txt"
    assert download_effects[0].text == report.body
