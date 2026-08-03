"""Property 25: 선택 독립 주장의 exact-once와 상태 총체성 (task 12.2).

The browser maps a valid text selection to overlapping claim IDs before calling
the domain layer. This property generates mappings with repeated and unknown
IDs, then verifies that review returns each known claim once in document order
and always assigns one permitted evidence status.
"""

from __future__ import annotations

from typing import Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_common import SourceAnchorId
from data.models_selection import ReviewableClaim
from data.models_source import ClaimEvidenceLink
from domain.enums import EvidenceStatus
from domain.ids import ClaimId, SourceId
from domain.selection_review import review_selection


_EVIDENCE_SPECS = st.lists(
    st.tuples(
        st.sampled_from(("DECISION", "REFERENCE")),
        st.sampled_from(("SUPPORTS", "CONTRADICTS", "RELATED")),
        st.sampled_from(("FULL", "PARTIAL", "NONE")),
    ),
    max_size=8,
)
_CLAIM_SPECS = st.lists(_EVIDENCE_SPECS, min_size=1, max_size=12)


def _evidence_from_specs(
    claim_index: int,
    specs: list[tuple[str, str, str]],
) -> Tuple[ClaimEvidenceLink, ...]:
    """Build evidence independently from selection-review logic."""

    return tuple(
        ClaimEvidenceLink(
            source_id=SourceId(f"source-{claim_index}-{evidence_index}"),
            anchor_id=SourceAnchorId(
                f"source-{claim_index}-{evidence_index}-anchor"
            ),
            purpose=purpose,  # type: ignore[arg-type]
            relation=relation,  # type: ignore[arg-type]
            coverage=coverage,  # type: ignore[arg-type]
        )
        for evidence_index, (purpose, relation, coverage) in enumerate(specs)
    )


def _claims_from_specs(
    claim_specs: list[list[tuple[str, str, str]]],
) -> Tuple[ReviewableClaim, ...]:
    """Reverse fixture order to verify document-order restoration."""

    claims = tuple(
        ReviewableClaim(
            id=ClaimId(f"claim-{index}"),
            text=f"독립 주장 {index}",
            document_order=index,
            evidence=_evidence_from_specs(index, specs),
        )
        for index, specs in enumerate(claim_specs)
    )
    return tuple(reversed(claims))


# Feature: police-case-law-ai-bot
# Property 25: 선택 독립 주장의 exact-once와 상태 총체성
# **Validates: Requirements 9.3, 9.4**
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(
    claim_specs=_CLAIM_SPECS,
    selected_indexes=st.lists(
        st.integers(min_value=-3, max_value=14), max_size=40
    ),
)
def test_selection_review_exact_once_and_total_status(
    claim_specs: list[list[tuple[str, str, str]]],
    selected_indexes: list[int],
) -> None:
    """A nonblank selection returns unique known claims in document order.

    **Validates: Requirements 9.3, 9.4**
    """

    claims = _claims_from_specs(claim_specs)
    selected_claim_ids = tuple(
        ClaimId(f"claim-{index}") for index in selected_indexes
    )

    result = review_selection("유효한 선택 문구", selected_claim_ids, claims)

    known_ids = {claim.id for claim in claims}
    selected_known_indexes = {
        index
        for index in selected_indexes
        if ClaimId(f"claim-{index}") in known_ids
    }
    expected_ids = tuple(
        ClaimId(f"claim-{index}") for index in sorted(selected_known_indexes)
    )
    actual_ids = tuple(outcome.claim_id for outcome in result.claims)

    assert actual_ids == expected_ids
    assert len(actual_ids) == len(set(actual_ids))
    assert all(
        outcome.status in set(EvidenceStatus) for outcome in result.claims
    )
