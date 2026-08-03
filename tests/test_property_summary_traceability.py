"""Property 15: 요약 설명·근거의 추적성과 안전 placeholder (task 8.4).

검증된 목업 fixture의 모든 판례·요약 단계와, 한 요약 항목을 근거 없음으로
표시하도록 변형한 경우를 생성한다. 현장 표현 설명은 fixture의 용어 대응에서만
유래해야 하고, 법원 결론·현장 경찰 핵심 포인트의 직접 근거는 유효한
source/anchor를 가리켜야 하며, 근거 없는 항목은 새 문구를 만들지 않고 표시 정책의
`근거 정보 없음`으로 표시되어야 한다.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from data.models_summary import (
    DetailedSummarySection,
    SummaryBundle,
    SummaryLine,
)
from data.models_source import ClaimEvidenceLink
from data.validated_dataset import ValidatedDataset
from domain.enums import SummaryLevel
from domain.summary_projection import (
    DisplayDetailedSummarySection,
    DisplaySummaryLine,
    project_summary,
)


_NO_EVIDENCE_KEY = "근거 정보 없음"
_TRACEABLE_KEYS = frozenset({"법원 결론", "현장 경찰 핵심 포인트"})


def _visible_items(
    bundle: SummaryBundle, level: SummaryLevel
) -> Sequence[SummaryLine]:
    if level is SummaryLevel.THREE_LINE:
        return bundle.three_line
    if level is SummaryLevel.TEN_LINE:
        return bundle.ten_line
    return bundle.detailed


def _without_evidence_at(
    bundle: SummaryBundle, level: SummaryLevel, index: int
) -> SummaryBundle:
    """선택한 표시 항목만 근거 없음 상태로 만든 구조 보존 변형."""

    if level is SummaryLevel.THREE_LINE:
        lines = list(bundle.three_line)
        source = lines[index]
        lines[index] = SummaryLine(source.key, None, ())
        return replace(
            bundle,
            three_line=tuple(lines),  # type: ignore[arg-type]
        )

    if level is SummaryLevel.TEN_LINE:
        lines = list(bundle.ten_line)
        source = lines[index]
        lines[index] = SummaryLine(source.key, None, ())
        return replace(bundle, ten_line=tuple(lines))  # type: ignore[arg-type]

    sections = list(bundle.detailed)
    source = sections[index]
    sections[index] = DetailedSummarySection(
        source.key,
        None,
        (),
        source.subsections,
    )
    return replace(bundle, detailed=tuple(sections))


def _display_items(
    level: SummaryLevel,
    projection_lines: Sequence[DisplaySummaryLine],
    projection_sections: Sequence[DisplayDetailedSummarySection],
) -> Sequence[DisplaySummaryLine]:
    if level is SummaryLevel.DETAILED:
        return projection_sections
    return projection_lines


def _assert_valid_direct_evidence(
    evidence: Sequence[ClaimEvidenceLink], dataset: ValidatedDataset
) -> None:
    """직접 근거가 clean source registry의 실제 anchor만 가리키는지 확인한다."""

    assert evidence
    for link in evidence:
        source = dataset.sources_by_id.get(link.source_id)
        assert source is not None
        assert any(anchor.id == link.anchor_id for anchor in source.anchors)


# Feature: police-case-law-ai-bot, Property 15:
# 요약 설명·근거의 추적성과 안전 placeholder
@settings(
    max_examples=100,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.data())
def test_summary_explanations_evidence_and_placeholders_are_traceable(
    validated_mock_dataset: ValidatedDataset,
    data: st.DataObject,
) -> None:
    """**Validates: Requirements 5.5, 5.6, 5.8, 5.9**

    The explanation pair is copied from a term-mapping fixture; conclusion and
    field-point evidence remain valid; and a missing item becomes only the
    configured no-evidence placeholder.
    """

    case = data.draw(
        st.sampled_from(validated_mock_dataset.cases),
        label="case",
    )
    level = data.draw(
        st.sampled_from(tuple(SummaryLevel)),
        label="summary_level",
    )
    source_items = _visible_items(case.summaries, level)
    missing_index = data.draw(
        st.integers(min_value=0, max_value=len(source_items) - 1),
        label="missing_summary_item_index",
    )

    projection = project_summary(
        case.summaries,
        level,
        validated_mock_dataset.display_policies.placeholders,
    )
    display_items = _display_items(
        level,
        projection.lines,
        projection.detailed_sections,
    )
    visible_keys = {item.key for item in display_items}

    mappings_by_field_expression = {
        mapping.field_expression: mapping
        for mapping in validated_mock_dataset.term_mappings
    }
    for explanation in projection.field_term_explanations:
        mapping = mappings_by_field_expression.get(
            explanation.field_expression
        )
        assert mapping is not None
        assert explanation.legal_term in mapping.legal_search_terms
        assert explanation.first_occurrence_block_id in visible_keys
        assert explanation.legal_term
        assert explanation.field_expression

    original_by_key = {
        item.key: item
        for item in source_items
    }
    for item in display_items:
        original = original_by_key[item.key]
        if item.key in _TRACEABLE_KEYS and original.text is not None:
            _assert_valid_direct_evidence(
                item.direct_evidence,
                validated_mock_dataset,
            )

    missing_bundle = _without_evidence_at(
        case.summaries,
        level,
        missing_index,
    )
    missing_projection = project_summary(
        missing_bundle,
        level,
        validated_mock_dataset.display_policies.placeholders,
    )
    missing_item = _display_items(
        level,
        missing_projection.lines,
        missing_projection.detailed_sections,
    )[missing_index]
    no_evidence_text = next(
        policy.text
        for policy in validated_mock_dataset.display_policies.placeholders
        if policy.key == _NO_EVIDENCE_KEY
    )

    assert missing_item.text == no_evidence_text
    assert missing_item.has_evidence is False
    assert missing_item.direct_evidence == ()
