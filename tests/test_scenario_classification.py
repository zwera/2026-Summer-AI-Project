"""``domain.scenario_classification`` 단위·속성 테스트 (task 7.1).

요구사항 4.2, 4.3, 4.4, 4.6, 4.8, 4.10, 4.12를 검증한다.

- 시나리오별 적법/위법/판단_혼재 partition이 서로소이고 완전한지(4.6, 4.8, design.md
  Property 10).
- 판단_혼재 판례의 행동-법원 판단 쌍이 그대로 보존되는지(4.10).
- ``filter_scenario_intersection``이 시나리오∧보조_필터의 순수 교집합만 반환하는지(4.12),
  그리고 ``traditional_areas``가 없는 판례가 보조_필터 지정 시 제외되는지.

fixture(``fixtures.mock_dataset``)에는 아직 판단_혼재 판례가 없으므로(요구사항 4.9는
적법·위법만 요구), 판단_혼재 partition 분기는 ``dataclasses.replace``로 테스트 전용
판례를 구성해 검증한다. ``fixtures/mock_dataset.py``는 수정하지 않는다.
"""

from __future__ import annotations

import dataclasses

import pytest

from data.models_case import CaseRecord
from data.models_risk import ActionJudgment
from domain.enums import LegalityStatus, PoliceScenario, TraditionalCaseArea
from domain.scenario_classification import (
    MixedCaseJudgments,
    filter_scenario_intersection,
    partition_scenario_cases,
)
from fixtures.mock_dataset import build_mock_dataset


@pytest.fixture(scope="module")
def dataset_cases() -> tuple[CaseRecord, ...]:
    return build_mock_dataset().cases


def _mixed_variant(case: CaseRecord) -> CaseRecord:
    """기존 판례를 복제해 판단_혼재 상태와 두 번째 행동-법원 판단을 추가한 테스트용 판례."""

    second_action = ActionJudgment(
        action_id=f"{case.id}-action-2",
        action_text="같은 판례 안의 또 다른 경찰 행위",
        court_finding="AMBIGUOUS",
        source_ids=case.source_ids,
    )
    return dataclasses.replace(
        case,
        id=f"{case.id}-mixed-variant",  # type: ignore[arg-type]
        legality_status=LegalityStatus.MIXED,
        action_judgments=case.action_judgments + (second_action,),
    )


class TestPartitionScenarioCases:
    def test_every_scenario_partition_is_disjoint_and_complete(
        self, dataset_cases: tuple[CaseRecord, ...]
    ) -> None:
        """4.6/4.8: 각 시나리오에서 매칭 판례 전체가 세 집합에 정확히 한 번씩만 나타나야 한다."""

        for scenario in PoliceScenario:
            partition = partition_scenario_cases(dataset_cases, scenario)

            lawful_ids = {c.id for c in partition.lawful}
            unlawful_ids = {c.id for c in partition.unlawful}
            mixed_ids = {m.case.id for m in partition.mixed}

            # 서로소.
            assert lawful_ids.isdisjoint(unlawful_ids)
            assert lawful_ids.isdisjoint(mixed_ids)
            assert unlawful_ids.isdisjoint(mixed_ids)

            expected_matching_ids = {
                c.id for c in dataset_cases if scenario in c.scenario_ids
            }
            # 완전성: 세 집합의 합집합 == 매칭되는 판례 전체.
            assert lawful_ids | unlawful_ids | mixed_ids == expected_matching_ids

            # fixture에는 적법·위법 각 1건 이상 존재(요구사항 4.9).
            assert lawful_ids
            assert unlawful_ids

    def test_partition_matches_only_cases_whose_scenario_ids_contain_scenario(
        self, dataset_cases: tuple[CaseRecord, ...]
    ) -> None:
        scenario = PoliceScenario.FLAGRANT_OFFENDER_ARREST
        partition = partition_scenario_cases(dataset_cases, scenario)

        all_returned = list(partition.lawful) + list(partition.unlawful) + [
            m.case for m in partition.mixed
        ]
        for case in all_returned:
            assert scenario in case.scenario_ids

        non_matching = [c for c in dataset_cases if scenario not in c.scenario_ids]
        returned_ids = {c.id for c in all_returned}
        for case in non_matching:
            assert case.id not in returned_ids

    def test_mixed_case_preserves_action_judgment_pairs_as_structured_list(
        self, dataset_cases: tuple[CaseRecord, ...]
    ) -> None:
        """4.10: 판단_혼재 판례는 각 행동-법원 판단 쌍을 별도 항목으로 보존해야 한다."""

        base_case = dataset_cases[0]
        scenario = base_case.scenario_ids[0]
        mixed_case = _mixed_variant(base_case)
        cases = (mixed_case,)

        partition = partition_scenario_cases(cases, scenario)

        assert partition.lawful == ()
        assert partition.unlawful == ()
        assert len(partition.mixed) == 1

        mixed_entry = partition.mixed[0]
        assert isinstance(mixed_entry, MixedCaseJudgments)
        assert mixed_entry.case.id == mixed_case.id
        # 두 행동-법원 판단 쌍이 모두, 그리고 정확히 한 번씩 보존되어야 한다.
        assert mixed_entry.action_judgments == mixed_case.action_judgments
        assert len(mixed_entry.action_judgments) == 2
        action_ids = [aj.action_id for aj in mixed_entry.action_judgments]
        assert len(action_ids) == len(set(action_ids))

    def test_case_belonging_to_multiple_scenarios_appears_in_each_scenarios_partition(
        self, dataset_cases: tuple[CaseRecord, ...]
    ) -> None:
        """4.3: 판례가 여러 시나리오에 속하면 각 시나리오의 partition에 나타날 수 있다."""

        base_case = dataset_cases[0]
        other_scenario = next(
            s for s in PoliceScenario if s not in base_case.scenario_ids
        )
        multi_scenario_case = dataclasses.replace(
            base_case,
            id=f"{base_case.id}-multi",  # type: ignore[arg-type]
            scenario_ids=base_case.scenario_ids + (other_scenario,),
        )
        cases = (multi_scenario_case,)

        first_partition = partition_scenario_cases(cases, base_case.scenario_ids[0])
        second_partition = partition_scenario_cases(cases, other_scenario)

        first_ids = {c.id for c in first_partition.lawful + first_partition.unlawful}
        second_ids = {c.id for c in second_partition.lawful + second_partition.unlawful}
        assert multi_scenario_case.id in first_ids
        assert multi_scenario_case.id in second_ids


