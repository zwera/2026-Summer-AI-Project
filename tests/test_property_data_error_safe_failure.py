"""Property 39: 데이터 오류의 안전 실패와 오류 전 상태 보존 (task 15.6).

A single fixture mutation must isolate only its affected record or safely stop
the active RAG stage. It must never overwrite the user's existing screen state
or produce a replacement legal conclusion.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Literal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.app_reducer import (
    AdvanceRag,
    FailStage,
    SelectCase,
    SelectClaims,
    SetAuxiliaryFilter,
    SetSummaryLevel,
    app_reducer,
    initial_app_state,
)
from app.mock_rag_state import RagStageError
from data.models_dataset import MockDataset
from data.models_source import LegalClaimBlock
from data.validated_dataset import validate_dataset
from domain.enums import RagStage, StageStatus, SummaryLevel, TraditionalCaseArea
from domain.ids import CaseId
from domain.result import Ok
from fixtures.mock_dataset import build_mock_dataset

FaultKind = Literal["dangling_source", "canonical_charge", "missing_case"]


def _single_fault_dataset(kind: FaultKind) -> MockDataset:
    """Apply exactly one recoverable fault to a valid fixture dataset."""
    raw = build_mock_dataset()
    if kind == "dangling_source":
        template = raw.response_templates[0]
        claim = next(
            block
            for block in template.blocks
            if isinstance(block, LegalClaimBlock)
        )
        source_id = claim.citation_links[0].source_id
        return replace(
            raw,
            sources=tuple(source for source in raw.sources if source.id != source_id),
        )
    if kind == "canonical_charge":
        case = raw.cases[0]
        bad_summaries = replace(
            case.summaries,
            canonical_instance_charge="충돌한 죄명",
        )
        return replace(
            raw,
            cases=(replace(case, summaries=bad_summaries),) + raw.cases[1:],
        )

    query = raw.queries[0]
    missing_id = CaseId("case-missing-property-39")
    bad_match = replace(
        query.match,
        case_ids=(missing_id,) + query.match.case_ids[1:],
    )
    return replace(raw, queries=(replace(query, match=bad_match),) + raw.queries[1:])


def _expected(kind: FaultKind) -> tuple[str, RagStage, bool]:
    """Independent mutation-to-safe-error oracle from the design error table."""
    if kind == "dangling_source":
        return "SOURCE_DATA_ERROR", RagStage.EVIDENCE, True
    if kind == "canonical_charge":
        return "CASE_DATA_INCONSISTENCY", RagStage.MOCK_SEARCH, True
    return "MOCK_DATA_INSUFFICIENT", RagStage.MOCK_SEARCH, True


def _state_at(stage: RagStage):
    state = initial_app_state()
    while state.rag.current is not stage:
        state, _ = app_reducer(state, AdvanceRag())
    return state


# Feature: police-case-law-ai-bot, Property 39: 데이터 오류의 안전 실패와 오류 전 상태 보존
@settings(
    max_examples=100,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    kind=st.sampled_from(("dangling_source", "canonical_charge", "missing_case")),
    summary_level=st.sampled_from(tuple(SummaryLevel)),
    auxiliary_filter=st.one_of(
        st.none(), st.sampled_from(tuple(TraditionalCaseArea))
    ),
    selected_text=st.text(max_size=40),
)
def test_single_data_fault_safely_fails_without_overwriting_prior_state(
    kind: FaultKind,
    summary_level: SummaryLevel,
    auxiliary_filter: TraditionalCaseArea | None,
    selected_text: str,
) -> None:
    """**Validates: Requirements 13.4, 13.5, 13.6, 13.9, 13.10**."""
    raw = _single_fault_dataset(kind)
    validated = validate_dataset(raw)
    assert isinstance(validated, Ok)
    clean = validated.value

    code, stage, retryable = _expected(kind)
    if kind == "dangling_source":
        assert len(clean.response_templates) == len(raw.response_templates) - 1
        assert len(clean.sources) == len(raw.sources)
    elif kind == "canonical_charge":
        assert raw.cases[0].id not in clean.cases_by_id
    else:
        assert raw.queries[0].id not in clean.queries_by_id

    state = _state_at(stage)
    selected_case_id = CaseId("case-state-property-39")
    for command in (
        SelectCase(selected_case_id),
        SetSummaryLevel(summary_level),
        SetAuxiliaryFilter(auxiliary_filter),
        SelectClaims((), selected_text),
    ):
        state, _ = app_reducer(state, command)
    state = replace(state, raw_query="오류 전 현장 질의")
    before = (
        state.raw_query,
        state.selected_case_id,
        state.summary_level,
        state.auxiliary_filter,
        state.selection_review.selected_text,
    )

    failed, effects = app_reducer(
        state,
        FailStage(
            RagStageError(code, stage, retryable, ("affected-record",))
        ),
    )

    assert effects == ()
    assert failed.before_error is not None
    assert (
        failed.before_error.raw_query,
        failed.before_error.selected_case_id,
        failed.before_error.summary_level,
        failed.before_error.auxiliary_filter,
        failed.before_error.selected_text,
    ) == before
    assert failed.rag.error is not None
    assert (
        failed.rag.error.code,
        failed.rag.error.stage,
        failed.rag.error.retryable,
    ) == (code, stage, retryable)
    assert failed.rag.active_stages == ()
    assert failed.rag.status_by_stage[stage] is StageStatus.FAILED
    assert all(
        failed.rag.status_by_stage[later] is StageStatus.INCOMPLETE
        for later in RagStage
        if tuple(RagStage).index(later) > tuple(RagStage).index(stage)
    )
