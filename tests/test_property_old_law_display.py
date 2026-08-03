"""Property 31: 구법 판례 표시의 완전성 (task 11.5).

유효하게 ``구법_기준``으로 분류되는 모든 판례 projection은 ``구법 기준``
배지와 적용 법조문 fixture의 개정 내용을 함께 포함해야 한다.
"""

from __future__ import annotations

from typing import Mapping, Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_statute import AppliedStatuteRef, StatuteVersion
from domain.enums import LawBasisStatus
from domain.ids import SourceId, StatuteVersionId
from domain.law_status import classify_law_status, old_law_basis_display


@st.composite
def _valid_old_law_case(
    draw: st.DrawFn,
) -> Tuple[
    Tuple[AppliedStatuteRef, ...],
    Mapping[StatuteVersionId, StatuteVersion],
    Mapping[str, StatuteVersionId],
]:
    """하나 이상 구법 버전과 개정 설명을 가진 비교 가능한 법령 조합을 만든다."""

    summaries = draw(
        st.lists(
            st.text(min_size=1, max_size=40),
            min_size=1,
            max_size=12,
        )
    )
    applied: list[AppliedStatuteRef] = []
    statutes: dict[StatuteVersionId, StatuteVersion] = {}
    current_version_ids: dict[str, StatuteVersionId] = {}

    for index, summary in enumerate(summaries):
        statute_id = f"property-31-statute-{index}"
        old_id = StatuteVersionId(  # type: ignore[arg-type]
            f"property-31-old-{index}"
        )
        current_id = StatuteVersionId(  # type: ignore[arg-type]
            f"property-31-current-{index}"
        )
        old_source_id = SourceId(  # type: ignore[arg-type]
            f"property-31-source-old-{index}"
        )
        current_source_id = SourceId(  # type: ignore[arg-type]
            f"property-31-source-current-{index}"
        )
        old_version = StatuteVersion(
            id=old_id,
            statute_id=statute_id,
            article="제1조",
            text_source_id=old_source_id,
            revision_date="2020-01-01",
            effective_date="2020-01-15",
            revision_summary=summary,
        )
        current_version = StatuteVersion(
            id=current_id,
            statute_id=statute_id,
            article="제1조",
            text_source_id=current_source_id,
            revision_date="2024-01-01",
            effective_date="2024-01-15",
        )
        applied.append(
            AppliedStatuteRef(
                citation_label=f"법령 {index} 제1조",
                statute_version_id=old_id,
            )
        )
        statutes[old_id] = old_version
        statutes[current_id] = current_version
        current_version_ids[statute_id] = current_id

    return tuple(applied), statutes, current_version_ids


def _expected_summaries(
    applied: Tuple[AppliedStatuteRef, ...],
    statutes: Mapping[StatuteVersionId, StatuteVersion],
) -> Tuple[str, ...]:
    """Fixture 개정 내용을 문서 순서·중복 제거 규칙으로 독립적으로 수집한다."""

    seen: set[str] = set()
    expected: list[str] = []
    for reference in applied:
        assert reference.statute_version_id is not None
        summary = statutes[reference.statute_version_id].revision_summary
        assert summary is not None
        if summary not in seen:
            seen.add(summary)
            expected.append(summary)
    return tuple(expected)


# Feature: police-case-law-ai-bot, Property 31: 구법 판례 표시의 완전성
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(case_data=_valid_old_law_case())
def test_old_law_case_projection_includes_badge_and_fixture_revision_summaries(
    case_data: Tuple[
        Tuple[AppliedStatuteRef, ...],
        Mapping[StatuteVersionId, StatuteVersion],
        Mapping[str, StatuteVersionId],
    ],
) -> None:
    """**Validates: Requirements 10.10**.

    All generated applied versions are older than their corresponding current
    versions, so their valid classification must be old-law. The display must
    expose the fixed badge and exactly the related fixture revision summaries.
    """

    applied, statutes, current_version_ids = case_data
    status = classify_law_status(applied, statutes, current_version_ids)

    assert status is LawBasisStatus.OLD_LAW_BASIS

    display = old_law_basis_display(status, applied, statutes)

    assert display is not None
    assert display.badge_label == "구법 기준"
    assert display.revision_summaries == _expected_summaries(applied, statutes)
