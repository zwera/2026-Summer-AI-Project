"""``data.validator_structural`` 구조 검증기 단위 테스트 (task 2.1).

이 테스트는 구조 검증(필수 필드·enum·ISO 날짜 형식·tuple 길이·유사도 점수 범위)만
다룬다. ID 유일성, 참조 존재, source anchor 체크섬, canonical 값 일치 같은 교차
참조·도메인 불변식 검증은 task 2.2 범위이며 여기서 다루지 않는다.

각 mutation 테스트는 최소 유효 fixture(``fixtures.mock_dataset.build_mock_dataset``)에
정확히 한 종류의 결함만 주입해 원인을 분리한다(``design.md`` Testing Strategy 5절).
"""

from __future__ import annotations

import dataclasses

from data.models_source import LegalClaimBlock
from data.models_timeline import EventAmbiguity, RecognizedEvent
from data.validator_structural import Severity, has_fatal, validate_structure
from fixtures.mock_dataset import build_mock_dataset


def test_valid_fixture_has_no_fatal_diagnostics() -> None:
    dataset = build_mock_dataset()
    diagnostics = validate_structure(dataset)
    assert not has_fatal(diagnostics), diagnostics


def test_valid_fixture_has_no_diagnostics_at_all() -> None:
    """최소 유효 fixture는 구조적으로 완전히 유효해야 하므로 진단이 아예 없어야 한다."""

    dataset = build_mock_dataset()
    diagnostics = validate_structure(dataset)
    assert diagnostics == ()


def test_bad_legality_status_enum_value_is_flagged() -> None:
    dataset = build_mock_dataset()
    bad_case = dataclasses.replace(dataset.cases[0], legality_status="알수없음")  # type: ignore[arg-type]
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_LEGALITY_STATUS" in codes


def test_malformed_decision_date_is_flagged() -> None:
    dataset = build_mock_dataset()
    bad_case = dataclasses.replace(dataset.cases[0], decision_date="2020/01/01")
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_ISO_DATE" in codes


def test_nonexistent_calendar_date_is_flagged() -> None:
    """``YYYY-MM-DD`` 형식이라도 실제 존재하지 않는 날짜(2월 30일)는 거부되어야 한다."""

    dataset = build_mock_dataset()
    bad_case = dataclasses.replace(dataset.cases[0], decision_date="2021-02-30")
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_ISO_DATE" in codes


def test_out_of_range_similarity_score_is_flagged() -> None:
    dataset = build_mock_dataset()
    query = dataset.queries[0]
    case_id, preset = next(iter(query.similarity_by_case.items()))
    bad_preset = dataclasses.replace(preset, score=101.0)
    mutated_similarity = dict(query.similarity_by_case)
    mutated_similarity[case_id] = bad_preset
    mutated_query = dataclasses.replace(query, similarity_by_case=mutated_similarity)
    mutated_queries = (mutated_query,) + dataset.queries[1:]
    mutated = dataclasses.replace(dataset, queries=mutated_queries)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "SIMILARITY_SCORE_OUT_OF_RANGE" in codes


def test_negative_similarity_score_is_flagged() -> None:
    dataset = build_mock_dataset()
    query = dataset.queries[0]
    case_id, preset = next(iter(query.similarity_by_case.items()))
    bad_preset = dataclasses.replace(preset, score=-1.0)
    mutated_similarity = dict(query.similarity_by_case)
    mutated_similarity[case_id] = bad_preset
    mutated_query = dataclasses.replace(query, similarity_by_case=mutated_similarity)
    mutated_queries = (mutated_query,) + dataset.queries[1:]
    mutated = dataclasses.replace(dataset, queries=mutated_queries)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "SIMILARITY_SCORE_OUT_OF_RANGE" in codes


def test_non_numeric_similarity_score_is_flagged() -> None:
    dataset = build_mock_dataset()
    query = dataset.queries[0]
    case_id, preset = next(iter(query.similarity_by_case.items()))
    bad_preset = dataclasses.replace(preset, score="높음")  # type: ignore[arg-type]
    mutated_similarity = dict(query.similarity_by_case)
    mutated_similarity[case_id] = bad_preset
    mutated_query = dataclasses.replace(query, similarity_by_case=mutated_similarity)
    mutated_queries = (mutated_query,) + dataset.queries[1:]
    mutated = dataclasses.replace(dataset, queries=mutated_queries)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "SIMILARITY_SCORE_INVALID" in codes


