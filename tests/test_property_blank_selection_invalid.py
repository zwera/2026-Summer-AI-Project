"""Property 28: 공백 선택의 무효성 (task 12.5).

Whitespace-only selections must remain in the selection-pending state.  The
server-side selection-review result therefore contains no claim outcomes; the
client can use that pending state to show its text-selection guidance.

**Validates: Requirements 9.12**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_selection import ReviewableClaim
from domain.ids import ClaimId
from domain.selection_review import is_selection_pending, review_selection


# ``str.strip()`` is the domain policy for whitespace-only selections.  This
# generator covers the empty string plus ordinary whitespace, tab, CR/LF, and
# Unicode space-separator characters.  Zero-width characters are intentionally
# excluded because Python's ``str.strip()`` treats them as non-whitespace.
_blank_selection_texts = st.lists(
    st.one_of(
        st.sampled_from((" ", "\t", "\r", "\n")),
        st.characters(whitelist_categories=("Zs",)),
    ),
    max_size=40,
).map("".join)


def _claim(claim_id: str, document_order: int) -> ReviewableClaim:
    """Create a valid reviewable claim independent of pending-state logic."""

    return ReviewableClaim(
        id=ClaimId(claim_id),
        text=f"독립 주장 {document_order}",
        document_order=document_order,
        evidence=(),
    )


# Feature: police-case-law-ai-bot
# Property 28: 공백 선택의 무효성
# **Validates: Requirements 9.12**
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(
    selected_text=_blank_selection_texts,
    selected_indexes=st.lists(
        st.integers(min_value=-2, max_value=4), min_size=1, max_size=20
    ),
)
def test_whitespace_only_selection_remains_pending_with_no_review_claims(
    selected_text: str, selected_indexes: list[int]
) -> None:
    """**Validates: Requirements 9.12**.

    Any blank selection is invalid even if the browser supplied valid,
    duplicate, or unknown overlapping claim IDs.  It must remain pending and
    return an empty review-result set instead of evaluating claims.
    """

    claims = (_claim("claim-0", 0), _claim("claim-1", 1))
    selected_claim_ids = tuple(
        ClaimId(f"claim-{index}") for index in selected_indexes
    )

    assert is_selection_pending(selected_text, selected_claim_ids, claims)

    result = review_selection(selected_text, selected_claim_ids, claims)

    assert result.selected_text == selected_text
    assert result.claims == ()
