"""Property 8: 검색 결과 projection의 필드 충실성 (task 5.4).

A fixture-backed mock search must preserve every displayed case and statute
field from the resolved source record.  The oracle reads repository records
without reusing search-projection construction logic.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from data.fixture_repository import FixtureRepository
from data.models_query import QueryFixture
from data.validated_dataset import ValidatedDataset
from domain.mock_search import SearchProjection, run_mock_search
from domain.result import Ok


def _expected_direct_source_ids(
    query: QueryFixture, repository: FixtureRepository
) -> tuple[object, ...]:
    """Build the unique resolved-case source sequence independently."""

    source_ids: list[object] = []
    for case_id in query.match.case_ids:
        case = repository.get_case(case_id)
        if case is None:
            continue
        for source_id in case.source_ids:
            if source_id not in source_ids:
                source_ids.append(source_id)
    return tuple(source_ids)


def _assert_case_projection_fidelity(
    projection: SearchProjection,
    query: QueryFixture,
    repository: FixtureRepository,
    not_confirmed: str,
) -> None:
    """Compare each result case with its fixture record field by field."""

    projected_case_ids = {item.case_id for item in projection.cases}
    expected_case_ids = set(query.match.case_ids)
    assert projected_case_ids == expected_case_ids

    for item in projection.cases:
        case = repository.get_case(item.case_id)
        assert case is not None
        preset = query.similarity_by_case[case.id]

        assert item.case_number == case.case_number
        assert item.court_name == case.court_name
        assert item.instance == case.instance
        assert item.decision_date == case.decision_date
        assert item.scenario_ids == case.scenario_ids
        assert item.legality_status == case.legality_status
        assert item.law_basis_status == case.expected_law_basis_status
        assert item.applied_statute_labels == tuple(
            reference.citation_label for reference in case.applied_statutes
        )
        assert item.similarity_score == preset.score
        assert item.search_priority == preset.search_priority
        assert item.tie_order == preset.tie_order
        assert item.instance_recognized_charge == (
            case.instance_recognized_charge
            if case.instance_recognized_charge is not None
            else not_confirmed
        )
        assert item.instance_outcome == (
            case.instance_outcome
            if case.instance_outcome is not None
            else not_confirmed
        )


def _assert_statute_projection_fidelity(
    projection: SearchProjection,
    query: QueryFixture,
    repository: FixtureRepository,
) -> None:
    """Compare each statute result with its version and owner records."""

    projected_version_ids = {
        item.statute_version_id for item in projection.statutes
    }
    expected_version_ids = set(query.match.statute_version_ids)
    assert projected_version_ids == expected_version_ids

    for item in projection.statutes:
        version = repository.get_statute_version(item.statute_version_id)
        assert version is not None
        statute = repository.get_statute(version.statute_id)
        assert statute is not None

        assert item.law_name == statute.law_name
        assert item.article == version.article
        assert item.paragraph == version.paragraph
        assert item.item == version.item
        assert item.effective_date == version.effective_date
        assert item.revision_date == version.revision_date
        assert item.version_label == version.version_label
        assert item.revision_summary == version.revision_summary


# Feature: police-case-law-ai-bot
# Property 8: 검색 결과 projection의 필드 충실성
@settings(
    max_examples=100,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.data())
def test_search_projection_fields_match_fixture_records(
    validated_mock_dataset: ValidatedDataset,
    data: st.DataObject,
) -> None:
    """**Validates: Requirements 3.3, 3.4, 3.5, 7.6,
    12.5**.

    Every registered query preserves case metadata, legal status, and statute
    display fields. It also preserves similarity/order values, instance charge
    and outcome, plus the direct evidence source sequence from fixture records.
    """

    query = data.draw(
        st.sampled_from(validated_mock_dataset.queries),
        label="registered_query",
    )
    repository = FixtureRepository(validated_mock_dataset)
    result = run_mock_search(query, repository)

    assert isinstance(result, Ok)
    projection = result.value
    not_confirmed = next(
        policy.text
        for policy in validated_mock_dataset.display_policies.placeholders
        if policy.key == "확인되지 않음"
    )

    _assert_case_projection_fidelity(
        projection,
        query,
        repository,
        not_confirmed,
    )
    _assert_statute_projection_fidelity(
        projection,
        query,
        repository,
    )
    expected_direct_sources = _expected_direct_source_ids(query, repository)
    assert projection.direct_evidence_source_ids == expected_direct_sources
    assert projection.missing_case_ids == ()
    assert projection.missing_statute_version_ids == ()
    assert projection.case_data_errors == ()
