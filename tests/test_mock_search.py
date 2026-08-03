"""``domain.mock_search.run_mock_search`` 단위 테스트 (task 5.1).

fixture ID 조회 기반 목업 검색과 결과 projection을 검증한다: 성공적인 조회의 모든
필드가 원본 ``CaseRecord``/``StatuteVersion``과 정확히 일치하는지(재계산 없음),
누락/dangling ID가 전체 실패 없이 격리되는지, 선언된 ID가 하나도 조회되지 않으면
``목업 데이터 부족``으로 안전 실패하는지를 확인한다.
"""

from __future__ import annotations

import dataclasses

from data.fixture_repository import FixtureRepository
from data.models_query import QueryMatch
from data.validated_dataset import validate_dataset
from domain.enums import RagStage
from domain.ids import CaseId, StatuteVersionId
from domain.result import Err, Ok
from domain.mock_search import run_mock_search
from fixtures.mock_dataset import build_mock_dataset


def _build_repo() -> FixtureRepository:
    dataset = build_mock_dataset()
    result = validate_dataset(dataset)
    assert isinstance(result, Ok)
    return FixtureRepository(result.value)


def test_successful_lookup_projects_all_required_fields_verbatim() -> None:
    dataset = build_mock_dataset()
    repo = _build_repo()
    query = next(q for q in dataset.queries if q.id == "query-arrest")
    lawful_case = repo.get_case(CaseId("case-arrest-lawful"))
    assert lawful_case is not None
    statute_version = repo.get_statute_version(
        StatuteVersionId("statute-version-criminal-act-125")
    )
    assert statute_version is not None
    statute = repo.get_statute(statute_version.statute_id)
    assert statute is not None

    result = run_mock_search(query, repo)

    assert isinstance(result, Ok)
    projection = result.value
    assert projection.missing_case_ids == ()
    assert projection.missing_statute_version_ids == ()

    case_projection = next(
        c for c in projection.cases if c.case_id == lawful_case.id
    )
    assert case_projection.case_number == lawful_case.case_number
    assert case_projection.court_name == lawful_case.court_name
    assert case_projection.instance == lawful_case.instance
    assert case_projection.decision_date == lawful_case.decision_date
    assert case_projection.scenario_ids == lawful_case.scenario_ids
    assert case_projection.legality_status == lawful_case.legality_status
    assert case_projection.law_basis_status == lawful_case.expected_law_basis_status
    assert case_projection.applied_statute_labels == tuple(
        ref.citation_label for ref in lawful_case.applied_statutes
    )
    assert case_projection.instance_recognized_charge == lawful_case.instance_recognized_charge
    assert case_projection.instance_outcome == lawful_case.instance_outcome

    statute_projection = next(
        s
        for s in projection.statutes
        if s.statute_version_id == statute_version.id
    )
    assert statute_projection.law_name == statute.law_name
    assert statute_projection.article == statute_version.article
    assert statute_projection.paragraph == statute_version.paragraph
    assert statute_projection.item == statute_version.item
    assert statute_projection.effective_date == statute_version.effective_date
    assert statute_projection.revision_date == statute_version.revision_date
    assert statute_projection.version_label == statute_version.version_label
    assert statute_projection.revision_summary == statute_version.revision_summary

    # 요구사항 3.1: 직접 근거 출처_식별자 집합은 resolved 판례의 source_ids 합집합이다.
    for case_projection2 in projection.cases:
        resolved_case = repo.get_case(case_projection2.case_id)
        assert resolved_case is not None
        for source_id in resolved_case.source_ids:
            assert source_id in projection.direct_evidence_source_ids


def test_missing_case_id_is_isolated_not_crashing_whole_search() -> None:
    dataset = build_mock_dataset()
    repo = _build_repo()
    query = next(q for q in dataset.queries if q.id == "query-arrest")
    dangling_case_id = CaseId("case-does-not-exist")
    mutated_match = dataclasses.replace(
        query.match, case_ids=query.match.case_ids + (dangling_case_id,)
    )
    mutated_query = dataclasses.replace(query, match=mutated_match)

    result = run_mock_search(mutated_query, repo)

    assert isinstance(result, Ok)
    projection = result.value
    assert dangling_case_id in projection.missing_case_ids
    # 유효한 판례는 여전히 조회되어 격리되지 않은 상태로 남는다.
    assert len(projection.cases) == len(query.match.case_ids)


