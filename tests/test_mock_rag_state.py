"""Unit tests for the mock-RAG stage machine (task 15.1)."""

from __future__ import annotations

from app.mock_rag_state import (
    RagStageError,
    advance_stage,
    fail_stage,
    initial_rag_state,
    reset_to_input,
    retry_stage,
)
from domain.enums import RagStage, StageStatus


def test_stages_advance_in_order_with_exactly_one_active_stage() -> None:
    state = initial_rag_state()
    expected = (
        RagStage.INPUT,
        RagStage.MOCK_SEARCH,
        RagStage.EVIDENCE,
        RagStage.RESPONSE,
    )

    for stage in expected:
        assert state.current is stage
        assert state.active_stages == (stage,)
        state = advance_stage(state)

    assert state.current is RagStage.RESPONSE
    assert state.active_stages == ()
    assert all(
        status is StageStatus.COMPLETED
        for status in state.status_by_stage.values()
    )


def test_advance_after_completed_response_does_not_restart_or_skip() -> None:
    state = initial_rag_state()
    for _ in range(4):
        state = advance_stage(state)

    assert advance_stage(state) == state


def test_failure_marks_future_stages_incomplete_and_retry_reactivates() -> None:
    state = advance_stage(initial_rag_state())
    error = RagStageError(
        "MOCK_DATA_INSUFFICIENT",
        RagStage.MOCK_SEARCH,
        retryable=True,
    )

    failed = fail_stage(state, error)

    assert failed.current is RagStage.MOCK_SEARCH
    assert failed.status_by_stage[RagStage.INPUT] is StageStatus.COMPLETED
    assert failed.status_by_stage[RagStage.MOCK_SEARCH] is StageStatus.FAILED
    assert failed.status_by_stage[RagStage.EVIDENCE] is StageStatus.INCOMPLETE
    assert failed.status_by_stage[RagStage.RESPONSE] is StageStatus.INCOMPLETE
    assert failed.active_stages == ()

    retried = retry_stage(failed)
    assert retried.current is RagStage.MOCK_SEARCH
    assert retried.status_by_stage[RagStage.MOCK_SEARCH] is StageStatus.ACTIVE
    assert retried.status_by_stage[RagStage.EVIDENCE] is StageStatus.INCOMPLETE
    assert retried.active_stages == (RagStage.MOCK_SEARCH,)


def test_non_retryable_or_wrong_stage_failure_preserves_state() -> None:
    state = initial_rag_state()
    wrong_stage = RagStageError(
        "SOURCE_DATA_ERROR",
        RagStage.EVIDENCE,
        retryable=True,
    )
    assert fail_stage(state, wrong_stage) == state

    error = RagStageError("SOURCE_DATA_ERROR", RagStage.INPUT, retryable=False)
    failed = fail_stage(state, error)
    assert retry_stage(failed) == failed


def test_reset_starts_clean_input_flow_after_failure() -> None:
    state = fail_stage(
        advance_stage(initial_rag_state()),
        RagStageError(
            "MOCK_DATA_INSUFFICIENT",
            RagStage.MOCK_SEARCH,
            retryable=True,
        ),
    )

    reset = reset_to_input(state)

    assert reset.current is RagStage.INPUT
    assert reset.error is None
    assert reset.active_stages == (RagStage.INPUT,)
    assert reset.status_by_stage[RagStage.INPUT] is StageStatus.ACTIVE
    assert reset.status_by_stage[RagStage.MOCK_SEARCH] is StageStatus.PENDING
    assert reset.status_by_stage[RagStage.EVIDENCE] is StageStatus.PENDING
    assert reset.status_by_stage[RagStage.RESPONSE] is StageStatus.PENDING
