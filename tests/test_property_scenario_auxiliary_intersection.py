"""Property 12: 시나리오와 보조 필터의 교집합 (task 7.3).

Generated metadata is projected onto a real immutable ``CaseRecord`` template.
The oracle is an independently expressed Boolean conjunction.
"""

from __future__ import annotations

from dataclasses import replace
from typing import FrozenSet, Optional, Tuple

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_case import CaseRecord
from domain.enums import PoliceScenario, TraditionalCaseArea
from domain.scenario_classification import filter_scenario_intersection
from fixtures.mock_dataset import build_mock_dataset


CaseMetadata = Tuple[
    FrozenSet[PoliceScenario], Optional[FrozenSet[TraditionalCaseArea]]
]

_SCENARIOS: Tuple[PoliceScenario, ...] = tuple(PoliceScenario)
_AREAS: Tuple[TraditionalCaseArea, ...] = tuple(TraditionalCaseArea)
_CASE_TEMPLATE = build_mock_dataset().cases[0]
_CASE_METADATA = st.lists(
    st.tuples(
        st.frozensets(st.sampled_from(_SCENARIOS), min_size=1),
        st.one_of(
            st.none(),
            st.frozensets(st.sampled_from(_AREAS), min_size=1),
        ),
    ),
    max_size=20,
).map(tuple)


def _ordered_scenarios(
    values: FrozenSet[PoliceScenario],
) -> Tuple[PoliceScenario, ...]:
    return tuple(scenario for scenario in _SCENARIOS if scenario in values)


def _ordered_areas(
    values: Optional[FrozenSet[TraditionalCaseArea]],
) -> Optional[Tuple[TraditionalCaseArea, ...]]:
    if values is None:
        return None
    return tuple(area for area in _AREAS if area in values)


def _cases_from_metadata(
    metadata: Tuple[CaseMetadata, ...],
) -> Tuple[CaseRecord, ...]:
    return tuple(
        replace(
            _CASE_TEMPLATE,
            id=f"property-case-{index}",  # type: ignore[arg-type]
            scenario_ids=_ordered_scenarios(scenarios),
            traditional_areas=_ordered_areas(areas),
        )
        for index, (scenarios, areas) in enumerate(metadata)
    )


# Feature: police-case-law-ai-bot
# Property 12:
# 시나리오와 보조 필터의 교집합
# **Validates: Requirements 4.10**
# ``print_blob=True`` prints a reproducible failing example.
# Hypothesis persists and shrinks the minimal counterexample locally.
@settings(max_examples=100, print_blob=True)
@given(
    metadata=_CASE_METADATA,
    scenario=st.sampled_from(_SCENARIOS),
    auxiliary=st.sampled_from(_AREAS),
)
def test_scenario_and_auxiliary_filter_returns_exact_set_intersection(
    metadata: Tuple[CaseMetadata, ...],
    scenario: PoliceScenario,
    auxiliary: TraditionalCaseArea,
) -> None:
    """Scenario and auxiliary selections return exactly cases satisfying both.

    **Validates: Requirements 4.10**
    """

    cases = _cases_from_metadata(metadata)
    expected_ids = {
        case.id
        for case in cases
        if scenario in case.scenario_ids
        and case.traditional_areas is not None
        and auxiliary in case.traditional_areas
    }

    result = filter_scenario_intersection(cases, scenario, auxiliary)

    assert {case.id for case in result} == expected_ids
    assert all(
        scenario in case.scenario_ids
        and case.traditional_areas is not None
        and auxiliary in case.traditional_areas
        for case in result
    )
