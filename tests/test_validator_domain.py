"""``data.validator_domain`` 도메인·교차 참조 불변식 검증기 단위 테스트 (task 2.2).

각 mutation 테스트는 최소 유효 fixture(``fixtures.mock_dataset.build_mock_dataset``)에
정확히 한 종류의 결함만 주입해 원인을 분리한다(``design.md`` Testing Strategy 5절). 이
파일은 task 2.2가 새로 구현하는 검증(ID 유일성·참조 존재·source anchor 체크섬·표시 정책
유일성·유사도 경고 구간 무결/비중첩·canonical 값 일치·현행법 우선순위·상대 시각 anchor
비순환)만 다룬다. 구조 검증(task 2.1)은 ``tests/test_validator_structural.py``에서 이미
다룬다.
"""

from __future__ import annotations

import dataclasses
import hashlib

from data.models_timeline import IssueLink, RecognizedEvent, RelativeTime
from data.validator_domain import Severity, has_fatal, validate_domain, validate_domain_detailed
from domain.enums import LawBasisStatus
from domain.ids import CaseId, EventId, SourceId, StatuteVersionId
from fixtures.mock_dataset import build_mock_dataset


def test_valid_fixture_has_no_diagnostics() -> None:
    dataset = build_mock_dataset()
    diagnostics = validate_domain(dataset)
    assert diagnostics == ()


def test_valid_fixture_excludes_no_records() -> None:
    dataset = build_mock_dataset()
    _diagnostics, exclusions = validate_domain_detailed(dataset)
    assert exclusions.case_ids == frozenset()
    assert exclusions.query_ids == frozenset()
    assert exclusions.source_ids == frozenset()
    assert exclusions.response_template_ids == frozenset()
    assert exclusions.review_fixture_response_template_ids == frozenset()
    assert exclusions.voice_fixture_ids == frozenset()


# ---------------------------------------------------------------------------
# (a) ID 유일성
# ---------------------------------------------------------------------------