def test_nan_similarity_score_is_flagged() -> None:
    dataset = build_mock_dataset()
    query = dataset.queries[0]
    case_id, preset = next(iter(query.similarity_by_case.items()))
    bad_preset = dataclasses.replace(preset, score=float("nan"))
    mutated_similarity = dict(query.similarity_by_case)
    mutated_similarity[case_id] = bad_preset
    mutated_query = dataclasses.replace(query, similarity_by_case=mutated_similarity)
    mutated_queries = (mutated_query,) + dataset.queries[1:]
    mutated = dataclasses.replace(dataset, queries=mutated_queries)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "SIMILARITY_SCORE_INVALID" in codes


def test_boundary_similarity_scores_are_accepted() -> None:
    """0과 100은 경계값으로서 유효해야 한다(범위는 [0, 100] inclusive)."""

    dataset = build_mock_dataset()
    query = dataset.queries[0]
    case_id, preset = next(iter(query.similarity_by_case.items()))
    for boundary in (0.0, 100.0):
        bad_preset = dataclasses.replace(preset, score=boundary)
        mutated_similarity = dict(query.similarity_by_case)
        mutated_similarity[case_id] = bad_preset
        mutated_query = dataclasses.replace(query, similarity_by_case=mutated_similarity)
        mutated_queries = (mutated_query,) + dataset.queries[1:]
        mutated = dataclasses.replace(dataset, queries=mutated_queries)

        diagnostics = validate_structure(mutated)

        codes = {d.code for d in diagnostics}
        assert "SIMILARITY_SCORE_OUT_OF_RANGE" not in codes
        assert "SIMILARITY_SCORE_INVALID" not in codes


def test_three_line_summary_wrong_length_is_flagged() -> None:
    dataset = build_mock_dataset()
    case = dataset.cases[0]
    bad_three_line = case.summaries.three_line[:2]  # 3개 대신 2개
    bad_summaries = dataclasses.replace(case.summaries, three_line=bad_three_line)  # type: ignore[arg-type]
    bad_case = dataclasses.replace(case, summaries=bad_summaries)
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "SUMMARY_THREE_LINE_LENGTH_MISMATCH" in codes


def test_ten_line_summary_wrong_length_is_flagged() -> None:
    dataset = build_mock_dataset()
    case = dataset.cases[0]
    bad_ten_line = case.summaries.ten_line[:9]  # 10개 대신 9개
    bad_summaries = dataclasses.replace(case.summaries, ten_line=bad_ten_line)  # type: ignore[arg-type]
    bad_case = dataclasses.replace(case, summaries=bad_summaries)
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "SUMMARY_TEN_LINE_LENGTH_MISMATCH" in codes


def test_invalid_summary_section_key_is_flagged() -> None:
    dataset = build_mock_dataset()
    case = dataset.cases[0]
    bad_line = dataclasses.replace(case.summaries.three_line[0], key="알수없는 항목")  # type: ignore[arg-type]
    bad_three_line = (bad_line,) + case.summaries.three_line[1:]
    bad_summaries = dataclasses.replace(case.summaries, three_line=bad_three_line)
    bad_case = dataclasses.replace(case, summaries=bad_summaries)
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_SUMMARY_SECTION_KEY" in codes


def test_missing_dataset_id_is_fatal() -> None:
    dataset = build_mock_dataset()
    mutated = dataclasses.replace(dataset, dataset_id="")  # type: ignore[arg-type]

    diagnostics = validate_structure(mutated)

    assert has_fatal(diagnostics)
    fatal_codes = {d.code for d in diagnostics if d.severity is Severity.FATAL}
    assert "REQUIRED_FIELD_EMPTY" in fatal_codes


def test_wrong_legal_safety_notice_text_is_not_flagged_by_structural_validator() -> None:
    """정확한 문구 일치 검증은 교차 참조/불변식 검증(task 2.2)의 책임이다.

    구조 검증기는 ``legal_safety_notice``가 비어 있지 않은 문자열인지만 확인하며, 정확한
    고정 문구와의 일치는 검사하지 않는다.
    """

    dataset = build_mock_dataset()
    mutated = dataclasses.replace(dataset, legal_safety_notice="다른 문구")

    diagnostics = validate_structure(mutated)

    assert not has_fatal(diagnostics)


