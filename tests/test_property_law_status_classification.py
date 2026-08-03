"""Property 30: 법령 기준 상태의 완전하고 보수적인 분류 (task 11.4).

The generated input distinguishes comparable current and old applied versions
from every condition that makes a law-status comparison impossible.  Its
reference oracle is deliberately independent from ``classify_law_status``.
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_statute import AppliedStatuteRef, StatuteVersion
from domain.enums import LawBasisStatus
from domain.ids import SourceId, StatuteVersionId
from domain.law_status import classify_law_status


_VALIDITY_KINDS = (
    "current",
    "old",
    "missing_applied",
    "dangling_applied",
    "missing_revision_date",
    "missing_effective_date",
    "missing_current_version",
)
_INDETERMINATE_KINDS = frozenset(_VALIDITY_KINDS[2:])


def _version(
    version_id: StatuteVersionId,
    statute_id: str,
    *,
    revision_date: Optional[str] = "2020-01-01",
    effective_date: Optional[str] = "2020-01-15",
) -> StatuteVersion:
    return StatuteVersion(
        id=version_id,
        statute_id=statute_id,
        article="제1조",
        text_source_id=SourceId(f"source-{version_id}"),
        revision_date=revision_date,
        effective_date=effective_date,
    )


def _expected_status(kinds: Sequence[str]) -> LawBasisStatus:
    """Independent three-branch oracle from Property 30's contract."""

    if not kinds or any(kind in _INDETERMINATE_KINDS for kind in kinds):
        return LawBasisStatus.INDETERMINATE
    if all(kind == "current" for kind in kinds):
        return LawBasisStatus.CURRENT_LAW_BASIS
    return LawBasisStatus.OLD_LAW_BASIS


@st.composite
def _law_status_inputs(
    draw: st.DrawFn,
) -> tuple[
    tuple[str, ...],
    tuple[AppliedStatuteRef, ...],
    Mapping[StatuteVersionId, StatuteVersion],
    Mapping[str, Optional[StatuteVersionId]],
]:
    """Generate independent current/old/incomparable statute-reference sets."""

    kinds = tuple(
        draw(st.lists(st.sampled_from(_VALIDITY_KINDS), max_size=12))
    )
    statutes: dict[StatuteVersionId, StatuteVersion] = {}
    current_version_ids: dict[str, Optional[StatuteVersionId]] = {}
    applied: list[AppliedStatuteRef] = []

    for index, kind in enumerate(kinds):
        statute_id = f"statute-{index}"
        version_id = StatuteVersionId(f"version-{index}")
        applied.append(
            AppliedStatuteRef(
                citation_label=f"법령 {index} 제1조",
                statute_version_id=(
                    None if kind == "missing_applied" else version_id
                ),
            )
        )

        if kind == "dangling_applied" or kind == "missing_applied":
            continue

        statutes[version_id] = _version(
            version_id,
            statute_id,
            revision_date=(
                None if kind == "missing_revision_date" else "2020-01-01"
            ),
            effective_date=(
                None if kind == "missing_effective_date" else "2020-01-15"
            ),
        )
        if kind == "current":
            current_version_ids[statute_id] = version_id
        elif kind == "missing_current_version":
            current_version_ids[statute_id] = None
        else:
            current_version_ids[statute_id] = StatuteVersionId(
                f"current-{index}"
            )

    return (
        kinds,
        tuple(applied),
        statutes,
        current_version_ids,
    )


# Feature: police-case-law-ai-bot
# Property 30: 법령 기준 상태의 완전하고 보수적인 분류
@settings(max_examples=100, derandomize=True)
@given(inputs=_law_status_inputs())
def test_law_basis_status_is_complete_and_conservative(
    inputs: tuple[
        tuple[str, ...],
        tuple[AppliedStatuteRef, ...],
        Mapping[StatuteVersionId, StatuteVersion],
        Mapping[str, Optional[StatuteVersionId]],
    ],
) -> None:
    """**Validates: Requirements 10.5, 10.6, 10.7, 10.8, 10.11**.

    All comparable references that match their statute's current version are
    current-law; any comparable old version makes the status old-law.  Empty,
    missing, or dangling applied references and missing comparison data are
    always indeterminate and are never inferred as current or old.
    """

    kinds, applied, statutes, current_version_ids = inputs

    actual = classify_law_status(applied, statutes, current_version_ids)
    expected = _expected_status(kinds)

    assert actual in set(LawBasisStatus)
    assert actual is expected
    if any(kind in _INDETERMINATE_KINDS for kind in kinds) or not kinds:
        assert actual is LawBasisStatus.INDETERMINATE
