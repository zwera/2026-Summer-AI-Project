"""Property 3: 법률 고지 정책의 표면 완전성 (task 16.2).

The surface generator covers every ``NoticeSurface`` value.  The reference
oracle is intentionally limited to Requirement 1.7: each supported surface
must require the exact legal-safety policy record, without synthesizing text.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from domain.notice_policy import NoticeSurface, notice_for
from fixtures.mock_dataset import build_mock_dataset


_ALL_SURFACES: tuple[NoticeSurface, ...] = (
    "APP_SHELL",
    "SEARCH_RESULTS",
    "MOCK_RESPONSE",
    "SOURCE_VIEWER",
    "REPORT_PREVIEW",
    "CLIPBOARD",
    "DOWNLOAD",
)
_POLICIES = build_mock_dataset().display_policies
_SAFETY_NOTICE_KEY = "LEGAL_SAFETY_NOTICE"


def _legal_safety_notice_id() -> str:
    """Resolve the fixture policy ID independently of ``notice_for``."""

    return next(
        record.id
        for record in _POLICIES.notices
        if record.key == _SAFETY_NOTICE_KEY
    )


# Feature: police-case-law-ai-bot
# Property 3: 법률 고지 정책의 표면 완전성
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(surface=st.sampled_from(_ALL_SURFACES))
def test_notice_surface_requires_exact_legal_safety_notice(
    surface: NoticeSurface,
) -> None:
    """**Validates: Requirements 1.7**.

    A mock response, source, or report presented on screen, copied, or
    downloaded must carry the fixture's exact legal-safety notice requirement.
    The policy must select its existing record ID rather than create a new
    notice string.
    """

    requirement = notice_for(surface, _POLICIES)
    safety_notice_id = _legal_safety_notice_id()

    assert requirement.include_safety_notice is True
    assert safety_notice_id in requirement.required_policy_record_ids
    assert requirement.required_policy_record_ids.count(safety_notice_id) == 1
