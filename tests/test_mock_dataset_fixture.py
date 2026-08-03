"""최소 유효 목업 데이터셋(fixture) 스모크 테스트.

이 테스트는 ``DatasetValidator``(task 2.x)의 구조·교차 참조 검증을 대체하지 않는다.
task 1.2 범위에서 fixture가 데이터 모델 dataclass로 오류 없이 로드되고, 요구사항
4.1·4.9·16.1·16.2가 요구하는 최소 요건(8개 시나리오 적법·위법 각 1건 이상, 심급 체인,
필수 표시 정책 레코드, 정확한 심급 주의 문구)을 기본적으로 만족하는지만 확인한다.
"""

from __future__ import annotations

from data.models import INSTANCE_CAUTION_NOTICE_TEXT
from domain.enums import LegalityStatus, PoliceScenario
from domain.ids import CaseId
from fixtures.mock_dataset import build_mock_dataset


def test_dataset_builds_without_error() -> None:
    dataset = build_mock_dataset()
    assert dataset.cases
    assert dataset.queries
    assert dataset.sources


def test_instance_caution_notice_matches_exact_design_literal() -> None:
    dataset = build_mock_dataset()
    expected = (
        "판례는 심급 및 절차 경과에 따라 결론이 달라질 수 있으므로, "
        "상급심 판단과 확정 여부를 함께 확인해야 합니다."
    )
    assert dataset.instance_caution_notice == expected
    assert dataset.instance_caution_notice == INSTANCE_CAUTION_NOTICE_TEXT


def test_every_scenario_has_at_least_one_lawful_and_one_unlawful_case() -> None:
    dataset = build_mock_dataset()
    for scenario in PoliceScenario:
        matching = [case for case in dataset.cases if scenario in case.scenario_ids]
        lawful = [c for c in matching if c.legality_status is LegalityStatus.LAWFUL]
        unlawful = [c for c in matching if c.legality_status is LegalityStatus.UNLAWFUL]
        assert lawful, f"{scenario.value} 시나리오에 적법 판례가 없음"
        assert unlawful, f"{scenario.value} 시나리오에 위법 판례가 없음"


def test_case_instance_values_are_restricted_to_three_literals() -> None:
    dataset = build_mock_dataset()
    allowed = {"1심", "항소심", "상고심"}
    for case in dataset.cases:
        assert case.instance in allowed


def test_full_instance_chain_case_links_first_instance_to_appellate() -> None:
    dataset = build_mock_dataset()
    by_id = {case.id: case for case in dataset.cases}

    first_instance = by_id[CaseId("case-arrest-lawful")]
    assert first_instance.instance == "1심"
    assert len(first_instance.related_instances) == 1
    related = first_instance.related_instances[0]
    assert related.instance == "항소심"
    assert related.relation == "상급심"
    appellate_case_id = related.case_id

    appellate_case = by_id[appellate_case_id]
    assert appellate_case.instance == "항소심"

    assert first_instance.appellate.state == "PRESENT"
    decision = first_instance.appellate.decisions[0]
    assert decision.relation_to_lower_instance in ("유지", "변경")
    assert decision.instance == "항소심"


def test_appellate_information_absent_state_has_no_decisions() -> None:
    dataset = build_mock_dataset()
    for case in dataset.cases:
        if case.appellate.state == "정보_없음":
            assert case.appellate.decisions == ()


def test_display_policies_include_required_placeholder_ids() -> None:
    dataset = build_mock_dataset()
    placeholder_keys = {record.key for record in dataset.display_policies.placeholders}
    assert placeholder_keys == {
        "정보_없음",
        "분류_불가",
        "확인 필요",
        "확인되지 않음",
        "근거 정보 없음",
    }


def test_display_policies_include_similarity_warning_bands_covering_0_to_100() -> None:
    dataset = build_mock_dataset()
    by_key = {record.key: record for record in dataset.display_policies.similarity_warnings}
    assert set(by_key) == {"HIGH", "MEDIUM", "LOW"}
    assert by_key["LOW"].min_inclusive == 0
    assert by_key["LOW"].max_exclusive == 50
    assert by_key["MEDIUM"].min_inclusive == 50
    assert by_key["MEDIUM"].max_exclusive == 80
    assert by_key["HIGH"].min_inclusive == 80
    assert by_key["HIGH"].max_inclusive == 100


def test_display_policies_include_legal_safety_notice_record() -> None:
    dataset = build_mock_dataset()
    notice_keys = {record.key for record in dataset.display_policies.notices}
    assert "LEGAL_SAFETY_NOTICE" in notice_keys
    assert "INSTANCE_CAUTION_NOTICE" in notice_keys


def test_query_fixture_match_ids_resolve_to_present_case_records() -> None:
    dataset = build_mock_dataset()
    case_ids = {case.id for case in dataset.cases}
    for query in dataset.queries:
        for case_id in query.match.case_ids:
            assert case_id in case_ids


def test_query_fixture_match_statute_ids_resolve_to_present_statute_versions() -> None:
    dataset = build_mock_dataset()
    version_ids = {version.id for version in dataset.statute_versions}
    for query in dataset.queries:
        for version_id in query.match.statute_version_ids:
            assert version_id in version_ids


def test_case_source_ids_resolve_to_present_source_records() -> None:
    dataset = build_mock_dataset()
    source_ids = {source.id for source in dataset.sources}
    for case in dataset.cases:
        for source_id in case.source_ids:
            assert source_id in source_ids


def test_response_template_claim_sources_resolve_to_present_source_records() -> None:
    dataset = build_mock_dataset()
    source_ids = {source.id for source in dataset.sources}
    for template in dataset.response_templates:
        for block in template.blocks:
            if block.type == "LEGAL_CLAIM":
                for link in block.citation_links:
                    assert link.source_id in source_ids