def test_missing_statute_version_id_is_isolated_not_crashing_whole_search() -> None:
    dataset = build_mock_dataset()
    repo = _build_repo()
    query = next(q for q in dataset.queries if q.id == "query-arrest")
    dangling_version_id = StatuteVersionId("statute-version-does-not-exist")
    mutated_match = dataclasses.replace(
        query.match,
        statute_version_ids=query.match.statute_version_ids + (dangling_version_id,),
    )
    mutated_query = dataclasses.replace(query, match=mutated_match)

    result = run_mock_search(mutated_query, repo)

    assert isinstance(result, Ok)
    projection = result.value
    assert dangling_version_id in projection.missing_statute_version_ids
    assert len(projection.statutes) == len(query.match.statute_version_ids)
    # 여전히 유효한 case 조회는 그대로 유지된다.
    assert len(projection.cases) == len(query.match.case_ids)


def test_all_ids_missing_returns_mock_data_insufficient_error() -> None:
    dataset = build_mock_dataset()
    repo = _build_repo()
    query = next(q for q in dataset.queries if q.id == "query-arrest")
    all_missing_match = QueryMatch(
        case_ids=(CaseId("case-missing-1"),),
        statute_version_ids=(StatuteVersionId("statute-version-missing-1"),),
        response_template_id=query.match.response_template_id,
    )
    mutated_query = dataclasses.replace(query, match=all_missing_match)

    result = run_mock_search(mutated_query, repo)

    assert isinstance(result, Err)
    error = result.error
    assert error.code == "MOCK_DATA_INSUFFICIENT"
    assert error.stage == RagStage.MOCK_SEARCH
    assert "case-missing-1" in error.affected_record_ids
    assert "statute-version-missing-1" in error.affected_record_ids


def test_empty_match_declaring_no_ids_returns_empty_ok_projection() -> None:
    dataset = build_mock_dataset()
    repo = _build_repo()
    query = next(q for q in dataset.queries if q.id == "query-arrest")
    empty_match = QueryMatch(
        case_ids=(),
        statute_version_ids=(),
        response_template_id=query.match.response_template_id,
    )
    mutated_query = dataclasses.replace(query, match=empty_match)

    result = run_mock_search(mutated_query, repo)

    assert isinstance(result, Ok)
    projection = result.value
    assert projection.cases == ()
    assert projection.statutes == ()
    assert projection.missing_case_ids == ()
    assert projection.missing_statute_version_ids == ()


def test_projection_preserves_match_order_no_resorting() -> None:
    dataset = build_mock_dataset()
    repo = _build_repo()
    query = next(q for q in dataset.queries if q.id == "query-arrest")

    result = run_mock_search(query, repo)

    assert isinstance(result, Ok)
    projection = result.value
    assert [c.case_id for c in projection.cases] == list(query.match.case_ids)
    assert [s.statute_version_id for s in projection.statutes] == list(
        query.match.statute_version_ids
    )


def test_similarity_score_is_preserved_and_invalid_preset_is_case_local() -> None:
    dataset = build_mock_dataset()
    repo = _build_repo()
    query = next(q for q in dataset.queries if q.id == "query-arrest")
    invalid_case_id = query.match.case_ids[0]
    valid_case_id = query.match.case_ids[1]
    invalid_preset = dataclasses.replace(
        query.similarity_by_case[invalid_case_id], score=float("inf")
    )
    mutated_presets = dict(query.similarity_by_case)
    mutated_presets[invalid_case_id] = invalid_preset
    mutated_query = dataclasses.replace(query, similarity_by_case=mutated_presets)

    result = run_mock_search(mutated_query, repo)

    assert isinstance(result, Ok)
    projection = result.value
    assert [case.case_id for case in projection.cases] == [valid_case_id]
    assert projection.cases[0].similarity_score == query.similarity_by_case[valid_case_id].score
    assert projection.case_data_errors == (
        projection.case_data_errors[0],
    )
    assert projection.case_data_errors[0].case_id == invalid_case_id
    assert projection.case_data_errors[0].policy_record_id == "status-similarity-data-error"
    assert projection.case_data_errors[0].message == "유사도 데이터 오류"


