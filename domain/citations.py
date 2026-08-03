"""Claim citation resolution with source/anchor integrity checks (task 6.2).

``citations_for_claim`` defensively validates source/anchor references at the
rendering boundary. A source ID must resolve exactly once, its anchor must
resolve exactly once, and the anchor's bounds and SHA-256 checksum must match
its source body. Invalid references are isolated, never silently resolved.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Set, Tuple

from domain.ids import ClaimId, SourceId
from domain.result import Err, Ok, Result
from domain.response_projection import CitationProjection

from data.models_common import SourceAnchorId
from data.models_source import (
    ClaimEvidenceLink,
    LegalClaimBlock,
    SourceAnchor,
    SourceRecord,
)
from data.validated_dataset import ValidatedDataset

__all__ = [
    "SOURCE_DATA_ERROR_TEXT",
    "InvalidCitationReference",
    "CitationError",
    "citations_for_claim",
    "citationsForClaim",
]

SOURCE_DATA_ERROR_TEXT: Literal["출처 데이터 오류"] = "출처 데이터 오류"
"""Fixture status label required when a citation reference is invalid."""

CitationInvalidReason = Literal[
    "CLAIM_NOT_FOUND",
    "DUPLICATE_CLAIM_ID",
    "SOURCE_NOT_FOUND",
    "DUPLICATE_SOURCE_ID",
    "ANCHOR_NOT_FOUND",
    "DUPLICATE_ANCHOR_ID",
    "ANCHOR_RANGE_INVALID",
    "ANCHOR_CHECKSUM_MISMATCH",
]


@dataclass(frozen=True)
class InvalidCitationReference:
    """One isolated invalid ``(source_id, anchor_id)`` citation reference."""

    source_id: SourceId
    anchor_id: SourceAnchorId
    reason: CitationInvalidReason


@dataclass(frozen=True)
class CitationError:
    """Safe source error with unaffected citations retained for rendering.

    The web layer can preserve ``valid_citations`` while displaying
    ``display_text``; it never needs to invent a replacement legal conclusion.
    """

    code: Literal["SOURCE_DATA_ERROR"]
    display_text: Literal["출처 데이터 오류"]
    claim_id: ClaimId
    invalid_references: Tuple[InvalidCitationReference, ...]
    valid_citations: Tuple[CitationProjection, ...]


def _claim_matches(
    claim_id: ClaimId,
    dataset: ValidatedDataset,
) -> Tuple[LegalClaimBlock, ...]:
    return tuple(
        block
        for template in dataset.response_templates
        for block in template.blocks
        if isinstance(block, LegalClaimBlock) and block.claim_id == claim_id
    )


def _citation_purpose(
    link: ClaimEvidenceLink,
) -> Literal["DIRECT", "REFERENCE"]:
    """Map fixture evidence semantics to the client citation contract."""

    if link.purpose == "DECISION" and link.relation != "RELATED":
        return "DIRECT"
    return "REFERENCE"


def _unique_source(
    source_id: SourceId,
    dataset: ValidatedDataset,
) -> Tuple[SourceRecord, ...]:
    """Scan clean sources so duplicate IDs cannot be silently selected."""

    return tuple(
        source for source in dataset.sources if source.id == source_id
    )


def _unique_anchor(
    anchor_id: SourceAnchorId,
    source: SourceRecord,
) -> Tuple[SourceAnchor, ...]:
    return tuple(anchor for anchor in source.anchors if anchor.id == anchor_id)


def _anchor_invalid_reason(
    anchor: SourceAnchor,
    source: SourceRecord,
) -> "Optional[CitationInvalidReason]":
    start, end = anchor.start_offset, anchor.end_offset
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or start < 0
        or end < start
        or end > len(source.body)
    ):
        return "ANCHOR_RANGE_INVALID"
    excerpt = source.body[start:end]
    actual_checksum = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    if actual_checksum != anchor.excerpt_checksum:
        return "ANCHOR_CHECKSUM_MISMATCH"
    return None


def _deduplicate_valid_citations(
    citations: Sequence[CitationProjection],
) -> Tuple[CitationProjection, ...]:
    seen: Set[
        Tuple[SourceId, SourceAnchorId, Literal["DIRECT", "REFERENCE"]]
    ] = set()
    result: List[CitationProjection] = []
    for citation in citations:
        key = (citation.source_id, citation.anchor_id, citation.purpose)
        if key not in seen:
            seen.add(key)
            result.append(citation)
    return tuple(result)


def _claim_error(
    claim_id: ClaimId,
    reason: Literal["CLAIM_NOT_FOUND", "DUPLICATE_CLAIM_ID"],
) -> Err[CitationError]:
    return Err(
        CitationError(
            code="SOURCE_DATA_ERROR",
            display_text=SOURCE_DATA_ERROR_TEXT,
            claim_id=claim_id,
            invalid_references=(
                InvalidCitationReference(
                    source_id=SourceId(""),
                    anchor_id=SourceAnchorId(""),
                    reason=reason,
                ),
            ),
            valid_citations=(),
        )
    )


def citations_for_claim(
    claim_id: ClaimId,
    dataset: ValidatedDataset,
) -> Result[Tuple[CitationProjection, ...], CitationError]:
    """Resolve validated citations or return a safe partial source error.

    A malformed claim, source, anchor range, checksum, or duplicate ID does
    not raise an exception. Its link is omitted while every independently
    valid citation remains available in ``CitationError.valid_citations``.
    """

    claims = _claim_matches(claim_id, dataset)
    if not claims:
        return _claim_error(claim_id, "CLAIM_NOT_FOUND")
    if len(claims) > 1:
        return _claim_error(claim_id, "DUPLICATE_CLAIM_ID")

    valid: List[CitationProjection] = []
    invalid: List[InvalidCitationReference] = []
    for link in claims[0].citation_links:
        sources = _unique_source(link.source_id, dataset)
        if len(sources) != 1:
            reason: CitationInvalidReason = (
                "SOURCE_NOT_FOUND" if not sources else "DUPLICATE_SOURCE_ID"
            )
            invalid.append(
                InvalidCitationReference(
                    source_id=link.source_id,
                    anchor_id=link.anchor_id,
                    reason=reason,
                )
            )
            continue
        anchors = _unique_anchor(link.anchor_id, sources[0])
        if len(anchors) != 1:
            reason = (
                "ANCHOR_NOT_FOUND"
                if not anchors
                else "DUPLICATE_ANCHOR_ID"
            )
            invalid.append(
                InvalidCitationReference(
                    source_id=link.source_id,
                    anchor_id=link.anchor_id,
                    reason=reason,
                )
            )
            continue
        anchor_reason = _anchor_invalid_reason(anchors[0], sources[0])
        if anchor_reason is not None:
            invalid.append(
                InvalidCitationReference(
                    source_id=link.source_id,
                    anchor_id=link.anchor_id,
                    reason=anchor_reason,
                )
            )
            continue
        valid.append(
            CitationProjection(
                source_id=link.source_id,
                anchor_id=link.anchor_id,
                purpose=_citation_purpose(link),
            )
        )

    valid_citations = _deduplicate_valid_citations(valid)
    if invalid:
        return Err(
            CitationError(
                code="SOURCE_DATA_ERROR",
                display_text=SOURCE_DATA_ERROR_TEXT,
                claim_id=claim_id,
                invalid_references=tuple(invalid),
                valid_citations=valid_citations,
            )
        )
    return Ok(valid_citations)


# The design contract is camelCase; Python callers use the snake_case name.
citationsForClaim = citations_for_claim
