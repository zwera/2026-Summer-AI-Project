"""Response template projection and citation assembly (task 6.1).

This module projects only fixture-defined :class:`ResponseTemplate` blocks in
fixture order. It does not generate legal text or validate source/anchor
existence; source/anchor validation and invalid-reference isolation belong to
task 6.2. For every legal claim it:

* classifies evidence with the same conflict-first rule used by selection
  review;
* exposes direct decision evidence as de-duplicated ``(source_id, anchor_id)``
  pairs, preserving first fixture occurrence;
* keeps merely related or explicitly reference evidence separate from direct
  citations; and
* leaves claims without full direct support as ``근거_부족``.

The output is therefore a deterministic, fixture-backed response contract for
the server/UI boundary (Requirements 3.4, 3.8, 1.9, 15.6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Sequence, Set, Tuple, Union

from domain.enums import EvidenceStatus
from domain.ids import ClaimId, SourceId
from domain.selection_review import classify_claim_evidence

from data.models_common import SourceAnchorId
from data.models_source import (
    ClaimEvidenceLink,
    LegalClaimBlock,
    ResponseTemplate,
)

__all__ = [
    "CitationProjection",
    "ResponseTextProjection",
    "ResponseLegalClaimProjection",
    "ResponseBlockProjection",
    "ResponseTemplateProjection",
    "project_response_template",
]


@dataclass(frozen=True)
class CitationProjection:
    """A fixture-backed source anchor reference for one response claim.

    ``purpose`` is intentionally an output concern rather than the fixture's
    ``DECISION``/``REFERENCE`` value: the client can render direct evidence and
    related references in separate regions without reclassifying legal data.
    """

    source_id: SourceId
    anchor_id: SourceAnchorId
    purpose: Literal["DIRECT", "REFERENCE"]


@dataclass(frozen=True)
class ResponseTextProjection:
    """A fixture ``TEXT`` block, preserved without transformation."""

    type: Literal["TEXT"]
    text: str


@dataclass(frozen=True)
class ResponseLegalClaimProjection:
    """A fixture ``LEGAL_CLAIM`` with evidence status and citations."""

    type: Literal["LEGAL_CLAIM"]
    claim_id: ClaimId
    text: str
    evidence_status: EvidenceStatus
    direct_citations: Tuple[CitationProjection, ...]
    reference_sources: Tuple[CitationProjection, ...]


ResponseBlockProjection = Union[
    ResponseTextProjection,
    ResponseLegalClaimProjection,
]
"""One projected block in the original ``ResponseTemplate.blocks`` order."""


@dataclass(frozen=True)
class ResponseTemplateProjection:
    """The deterministic projection of one fixture response template."""

    template_id: str
    blocks: Tuple[ResponseBlockProjection, ...]


def _deduplicate_citations(
    links: Sequence[ClaimEvidenceLink],
    purpose: Literal["DIRECT", "REFERENCE"],
) -> Tuple[CitationProjection, ...]:
    """Return source/anchor pairs once, retaining their first fixture order."""

    seen: Set[Tuple[SourceId, SourceAnchorId]] = set()
    citations: List[CitationProjection] = []
    for link in links:
        pair = (link.source_id, link.anchor_id)
        if pair in seen:
            continue
        seen.add(pair)
        citations.append(
            CitationProjection(
                source_id=link.source_id,
                anchor_id=link.anchor_id,
                purpose=purpose,
            )
        )
    return tuple(citations)


def _project_claim(block: LegalClaimBlock) -> ResponseLegalClaimProjection:
    """Project one claim while keeping deciding evidence and references apart.

    ``DECISION`` links that provide support or contradiction are direct
    evidence. ``REFERENCE`` links, and any link declared merely ``RELATED``,
    are references only. This prevents a related source from being displayed
    as direct support. If a pair is present in both groups, direct evidence
    takes precedence so the two output collections remain disjoint.
    """

    direct_links = tuple(
        link
        for link in block.citation_links
        if link.purpose == "DECISION" and link.relation != "RELATED"
    )
    direct_citations = _deduplicate_citations(direct_links, "DIRECT")
    direct_pairs = {
        (citation.source_id, citation.anchor_id)
        for citation in direct_citations
    }
    reference_links = tuple(
        link
        for link in block.citation_links
        if (link.purpose == "REFERENCE" or link.relation == "RELATED")
        and (link.source_id, link.anchor_id) not in direct_pairs
    )

    return ResponseLegalClaimProjection(
        type="LEGAL_CLAIM",
        claim_id=block.claim_id,
        text=block.text,
        evidence_status=classify_claim_evidence(block.citation_links),
        direct_citations=direct_citations,
        reference_sources=_deduplicate_citations(
            reference_links,
            "REFERENCE",
        ),
    )


def project_response_template(
    template: ResponseTemplate,
) -> ResponseTemplateProjection:
    """Project ``template`` blocks in their declared order.

    Text and claim content are copied verbatim from the fixture. Every claim
    obtains exactly one evidence status; no direct/full support, including an
    empty evidence list or partial support only, is represented by
    :attr:`EvidenceStatus.INSUFFICIENT` (``근거_부족``).
    """

    blocks: List[ResponseBlockProjection] = []
    for block in template.blocks:
        if isinstance(block, LegalClaimBlock):
            blocks.append(_project_claim(block))
        else:
            blocks.append(ResponseTextProjection(type="TEXT", text=block.text))
    return ResponseTemplateProjection(
        template_id=template.id,
        blocks=tuple(blocks),
    )