def test_invalid_source_kind_is_flagged() -> None:
    dataset = build_mock_dataset()
    source = dataset.sources[0]
    bad_source = dataclasses.replace(source, source_kind="UNKNOWN_KIND")  # type: ignore[arg-type]
    mutated_sources = (bad_source,) + dataset.sources[1:]
    mutated = dataclasses.replace(dataset, sources=mutated_sources)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_SOURCE_KIND" in codes


def test_invalid_court_finding_is_flagged() -> None:
    dataset = build_mock_dataset()
    case = dataset.cases[0]
    bad_judgment = dataclasses.replace(case.action_judgments[0], court_finding="UNKNOWN")  # type: ignore[arg-type]
    bad_case = dataclasses.replace(case, action_judgments=(bad_judgment,))
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_COURT_FINDING" in codes


def test_malformed_statute_version_date_is_flagged() -> None:
    dataset = build_mock_dataset()
    version = dataset.statute_versions[0]
    bad_version = dataclasses.replace(version, effective_date="not-a-date")
    mutated_versions = (bad_version,) + dataset.statute_versions[1:]
    mutated = dataclasses.replace(dataset, statute_versions=mutated_versions)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_ISO_DATE" in codes


def test_none_optional_statute_dates_are_not_flagged() -> None:
    """``revision_date``/``effective_date``는 선택 필드이므로 ``None``은 구조 오류가 아니다."""

    dataset = build_mock_dataset()
    version = dataset.statute_versions[0]
    ok_version = dataclasses.replace(version, revision_date=None, effective_date=None)
    mutated_versions = (ok_version,) + dataset.statute_versions[1:]
    mutated = dataclasses.replace(dataset, statute_versions=mutated_versions)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_ISO_DATE" not in codes


def test_invalid_appellate_state_is_flagged() -> None:
    dataset = build_mock_dataset()
    case = dataset.cases[0]
    bad_appellate = dataclasses.replace(case.appellate, state="UNKNOWN")  # type: ignore[arg-type]
    bad_case = dataclasses.replace(case, appellate=bad_appellate)
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_APPELLATE_STATE" in codes


def test_invalid_display_policy_kind_is_flagged() -> None:
    dataset = build_mock_dataset()
    notices = dataset.display_policies.notices
    bad_notice = dataclasses.replace(notices[0], kind="UNKNOWN_KIND")  # type: ignore[arg-type]
    mutated_notices = (bad_notice,) + notices[1:]
    mutated_policies = dataclasses.replace(dataset.display_policies, notices=mutated_notices)
    mutated = dataclasses.replace(dataset, display_policies=mutated_policies)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_DISPLAY_POLICY_KIND" in codes


def test_invalid_similarity_warning_key_is_flagged() -> None:
    dataset = build_mock_dataset()
    warnings = dataset.display_policies.similarity_warnings
    bad_warning = dataclasses.replace(warnings[0], key="EXTREME")  # type: ignore[arg-type]
    mutated_warnings = (bad_warning,) + warnings[1:]
    mutated_policies = dataclasses.replace(
        dataset.display_policies, similarity_warnings=mutated_warnings
    )
    mutated = dataclasses.replace(dataset, display_policies=mutated_policies)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_SIMILARITY_WARNING_KEY" in codes


# ---------------------------------------------------------------------------
# task 2.4에서 발견한 추가 enum-membership mutation 커버리지 (기존 2.1 테스트가
# ``_check_enum_membership`` 호출 지점 전체를 다루지 않았던 부분).
# ---------------------------------------------------------------------------


def test_invalid_instance_value_is_flagged() -> None:
    dataset = build_mock_dataset()
    bad_case = dataclasses.replace(dataset.cases[0], instance="2심")  # type: ignore[arg-type]
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_INSTANCE" in codes


def test_invalid_law_basis_status_is_flagged() -> None:
    dataset = build_mock_dataset()
    bad_case = dataclasses.replace(dataset.cases[0], expected_law_basis_status="알수없음")  # type: ignore[arg-type]
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_LAW_BASIS_STATUS" in codes