class TestFilterScenarioIntersection:
    def test_scenario_only_matches_same_set_as_partition_union(
        self, dataset_cases: tuple[CaseRecord, ...]
    ) -> None:
        scenario = PoliceScenario.DUI_CHECKPOINT
        result = filter_scenario_intersection(dataset_cases, scenario)
        partition = partition_scenario_cases(dataset_cases, scenario)
        expected_ids = {c.id for c in partition.lawful + partition.unlawful} | {
            m.case.id for m in partition.mixed
        }
        assert {c.id for c in result} == expected_ids

    def test_auxiliary_filter_returns_only_cases_matching_both_conditions(
        self, dataset_cases: tuple[CaseRecord, ...]
    ) -> None:
        """4.12: 두 조건을 모두 충족하는 판례의 교집합만 반환해야 한다."""

        base_case = dataset_cases[0]
        scenario = base_case.scenario_ids[0]
        area = TraditionalCaseArea.CRIMINAL

        matching_case = dataclasses.replace(
            base_case,
            id=f"{base_case.id}-with-area",  # type: ignore[arg-type]
            traditional_areas=(area,),
        )
        non_matching_area_case = dataclasses.replace(
            base_case,
            id=f"{base_case.id}-other-area",  # type: ignore[arg-type]
            traditional_areas=(TraditionalCaseArea.CIVIL,),
        )
        non_matching_scenario_case = dataclasses.replace(
            matching_case,
            id=f"{base_case.id}-other-scenario",  # type: ignore[arg-type]
            scenario_ids=tuple(s for s in PoliceScenario if s != scenario)[:1],
        )
        cases = (matching_case, non_matching_area_case, non_matching_scenario_case)

        result = filter_scenario_intersection(cases, scenario, area)

        assert {c.id for c in result} == {matching_case.id}

    def test_auxiliary_filter_excludes_case_with_no_traditional_areas(
        self, dataset_cases: tuple[CaseRecord, ...]
    ) -> None:
        """traditional_areas가 None인 판례는 보조_필터 지정 시 제외되어야 한다."""

        base_case = dataset_cases[0]
        scenario = base_case.scenario_ids[0]
        assert base_case.traditional_areas is None

        result = filter_scenario_intersection(
            (base_case,), scenario, TraditionalCaseArea.CRIMINAL
        )

        assert result == ()

    def test_no_auxiliary_filter_behaves_like_scenario_only_match(
        self, dataset_cases: tuple[CaseRecord, ...]
    ) -> None:
        scenario = PoliceScenario.MIRANDA_WARNING
        with_none = filter_scenario_intersection(dataset_cases, scenario, None)
        without_arg = filter_scenario_intersection(dataset_cases, scenario)
        assert {c.id for c in with_none} == {c.id for c in without_arg}