def test_duplicate_case_id_is_fatal() -> None:
    dataset = build_mock_dataset()
    duplicated = dataclasses.replace(dataset.cases[1], id=dataset.cases[0].id)
    mutated_cases = (dataset.cases[0], duplicated) + dataset.cases[2:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics = validate_domain(mutated)

    assert has_fatal(diagnostics)
    fatal_codes = {d.code for d in diagnostics if d.severity is Severity.FATAL}
    assert "DUPLICATE_CASE_ID" in fatal_codes


def test_duplicate_source_id_is_fatal() -> None:
    dataset = build_mock_dataset()
    duplicated = dataclasses.replace(dataset.sources[1], id=dataset.sources[0].id)
    mutated_sources = (dataset.sources[0], duplicated) + dataset.sources[2:]
    mutated = dataclasses.replace(dataset, sources=mutated_sources)

    diagnostics = validate_domain(mutated)

    assert has_fatal(diagnostics)
    fatal_codes = {d.code for d in diagnostics if d.severity is Severity.FATAL}
    assert "DUPLICATE_SOURCE_ID" in fatal_codes


# ---------------------------------------------------------------------------
# (b) 참조 존재
# ---------------------------------------------------------------------------


def test_dangling_case_source_reference_is_warning_and_isolates_case() -> None:
    dataset = build_mock_dataset()
    case = dataset.cases[0]
    bad_case = dataclasses.replace(case, source_ids=(SourceId("source-does-not-exist"),))
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "DANGLING_SOURCE_REFERENCE" in codes
    assert case.id in exclusions.case_ids


def test_dangling_query_match_case_reference_is_warning_and_isolates_query() -> None:
    dataset = build_mock_dataset()
    query = dataset.queries[0]
    bad_match = dataclasses.replace(query.match, case_ids=(CaseId("case-does-not-exist"),))
    bad_query = dataclasses.replace(query, match=bad_match)
    mutated_queries = (bad_query,) + dataset.queries[1:]
    mutated = dataclasses.replace(dataset, queries=mutated_queries)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "DANGLING_CASE_REFERENCE" in codes
    assert query.id in exclusions.query_ids


def test_dangling_response_template_source_reference_isolates_template() -> None:
    dataset = build_mock_dataset()
    template = dataset.response_templates[0]
    claim_block = template.blocks[1]
    assert claim_block.type == "LEGAL_CLAIM"
    bad_link = dataclasses.replace(claim_block.citation_links[0], source_id=SourceId("source-missing"))
    bad_block = dataclasses.replace(claim_block, citation_links=(bad_link,))
    mutated_blocks = (template.blocks[0], bad_block) + template.blocks[2:]
    bad_template = dataclasses.replace(template, blocks=mutated_blocks)
    mutated_templates = (bad_template,) + dataset.response_templates[1:]
    mutated = dataclasses.replace(dataset, response_templates=mutated_templates)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "DANGLING_SOURCE_REFERENCE" in codes
    assert template.id in exclusions.response_template_ids


def test_dangling_voice_fixture_query_reference_isolates_voice_fixture() -> None:
    dataset = build_mock_dataset()
    voice = dataset.voice_fixtures[0]
    assert voice.query_id is not None
    from domain.ids import QueryId

    bad_voice = dataclasses.replace(voice, query_id=QueryId("query-does-not-exist"))
    mutated_voice = (bad_voice,) + dataset.voice_fixtures[1:]
    mutated = dataclasses.replace(dataset, voice_fixtures=mutated_voice)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "DANGLING_QUERY_REFERENCE" in codes
    assert voice.id in exclusions.voice_fixture_ids


# ---------------------------------------------------------------------------
# (c) source -> anchor 범위 · 체크섬
# ---------------------------------------------------------------------------


def test_anchor_checksum_mismatch_is_warning_and_isolates_source() -> None:
    dataset = build_mock_dataset()
    source = dataset.sources[1]
    bad_anchor = dataclasses.replace(source.anchors[0], excerpt_checksum="0" * 64)
    bad_source = dataclasses.replace(source, anchors=(bad_anchor,))
    mutated_sources = (dataset.sources[0], bad_source) + dataset.sources[2:]
    mutated = dataclasses.replace(dataset, sources=mutated_sources)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "SOURCE_ANCHOR_CHECKSUM_MISMATCH" in codes
    assert source.id in exclusions.source_ids


def test_anchor_range_out_of_bounds_is_warning_and_isolates_source() -> None:
    dataset = build_mock_dataset()
    source = dataset.sources[1]
    bad_anchor = dataclasses.replace(source.anchors[0], end_offset=len(source.body) + 1000)
    bad_source = dataclasses.replace(source, anchors=(bad_anchor,))
    mutated_sources = (dataset.sources[0], bad_source) + dataset.sources[2:]
    mutated = dataclasses.replace(dataset, sources=mutated_sources)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "SOURCE_ANCHOR_RANGE_OUT_OF_BOUNDS" in codes
    assert source.id in exclusions.source_ids


def test_anchor_checksum_covers_excerpt_substring_not_whole_body() -> None:
    """체크섬은 ``body[start:end]`` 부분 문자열 기준이어야 한다(design.md "앵커가 가리키는
    부분 문자열의 빌드 시 해시"). anchor가 본문의 진짜 부분집합을 가리키는데 체크섬이 전체
    본문 해시라면(부분 문자열 해시가 아니라면) 불일치로 잡혀야 한다.
    """

    dataset = build_mock_dataset()
    source = dataset.sources[1]
    partial_end = min(10, len(source.body))
    whole_body_checksum = hashlib.sha256(source.body.encode("utf-8")).hexdigest()
    bad_anchor = dataclasses.replace(
        source.anchors[0],
        start_offset=0,
        end_offset=partial_end,
        excerpt_checksum=whole_body_checksum,
    )
    bad_source = dataclasses.replace(source, anchors=(bad_anchor,))
    mutated_sources = (dataset.sources[0], bad_source) + dataset.sources[2:]
    mutated = dataclasses.replace(dataset, sources=mutated_sources)

    diagnostics = validate_domain(mutated)

    codes = {d.code for d in diagnostics}
    assert "SOURCE_ANCHOR_CHECKSUM_MISMATCH" in codes


# ---------------------------------------------------------------------------
# (d) 표시 정책 유일성
# ---------------------------------------------------------------------------


def test_duplicate_display_policy_id_is_fatal() -> None:
    dataset = build_mock_dataset()
    notices = dataset.display_policies.notices
    duplicated_notice = dataclasses.replace(notices[1], id=notices[0].id)
    mutated_notices = (notices[0], duplicated_notice) + notices[2:]
    mutated_policies = dataclasses.replace(dataset.display_policies, notices=mutated_notices)
    mutated = dataclasses.replace(dataset, display_policies=mutated_policies)

    diagnostics = validate_domain(mutated)

    assert has_fatal(diagnostics)
    fatal_codes = {d.code for d in diagnostics if d.severity is Severity.FATAL}
    assert "DUPLICATE_DISPLAY_POLICY_ID" in fatal_codes


def test_duplicate_similarity_warning_policy_id_is_fatal() -> None:
    dataset = build_mock_dataset()
    warnings = dataset.display_policies.similarity_warnings
    duplicated = dataclasses.replace(warnings[1], id=warnings[0].id)
    mutated_warnings = (warnings[0], duplicated) + warnings[2:]
    mutated_policies = dataclasses.replace(dataset.display_policies, similarity_warnings=mutated_warnings)
    mutated = dataclasses.replace(dataset, display_policies=mutated_policies)

    diagnostics = validate_domain(mutated)

    assert has_fatal(diagnostics)
    fatal_codes = {d.code for d in diagnostics if d.severity is Severity.FATAL}
    assert "DUPLICATE_SIMILARITY_WARNING_POLICY_ID" in fatal_codes


# ---------------------------------------------------------------------------
# (e) 유사도 경고 구간 [0, 100] 무결·비중첩
# ---------------------------------------------------------------------------


def test_similarity_warning_band_gap_is_fatal() -> None:
    dataset = build_mock_dataset()
    warnings = dataset.display_policies.similarity_warnings
    by_key = {w.key: w for w in warnings}
    low = by_key["LOW"]
    # LOW의 상한을 40으로 좁혀서 [40, 50)에 gap을 만든다(MEDIUM은 [50, 80) 그대로).
    narrowed_low = dataclasses.replace(low, max_exclusive=40)
    mutated_warnings = tuple(narrowed_low if w.key == "LOW" else w for w in warnings)
    mutated_policies = dataclasses.replace(dataset.display_policies, similarity_warnings=mutated_warnings)
    mutated = dataclasses.replace(dataset, display_policies=mutated_policies)

    diagnostics = validate_domain(mutated)

    assert has_fatal(diagnostics)
    fatal_codes = {d.code for d in diagnostics if d.severity is Severity.FATAL}
    assert "SIMILARITY_WARNING_BAND_GAP" in fatal_codes


def test_similarity_warning_band_overlap_is_fatal() -> None:
    dataset = build_mock_dataset()
    warnings = dataset.display_policies.similarity_warnings
    by_key = {w.key: w for w in warnings}
    low = by_key["LOW"]
    # LOW의 상한을 60으로 넓혀서 MEDIUM([50, 80))과 겹치게 만든다.
    widened_low = dataclasses.replace(low, max_exclusive=60)
    mutated_warnings = tuple(widened_low if w.key == "LOW" else w for w in warnings)
    mutated_policies = dataclasses.replace(dataset.display_policies, similarity_warnings=mutated_warnings)
    mutated = dataclasses.replace(dataset, display_policies=mutated_policies)

    diagnostics = validate_domain(mutated)

    assert has_fatal(diagnostics)
    fatal_codes = {d.code for d in diagnostics if d.severity is Severity.FATAL}
    assert "SIMILARITY_WARNING_BAND_OVERLAP" in fatal_codes


def test_similarity_warning_band_missing_lower_zero_is_fatal() -> None:
    dataset = build_mock_dataset()
    warnings = dataset.display_policies.similarity_warnings
    by_key = {w.key: w for w in warnings}
    low = by_key["LOW"]
    mutated_low = dataclasses.replace(low, min_inclusive=1)
    mutated_warnings = tuple(mutated_low if w.key == "LOW" else w for w in warnings)
    mutated_policies = dataclasses.replace(dataset.display_policies, similarity_warnings=mutated_warnings)
    mutated = dataclasses.replace(dataset, display_policies=mutated_policies)

    diagnostics = validate_domain(mutated)

    assert has_fatal(diagnostics)
    fatal_codes = {d.code for d in diagnostics if d.severity is Severity.FATAL}
    assert "SIMILARITY_WARNING_BAND_LOWER_BOUND_INVALID" in fatal_codes


def test_similarity_warning_band_missing_upper_hundred_is_fatal() -> None:
    dataset = build_mock_dataset()
    warnings = dataset.display_policies.similarity_warnings
    by_key = {w.key: w for w in warnings}
    high = by_key["HIGH"]
    mutated_high = dataclasses.replace(high, max_inclusive=99)
    mutated_warnings = tuple(mutated_high if w.key == "HIGH" else w for w in warnings)
    mutated_policies = dataclasses.replace(dataset.display_policies, similarity_warnings=mutated_warnings)
    mutated = dataclasses.replace(dataset, display_policies=mutated_policies)

    diagnostics = validate_domain(mutated)

    assert has_fatal(diagnostics)
    fatal_codes = {d.code for d in diagnostics if d.severity is Severity.FATAL}
    assert "SIMILARITY_WARNING_BAND_UPPER_BOUND_INVALID" in fatal_codes


# ---------------------------------------------------------------------------
# (f) 요약 canonical 값 일치
# ---------------------------------------------------------------------------


def test_canonical_legality_status_mismatch_is_warning_and_isolates_case() -> None:
    dataset = build_mock_dataset()
    case = dataset.cases[0]
    from domain.enums import LegalityStatus

    other_status = (
        LegalityStatus.UNLAWFUL if case.legality_status is LegalityStatus.LAWFUL else LegalityStatus.LAWFUL
    )
    bad_summaries = dataclasses.replace(case.summaries, canonical_legality_status=other_status)
    bad_case = dataclasses.replace(case, summaries=bad_summaries)
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "SUMMARY_CANONICAL_LEGALITY_MISMATCH" in codes
    assert case.id in exclusions.case_ids


def test_canonical_instance_charge_mismatch_is_warning_and_isolates_case() -> None:
    dataset = build_mock_dataset()
    case = dataset.cases[0]
    bad_summaries = dataclasses.replace(case.summaries, canonical_instance_charge="다른 죄명")
    bad_case = dataclasses.replace(case, summaries=bad_summaries)
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "SUMMARY_CANONICAL_CHARGE_MISMATCH" in codes
    assert case.id in exclusions.case_ids


def test_canonical_instance_outcome_mismatch_is_warning_and_isolates_case() -> None:
    dataset = build_mock_dataset()
    case = dataset.cases[0]
    bad_summaries = dataclasses.replace(case.summaries, canonical_instance_outcome="다른 결과")
    bad_case = dataclasses.replace(case, summaries=bad_summaries)
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "SUMMARY_CANONICAL_OUTCOME_MISMATCH" in codes
    assert case.id in exclusions.case_ids


# ---------------------------------------------------------------------------
# (g) 현행법 우선순위 배정
# ---------------------------------------------------------------------------


def test_current_law_basis_lower_priority_than_old_law_basis_is_warning_and_isolates_query() -> None:
    dataset = build_mock_dataset()
    query = dataset.queries[0]
    case_id, preset = next(iter(query.similarity_by_case.items()))
    case = next(c for c in dataset.cases if c.id == case_id)

    # 대상 판례를 구법_기준으로 바꾸고 search_priority를 1(가장 좋은 우선순위)로 둔다.
    old_case = dataclasses.replace(case, expected_law_basis_status=LawBasisStatus.OLD_LAW_BASIS)
    mutated_cases = tuple(old_case if c.id == case_id else c for c in dataset.cases)

    other_case_id, other_preset = next(
        (cid, p) for cid, p in query.similarity_by_case.items() if cid != case_id
    )
    # 나머지 현행법_기준 판례가 구법_기준 판례보다 더 나쁜(더 큰) search_priority를 갖게 해
    # "현행법_기준이 구법_기준보다 낮은 우선순위" 위반을 만든다.
    old_preset = dataclasses.replace(preset, search_priority=1)
    current_preset = dataclasses.replace(other_preset, search_priority=2)
    mutated_similarity = dict(query.similarity_by_case)
    mutated_similarity[case_id] = old_preset
    mutated_similarity[other_case_id] = current_preset
    mutated_query = dataclasses.replace(query, similarity_by_case=mutated_similarity)
    mutated_queries = (mutated_query,) + dataset.queries[1:]

    mutated = dataclasses.replace(dataset, cases=mutated_cases, queries=mutated_queries)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "LAW_BASIS_PRIORITY_VIOLATION" in codes
    assert query.id in exclusions.query_ids


# ---------------------------------------------------------------------------
# (h) 상대 시각 anchor 비순환
# ---------------------------------------------------------------------------


def test_relative_time_anchor_cycle_is_warning_and_isolates_query() -> None:
    dataset = build_mock_dataset()
    query = dataset.queries[0]

    event_a = RecognizedEvent(
        id=EventId("event-a"),
        original_text="사건 A",
        action="행위 A",
        original_order=1,
        relative_time=RelativeTime(expression="사건 B 이후", anchor_event_id=EventId("event-b")),
    )
    event_b = RecognizedEvent(
        id=EventId("event-b"),
        original_text="사건 B",
        action="행위 B",
        original_order=2,
        relative_time=RelativeTime(expression="사건 A 이후", anchor_event_id=EventId("event-a")),
    )
    mutated_query = dataclasses.replace(query, recognized_events=(event_a, event_b))
    mutated_queries = (mutated_query,) + dataset.queries[1:]
    mutated = dataclasses.replace(dataset, queries=mutated_queries)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "RELATIVE_TIME_ANCHOR_CYCLE" in codes
    assert query.id in exclusions.query_ids


def test_relative_time_anchor_acyclic_chain_is_not_flagged() -> None:
    """비순환 사슬(A -> B -> C)은 순환으로 잘못 판정되지 않아야 한다."""

    dataset = build_mock_dataset()
    query = dataset.queries[0]

    event_c = RecognizedEvent(
        id=EventId("event-c"),
        original_text="사건 C",
        action="행위 C",
        original_order=1,
        explicit_time="2024-01-01T09:00:00",
    )
    event_b = RecognizedEvent(
        id=EventId("event-b"),
        original_text="사건 B",
        action="행위 B",
        original_order=2,
        relative_time=RelativeTime(expression="사건 C 이후", anchor_event_id=EventId("event-c")),
    )
    event_a = RecognizedEvent(
        id=EventId("event-a"),
        original_text="사건 A",
        action="행위 A",
        original_order=3,
        relative_time=RelativeTime(expression="사건 B 이후", anchor_event_id=EventId("event-b")),
    )
    mutated_query = dataclasses.replace(query, recognized_events=(event_a, event_b, event_c))
    mutated_queries = (mutated_query,) + dataset.queries[1:]
    mutated = dataclasses.replace(dataset, queries=mutated_queries)

    diagnostics = validate_domain(mutated)

    codes = {d.code for d in diagnostics}
    assert "RELATIVE_TIME_ANCHOR_CYCLE" not in codes


def test_dangling_applied_statute_source_reference_is_warning_and_isolates_case() -> None:
    """``CaseRecord.applied_statutes[].source_id``가 끊긴 경우는 ``CaseRecord.source_ids``의
    단절(``test_dangling_case_source_reference_is_warning_and_isolates_case``)과 별도 경로에서
    검사되므로 독립적으로 mutation 테스트한다."""

    dataset = build_mock_dataset()
    case = dataset.cases[0]
    bad_applied = dataclasses.replace(
        case.applied_statutes[0], source_id=SourceId("source-does-not-exist")
    )
    bad_case = dataclasses.replace(case, applied_statutes=(bad_applied,))
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "DANGLING_SOURCE_REFERENCE" in codes
    assert any("applied_statutes[0].source_id" in d.path for d in diagnostics)
    assert case.id in exclusions.case_ids


def test_dangling_applied_statute_version_reference_is_warning_and_isolates_case() -> None:
    dataset = build_mock_dataset()
    case = dataset.cases[0]
    bad_applied = dataclasses.replace(
        case.applied_statutes[0], statute_version_id=StatuteVersionId("statute-version-missing")
    )
    bad_case = dataclasses.replace(case, applied_statutes=(bad_applied,))
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "DANGLING_STATUTE_VERSION_REFERENCE" in codes
    assert case.id in exclusions.case_ids


def test_dangling_query_match_statute_version_reference_is_warning_and_isolates_query() -> None:
    """``QueryFixture.match.case_ids`` 단절(이미 테스트됨)과 별도로
    ``match.statute_version_ids`` 단절도 독립적으로 검사되어야 한다."""

    dataset = build_mock_dataset()
    query = dataset.queries[0]
    bad_match = dataclasses.replace(
        query.match, statute_version_ids=(StatuteVersionId("statute-version-does-not-exist"),)
    )
    bad_query = dataclasses.replace(query, match=bad_match)
    mutated_queries = (bad_query,) + dataset.queries[1:]
    mutated = dataclasses.replace(dataset, queries=mutated_queries)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "DANGLING_STATUTE_VERSION_REFERENCE" in codes
    assert query.id in exclusions.query_ids


def test_dangling_issue_link_source_reference_is_warning_and_isolates_query() -> None:
    """``RecognizedEvent.issue_links[].source_ids``의 단절은 별도 경로에서 검사되며 다른
    참조 단절 검사(response template, review fixture 등)와 별개로 커버되어야 한다."""

    dataset = build_mock_dataset()
    query = dataset.queries[0]

    event = RecognizedEvent(
        id=EventId("event-issue-link"),
        original_text="사건",
        action="행위",
        original_order=1,
        issue_links=(IssueLink(issue="쟁점", source_ids=(SourceId("source-does-not-exist"),)),),
    )
    mutated_query = dataclasses.replace(query, recognized_events=(event,))
    mutated_queries = (mutated_query,) + dataset.queries[1:]
    mutated = dataclasses.replace(dataset, queries=mutated_queries)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "DANGLING_SOURCE_REFERENCE" in codes
    assert query.id in exclusions.query_ids


def test_relative_time_anchor_dangling_reference_is_warning_and_isolates_query() -> None:
    """순환이 아니라 존재하지 않는 이벤트를 가리키는 단순 단절은
    ``RELATIVE_TIME_ANCHOR_DANGLING``으로 잡혀야 하며 ``RELATIVE_TIME_ANCHOR_CYCLE``(이미
    테스트됨)과는 다른 코드다."""

    dataset = build_mock_dataset()
    query = dataset.queries[0]

    event = RecognizedEvent(
        id=EventId("event-solo"),
        original_text="사건",
        action="행위",
        original_order=1,
        relative_time=RelativeTime(
            expression="사건 X 이후", anchor_event_id=EventId("event-does-not-exist")
        ),
    )
    mutated_query = dataclasses.replace(query, recognized_events=(event,))
    mutated_queries = (mutated_query,) + dataset.queries[1:]
    mutated = dataclasses.replace(dataset, queries=mutated_queries)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "RELATIVE_TIME_ANCHOR_DANGLING" in codes
    assert "RELATIVE_TIME_ANCHOR_CYCLE" not in codes
    assert query.id in exclusions.query_ids


def test_dangling_selection_review_fixture_evidence_source_reference_isolates_fixture() -> None:
    """``SelectionReviewFixture.claims[].evidence[].source_id`` 단절은
    ``response_templates``의 동일한 종류 단절과 별도 경로(``_check_selection_review_fixture``)
    에서 검사되며, 지금까지는 response_template 쪽만 mutation 테스트되어 있었다."""

    dataset = build_mock_dataset()
    fixture = dataset.review_fixtures[0]
    claim = fixture.claims[0]
    bad_evidence = dataclasses.replace(claim.evidence[0], source_id=SourceId("source-missing"))
    bad_claim = dataclasses.replace(claim, evidence=(bad_evidence,))
    mutated_claims = (bad_claim,) + fixture.claims[1:]
    bad_fixture = dataclasses.replace(fixture, claims=mutated_claims)
    mutated_fixtures = (bad_fixture,) + dataset.review_fixtures[1:]
    mutated = dataclasses.replace(dataset, review_fixtures=mutated_fixtures)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "DANGLING_SOURCE_REFERENCE" in codes
    assert fixture.response_template_id in exclusions.review_fixture_response_template_ids


def test_duplicate_event_id_within_query_is_warning_and_isolates_query() -> None:
    dataset = build_mock_dataset()
    query = dataset.queries[0]

    event_1 = RecognizedEvent(
        id=EventId("event-dup"),
        original_text="사건 1",
        action="행위 1",
        original_order=1,
    )
    event_2 = RecognizedEvent(
        id=EventId("event-dup"),
        original_text="사건 2",
        action="행위 2",
        original_order=2,
    )
    mutated_query = dataclasses.replace(query, recognized_events=(event_1, event_2))
    mutated_queries = (mutated_query,) + dataset.queries[1:]
    mutated = dataclasses.replace(dataset, queries=mutated_queries)

    diagnostics, exclusions = validate_domain_detailed(mutated)

    assert not has_fatal(diagnostics)
    codes = {d.code for d in diagnostics}
    assert "DUPLICATE_EVENT_ID" in codes
    assert query.id in exclusions.query_ids