def test_missing_non_numeric_and_out_of_range_scores_are_isolated() -> None:
    dataset = build_mock_dataset()
    repo = _build_repo()
    query = next(q for q in dataset.queries if q.id == "query-arrest")
    invalid_case_id = query.match.case_ids[0]

    for invalid_score in (None, "90", -0.1, 100.1):
        mutated_presets = dict(query.similarity_by_case)
        if invalid_score is None:
            del mutated_presets[invalid_case_id]
        else:
            mutated_presets[invalid_case_id] = dataclasses.replace(
                query.similarity_by_case[invalid_case_id], score=invalid_score  # type: ignore[arg-type]
            )
        result = run_mock_search(
            dataclasses.replace(query, similarity_by_case=mutated_presets), repo
        )

        assert isinstance(result, Ok)
        assert invalid_case_id not in [case.case_id for case in result.value.cases]
        assert [error.case_id for error in result.value.case_data_errors] == [invalid_case_id]


def test_sort_is_deterministic_and_keeps_current_law_before_old_law() -> None:
    from domain.enums import LawBasisStatus, LegalityStatus
    from domain.mock_search import SearchCaseProjection, sort_cases_deterministically

    def projection(case_id: str, status: LawBasisStatus, priority: int, tie_order: int) -> SearchCaseProjection:
        return SearchCaseProjection(
            case_id=CaseId(case_id),
            case_number=case_id,
            court_name="법원",
            instance="1심",
            decision_date="2024-01-01",
            scenario_ids=(),
            legality_status=LegalityStatus.LAWFUL,
            law_basis_status=status,
            applied_statute_labels=(),
            similarity_score=50.0,
            search_priority=priority,
            tie_order=tie_order,
            instance_recognized_charge="죄명",
            instance_outcome="결과",
        )

    cases = (
        projection("case-z", LawBasisStatus.OLD_LAW_BASIS, 1, 1),
        projection("case-b", LawBasisStatus.CURRENT_LAW_BASIS, 2, 1),
        projection("case-a", LawBasisStatus.CURRENT_LAW_BASIS, 2, 1),
    )

    assert [case.case_id for case in sort_cases_deterministically(cases)] == [
        CaseId("case-a"),
        CaseId("case-b"),
        CaseId("case-z"),
    ]
    assert sort_cases_deterministically(tuple(reversed(cases))) == sort_cases_deterministically(cases)


def test_duplicate_match_and_reference_ids_are_projected_exactly_once() -> None:
    """Requirements 3.1, 3.2, 3.7, and 10.1 preserve unique IDs/tags."""

    dataset = build_mock_dataset()
    repo = _build_repo()
    query = next(item for item in dataset.queries if item.id == "query-arrest")
    case_id = query.match.case_ids[0]
    source_case = repo.get_case(case_id)
    assert source_case is not None
    repo._cases_by_id[case_id] = dataclasses.replace(
        source_case,
        source_ids=source_case.source_ids + source_case.source_ids,
        applied_statutes=source_case.applied_statutes + source_case.applied_statutes,
    )
    duplicated_query = dataclasses.replace(
        query,
        match=QueryMatch(
            case_ids=(case_id, case_id),
            statute_version_ids=(
                query.match.statute_version_ids[0],
                query.match.statute_version_ids[0],
            ),
            response_template_id=query.match.response_template_id,
        ),
    )

    result = run_mock_search(duplicated_query, repo)

    assert isinstance(result, Ok)
    assert [item.case_id for item in result.value.cases] == [case_id]
    assert [item.statute_version_id for item in result.value.statutes] == [
        query.match.statute_version_ids[0]
    ]
    assert result.value.direct_evidence_source_ids == source_case.source_ids
    assert result.value.cases[0].applied_statute_labels == ("형법 제125조",)


def test_charge_and_outcome_missingness_use_independent_placeholders() -> None:
    dataset = build_mock_dataset()
    repo = _build_repo()
    query = next(q for q in dataset.queries if q.id == "query-accompany")
    case_id = query.match.case_ids[0]
    case = repo.get_case(case_id)
    assert case is not None
    repo._cases_by_id[case_id] = dataclasses.replace(case, instance_outcome=None)

    result = run_mock_search(query, repo)

    assert isinstance(result, Ok)
    projection = next(item for item in result.value.cases if item.case_id == case_id)
    assert projection.instance_recognized_charge == "확인되지 않음"
    assert projection.instance_outcome == "확인되지 않음"