def test_invalid_finality_is_flagged() -> None:
    dataset = build_mock_dataset()
    bad_case = dataclasses.replace(dataset.cases[0], finality="알수없음")  # type: ignore[arg-type]
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_FINALITY" in codes


def test_invalid_source_owner_type_is_flagged() -> None:
    dataset = build_mock_dataset()
    source = dataset.sources[0]
    bad_owner = dataclasses.replace(source.owner, type="UNKNOWN_OWNER")  # type: ignore[arg-type]
    bad_source = dataclasses.replace(source, owner=bad_owner)
    mutated_sources = (bad_source,) + dataset.sources[1:]
    mutated = dataclasses.replace(dataset, sources=mutated_sources)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_SOURCE_OWNER_TYPE" in codes


def test_invalid_input_mode_is_flagged() -> None:
    dataset = build_mock_dataset()
    query = dataset.queries[0]
    bad_variant = dataclasses.replace(query.variants[0], input_mode="UNKNOWN_MODE")  # type: ignore[arg-type]
    bad_query = dataclasses.replace(query, variants=(bad_variant,))
    mutated_queries = (bad_query,) + dataset.queries[1:]
    mutated = dataclasses.replace(dataset, queries=mutated_queries)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_INPUT_MODE" in codes


def test_invalid_response_block_type_is_flagged() -> None:
    dataset = build_mock_dataset()
    template = dataset.response_templates[0]
    bad_block = dataclasses.replace(template.blocks[0], type="UNKNOWN_BLOCK")  # type: ignore[arg-type]
    mutated_blocks = (bad_block,) + template.blocks[1:]
    bad_template = dataclasses.replace(template, blocks=mutated_blocks)
    mutated_templates = (bad_template,) + dataset.response_templates[1:]
    mutated = dataclasses.replace(dataset, response_templates=mutated_templates)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_RESPONSE_BLOCK_TYPE" in codes


def test_invalid_claim_evidence_purpose_is_flagged() -> None:
    dataset = build_mock_dataset()
    template = dataset.response_templates[0]
    claim_block = template.blocks[1]
    assert isinstance(claim_block, LegalClaimBlock)
    bad_link = dataclasses.replace(claim_block.citation_links[0], purpose="UNKNOWN_PURPOSE")  # type: ignore[arg-type]
    bad_block = dataclasses.replace(claim_block, citation_links=(bad_link,))
    mutated_blocks = (template.blocks[0], bad_block) + template.blocks[2:]
    bad_template = dataclasses.replace(template, blocks=mutated_blocks)
    mutated_templates = (bad_template,) + dataset.response_templates[1:]
    mutated = dataclasses.replace(dataset, response_templates=mutated_templates)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_CLAIM_EVIDENCE_PURPOSE" in codes


def test_invalid_claim_evidence_relation_is_flagged() -> None:
    dataset = build_mock_dataset()
    template = dataset.response_templates[0]
    claim_block = template.blocks[1]
    assert isinstance(claim_block, LegalClaimBlock)
    bad_link = dataclasses.replace(claim_block.citation_links[0], relation="UNKNOWN_RELATION")  # type: ignore[arg-type]
    bad_block = dataclasses.replace(claim_block, citation_links=(bad_link,))
    mutated_blocks = (template.blocks[0], bad_block) + template.blocks[2:]
    bad_template = dataclasses.replace(template, blocks=mutated_blocks)
    mutated_templates = (bad_template,) + dataset.response_templates[1:]
    mutated = dataclasses.replace(dataset, response_templates=mutated_templates)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_CLAIM_EVIDENCE_RELATION" in codes


def test_invalid_claim_evidence_coverage_is_flagged() -> None:
    dataset = build_mock_dataset()
    template = dataset.response_templates[0]
    claim_block = template.blocks[1]
    assert isinstance(claim_block, LegalClaimBlock)
    bad_link = dataclasses.replace(claim_block.citation_links[0], coverage="UNKNOWN_COVERAGE")  # type: ignore[arg-type]
    bad_block = dataclasses.replace(claim_block, citation_links=(bad_link,))
    mutated_blocks = (template.blocks[0], bad_block) + template.blocks[2:]
    bad_template = dataclasses.replace(template, blocks=mutated_blocks)
    mutated_templates = (bad_template,) + dataset.response_templates[1:]
    mutated = dataclasses.replace(dataset, response_templates=mutated_templates)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_CLAIM_EVIDENCE_COVERAGE" in codes


