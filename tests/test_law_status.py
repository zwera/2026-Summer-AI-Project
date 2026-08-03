"""``domain.law_status`` 단위 테스트 (task 11.1).

요구사항 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.10, 10.11을 검증한다.

- ``classify_law_status``가 현행법_기준/구법_기준/법령_상태_판별불가를 보수적으로
  판정하는지(10.5~10.8, 10.11).
- ``statute_date_display``가 개정일·시행일 누락 필드만 개별적으로 ``정보_없음``으로
  대체하는지(10.2, 10.3).
- ``old_law_basis_display``가 구법_기준 판례에만 배지·개정 설명을 연결하는지(10.10).

Property 기반 테스트(Property 29~31)는 별도 태스크(11.3~11.5)의 책임이며, 이 테스트는
개별 예시와 경계 사례만 다룬다.
"""

from __future__ import annotations

from typing import Mapping, Optional

import pytest

from domain.enums import LawBasisStatus
from domain.ids import SourceId, StatuteVersionId
from domain.law_status import (
    classify_law_status,
    old_law_basis_display,
    statute_date_display,
)
from data.models_statute import AppliedStatuteRef, StatuteVersion


def _version(
    version_id: str,
    statute_id: str,
    *,
    revision_date: Optional[str] = "2020-01-01",
    effective_date: Optional[str] = "2020-01-15",
    revision_summary: Optional[str] = None,
) -> StatuteVersion:
    return StatuteVersion(
        id=StatuteVersionId(version_id),  # type: ignore[arg-type]
        statute_id=statute_id,
        article="제1조",
        text_source_id=SourceId("source-1"),  # type: ignore[arg-type]
        revision_date=revision_date,
        effective_date=effective_date,
        revision_summary=revision_summary,
    )


def _applied(version_id: Optional[str]) -> AppliedStatuteRef:
    return AppliedStatuteRef(
        citation_label="형사소송법 제1조",
        statute_version_id=StatuteVersionId(version_id) if version_id is not None else None,  # type: ignore[arg-type]
    )


class TestClassifyLawStatus:
    def test_empty_applied_is_indeterminate(self) -> None:
        assert classify_law_status([], {}, {}) is LawBasisStatus.INDETERMINATE

    def test_all_applied_equal_current_version_is_current_law_basis(self) -> None:
        version = _version("v-current", "statute-A")
        statutes: Mapping[StatuteVersionId, StatuteVersion] = {version.id: version}
        current_ids = {"statute-A": version.id}

        result = classify_law_status([_applied("v-current")], statutes, current_ids)

        assert result is LawBasisStatus.CURRENT_LAW_BASIS

    def test_applied_older_than_current_version_is_old_law_basis(self) -> None:
        old_version = _version("v-old", "statute-A")
        current_version = _version("v-current", "statute-A")
        statutes: Mapping[StatuteVersionId, StatuteVersion] = {
            old_version.id: old_version,
            current_version.id: current_version,
        }
        current_ids = {"statute-A": current_version.id}

        result = classify_law_status([_applied("v-old")], statutes, current_ids)

        assert result is LawBasisStatus.OLD_LAW_BASIS

    def test_missing_statute_version_id_is_indeterminate(self) -> None:
        result = classify_law_status([_applied(None)], {}, {})
        assert result is LawBasisStatus.INDETERMINATE

    def test_dangling_statute_version_id_is_indeterminate(self) -> None:
        result = classify_law_status([_applied("v-missing")], {}, {"statute-A": None})
        assert result is LawBasisStatus.INDETERMINATE

    def test_missing_revision_date_is_indeterminate(self) -> None:
        version = _version("v-1", "statute-A", revision_date=None)
        statutes: Mapping[StatuteVersionId, StatuteVersion] = {version.id: version}
        current_ids = {"statute-A": version.id}

        result = classify_law_status([_applied("v-1")], statutes, current_ids)

        assert result is LawBasisStatus.INDETERMINATE

    def test_missing_effective_date_is_indeterminate(self) -> None:
        version = _version("v-1", "statute-A", effective_date=None)
        statutes: Mapping[StatuteVersionId, StatuteVersion] = {version.id: version}
        current_ids = {"statute-A": version.id}

        result = classify_law_status([_applied("v-1")], statutes, current_ids)

        assert result is LawBasisStatus.INDETERMINATE

    def test_missing_current_version_at_as_of_is_indeterminate(self) -> None:
        version = _version("v-1", "statute-A")
        statutes: Mapping[StatuteVersionId, StatuteVersion] = {version.id: version}

        result = classify_law_status([_applied("v-1")], statutes, {"statute-A": None})

        assert result is LawBasisStatus.INDETERMINATE

    def test_mixed_current_and_indeterminate_applied_refs_is_indeterminate(self) -> None:
        """비교 가능한 참조가 있어도 하나라도 비교 불가면 전체가 판별불가여야 한다."""

        current_version = _version("v-current", "statute-A")
        statutes: Mapping[StatuteVersionId, StatuteVersion] = {current_version.id: current_version}
        current_ids = {"statute-A": current_version.id, "statute-B": None}

        result = classify_law_status(
            [_applied("v-current"), _applied(None)], statutes, current_ids
        )

        assert result is LawBasisStatus.INDETERMINATE


