"""Property 10: scenario-legality complete partition (task 7.2).

Generated case records cover multiple scenarios and all legality statuses.
For a selected scenario, the classifier must return a complete partition.
Mixed cases retain their action--court-judgment pairs.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from data.models_case import CaseRecord
from data.models_risk import ActionJudgment
from domain.enums import LegalityStatus, PoliceScenario
from domain.scenario_classification import partition_scenario_cases
from fixtures.mock_dataset import build_mock_dataset


_CASE_TEMPLATE = build_mock_dataset().cases[0]


@st.composite
def _scenario_cases(
    draw: st.DrawFn,
) -> tuple[CaseRecord, ...]:
    """Build valid-shaped immutable cases with unique IDs."""

    specifications = draw(
        st.lists(
            st.tuples(
                st.lists(
                    st.sampled_from(tuple(PoliceScenario)),
                    min_size=1,
                    max_size=3,
                    unique=True,
                ),
                st.sampled_from(tuple(LegalityStatus)),
                st.integers(min_value=1, max_value=3),
            ),
            min_size=1,
            max_size=16,
        )
    )

    cases: list[CaseRecord] = []
    for index, (scenarios, legality_status, action_count) in enumerate(
        specifications
    ):
        if legality_status is LegalityStatus.MIXED:
            court_finding = "AMBIGUOUS"
        else:
            court_finding = "LAWFUL"
        action_judgments = tuple(
            ActionJudgment(
                action_id=f"property-10-{index}-action-{action_index}",
                action_text=f"property action {action_index}",
                court_finding=court_finding,
                source_ids=_CASE_TEMPLATE.source_ids,
            )
            for action_index in range(action_count)
        )
        cases.append(
            replace(
                _CASE_TEMPLATE,
                id=f"property-10-case-{index}",  # type: ignore[arg-type]
                scenario_ids=tuple(scenarios),
                legality_status=legality_status,
                action_judgments=action_judgments,
            )
        )
    return tuple(cases)


# Feature: police-case-law-ai-bot, Property 10
# Scenario-legality complete partition
@settings(max_examples=100, derandomize=True)
@given(
    cases=_scenario_cases(),
    scenario=st.sampled_from(tuple(PoliceScenario)),
)
def test_scenario_legality_partition_is_complete_and_disjoint(
    cases: tuple[CaseRecord, ...], scenario: PoliceScenario
) -> None:
    """**Validates: Requirements 4.3, 4.4, 4.6, 4.8**."""

    partition = partition_scenario_cases(cases, scenario)
    expected_cases = tuple(
        case for case in cases if scenario in case.scenario_ids
    )

    lawful_ids = [case.id for case in partition.lawful]
    unlawful_ids = [case.id for case in partition.unlawful]
    mixed_ids = [entry.case.id for entry in partition.mixed]
    returned_ids = lawful_ids + unlawful_ids + mixed_ids

    # Requirements 4.3 and 4.4: each case has scenarios and one status.
    assert all(case.scenario_ids for case in cases)
    assert all(
        isinstance(case.legality_status, LegalityStatus) for case in cases
    )

    # Requirements 4.6 and 4.8: regions are disjoint and cover matches once.
    assert set(lawful_ids).isdisjoint(unlawful_ids)
    assert set(lawful_ids).isdisjoint(mixed_ids)
    assert set(unlawful_ids).isdisjoint(mixed_ids)
    assert Counter(returned_ids) == Counter(case.id for case in expected_cases)
    assert all(
        case.legality_status is LegalityStatus.LAWFUL
        for case in partition.lawful
    )
    assert all(
        case.legality_status is LegalityStatus.UNLAWFUL
        for case in partition.unlawful
    )
    assert all(
        entry.case.legality_status is LegalityStatus.MIXED
        for entry in partition.mixed
    )

    # Mixed cases keep every action--court-judgment pair unchanged.
    for entry in partition.mixed:
        assert entry.action_judgments == entry.case.action_judgments
