"""Property 29: 법조문 날짜의 필드별 보존과 정보 없음 (task 11.3).

The generated revision and effective dates are independently nullable valid ISO
calendar dates.  The oracle is deliberately field-local so a missing date can
never replace, infer, or alter the other date field.
"""

from __future__ import annotations

from typing import Optional

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_statute import StatuteVersion
from domain.ids import SourceId, StatuteVersionId
from domain.law_status import statute_date_display


_NO_INFORMATION = "정보_없음"


def _expected_date_display(value: Optional[str]) -> str:
    """Independent field-level Property 29 oracle."""

    return _NO_INFORMATION if value is None else value


_iso_dates = st.dates().map(lambda value: value.isoformat())
_nullable_iso_dates = st.one_of(st.none(), _iso_dates)


# Feature: police-case-law-ai-bot
# Property 29: 법조문 날짜의 필드별 보존과 정보 없음
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(revision_date=_nullable_iso_dates, effective_date=_nullable_iso_dates)
def test_statute_dates_are_preserved_or_independently_marked_no_information(
    revision_date: Optional[str], effective_date: Optional[str]
) -> None:
    """**Validates: Requirements 10.2, 10.3**.

    Present fixture dates are returned exactly as stored.  Only the missing
    field is rendered as ``정보_없음``; the other date remains untouched.
    """

    version = StatuteVersion(
        id=StatuteVersionId("property-29-statute-version"),
        statute_id="property-29-statute",
        article="제1조",
        text_source_id=SourceId("property-29-source"),
        revision_date=revision_date,
        effective_date=effective_date,
    )

    display = statute_date_display(version)

    assert display.revision_date == _expected_date_display(revision_date)
    assert display.effective_date == _expected_date_display(effective_date)
