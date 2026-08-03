"""Deterministic mock-RAG stage state machine (task 15.1).

The machine models only the four staged mock flow. It performs no fixture
lookup, network I/O, or legal-result generation; later tasks attach those effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from domain.enums import RagStage, StageStatus

__all__ = [
    "MockRagState",
    "RagStageError",
    "advance_stage",
    "fail_stage",
    "initial_rag_state",
    "reset_to_input",
    "retry_stage",
]

_STAGES: Tuple[RagStage, ...] = (
    RagStage.INPUT,
    RagStage.MOCK_SEARCH,
    RagStage.EVIDENCE,
    RagStage.RESPONSE,
)


@dataclass(frozen=True)
class RagStageError:
    """Safe stage-error metadata needed for failure and retry transitions."""

    code: str
    stage: RagStage
    retryable: bool
    affected_record_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class MockRagState:
    """Immutable state for the sequential mock-RAG pipeline.

    At most one stage may be active. A failed stage remains current so the UI can
    name it, while all later stages remain incomplete.
    """

    current: RagStage
    status_by_stage: Mapping[RagStage, StageStatus]
    error: Optional[RagStageError] = None

    @property
    def active_stages(self) -> Tuple[RagStage, ...]:
        """Return active stages; it is empty only after response completion or failure."""

        return tuple(
            stage
            for stage in _STAGES
            if self.status_by_stage[stage] is StageStatus.ACTIVE
        )


def initial_rag_state() -> MockRagState:
    """Start a new flow with INPUT as its only active stage."""

    return MockRagState(
        current=RagStage.INPUT,
        status_by_stage={
            RagStage.INPUT: StageStatus.ACTIVE,
            RagStage.MOCK_SEARCH: StageStatus.PENDING,
            RagStage.EVIDENCE: StageStatus.PENDING,
            RagStage.RESPONSE: StageStatus.PENDING,
        },
    )


def advance_stage(state: MockRagState) -> MockRagState:
    """Complete the active stage and activate its immediate successor only.

    Invalid advancement attempts, including attempts after RESPONSE, preserve the
    state. This makes stage skipping impossible through this state-machine API.
    """

    if (
        state.error is not None
        or state.status_by_stage[state.current] is not StageStatus.ACTIVE
    ):
        return state

    position = _STAGES.index(state.current)
    statuses = dict(state.status_by_stage)
    statuses[state.current] = StageStatus.COMPLETED
    if position == len(_STAGES) - 1:
        return MockRagState(current=state.current, status_by_stage=statuses)

    next_stage = _STAGES[position + 1]
    statuses[next_stage] = StageStatus.ACTIVE
    return MockRagState(current=next_stage, status_by_stage=statuses)


def fail_stage(state: MockRagState, error: RagStageError) -> MockRagState:
    """Fail the active stage and mark every later stage incomplete.

    An error cannot fail a different stage, preventing callers from bypassing the
    required sequence. Invalid failure events preserve state.
    """

    if (
        state.error is not None
        or state.status_by_stage[state.current] is not StageStatus.ACTIVE
        or error.stage is not state.current
    ):
        return state

    statuses = dict(state.status_by_stage)
    statuses[state.current] = StageStatus.FAILED
    for stage in _STAGES[_STAGES.index(state.current) + 1:]:
        statuses[stage] = StageStatus.INCOMPLETE
    return MockRagState(
        current=state.current,
        status_by_stage=statuses,
        error=error,
    )


def retry_stage(state: MockRagState) -> MockRagState:
    """Reactivate exactly the failed, retryable stage without advancing it."""

    if state.error is None or not state.error.retryable:
        return state
    if state.status_by_stage[state.current] is not StageStatus.FAILED:
        return state

    statuses = dict(state.status_by_stage)
    statuses[state.current] = StageStatus.ACTIVE
    return MockRagState(current=state.current, status_by_stage=statuses)


def reset_to_input(_: MockRagState) -> MockRagState:
    """Discard the previous flow and begin a fresh input-stage sequence."""

    return initial_rag_state()
