"""Property 40: 전체 목업 RAG 관찰 결과의 결정성 (task 15.7)."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.mock_rag_state import advance_stage, initial_rag_state
from data.fixture_repository import FixtureRepository
from data.validated_dataset import ValidatedDataset
from domain.law_status import classify_law_status
from domain.liability_classification import (
    classify_action_badge,
    classify_evidence,
)
from domain.mock_search import run_mock_search
from domain.query_interpretation import (
    SupportedQueryInterpretation,
    interpret_query,
)
from domain.response_projection import project_response_template
from domain.result import Ok
from domain.similarity_and_difference import (
    order_fact_differences,
    similarity_warning,
)


def _canonical(value: Any) -> Any:
    """Serialize projections without object identity or DOM-only values."""

    if hasattr(value, "__dataclass_fields__"):
        return _canonical(asdict(value))
    if isinstance(value, dict):
        items = ((str(key), _canonical(item)) for key, item in value.items())
        return tuple(sorted(items))
    if isinstance(value, (tuple, list)):
        return tuple(_canonical(item) for item in value)
    if hasattr(value, "value"):
        return value.value
    return value


def _run_full_flow(
    raw_query: str, dataset: ValidatedDataset
) -> tuple[Any, ...]:
    """Execute the fixture-only RAG pipeline and collect its observations."""

    interpretation = interpret_query(raw_query, dataset)
    assert isinstance(interpretation, SupportedQueryInterpretation)
    repository = FixtureRepository(dataset)

    state = initial_rag_state()
    stage_history = [state]
    for _ in range(4):
        state = advance_stage(state)
        stage_history.append(state)

    query = repository.find_query_by_normalized_variant(raw_query.strip())
    assert query is not None
    search_result = run_mock_search(query, repository)
    assert isinstance(search_result, Ok)
    search = search_result.value
    template = next(
        item
        for item in dataset.response_templates
        if item.id == interpretation.match.response_template_id
    )

    statute_versions = {item.id: item for item in dataset.statute_versions}
    current_versions = {
        item.id: item.current_version_id_at_as_of
        for item in dataset.statutes
    }
    case_observations = []
    for search_case in search.cases:
        case = repository.get_case(search_case.case_id)
        assert case is not None
        risks = (
            classify_evidence(case.liability.civil.evidence),
            classify_evidence(
                case.liability.criminal.abuse_of_authority.evidence
            ),
            classify_evidence(
                case.liability.criminal.custodial_violence.evidence
            ),
            classify_evidence(case.liability.discipline.evidence),
        )
        badges = tuple(
            classify_action_badge((judgment,))
            for judgment in case.action_judgments
        )
        warning = similarity_warning(
            search_case.similarity_score,
            dataset.display_policies.similarity_warnings,
        )
        differences = order_fact_differences(
            search_case.similarity_score,
            case.fact_differences_by_query.get(interpretation.query_id, ()),
        )
        case_observations.append((
            search_case,
            classify_law_status(
                case.applied_statutes,
                statute_versions,
                current_versions,
            ),
            risks,
            badges,
            warning,
            differences,
        ))

    return _canonical((
        interpretation,
        stage_history,
        search,
        project_response_template(template),
        tuple(case_observations),
    ))


# Feature: police-case-law-ai-bot
# Property 40: 전체 목업 RAG 관찰 결과의 결정성
@settings(
    max_examples=100,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.data())
def test_full_mock_rag_observation_is_deterministic(
    validated_mock_dataset: ValidatedDataset,
    data: st.DataObject,
) -> None:
    """**Validates: Requirements 13.7**.

    Repeating each fixture-backed phase preserves the stage history, ordered
    search results, source-backed response, liability, law-status, and warning
    observations exactly.
    """

    variant = data.draw(
        st.sampled_from(
            tuple(
                variant
                for query in validated_mock_dataset.queries
                for variant in query.variants
            )
        ),
        label="registered_query_variant",
    )

    first = _run_full_flow(variant.raw_example, validated_mock_dataset)
    second = _run_full_flow(variant.raw_example, validated_mock_dataset)
    assert first == second
