"""Unit tests for claim citation validation (task 6.2).

Validates: Requirements 3.9, 3.13, 3.14, 13.2, 13.6.
"""

from __future__ import annotations

import dataclasses
from typing import Tuple

from domain.citations import (
    SOURCE_DATA_ERROR_TEXT,
    citationsForClaim,
    citations_for_claim,
)
from domain.result import Err, Ok

from data.models_dataset import MockDataset
from data.models_source import ClaimEvidenceLink, LegalClaimBlock
from data.validated_dataset import ValidatedDataset, validate_dataset
from fixtures.mock_dataset import build_mock_dataset


def _validated_dataset() -> ValidatedDataset:
    result = validate_dataset(build_mock_dataset())
    assert isinstance(result, Ok)
    return result.value


def _claim(
    template_blocks: Tuple[object, ...],
    block_index: int = 1,
) -> LegalClaimBlock:
    block = template_blocks[block_index]
    assert isinstance(block, LegalClaimBlock)
    return block


def _first_claim(raw: MockDataset) -> LegalClaimBlock:
    return _claim(raw.response_templates[0].blocks)


def test_citations_for_claim_resolves_unique_valid_source_and_anchor() -> None:
    dataset = _validated_dataset()
    claim = _claim(dataset.response_templates[0].blocks)

    result = citations_for_claim(claim.claim_id, dataset)

    assert isinstance(result, Ok)
    assert len(result.value) == 1
    assert result.value[0].source_id == claim.citation_links[0].source_id
    assert result.value[0].anchor_id == claim.citation_links[0].anchor_id
    assert result.value[0].purpose == "DIRECT"
    assert citationsForClaim(claim.claim_id, dataset) == result


def test_invalid_source_is_isolated_and_valid_citation_is_retained() -> None:
    raw = build_mock_dataset()
    template = raw.response_templates[0]
    claim = _first_claim(raw)
    valid_link = claim.citation_links[0]
    invalid_source = raw.sources[2]
    broken_anchor = dataclasses.replace(
        invalid_source.anchors[0],
        excerpt_checksum="0" * 64,
    )
    broken_source = dataclasses.replace(
        invalid_source,
        anchors=(broken_anchor,),
    )
    mixed_claim = dataclasses.replace(
        claim,
        citation_links=claim.citation_links
        + (
            ClaimEvidenceLink(
                source_id=invalid_source.id,
                anchor_id=broken_anchor.id,
                purpose="DECISION",
                relation="SUPPORTS",
                coverage="FULL",
            ),
        ),
    )
    mixed_template = dataclasses.replace(
        template,
        blocks=(template.blocks[0], mixed_claim) + template.blocks[2:],
    )
    mutated = dataclasses.replace(
        raw,
        sources=tuple(
            broken_source if source.id == invalid_source.id else source
            for source in raw.sources
        ),
        response_templates=(mixed_template,) + raw.response_templates[1:],
    )
    validated = validate_dataset(mutated)
    assert isinstance(validated, Ok)

    result = citations_for_claim(mixed_claim.claim_id, validated.value)

    assert isinstance(result, Err)
    assert result.error.code == "SOURCE_DATA_ERROR"
    assert result.error.display_text == SOURCE_DATA_ERROR_TEXT
    valid_citations = result.error.valid_citations
    assert valid_citations[0].source_id == valid_link.source_id
    invalid_references = result.error.invalid_references
    assert [reference.reason for reference in invalid_references] == [
        "SOURCE_NOT_FOUND"
    ]


def test_anchor_bounds_failure_is_isolated_as_source_error() -> None:
    raw = build_mock_dataset()
    claim = _first_claim(raw)
    source = next(
        source
        for source in raw.sources
        if source.id == claim.citation_links[0].source_id
    )
    out_of_bounds = dataclasses.replace(
        source.anchors[0],
        end_offset=len(source.body) + 1,
    )
    mutated = dataclasses.replace(
        raw,
        sources=tuple(
            dataclasses.replace(source, anchors=(out_of_bounds,))
            if candidate.id == source.id
            else candidate
            for candidate in raw.sources
        ),
    )
    validated = validate_dataset(mutated)
    assert isinstance(validated, Ok)

    result = citations_for_claim(claim.claim_id, validated.value)

    assert isinstance(result, Err)
    assert result.error.display_text == SOURCE_DATA_ERROR_TEXT
    assert result.error.invalid_references[0].reason == "SOURCE_NOT_FOUND"


def test_runtime_duplicate_source_id_is_not_resolved_arbitrarily() -> None:
    dataset = _validated_dataset()
    claim = _claim(dataset.response_templates[0].blocks)
    source = next(
        source
        for source in dataset.sources
        if source.id == claim.citation_links[0].source_id
    )
    # The normal validator rejects duplicate IDs. Mutate only this test object
    # to prove the citation boundary also enforces exact-one resolution.
    object.__setattr__(dataset, "sources", dataset.sources + (source,))

    result = citations_for_claim(claim.claim_id, dataset)

    assert isinstance(result, Err)
    assert result.error.invalid_references[0].reason == "DUPLICATE_SOURCE_ID"
    assert result.error.valid_citations == ()
