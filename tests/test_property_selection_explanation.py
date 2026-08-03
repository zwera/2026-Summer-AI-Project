"""Property 27: 선택 상세 설명의 fixture 충실성과 fallback (task 12.4).

선택 가능한 claim의 상세 설명은 fixture가 확인 가능한 내용을 가지면 그 법률 용어,
문맥, 판례 쟁점을 그대로 표시해야 한다. 대응 fixture가 없거나 설명 영역이 모두
비어 있으면, 시스템은 내용을 합성하지 않고 표시 정책의 fallback 문구와 fixture에
사전 정의된 추가 필요 정보만 표시해야 한다.
"""

from __future__ import annotations

from typing import Optional, Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_common import DisplayPolicyRecord
from data.models_selection import (
    LegalTermExplanationEntry,
    SelectionExplanationFixture,
)
from domain.ids import ClaimId
from domain.selection_review import resolve_selection_explanation


_STATUS_LABELS = (
    DisplayPolicyRecord(
        id="status-explanation-not-found",
        kind="STATUS_LABEL",
        key="EXPLANATION_NOT_FOUND",
        text="목업 자료에서 확인할 수 없음",
    ),
)
_NOT_FOUND_TEXT = "목업 자료에서 확인할 수 없음"
_NONEMPTY_TEXT = st.text(min_size=1, max_size=20)


# Feature: police-case-law-ai-bot
# Property 27: 선택 상세 설명의 fixture 충실성과 fallback
# **Validates: Requirements 9.9, 9.10**
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(
    has_fixture=st.booleans(),
    legal_term_specs=st.lists(
        st.tuples(_NONEMPTY_TEXT, _NONEMPTY_TEXT), max_size=4
    ),
    context=st.one_of(st.none(), _NONEMPTY_TEXT),
    issues=st.lists(_NONEMPTY_TEXT, max_size=4),
    additional_information_needed=st.lists(_NONEMPTY_TEXT, max_size=4),
)
def test_selection_explanation_is_fixture_faithful_or_uses_fallback(
    has_fixture: bool,
    legal_term_specs: list[tuple[str, str]],
    context: Optional[str],
    issues: list[str],
    additional_information_needed: list[str],
) -> None:
    """Fixture content is exact; unavailable meaning uses fallback data only.

    **Validates: Requirements 9.9, 9.10**
    """

    claim_id = ClaimId("claim-property-27")
    fixture = SelectionExplanationFixture(
        claim_id=claim_id,
        legal_terms=tuple(
            LegalTermExplanationEntry(
                term=term, explanation=explanation
            )
            for term, explanation in legal_term_specs
        ),
        context=context,
        issues=tuple(issues),
        additional_information_needed=tuple(additional_information_needed),
    )
    explanations: Tuple[SelectionExplanationFixture, ...] = (
        (fixture,) if has_fixture else ()
    )

    display = resolve_selection_explanation(
        claim_id, explanations, _STATUS_LABELS
    )
    confirmable = bool(
        fixture.legal_terms or fixture.context is not None or fixture.issues
    )

    if has_fixture and confirmable:
        assert display.found is True
        assert display.legal_terms == fixture.legal_terms
        assert display.context == fixture.context
        assert display.issues == fixture.issues
        assert (
            display.additional_information_needed
            == fixture.additional_information_needed
        )
        assert display.not_found_text is None
    else:
        assert display.found is False
        assert display.legal_terms == ()
        assert display.context is None
        assert display.issues == ()
        assert display.not_found_text == _NOT_FOUND_TEXT
        expected_additional = (
            fixture.additional_information_needed if has_fixture else ()
        )
        assert display.additional_information_needed == expected_additional
