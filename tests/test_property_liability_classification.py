"""Property 16: 개인 책임 위험의 총 분류와 provenance (task 9.2).

Each generated case contains evidence for all four liability-risk axes.  The
oracle is independent from the implementation: it filters non-supporting
evidence, counts distinct supported statuses, and preserves first-seen valid
source IDs as provenance.
"""

from __future__ import annotations

from typing import Optional, Tuple, cast

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_common import SourceAnchorId
from data.models_risk import CivilStatus, ClassifiedEvidence
from domain.ids import SourceId
from domain.liability_classification import classify_evidence


_RISK_AXIS_STATUSES: Tuple[Tuple[str, Tuple[str, str]], ...] = (
    ("civil", ("국가배상_인정", "국가배상_기각")),
    ("abuse_of_authority", ("해당", "불해당")),
    ("custodial_violence", ("해당", "불해당")),
    ("discipline", ("징계_인정", "징계_불인정")),
)
_FALLBACK_STATUSES = {"정보_없음", "분류_불가"}


def _expected_classification(
    evidence: Tuple[ClassifiedEvidence[CivilStatus], ...],
) -> tuple[str, tuple[SourceId, ...]]:
    """Reference oracle for the Property 16 cardinality/provenance contract."""

    supported = [item for item in evidence if item.supports_status is not None]
    if not supported:
        return "정보_없음", ()

    source_ids: list[SourceId] = []
    for item in supported:
        if item.source_id not in source_ids:
            source_ids.append(item.source_id)

    statuses = {item.supports_status for item in supported}
    if len(statuses) == 1:
        return next(iter(statuses)), tuple(source_ids)
    return "분류_불가", tuple(source_ids)


@st.composite
def _all_risk_axis_evidence(
    draw: st.DrawFn,
) -> tuple[tuple[tuple[str, tuple[str, str]], tuple[ClassifiedEvidence[CivilStatus], ...]], ...]:
    """Generate empty, unanimous, conflicting, duplicate, and null evidence per axis."""

    generated_axes = []
    for axis in _RISK_AXIS_STATUSES:
        _, allowed_statuses = axis
        specifications = draw(
            st.lists(
                st.tuples(
                    st.sampled_from((*allowed_statuses, None)),
                    st.sampled_from(("source-a", "source-b", "source-c")),
                ),
                min_size=0,
                max_size=12,
            )
        )
        evidence = tuple(
            cast(
                ClassifiedEvidence[CivilStatus],
                ClassifiedEvidence(
                    source_id=SourceId(source_id),
                    anchor_id=SourceAnchorId(f"{source_id}-anchor-{index}"),
                    supports_status=cast(Optional[CivilStatus], status),
                ),
            )
            for index, (status, source_id) in enumerate(specifications)
        )
        generated_axes.append((axis, evidence))
    return tuple(generated_axes)


# Feature: police-case-law-ai-bot
# Property 16: 개인 책임 위험의 총 분류와 provenance
@settings(max_examples=100, derandomize=True)
@given(axis_evidence=_all_risk_axis_evidence())
def test_personal_liability_risk_classification_and_provenance(
    axis_evidence: tuple[
        tuple[
            tuple[str, tuple[str, str]],
            tuple[ClassifiedEvidence[CivilStatus], ...],
        ],
        ...,
    ],
) -> None:
    """**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.10, 6.11**.

    Every liability axis has exactly one allowed result. No supporting evidence
    yields ``정보_없음``; one supported status yields that status; conflicting
    statuses yield ``분류_불가``. Every non-empty result retains exactly the
    valid, de-duplicated source IDs used for its classification.
    """

    for (_, allowed_statuses), evidence in axis_evidence:
        actual_status, actual_source_ids = classify_evidence(evidence)
        expected_status, expected_source_ids = _expected_classification(evidence)

        assert actual_status in {*allowed_statuses, *_FALLBACK_STATUSES}
        assert actual_status == expected_status
        assert actual_source_ids == expected_source_ids
        if actual_status == "정보_없음":
            assert actual_source_ids == ()
        else:
            assert actual_source_ids
