"""Property 2: 목업 RAG 상태 기계의 순차성과 단일 활성 단계 (task 15.4)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from app.mock_rag_state import (
    MockRagState,
    RagStageError,
    advance_stage,
    fail_stage,
    initial_rag_state,
    reset_to_input,
    retry_stage,
)
from domain.enums import RagStage, StageStatus


_STAGES: Tuple[RagStage, ...] = (
    RagStage.INPUT,
    RagStage.MOCK_SEARCH,
    RagStage.EVIDENCE,
    RagStage.RESPONSE,
)


@dataclass(frozen=True)
class _Command:
    """Generated legal and illegal state-machine events."""

    kind: str
    error_stage: Optional[RagStage] = None
    retryable: bool = False


_COMMANDS = st.one_of(
    st.just(_Command("advance")),
    st.just(_Command("retry")),
    st.just(_Command("reset")),
    st.builds(
        _Command,
        st.just("fail"),
        st.sampled_from(_STAGES),
        st.booleans(),
    ),
)


def _reference_apply(
    state: MockRagState,
    command: _Command,
) -> MockRagState:
    """Reference transition-table oracle."""

    statuses: Dict[RagStage, StageStatus] = dict(state.status_by_stage)
    current = state.current
    error = state.error

    if command.kind == "reset":
        return initial_rag_state()
    if command.kind == "advance":
        if error is not None or statuses[current] is not StageStatus.ACTIVE:
            return state
        index = _STAGES.index(current)
        statuses[current] = StageStatus.COMPLETED
        if index == len(_STAGES) - 1:
            return MockRagState(current, statuses)
        successor = _STAGES[index + 1]
        statuses[successor] = StageStatus.ACTIVE
        return MockRagState(successor, statuses)
    if command.kind == "fail":
        if (
            error is not None
            or statuses[current] is not StageStatus.ACTIVE
            or command.error_stage is not current
        ):
            return state
        statuses[current] = StageStatus.FAILED
        for stage in _STAGES[_STAGES.index(current) + 1:]:
            statuses[stage] = StageStatus.INCOMPLETE
        return MockRagState(
            current,
            statuses,
            RagStageError("TEST_ERROR", current, command.retryable),
        )
    if command.kind == "retry":
        if (
            error is None
            or not error.retryable
            or statuses[current] is not StageStatus.FAILED
        ):
            return state
        statuses[current] = StageStatus.ACTIVE
        return MockRagState(current, statuses)
    raise AssertionError(f"unknown command: {command.kind}")


def _apply_actual(state: MockRagState, command: _Command) -> MockRagState:
    """Apply a generated command through the public state-machine API."""

    if command.kind == "advance":
        return advance_stage(state)
    if command.kind == "retry":
        return retry_stage(state)
    if command.kind == "reset":
        return reset_to_input(state)
    assert command.kind == "fail"
    assert command.error_stage is not None
    return fail_stage(
        state,
        RagStageError("TEST_ERROR", command.error_stage, command.retryable),
    )


def _assert_state_invariants(state: MockRagState) -> None:
    """Check stage-machine invariants."""

    statuses = tuple(state.status_by_stage[stage] for stage in _STAGES)
    active = tuple(
        stage
        for stage in _STAGES
        if state.status_by_stage[stage] is StageStatus.ACTIVE
    )

    if (
        state.error is None
        and statuses[-1] is not StageStatus.COMPLETED
    ):
        assert active == (state.current,)
    else:
        assert active in ((), (state.current,))

    if state.error is None:
        current_index = _STAGES.index(state.current)
        assert all(
            status is StageStatus.COMPLETED
            for status in statuses[:current_index]
        )
        if statuses[-1] is StageStatus.COMPLETED:
            assert statuses == (StageStatus.COMPLETED,) * len(_STAGES)
        else:
            assert statuses[current_index] is StageStatus.ACTIVE
            assert all(
                status is StageStatus.PENDING
                for status in statuses[current_index + 1:]
            )
    else:
        failed_index = _STAGES.index(state.current)
        assert statuses[failed_index] in (
            StageStatus.FAILED,
            StageStatus.ACTIVE,
        )
        assert all(
            status is StageStatus.COMPLETED
            for status in statuses[:failed_index]
        )
        assert all(
            status is StageStatus.INCOMPLETE
            for status in statuses[failed_index + 1:]
        )


# Feature: police-case-law-ai-bot
# Property 2: 목업 RAG 상태 기계의 순차성과 단일 활성 단계
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(commands=st.lists(_COMMANDS, min_size=0, max_size=50))
def test_mock_rag_state_machine_is_sequential_and_has_one_active_stage(
    commands: list[_Command],
) -> None:
    """**Validates: Requirements 1.3, 1.4, 13.8, 13.11**.

    Across legal and illegal advance/fail/retry/reset sequences, the public
    state machine must match the four-stage transition table. It cannot skip a
    stage, can activate only a direct successor, and marks all later stages
    incomplete after an unresolved failure.
    """

    actual = initial_rag_state()
    expected = initial_rag_state()
    _assert_state_invariants(actual)

    for command in commands:
        actual = _apply_actual(actual, command)
        expected = _reference_apply(expected, command)

        assert actual == expected
        _assert_state_invariants(actual)