class TestStatuteDateDisplay:
    def test_both_dates_present_are_returned_as_is(self) -> None:
        version = _version("v-1", "statute-A", revision_date="2020-01-01", effective_date="2020-02-01")
        display = statute_date_display(version)
        assert display.revision_date == "2020-01-01"
        assert display.effective_date == "2020-02-01"

    def test_missing_revision_date_only_is_no_information(self) -> None:
        version = _version("v-1", "statute-A", revision_date=None, effective_date="2020-02-01")
        display = statute_date_display(version)
        assert display.revision_date == "정보_없음"
        assert display.effective_date == "2020-02-01"

    def test_missing_effective_date_only_is_no_information(self) -> None:
        version = _version("v-1", "statute-A", revision_date="2020-01-01", effective_date=None)
        display = statute_date_display(version)
        assert display.revision_date == "2020-01-01"
        assert display.effective_date == "정보_없음"

    def test_both_missing_are_both_no_information(self) -> None:
        version = _version("v-1", "statute-A", revision_date=None, effective_date=None)
        display = statute_date_display(version)
        assert display.revision_date == "정보_없음"
        assert display.effective_date == "정보_없음"


class TestOldLawBasisDisplay:
    def test_current_law_basis_returns_none(self) -> None:
        version = _version("v-1", "statute-A", revision_summary="개정 내용")
        statutes: Mapping[StatuteVersionId, StatuteVersion] = {version.id: version}
        result = old_law_basis_display(
            LawBasisStatus.CURRENT_LAW_BASIS, [_applied("v-1")], statutes
        )
        assert result is None

    def test_indeterminate_returns_none(self) -> None:
        version = _version("v-1", "statute-A", revision_summary="개정 내용")
        statutes: Mapping[StatuteVersionId, StatuteVersion] = {version.id: version}
        result = old_law_basis_display(
            LawBasisStatus.INDETERMINATE, [_applied("v-1")], statutes
        )
        assert result is None

    def test_old_law_basis_returns_badge_and_revision_summary(self) -> None:
        version = _version("v-1", "statute-A", revision_summary="2020년 개정: 요건 강화")
        statutes: Mapping[StatuteVersionId, StatuteVersion] = {version.id: version}

        result = old_law_basis_display(LawBasisStatus.OLD_LAW_BASIS, [_applied("v-1")], statutes)

        assert result is not None
        assert result.badge_label == "구법 기준"
        assert result.revision_summaries == ("2020년 개정: 요건 강화",)

    def test_missing_revision_summary_is_skipped_not_fabricated(self) -> None:
        version = _version("v-1", "statute-A", revision_summary=None)
        statutes: Mapping[StatuteVersionId, StatuteVersion] = {version.id: version}

        result = old_law_basis_display(LawBasisStatus.OLD_LAW_BASIS, [_applied("v-1")], statutes)

        assert result is not None
        assert result.revision_summaries == ()

    def test_duplicate_revision_summaries_are_deduplicated_in_document_order(self) -> None:
        version_a = _version("v-1", "statute-A", revision_summary="같은 개정 내용")
        version_b = _version("v-2", "statute-B", revision_summary="같은 개정 내용")
        statutes: Mapping[StatuteVersionId, StatuteVersion] = {
            version_a.id: version_a,
            version_b.id: version_b,
        }

        result = old_law_basis_display(
            LawBasisStatus.OLD_LAW_BASIS, [_applied("v-1"), _applied("v-2")], statutes
        )

        assert result is not None
        assert result.revision_summaries == ("같은 개정 내용",)
