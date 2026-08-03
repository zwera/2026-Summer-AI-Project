"""Property 13: 요약 단계의 구조 계약 (task 8.2).

This property independently builds valid summary bundles. It then checks every
summary projection level against its required structural contract.
"""

from __future__ import annotations

from typing import Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_common import DisplayPolicyRecord
from data.models_summary import (
    DetailedSummarySection,
    SummaryBundle,
    SummaryLine,
)
from domain.enums import LegalityStatus, SummaryLevel
from domain.summary_projection import (
    REQUIRED_SUMMARY_SECTION_KEYS,
    THREE_LINE_KEY_ORDER,
    project_summary,
)


_SECTION_KEYS: Tuple[str, ...] = (
    "사건 개요",
    "주요 사실관계",
    "판례 쟁점",
    "법원 결론",
    "적용 법조문",
    "해당 심급 인정 죄명",
    "해당 심급 재판 결과",
    "현장 경찰 핵심 포인트",
)
_PLACEHOLDERS = (
    DisplayPolicyRecord(
        id="placeholder-no-evidence",
        kind="PLACEHOLDER",
        key="근거 정보 없음",
        text="근거 정보 없음",
    ),
)


def _line(key: str, text: str) -> SummaryLine:
    return SummaryLine(
        key=key,  # type: ignore[arg-type]
        text=text,
        direct_evidence=(),
    )


@st.composite
def valid_summary_bundle_strategy(draw: st.DrawFn) -> SummaryBundle:
    """Generate bundles satisfying Property 13 preconditions."""

    text = draw(st.text(min_size=1, max_size=20))
    extra_keys = draw(
        st.lists(st.sampled_from(_SECTION_KEYS), min_size=2, max_size=2)
    )
    ten_line_keys = list(_SECTION_KEYS) + extra_keys
    draw(st.randoms()).shuffle(ten_line_keys)

    three_line = tuple(_line(key, text) for key in THREE_LINE_KEY_ORDER)
    ten_line = tuple(_line(key, text) for key in ten_line_keys)
    detailed = tuple(
        DetailedSummarySection(
            key=key,  # type: ignore[arg-type]
            text=text,
            direct_evidence=(),
        )
        for key in _SECTION_KEYS
    )

    return SummaryBundle(
        canonical_conclusion="결론",
        canonical_legality_status=LegalityStatus.LAWFUL,
        canonical_instance_charge=None,
        canonical_instance_outcome=None,
        three_line=three_line,  # type: ignore[arg-type]
        ten_line=ten_line,  # type: ignore[arg-type]
        detailed=detailed,
        field_term_explanations=(),
    )


# Feature: police-case-law-ai-bot
# Property 13: 요약 단계의 구조 계약
@settings(max_examples=100, derandomize=True)
@given(bundle=valid_summary_bundle_strategy())
def test_summary_structure_contract(
    bundle: SummaryBundle,
) -> None:
    """**Validates: Requirements 5.2, 5.3, 5.4**

    The three-line form has prescribed ordered keys. The ten-line form has
    ten lines containing all required keys. The detailed form keeps required
    sections separate.
    """

    three_line = project_summary(
        bundle,
        SummaryLevel.THREE_LINE,
        _PLACEHOLDERS,
    )
    ten_line = project_summary(
        bundle,
        SummaryLevel.TEN_LINE,
        _PLACEHOLDERS,
    )
    detailed = project_summary(
        bundle,
        SummaryLevel.DETAILED,
        _PLACEHOLDERS,
    )

    assert tuple(line.key for line in three_line.lines) == THREE_LINE_KEY_ORDER
    assert len(three_line.lines) == 3
    assert three_line.detailed_sections == ()

    assert len(ten_line.lines) == 10
    assert REQUIRED_SUMMARY_SECTION_KEYS <= {
        line.key for line in ten_line.lines
    }
    assert ten_line.detailed_sections == ()

    assert detailed.lines == ()
    assert REQUIRED_SUMMARY_SECTION_KEYS <= {
        section.key for section in detailed.detailed_sections
    }
