"""Property 1: 표시 값의 fixture provenance와 무합성 (task 15.3)."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from data.fixture_repository import FixtureRepository
from data.models_source import LegalClaimBlock
from data.validated_dataset import ValidatedDataset
from domain.enums import SummaryLevel
from domain.mock_search import run_mock_search
from domain.notice_policy import notice_for
from domain.response_projection import (
    ResponseLegalClaimProjection,
    ResponseTextProjection,
    project_response_template,
)
from domain.result import Ok
from domain.summary_projection import project_summary


# Feature: police-case-law-ai-bot, Property 1: 표시 값의 fixture provenance와 무합성
@settings(
    max_examples=100,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.data())
def test_every_legal_display_value_has_fixture_or_policy_provenance(
    validated_mock_dataset: ValidatedDataset, data: st.DataObject
) -> None:
    """**Validates: Requirements 1.2, 13.1, 13.12**.

    Search, response, summary, and notice projections may select fixture values
    and policy text, but may not introduce a legal value absent from those
    registries. The independently built indexes are the provenance oracle.
    """

    dataset = validated_mock_dataset
    repository = FixtureRepository(dataset)
    case_by_id = dataset.cases_by_id
    statute_version_by_id = {
        item.id: item for item in dataset.statute_versions
    }
    statute_by_id = {item.id: item for item in dataset.statutes}
    source_by_id = dataset.sources_by_id
    policy_by_id = {
        record.id: record
        for collection in (
            dataset.display_policies.notices,
            dataset.display_policies.placeholders,
            dataset.display_policies.status_labels,
        )
        for record in collection
    }

    query = data.draw(st.sampled_from(dataset.queries), label="query")
    search_result = run_mock_search(query, repository)
    assert isinstance(search_result, Ok)
    search = search_result.value

    for displayed in search.cases:
        source = case_by_id[displayed.case_id]
        preset = query.similarity_by_case[displayed.case_id]
        assert (
            displayed.case_number,
            displayed.court_name,
            displayed.instance,
        ) == (source.case_number, source.court_name, source.instance)
        assert displayed.decision_date == source.decision_date
        assert displayed.scenario_ids == source.scenario_ids
        assert displayed.legality_status == source.legality_status
        assert displayed.law_basis_status == source.expected_law_basis_status
        assert displayed.similarity_score == preset.score
        assert displayed.instance_recognized_charge in {
            source.instance_recognized_charge,
            policy_by_id["placeholder-not-confirmed"].text,
        }
        assert displayed.instance_outcome in {
            source.instance_outcome,
            policy_by_id["placeholder-not-confirmed"].text,
        }

    for displayed in search.statutes:
        version = statute_version_by_id[displayed.statute_version_id]
        statute = statute_by_id[version.statute_id]
        assert (
            displayed.law_name,
            displayed.article,
            displayed.paragraph,
        ) == (statute.law_name, version.article, version.paragraph)
        assert displayed.effective_date == version.effective_date

    for source_id in search.direct_evidence_source_ids:
        assert source_id in source_by_id
    for error in search.case_data_errors:
        assert error.policy_record_id in policy_by_id
        assert error.message == policy_by_id[error.policy_record_id].text

    template = data.draw(
        st.sampled_from(dataset.response_templates), label="template"
    )
    response = project_response_template(template)
    assert response.template_id == template.id
    for fixture_block, displayed_block in zip(
        template.blocks, response.blocks
    ):
        assert fixture_block.text == displayed_block.text
        if isinstance(fixture_block, LegalClaimBlock):
            assert isinstance(displayed_block, ResponseLegalClaimProjection)
            assert displayed_block.claim_id == fixture_block.claim_id
            citations = (
                displayed_block.direct_citations
                + displayed_block.reference_sources
            )
            for citation in citations:
                source = source_by_id[citation.source_id]
                assert any(
                    anchor.id == citation.anchor_id
                    for anchor in source.anchors
                )
        else:
            assert isinstance(displayed_block, ResponseTextProjection)

    case = data.draw(st.sampled_from(dataset.cases), label="summary_case")
    level = data.draw(
        st.sampled_from(tuple(SummaryLevel)), label="summary_level"
    )
    summary = project_summary(
        case.summaries, level, dataset.display_policies.placeholders
    )
    assert summary.canonical_conclusion == case.summaries.canonical_conclusion
    fixture_summary_texts = {
        item.text
        for item in (
            case.summaries.three_line
            + case.summaries.ten_line
            + case.summaries.detailed
        )
        if item.text is not None
    }
    permitted_summary_texts = fixture_summary_texts | {
        policy_by_id["placeholder-no-evidence-information"].text
    }
    for displayed in summary.lines + summary.detailed_sections:
        assert displayed.text in permitted_summary_texts

    surface = data.draw(
        st.sampled_from(
            (
                "APP_SHELL",
                "SEARCH_RESULTS",
                "MOCK_RESPONSE",
                "SOURCE_VIEWER",
                "REPORT_PREVIEW",
                "CLIPBOARD",
                "DOWNLOAD",
            )
        ),
        label="notice_surface",
    )
    notice = notice_for(surface, dataset.display_policies)
    for policy_id in notice.required_policy_record_ids:
        assert policy_id in policy_by_id
