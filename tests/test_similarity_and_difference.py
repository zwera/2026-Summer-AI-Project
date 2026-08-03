"""``domain.similarity_and_difference`` 단위 테스트 (task 10.1).

요구사항 8.1~8.11을 검증한다.

- ``similarity_warning``이 ``[0,50)``·``[50,80)``·``[80,100]`` 구간 각각에 고정된
  ``SimilarityWarningPolicyRecord``를 선택하는지(8.7~8.9).
- ``order_fact_differences``가 ``could_change_conclusion=True``를 먼저 배치하고, 각
  그룹 안에서는 ``(display_priority, id)`` 순으로 안정 정렬하는지(8.10).
- ``resolve_fact_difference_display``가 ``user_fact``·``case_fact``·
  ``conclusion_impact``의 ``None`` 필드만 독립적으로 `확인 필요`로 치환하는지(8.4~8.6).

fixture(``fixtures.mock_dataset``)의 실제 ``SimilarityWarningPolicyRecord``·
``DisplayPolicyRecord`` 목록을 그대로 사용해 실제 데이터와 일치하는지 확인한다.
"""

from __future__ import annotations

from typing import Optional

import pytest

from data.models_dataset import MockDataset
from data.models_fact_difference import FactDifference
from domain.ids import SourceId
from domain.similarity_and_difference import (
    NoMatchingSimilarityWarningError,
    order_fact_differences,
    resolve_fact_difference_display,
    similarity_warning,
)
from fixtures.mock_dataset import build_mock_dataset


@pytest.fixture(scope="module")
def dataset() -> MockDataset:
    return build_mock_dataset()


class TestSimilarityWarning:
    def test_high_band_is_inclusive_both_ends(self, dataset: MockDataset) -> None:
        policies = dataset.display_policies.similarity_warnings
        assert similarity_warning(80, policies).key == "HIGH"
        assert similarity_warning(100, policies).key == "HIGH"
        assert similarity_warning(90, policies).key == "HIGH"

    def test_medium_band_excludes_upper_bound(self, dataset: MockDataset) -> None:
        policies = dataset.display_policies.similarity_warnings
        assert similarity_warning(50, policies).key == "MEDIUM"
        assert similarity_warning(79.999, policies).key == "MEDIUM"

    def test_low_band_covers_zero_to_just_below_fifty(self, dataset: MockDataset) -> None:
        policies = dataset.display_policies.similarity_warnings
        assert similarity_warning(0, policies).key == "LOW"
        assert similarity_warning(49.999, policies).key == "LOW"

    def test_boundary_between_medium_and_high_is_exclusive_for_medium(
        self, dataset: MockDataset
    ) -> None:
        policies = dataset.display_policies.similarity_warnings
        assert similarity_warning(79.999, policies).key == "MEDIUM"
        assert similarity_warning(80, policies).key == "HIGH"

    def test_returned_text_matches_fixed_wording(self, dataset: MockDataset) -> None:
        policies = dataset.display_policies.similarity_warnings
        assert similarity_warning(90, policies).text == "높은 유사도 — 핵심 차이 확인 필요"
        assert (
            similarity_warning(60, policies).text
            == "중간 유사도 — 직접 적용 전 사실관계 재검토 필요"
        )
        assert similarity_warning(10, policies).text == "낮은 유사도 — 결론 근거로 사용 금지"

    def test_no_matching_band_raises(self, dataset: MockDataset) -> None:
        policies = dataset.display_policies.similarity_warnings
        with pytest.raises(NoMatchingSimilarityWarningError):
            similarity_warning(150, policies)
        with pytest.raises(NoMatchingSimilarityWarningError):
            similarity_warning(-1, policies)