def test_invalid_traditional_case_area_is_flagged() -> None:
    dataset = build_mock_dataset()
    bad_case = dataclasses.replace(dataset.cases[0], traditional_areas=("알수없는분야",))  # type: ignore[arg-type]
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_TRADITIONAL_CASE_AREA" in codes


def test_invalid_fact_dimension_in_case_fact_differences_is_flagged() -> None:
    """``case-arrest-lawful``(``dataset.cases[0]``)은 ``fact_differences_by_query``에 실제
    항목을 갖고 있으므로 이 필드의 ``dimension`` mutation을 검사할 수 있다."""

    dataset = build_mock_dataset()
    case = dataset.cases[0]
    query_id, differences = next(iter(case.fact_differences_by_query.items()))
    bad_difference = dataclasses.replace(differences[0], dimension="알수없는차원")  # type: ignore[arg-type]
    mutated_differences = {query_id: (bad_difference,)}
    bad_case = dataclasses.replace(case, fact_differences_by_query=mutated_differences)
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_FACT_DIMENSION" in codes


def test_invalid_appellate_instance_is_flagged() -> None:
    """``case-arrest-lawful``(``dataset.cases[0]``)은 실제 ``appellate.decisions`` 항목을
    가진 유일한 fixture 판례이므로 여기서 ``instance`` mutation을 검사한다."""

    dataset = build_mock_dataset()
    case = dataset.cases[0]
    assert case.appellate.decisions, "fixture가 바뀌어 appellate.decisions가 비어버림"
    bad_decision = dataclasses.replace(case.appellate.decisions[0], instance="1심")  # type: ignore[arg-type]
    bad_appellate = dataclasses.replace(case.appellate, decisions=(bad_decision,))
    bad_case = dataclasses.replace(case, appellate=bad_appellate)
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_APPELLATE_INSTANCE" in codes


def test_invalid_relation_to_lower_instance_is_flagged() -> None:
    dataset = build_mock_dataset()
    case = dataset.cases[0]
    assert case.appellate.decisions, "fixture가 바뀌어 appellate.decisions가 비어버림"
    bad_decision = dataclasses.replace(
        case.appellate.decisions[0], relation_to_lower_instance="알수없음"  # type: ignore[arg-type]
    )
    bad_appellate = dataclasses.replace(case.appellate, decisions=(bad_decision,))
    bad_case = dataclasses.replace(case, appellate=bad_appellate)
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_RELATION_TO_LOWER_INSTANCE" in codes


def test_invalid_instance_relation_in_related_instances_is_flagged() -> None:
    """``case-arrest-lawful``(``dataset.cases[0]``)은 실제 ``related_instances`` 항목을
    가진 유일한 fixture 판례다."""

    dataset = build_mock_dataset()
    case = dataset.cases[0]
    assert case.related_instances, "fixture가 바뀌어 related_instances가 비어버림"
    bad_ref = dataclasses.replace(case.related_instances[0], relation="알수없음")  # type: ignore[arg-type]
    bad_case = dataclasses.replace(case, related_instances=(bad_ref,))
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_INSTANCE_RELATION" in codes


def test_invalid_event_ambiguity_kind_is_flagged() -> None:
    """fixture는 기본적으로 ``recognized_events=()``이므로 ``EventAmbiguity``를 가진
    이벤트를 직접 구성해 주입해야만 이 경로를 검사할 수 있다."""

    dataset = build_mock_dataset()
    query = dataset.queries[0]
    bad_event = RecognizedEvent(
        id="event-ambiguity-test",  # type: ignore[arg-type]
        original_text="사건",
        action="행위",
        original_order=1,
        ambiguity=EventAmbiguity(kind="UNKNOWN_KIND", alternatives=("대안1", "대안2")),  # type: ignore[arg-type]
    )
    mutated_query = dataclasses.replace(query, recognized_events=(bad_event,))
    mutated_queries = (mutated_query,) + dataset.queries[1:]
    mutated = dataclasses.replace(dataset, queries=mutated_queries)

    diagnostics = validate_structure(mutated)

    codes = {d.code for d in diagnostics}
    assert "INVALID_EVENT_AMBIGUITY_KIND" in codes

