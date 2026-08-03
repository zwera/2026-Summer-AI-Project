"""fixture ID 조회 기반 목업 검색과 결과 projection (task 5.1).

``design.md`` "핵심 포트와 함수 시그니처"의 다음 계약을 구현한다::

    function runMockSearch(
      query: AcceptedQuery,
      repo: FixtureRepository
    ): Result<SearchProjection, MockRagError>;

그리고 "목업 검색과 정렬"(4.2) 절의 첫 규칙을 구현한다: "검색은
``queryFixture.match.caseIds``와 ``statuteVersionIds``를 ID로 조회하는 작업이다. 전문
검색, 임베딩 또는 점수 계산을 하지 않는다."

## 이 태스크(5.1)의 범위

task 5.1은 **순수 ID 조회 + 있는 그대로의 필드 projection**만 다룬다. 다음은 이 모듈이
하지 않는다(각각 이후 태스크의 책임):

- 유사도 preset 보존/격리, 안정 정렬(task 5.2 ``sortCasesDeterministically``) — 이 모듈은
  ``query.match.case_ids``/``statute_version_ids`` 순서를 그대로 유지한다.
- ``instance_recognized_charge``/``instance_outcome`` 누락 필드의 ``확인되지 않음``
  placeholder 치환(task 5.2, 요구사항 7.10) — 이 모듈은 ``CaseRecord``의 원본 값(``None``
  포함)을 그대로 옮긴다.
- 인용 조립·출처 완전성 검증(task 6.x ``citationsForClaim``).
- 시나리오·적법성 partition(task 7.x).
- ``classifyLawStatus``를 통한 실제 법령_기준_상태 재판정(task 11.1) — 이 모듈은
  ``CaseRecord.expected_law_basis_status``(사전 선언된/기대되는 값)를 재계산 없이
  placeholder로 그대로 옮긴다. task 11.1이 ``applied_statutes``와 ``StatuteVersion``에서
  실제 ``classifyLawStatus``를 실행해 이 값을 검증하거나 대체할 별도 projection 계층을
  추가할 수 있다.

## 개별 누락 ID 처리 방침 (요구사항 13.8, "레코드_격리")

``data.validated_dataset``의 격리 전략은 **비전이적**이다: 판례 A가 격리된 출처를
참조해도 A 자체는 그대로 노출될 수 있다. 같은 이유로, 질의가 격리되지 않았어도(clean
``QueryFixture``) 그 ``match.case_ids``/``statute_version_ids``가 가리키는 개별 판례나
법조문 버전이 *다른* 이유로 격리되어 ``FixtureRepository``에서 조회되지 않을 수 있다.

이 함수는 다음과 같이 두 단계로 나눠 처리한다.

1. **개별 누락은 격리한다**: 조회에 실패한 개별 case_id/statute_version_id는 그 ID만
   결과 projection에서 제외하고(요구사항 13.8·설계 문서 "레코드_격리" 원칙과 동일하게
   유효한 나머지 레코드는 그대로 유지) 조사를 위해 ``missing_case_ids``/
   ``missing_statute_version_ids``로 반환값에 보존한다. 이는 목업 데이터 규모에서
   "판례 목록이 비어 있으면 일치하는 목업 자료 없음을 표시"(요구사항 3.12)하는 흐름과
   합성적으로 맞는다 — 부분 결과도 유효한 결과다.
2. **전체 실패는 안전하게 실패한다**: ``query.match``가 하나 이상의 case_id 또는
   statute_version_id를 선언했는데 그중 **단 하나도** 조회에 성공하지 못하면(즉 판례도
   법조문도 전혀 근거로 제시할 수 없으면) 목업_RAG 흐름을 완료할 수 없다고 보아
   ``Err(MockRagError(code="MOCK_DATA_INSUFFICIENT", stage=MOCK_SEARCH, ...))``을 반환한다
   (요구사항 13.8 "필수 목업_데이터_레코드가 누락되어 목업_RAG 흐름을 완료할 수 없으면
   ... `목업 데이터 부족`으로 반환"). ``design.md`` 상태 기계의
   ``MOCK_SEARCH --> FAILED: 목업 데이터 부족 / 데이터 오류`` 전이가 바로 이 경로다.
   ``query.match``가 원래 case_id·statute_version_id를 하나도 선언하지 않은 경우는 이
   실패 조건에 해당하지 않는다(선언되지 않은 것과 선언되었지만 격리된 것은 다르다) —
   그 경우 두 목록이 모두 빈 ``Ok(SearchProjection)``을 반환한다.

이 방침은 개별 참조 오류마다 전체 검색을 실패시키지 않으면서도, 완전히 근거를 제시할 수
없는 상태를 안전하게 구분해 실패시킨다는 두 요구사항(레코드_격리의 "유효한 다른 레코드
유지"와 데이터셋_가용성_실패의 "필수 레코드 누락 시 안전 실패")을 모두 만족하기 위한
설계 판단이다.

## projection 필드 선택 근거

- **판례별 필드**(``SearchCaseProjection``): 요구사항 3.5(사건번호·법원명·심급·선고일·
  경찰_직무_시나리오), 3.6(적법성_상태·법령_기준_상태 — 유사도_점수는 task 5.2 책임),
  7.9(해당_심급_인정_죄명·해당_심급_재판_결과), 12.5(법원명·심급·사건번호·선고일·
  해당_심급_재판_결과)에서 요구하는 필드를 모두 ``CaseRecord``에서 재계산 없이 옮긴다.
  ``applied_statute_labels``는 태스크 지시의 "법조문 표시" 중 판례에 인용된 법조문의
  citation label을 판례 카드에 표시하는 부분을 담당한다(``AppliedStatuteRef.citationLabel``
  을 그대로 옮김). 요구사항 3.7이 요구하는 독립된 법조문 목록(법령명·조·항·호·시행일)은
  아래 ``SearchStatuteProjection``이 별도로 담당한다 — 두 field는 서로 다른 요구사항을
  만족하는 서로 다른 정보이므로 중복이 아니다.
- **법조문별 필드**(``SearchStatuteProjection``): 요구사항 3.7(법령명·조·항·호·시행일)을
  위해 ``StatuteVersion``과, 법령명은 ``StatuteRecord``(``FixtureRepository.get_statute``)
  에서 옮긴다. 개정일(``revision_date``)과 개정 설명(``revision_summary``)도 함께
  옮겨 두어 task 11.x의 "구법 기준" 배지 표시(요구사항 10.10)가 재조회 없이 이 projection
  을 재사용할 수 있게 한다.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import List, Optional, Sequence, Set, Tuple

from domain.enums import LawBasisStatus, LegalityStatus, PoliceScenario, RagStage
from domain.ids import CaseId, SourceId, StatuteVersionId
from domain.result import Err, Ok, Result

from data.fixture_repository import FixtureRepository
from data.models_common import Instance, IsoDate
from data.models_query import QueryFixture, SimilarityPreset

__all__ = [
    "MockRagError",
    "SearchCaseDataError",
    "SearchCaseProjection",
    "SearchStatuteProjection",
    "SearchProjection",
    "run_mock_search",
    "sort_cases_deterministically",
]


@dataclass(frozen=True)
class MockRagError:
    """목업_RAG 오류. design.md Data Models 12절 ``MockRagError``.

    ``code``는 design.md가 선언한 판별 유니온 값 중 이 모듈이 실제로 반환할 수 있는
    ``"MOCK_DATA_INSUFFICIENT"``만 사용한다. 다른 코드(``SOURCE_DATA_ERROR`` 등)는 각각
    책임을 지는 이후 태스크(6.x, 13.x 등)가 반환한다.
    """

    code: str
    stage: RagStage
    retryable: bool
    affected_record_ids: Tuple[str, ...]


@dataclass(frozen=True)
class SearchCaseDataError:
    """A fixture-backed, case-local search error.

    A malformed similarity preset never removes valid sibling cases.  The
    policy ID keeps the displayed message traceable to the dataset.
    """

    case_id: CaseId
    policy_record_id: str
    message: str


@dataclass(frozen=True)
class SearchCaseProjection:
    """판례 목업 검색 결과 하나. design.md ``SearchCaseProjection``(요구사항 3.5, 3.6,
    7.9, 12.5)의 필드를 ``CaseRecord``에서 재계산 없이 옮긴다.

    ``law_basis_status``는 ``CaseRecord.expected_law_basis_status``를 그대로 옮긴
    placeholder다 — 실제 ``classifyLawStatus`` 판정은 task 11.1의 책임이다(모듈
    docstring 참조). ``instance_recognized_charge``/``instance_outcome``은 ``None``일 수
    있으며, ``확인되지 않음`` placeholder 치환은 task 5.2가 수행한다.
    """

    case_id: CaseId
    case_number: str
    court_name: str
    instance: Instance
    decision_date: IsoDate
    scenario_ids: Tuple[PoliceScenario, ...]
    legality_status: LegalityStatus
    law_basis_status: LawBasisStatus
    applied_statute_labels: Tuple[str, ...]
    similarity_score: float
    search_priority: int
    tie_order: int
    instance_recognized_charge: str
    instance_outcome: str


@dataclass(frozen=True)
class SearchStatuteProjection:
    """법조문 목업 검색 결과 하나. design.md ``SearchStatuteProjection``(요구사항 3.7)의
    필드를 ``StatuteVersion``/``StatuteRecord``에서 재계산 없이 옮긴다.
    """

    statute_version_id: StatuteVersionId
    law_name: str
    article: str
    paragraph: Optional[str]
    item: Optional[str]
    effective_date: Optional[IsoDate]
    revision_date: Optional[IsoDate]
    version_label: Optional[str]
    revision_summary: Optional[str]


@dataclass(frozen=True)
class SearchProjection:
    """``runMockSearch``의 성공 결과. design.md ``SearchProjection``.

    ``cases``와 ``statutes``는 ``query.match``의 최초 등장 순서를 유지하되 각 유효 ID를
    정확히 한 번만 projection한다(정렬은 task 5.2 책임). ``direct_evidence_source_ids``는 요구사항 3.1 "직접 근거 출처_식별자
    집합"을 만족하기 위해 resolved 판례들의 ``source_ids``를 첫 등장 순서로 중복 제거해
    합친 것이다(claim 단위 인용 조립은 task 6.x 책임 — 이 필드는 판례 단위 직접 근거
    출처의 합집합일 뿐이다). ``missing_case_ids``/``missing_statute_version_ids``는 개별
    격리된(조회 실패한) ID를 진단용으로 보존한다.
    """

    cases: Tuple[SearchCaseProjection, ...]
    statutes: Tuple[SearchStatuteProjection, ...]
    direct_evidence_source_ids: Tuple[SourceId, ...]
    missing_case_ids: Tuple[CaseId, ...]
    missing_statute_version_ids: Tuple[StatuteVersionId, ...]
    case_data_errors: Tuple[SearchCaseDataError, ...]


def _is_valid_similarity_score(preset: Optional[SimilarityPreset]) -> bool:
    """Return whether ``preset`` has a finite numeric score in ``[0, 100]``."""

    if preset is None:
        return False
    score = preset.score
    return (
        isinstance(score, (int, float))
        and not isinstance(score, bool)
        and math.isfinite(score)
        and 0 <= score <= 100
    )


def _law_status_rank(status: LawBasisStatus) -> int:
    """Keep current-law cases ahead of old-law cases without recalculating ranks."""

    if status is LawBasisStatus.CURRENT_LAW_BASIS:
        return 0
    if status is LawBasisStatus.INDETERMINATE:
        return 1
    return 2


def sort_cases_deterministically(
    cases: Sequence[SearchCaseProjection],
) -> Tuple[SearchCaseProjection, ...]:
    """Sort by current-law precedence then ``(priority, tie order, case ID)``.

    The priority and tie values are fixture values.  The law-status prefix is
    only the explicit current-law safeguard required for a mixed result set;
    within each status group no score, priority, or tie value is recalculated.
    """

    return tuple(
        sorted(
            cases,
            key=lambda case: (
                _law_status_rank(case.law_basis_status),
                case.search_priority,
                case.tie_order,
                str(case.case_id),
            ),
        )
    )


def run_mock_search(
    query: QueryFixture, repo: FixtureRepository
) -> "Result[SearchProjection, MockRagError]":
    """``query.match``의 case/statute ID를 ``repo``에서 조회해 결과 projection을 만든다.

    재계산 없음: 유사도·정렬·법령 상태 재판정·인용 조립을 하지 않는다(모듈 docstring
    참조). 개별 누락 ID는 격리하고, ``match``가 선언한 ID가 하나 이상 있는데 전부 조회에
    실패하면 ``Err(MockRagError(code="MOCK_DATA_INSUFFICIENT", ...))``을 반환한다.
    """

    similarity_error_policy = repo.get_display_policy("SIMILARITY_DATA_ERROR")
    not_confirmed_policy = repo.get_display_policy("확인되지 않음")
    if similarity_error_policy is None or not_confirmed_policy is None:
        raise ValueError("validated dataset is missing required search display policies")

    resolved_cases: List[SearchCaseProjection] = []
    case_data_errors: List[SearchCaseDataError] = []
    missing_case_ids: List[CaseId] = []
    direct_evidence_source_ids: List[SourceId] = []
    seen_case_ids: Set[CaseId] = set()
    seen_source_ids: Set[SourceId] = set()

    for case_id in query.match.case_ids:
        if case_id in seen_case_ids:
            continue
        seen_case_ids.add(case_id)
        case = repo.get_case(case_id)
        if case is None:
            missing_case_ids.append(case_id)
            continue
        preset = query.similarity_by_case.get(case.id)
        if not _is_valid_similarity_score(preset):
            case_data_errors.append(
                SearchCaseDataError(
                    case_id=case.id,
                    policy_record_id=similarity_error_policy.id,
                    message=similarity_error_policy.text,
                )
            )
            continue
        assert preset is not None
        resolved_cases.append(
            SearchCaseProjection(
                case_id=case.id,
                case_number=case.case_number,
                court_name=case.court_name,
                instance=case.instance,
                decision_date=case.decision_date,
                scenario_ids=case.scenario_ids,
                legality_status=case.legality_status,
                law_basis_status=case.expected_law_basis_status,
                applied_statute_labels=tuple(
                    dict.fromkeys(
                        ref.citation_label for ref in case.applied_statutes
                    )
                ),
                similarity_score=preset.score,
                search_priority=preset.search_priority,
                tie_order=preset.tie_order,
                instance_recognized_charge=(
                    case.instance_recognized_charge
                    if case.instance_recognized_charge is not None
                    else not_confirmed_policy.text
                ),
                instance_outcome=(
                    case.instance_outcome
                    if case.instance_outcome is not None
                    else not_confirmed_policy.text
                ),
            )
        )
        for source_id in case.source_ids:
            if source_id not in seen_source_ids:
                seen_source_ids.add(source_id)
                direct_evidence_source_ids.append(source_id)

    resolved_statutes: List[SearchStatuteProjection] = []
    missing_statute_version_ids: List[StatuteVersionId] = []
    seen_statute_version_ids: Set[StatuteVersionId] = set()

    for statute_version_id in query.match.statute_version_ids:
        if statute_version_id in seen_statute_version_ids:
            continue
        seen_statute_version_ids.add(statute_version_id)
        version = repo.get_statute_version(statute_version_id)
        if version is None:
            missing_statute_version_ids.append(statute_version_id)
            continue
        statute = repo.get_statute(version.statute_id)
        law_name = statute.law_name if statute is not None else version.statute_id
        resolved_statutes.append(
            SearchStatuteProjection(
                statute_version_id=version.id,
                law_name=law_name,
                article=version.article,
                paragraph=version.paragraph,
                item=version.item,
                effective_date=version.effective_date,
                revision_date=version.revision_date,
                version_label=version.version_label,
                revision_summary=version.revision_summary,
            )
        )

    declared_any_id = bool(query.match.case_ids) or bool(query.match.statute_version_ids)
    resolved_any_id = bool(resolved_cases) or bool(resolved_statutes)

    if declared_any_id and not resolved_any_id:
        affected_record_ids = tuple(str(case_id) for case_id in missing_case_ids) + tuple(
            str(version_id) for version_id in missing_statute_version_ids
        )
        return Err(
            MockRagError(
                code="MOCK_DATA_INSUFFICIENT",
                stage=RagStage.MOCK_SEARCH,
                retryable=False,
                affected_record_ids=affected_record_ids,
            )
        )

    return Ok(
        SearchProjection(
            cases=sort_cases_deterministically(resolved_cases),
            statutes=tuple(resolved_statutes),
            direct_evidence_source_ids=tuple(direct_evidence_source_ids),
            missing_case_ids=tuple(missing_case_ids),
            missing_statute_version_ids=tuple(missing_statute_version_ids),
            case_data_errors=tuple(case_data_errors),
        )
    )
