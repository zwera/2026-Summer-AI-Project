"""``domain.summary_projection.project_summary`` 단위 테스트 (task 8.1).

요구사항 5.1~5.9를 검증한다: 3줄/10줄/상세 요약의 구조 계약, 단계 무관 canonical 값
일관성, 최초 용어 설명 병기, 근거 없는 항목의 `근거 정보 없음` placeholder.
"""

from __future__ import annotations

import dataclasses

import pytest

from typing import Tuple

from data.models_case import CaseRecord
from data.models_common import DisplayPolicyRecord
from data.models_summary import DetailedSummarySection, SummaryLine
from data.validated_dataset import ValidatedDataset, validate_dataset
from domain.enums import SummaryLevel
from domain.result import Ok
from domain.summary_projection import (
    REQUIRED_SUMMARY_SECTION_KEYS,
    THREE_LINE_KEY_ORDER,
    SummaryStructureError,
    project_summary,
)
from fixtures.mock_dataset import build_mock_dataset


def _validated_dataset() -> ValidatedDataset:
    result = validate_dataset(build_mock_dataset())
    assert isinstance(result, Ok)
    return result.value


def _first_case() -> CaseRecord:
    return _validated_dataset().cases[0]


def _placeholders() -> Tuple[DisplayPolicyRecord, ...]:
    return _validated_dataset().display_policies.placeholders


class TestStructuralContract:
    def test_three_line_has_exact_three_keys_in_specified_order(self) -> None:
        case = _first_case()
        projection = project_summary(case.summaries, SummaryLevel.THREE_LINE, _placeholders())
        assert tuple(line.key for line in projection.lines) == THREE_LINE_KEY_ORDER
        assert len(projection.lines) == 3
        assert projection.detailed_sections == ()

    def test_ten_line_has_exactly_ten_lines_including_all_required_keys(self) -> None:
        case = _first_case()
        projection = project_summary(case.summaries, SummaryLevel.TEN_LINE, _placeholders())
        assert len(projection.lines) == 10
        present_keys = {line.key for line in projection.lines}
        assert REQUIRED_SUMMARY_SECTION_KEYS <= present_keys
        assert projection.detailed_sections == ()

    def test_detailed_includes_all_required_sections(self) -> None:
        case = _first_case()
        projection = project_summary(case.summaries, SummaryLevel.DETAILED, _placeholders())
        present_keys = {section.key for section in projection.detailed_sections}
        assert REQUIRED_SUMMARY_SECTION_KEYS <= present_keys
        assert projection.lines == ()

    def test_wrong_three_line_key_order_raises_structure_error(self) -> None:
        case = _first_case()
        reordered = (
            case.summaries.three_line[1],
            case.summaries.three_line[0],
            case.summaries.three_line[2],
        )
        bad_bundle = dataclasses.replace(case.summaries, three_line=reordered)
        with pytest.raises(SummaryStructureError):
            project_summary(bad_bundle, SummaryLevel.THREE_LINE, _placeholders())

    def test_missing_required_key_in_ten_line_raises_structure_error(self) -> None:
        case = _first_case()
        lines = list(case.summaries.ten_line)
        # 필수 key인 "법원 결론"을 다른 필수 key로 덮어써 누락 상태를 만든다.
        lines[3] = SummaryLine(
            key="사건 개요", text="중복 대체", direct_evidence=lines[3].direct_evidence
        )
        bad_bundle = dataclasses.replace(case.summaries, ten_line=tuple(lines))  # type: ignore[arg-type]
        with pytest.raises(SummaryStructureError):
            project_summary(bad_bundle, SummaryLevel.TEN_LINE, _placeholders())

    def test_missing_required_section_in_detailed_raises_structure_error(self) -> None:
        case = _first_case()
        truncated = case.summaries.detailed[:-1]
        bad_bundle = dataclasses.replace(case.summaries, detailed=truncated)
        with pytest.raises(SummaryStructureError):
            project_summary(bad_bundle, SummaryLevel.DETAILED, _placeholders())


class TestCanonicalInvariance:
    def test_canonical_fields_are_identical_across_all_three_levels(self) -> None:
        case = _first_case()
        placeholders = _placeholders()
        three = project_summary(case.summaries, SummaryLevel.THREE_LINE, placeholders)
        ten = project_summary(case.summaries, SummaryLevel.TEN_LINE, placeholders)
        detailed = project_summary(case.summaries, SummaryLevel.DETAILED, placeholders)

        for projection in (three, ten, detailed):
            assert projection.canonical_conclusion == case.summaries.canonical_conclusion
            assert (
                projection.canonical_legality_status
                == case.summaries.canonical_legality_status
            )
            assert (
                projection.canonical_instance_charge
                == case.summaries.canonical_instance_charge
            )
            assert (
                projection.canonical_instance_outcome
                == case.summaries.canonical_instance_outcome
            )


class TestEvidenceTraceabilityAndPlaceholder:
    def test_missing_text_is_replaced_with_no_evidence_placeholder(self) -> None:
        case = _first_case()
        lines = list(case.summaries.three_line)
        lines[1] = SummaryLine(key=lines[1].key, text=None, direct_evidence=())
        bad_bundle = dataclasses.replace(case.summaries, three_line=tuple(lines))  # type: ignore[arg-type]

        projection = project_summary(bad_bundle, SummaryLevel.THREE_LINE, _placeholders())

        no_evidence_line = next(line for line in projection.lines if line.key == lines[1].key)
        assert no_evidence_line.text == "근거 정보 없음"
        assert no_evidence_line.has_evidence is False

    def test_present_text_is_preserved_verbatim(self) -> None:
        case = _first_case()
        projection = project_summary(case.summaries, SummaryLevel.THREE_LINE, _placeholders())
        for original, resolved in zip(case.summaries.three_line, projection.lines):
            assert original.text is not None
            assert resolved.text == original.text
            assert resolved.has_evidence is True

    def test_field_term_explanations_are_filtered_to_visible_keys(self) -> None:
        case = _first_case()
        projection = project_summary(case.summaries, SummaryLevel.THREE_LINE, _placeholders())
        visible_keys = {line.key for line in projection.lines}
        for explanation in projection.field_term_explanations:
            assert explanation.first_occurrence_block_id in visible_keys
        # fixture의 최초 설명 위치는 "사건 개요"이며 3줄에 포함되므로 최소 1건 남아야 한다.
        assert projection.field_term_explanations

    def test_field_term_explanation_pairs_legal_term_with_field_expression(self) -> None:
        case = _first_case()
        projection = project_summary(case.summaries, SummaryLevel.THREE_LINE, _placeholders())
        for explanation in projection.field_term_explanations:
            assert explanation.legal_term
            assert explanation.field_expression

    def test_detailed_section_subsections_are_preserved(self) -> None:
        case = _first_case()
        section = DetailedSummarySection(
            key="사건 개요",
            text="본문",
            direct_evidence=(),
            subsections=(),
        )
        bad_bundle = dataclasses.replace(
            case.summaries, detailed=(section,) + case.summaries.detailed[1:]
        )
        projection = project_summary(bad_bundle, SummaryLevel.DETAILED, _placeholders())
        resolved_section = next(s for s in projection.detailed_sections if s.key == "사건 개요")
        assert resolved_section.subsections == ()
