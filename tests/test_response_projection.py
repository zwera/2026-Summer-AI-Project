"""Unit tests for response template projection (task 6.1).

Validates: Requirements 3.4, 3.8, 1.9, 15.6.
Property 9 is intentionally deferred to task 6.3; these focused examples cover
order, evidence-pair de-duplication, insufficient support, and references.
"""

from __future__ import annotations

from domain.enums import EvidenceStatus
from domain.ids import ClaimId, SourceId
from domain.response_projection import (
    ResponseLegalClaimProjection,
    ResponseTextProjection,
    project_response_template,
)

from data.models_common import SourceAnchorId
from data.models_source import (
    ClaimEvidenceLink,
    LegalClaimBlock,
    ResponseTemplate,
    TextBlock,
)


def _link(
    source: str,
    anchor: str,
    *,
    purpose: str = "DECISION",
    relation: str = "SUPPORTS",
    coverage: str = "FULL",
) -> ClaimEvidenceLink:
    return ClaimEvidenceLink(
        source_id=SourceId(source),
        anchor_id=SourceAnchorId(anchor),
        purpose=purpose,  # type: ignore[arg-type]
        relation=relation,  # type: ignore[arg-type]
        coverage=coverage,  # type: ignore[arg-type]
    )


def test_projects_text_and_claim_blocks_in_declared_order() -> None:
    """The response is a fixture projection, not a generated answer."""

    template = ResponseTemplate(
        id="template-order",
        blocks=(
            TextBlock(type="TEXT", text="안내"),
            LegalClaimBlock(
                type="LEGAL_CLAIM",
                claim_id=ClaimId("claim-1"),
                text="법률 주장",
                citation_links=(_link("source-1", "anchor-1"),),
            ),
            TextBlock(type="TEXT", text="마무리"),
        ),
    )

    projection = project_response_template(template)

    assert projection.template_id == "template-order"
    assert [block.type for block in projection.blocks] == [
        "TEXT",
        "LEGAL_CLAIM",
        "TEXT",
    ]
    assert isinstance(projection.blocks[0], ResponseTextProjection)
    assert projection.blocks[0].text == "안내"
    assert isinstance(projection.blocks[1], ResponseLegalClaimProjection)
    assert projection.blocks[1].text == "법률 주장"
    assert isinstance(projection.blocks[2], ResponseTextProjection)
    assert projection.blocks[2].text == "마무리"


def test_deduplicates_direct_pairs_and_separates_references() -> None:
    """Direct pairs are unique; related sources remain references."""

    template = ResponseTemplate(
        id="template-citations",
        blocks=(
            LegalClaimBlock(
                type="LEGAL_CLAIM",
                claim_id=ClaimId("claim-1"),
                text="주장",
                citation_links=(
                    _link("source-1", "anchor-1"),
                    _link("source-1", "anchor-1"),
                    _link("source-1", "anchor-2"),
                    _link(
                        "source-2",
                        "anchor-1",
                        purpose="REFERENCE",
                        relation="RELATED",
                        coverage="NONE",
                    ),
                    _link(
                        "source-3",
                        "anchor-1",
                        purpose="DECISION",
                        relation="RELATED",
                        coverage="NONE",
                    ),
                ),
            ),
        ),
    )

    claim = project_response_template(template).blocks[0]

    assert isinstance(claim, ResponseLegalClaimProjection)
    assert claim.evidence_status is EvidenceStatus.MATCH
    assert [
        (citation.source_id, citation.anchor_id, citation.purpose)
        for citation in claim.direct_citations
    ] == [
        (SourceId("source-1"), SourceAnchorId("anchor-1"), "DIRECT"),
        (SourceId("source-1"), SourceAnchorId("anchor-2"), "DIRECT"),
    ]
    assert [
        (citation.source_id, citation.anchor_id, citation.purpose)
        for citation in claim.reference_sources
    ] == [
        (SourceId("source-2"), SourceAnchorId("anchor-1"), "REFERENCE"),
        (SourceId("source-3"), SourceAnchorId("anchor-1"), "REFERENCE"),
    ]


def test_marks_insufficient_support() -> None:
    """Absent or partial support is explicit `근거_부족`."""

    template = ResponseTemplate(
        id="template-insufficient",
        blocks=(
            LegalClaimBlock(
                type="LEGAL_CLAIM",
                claim_id=ClaimId("claim-empty"),
                text="근거 없는 주장",
                citation_links=(),
            ),
            LegalClaimBlock(
                type="LEGAL_CLAIM",
                claim_id=ClaimId("claim-partial"),
                text="부분 근거 주장",
                citation_links=(
                    _link("source-partial", "anchor-1", coverage="PARTIAL"),
                    _link(
                        "source-related",
                        "anchor-1",
                        purpose="REFERENCE",
                        relation="RELATED",
                        coverage="NONE",
                    ),
                ),
            ),
        ),
    )

    empty_claim, partial_claim = project_response_template(template).blocks

    assert isinstance(empty_claim, ResponseLegalClaimProjection)
    assert empty_claim.evidence_status is EvidenceStatus.INSUFFICIENT
    assert empty_claim.direct_citations == ()
    assert empty_claim.reference_sources == ()

    assert isinstance(partial_claim, ResponseLegalClaimProjection)
    assert partial_claim.evidence_status is EvidenceStatus.INSUFFICIENT
    assert [
        (citation.source_id, citation.anchor_id)
        for citation in partial_claim.direct_citations
    ] == [(SourceId("source-partial"), SourceAnchorId("anchor-1"))]
    assert [
        (citation.source_id, citation.anchor_id)
        for citation in partial_claim.reference_sources
    ] == [(SourceId("source-related"), SourceAnchorId("anchor-1"))]
