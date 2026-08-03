"""Property 26: 주장 근거 분류와 결정·참고 출처 partition (task 12.3).

The oracle deliberately does not call the implementation.  It classifies only
``DECISION`` links using the conflict-first truth table, then independently
builds the evidence that determines the status and the separate reference
collection.
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
from domain.selection_review import review_claim


_EVIDENCE_SPECS = st.lists(
    st.tuples(
        st.sampled_from(("DECISION", "REFERENCE")),
        st.sampled_from(("SUPPORTS", "CONTRADICTS", "RELATED")),
        st.sampled_from(("FULL", "PARTIAL", "NONE")),
    ),
    max_size=20,
)


def _evidence_from_specs(
    specs: list[tuple[str, str, str]],
) -> Tuple[ClaimEvidenceLink, ...]:
    """Create unique source/anchor pairs for valid evidence collections."""

    return tuple(
        ClaimEvidenceLink(
            source_id=SourceId(f"source-{index}"),
            anchor_id=SourceAnchorId(f"anchor-{index}"),
            purpose=purpose,  # type: ignore[arg-type]
            relation=relation,  # type: ignore[arg-type]
            coverage=coverage,  # type: ignore[arg-type]
        )
        for index, (purpose, relation, coverage) in enumerate(specs)
    )


def _expected_status(
    evidence: Tuple[ClaimEvidenceLink, ...],
) -> EvidenceStatus:
    """Independent conflict-first reference classifier for Property 26."""

    decisions = [link for link in evidence if link.purpose == "DECISION"]
    if any(link.relation == "CONTRADICTS" for link in decisions):
        return EvidenceStatus.CONFLICT
    if any(
        link.relation == "SUPPORTS" and link.coverage == "FULL"
        for link in decisions
    ):
        return EvidenceStatus.MATCH
    return EvidenceStatus.INSUFFICIENT


def _expected_decision_evidence(
    evidence: Tuple[ClaimEvidenceLink, ...],
    status: EvidenceStatus,
) -> Tuple[ClaimEvidenceLink, ...]:
    """Return only the DECISION links that determine ``status``."""

    if status is EvidenceStatus.CONFLICT:
        return tuple(
            link
            for link in evidence
            if link.purpose == "DECISION" and link.relation == "CONTRADICTS"
        )
    if status is EvidenceStatus.MATCH:
        return tuple(
            link
            for link in evidence
            if link.purpose == "DECISION"
            and link.relation == "SUPPORTS"
            and link.coverage == "FULL"
        )
    return ()


def _citation_keys(
    evidence: Tuple[ClaimEvidenceLink, ...],
) -> set[tuple[SourceId, SourceAnchorId]]:
    return {(link.source_id, link.anchor_id) for link in evidence}


# Feature: police-case-law-ai-bot
# Property 26: 주장 근거 분류와 결정·참고 출처 partition
# **Validates: Requirements 1.9, 9.5, 9.6, 9.7, 9.8, 9.11**
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(evidence_specs=_EVIDENCE_SPECS)
def test_claim_evidence_classification_and_source_partition(
    evidence_specs: list[tuple[str, str, str]],
) -> None:
    """Decision evidence is conflict-first and partitions from references.

    **Validates: Requirements 1.9, 9.5, 9.6, 9.7, 9.8, 9.11**
    """

    evidence = _evidence_from_specs(evidence_specs)
    claim = ReviewableClaim(
        id=ClaimId("claim-property-26"),
        text="독립 주장",
        document_order=0,
        evidence=evidence,
    )

    outcome = review_claim(claim)
    expected_status = _expected_status(evidence)
    expected_decisions = _expected_decision_evidence(evidence, expected_status)
    expected_references = tuple(
        link for link in evidence if link.purpose == "REFERENCE"
    )

    assert outcome.status is expected_status
    assert outcome.decision_evidence == expected_decisions
    assert outcome.reference_sources == expected_references

    decision_keys = _citation_keys(outcome.decision_evidence)
    reference_keys = _citation_keys(outcome.reference_sources)
    assert decision_keys.isdisjoint(reference_keys)
    assert decision_keys | reference_keys == _citation_keys(
        expected_decisions + expected_references
    )
