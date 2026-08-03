"""Property 9: 인용의 완전·고유 직접 출처와 source ID 유일성 (task 6.3).

응답 claim의 직접 근거와 참고 근거, 반복된 인용 링크를 생성해 response
projection이 직접 근거 ``(source_id, anchor_id)``를 빠짐없이 한 번씩만
보존하는지 검증한다. 또한 런타임 source registry에 단일 중복 source ID를
주입해 citation 경계가 임의의 record를 선택하지 않고 안전하게 격리하는지도
검증한다.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Tuple

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from data.models_source import (
    ClaimEvidenceLink,
    LegalClaimBlock,
    ResponseTemplate,
)
from data.validated_dataset import ValidatedDataset, validate_dataset
from domain.citations import citations_for_claim
from fixtures.mock_dataset import build_mock_dataset
from domain.response_projection import (
    ResponseLegalClaimProjection,
    project_response_template,
)
from domain.result import Err


def _legal_claims(dataset: ValidatedDataset) -> Tuple[LegalClaimBlock, ...]:
    return tuple(
        block
        for template in dataset.response_templates
        for block in template.blocks
        if isinstance(block, LegalClaimBlock)
    )


def _direct_pairs(
    links: Tuple[ClaimEvidenceLink, ...],
) -> set[tuple[object, object]]:
    return {
        (link.source_id, link.anchor_id)
        for link in links
        if link.purpose == "DECISION" and link.relation != "RELATED"
    }


# Feature: police-case-law-ai-bot, Property 9:
# 인용의 완전·고유 직접 출처와 source ID 유일성
@settings(
    max_examples=100,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.data(), duplicate_count=st.integers(min_value=0, max_value=5))
def test_direct_citations_are_complete_unique_and_source_ids_resolve_once(
    data: st.DataObject,
    duplicate_count: int,
) -> None:
    """**Validates: Requirements 3.8, 13.2**

    DIRECT citation pairs are the complete set of deciding non-related fixture
    links despite repeated links. Every projected source ID has exactly one
    registry record. A duplicate source-ID registry mutation is rejected at
    the citation boundary rather than being resolved arbitrarily.
    """

    validated_result = validate_dataset(build_mock_dataset())
    assert not isinstance(validated_result, Err)
    validated_mock_dataset = validated_result.value
    claim = data.draw(st.sampled_from(_legal_claims(validated_mock_dataset)))
    reference_link = ClaimEvidenceLink(
        source_id=claim.citation_links[0].source_id,
        anchor_id=claim.citation_links[0].anchor_id,
        purpose="REFERENCE",
        relation="RELATED",
        coverage="NONE",
    )
    expanded_links = (
        claim.citation_links
        + (claim.citation_links[0],) * duplicate_count
        + (reference_link,)
    )
    expanded_claim = replace(claim, citation_links=expanded_links)
    template = ResponseTemplate(
        id="property-9-template",
        blocks=(expanded_claim,),
    )

    projection = project_response_template(template)
    projected_claim = projection.blocks[0]
    assert isinstance(projected_claim, ResponseLegalClaimProjection)

    expected_pairs = _direct_pairs(expanded_links)
    actual_pairs = {
        (citation.source_id, citation.anchor_id)
        for citation in projected_claim.direct_citations
    }
    assert actual_pairs == expected_pairs
    assert len(projected_claim.direct_citations) == len(actual_pairs)
    assert all(
        citation.purpose == "DIRECT"
        for citation in projected_claim.direct_citations
    )
    assert all(
        sum(
            source.id == citation.source_id
            for source in validated_mock_dataset.sources
        )
        == 1
        for citation in projected_claim.direct_citations
    )

    source = next(
        source
        for source in validated_mock_dataset.sources
        if source.id == claim.citation_links[0].source_id
    )
    object.__setattr__(
        validated_mock_dataset,
        "sources",
        validated_mock_dataset.sources + (source,),
    )
    duplicate_result = citations_for_claim(
        claim.claim_id,
        validated_mock_dataset,
    )

    assert isinstance(duplicate_result, Err)
    assert (
        duplicate_result.error.invalid_references[0].reason
        == "DUPLICATE_SOURCE_ID"
    )
    assert duplicate_result.error.valid_citations == ()