def _difference(
    id_: str,
    could_change_conclusion: bool,
    display_priority: int,
    user_fact: Optional[str] = "user",
    case_fact: Optional[str] = "case",
    conclusion_impact: Optional[str] = "impact",
) -> FactDifference:
    return FactDifference(
        id=id_,
        dimension="체포 시점",
        user_fact=user_fact,
        case_fact=case_fact,
        conclusion_impact=conclusion_impact,
        could_change_conclusion=could_change_conclusion,
        display_priority=display_priority,
        source_ids=(SourceId("source-1"),),
    )


class TestOrderFactDifferences:
    def test_decisive_differences_come_before_non_decisive(self) -> None:
        non_decisive = _difference("d-non-decisive", False, display_priority=0)
        decisive = _difference("d-decisive", True, display_priority=99)

        ordered = order_fact_differences(90, [non_decisive, decisive])

        assert [d.id for d in ordered] == ["d-decisive", "d-non-decisive"]

    def test_within_same_group_sorted_by_display_priority_then_id(self) -> None:
        a = _difference("d-b", True, display_priority=2)
        b = _difference("d-a", True, display_priority=1)
        c = _difference("d-c", True, display_priority=2)

        ordered = order_fact_differences(90, [a, b, c])

        assert [d.id for d in ordered] == ["d-a", "d-b", "d-c"]

    def test_ordering_independent_of_score_band(self) -> None:
        decisive = _difference("d-decisive", True, display_priority=5)
        non_decisive = _difference("d-non-decisive", False, display_priority=0)

        for score in (10, 60, 90):
            ordered = order_fact_differences(score, [non_decisive, decisive])
            assert [d.id for d in ordered] == ["d-decisive", "d-non-decisive"]

    def test_empty_input_returns_empty_tuple(self) -> None:
        assert order_fact_differences(50, []) == ()


class TestResolveFactDifferenceDisplay:
    def test_no_null_fields_are_preserved_verbatim(self, dataset: MockDataset) -> None:
        placeholders = dataset.display_policies.placeholders
        difference = _difference("d-1", True, 0)

        display = resolve_fact_difference_display(difference, placeholders)

        assert display.user_fact == "user"
        assert display.case_fact == "case"
        assert display.conclusion_impact == "impact"

    def test_each_null_field_independently_becomes_confirmation_needed(
        self, dataset: MockDataset
    ) -> None:
        placeholders = dataset.display_policies.placeholders
        difference = _difference(
            "d-2", True, 0, user_fact=None, case_fact="case", conclusion_impact="impact"
        )

        display = resolve_fact_difference_display(difference, placeholders)

        assert display.user_fact == "확인 필요"
        assert display.case_fact == "case"
        assert display.conclusion_impact == "impact"

    def test_all_three_null_fields_all_become_confirmation_needed(
        self, dataset: MockDataset
    ) -> None:
        placeholders = dataset.display_policies.placeholders
        difference = _difference(
            "d-3", False, 0, user_fact=None, case_fact=None, conclusion_impact=None
        )

        display = resolve_fact_difference_display(difference, placeholders)

        assert display.user_fact == "확인 필요"
        assert display.case_fact == "확인 필요"
        assert display.conclusion_impact == "확인 필요"

    def test_non_null_fields_unaffected_by_sibling_null_fields(
        self, dataset: MockDataset
    ) -> None:
        placeholders = dataset.display_policies.placeholders
        difference = _difference(
            "d-4", False, 0, user_fact="user", case_fact=None, conclusion_impact="impact"
        )

        display = resolve_fact_difference_display(difference, placeholders)

        assert display.user_fact == "user"
        assert display.case_fact == "확인 필요"
        assert display.conclusion_impact == "impact"

    def test_other_fields_pass_through_unchanged(self, dataset: MockDataset) -> None:
        placeholders = dataset.display_policies.placeholders
        difference = _difference("d-5", True, 7)

        display = resolve_fact_difference_display(difference, placeholders)

        assert display.id == "d-5"
        assert display.dimension == "체포 시점"
        assert display.could_change_conclusion is True
        assert display.display_priority == 7
        assert display.source_ids == ("source-1",)
