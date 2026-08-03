"""선택 영역 재검토: 독립 주장 exact-once 추출, 근거 분류, 상세 설명 (task 12.1).

``design.md`` "4.7 선택 영역 재검토" 절의 다음 계약 의사코드를 Python으로 구현한다::

    classifyClaim(evidence):
      if any decision evidence has relation=CONTRADICTS: return CONFLICT
      if one or more decision evidence collectively cover the whole claim
         and none contradicts: return MATCH
      return INSUFFICIENT

그리고 "Components and Interfaces > 핵심 포트와 함수 시그니처"의::

    function classifyClaimEvidence(
      evidence: readonly ClaimEvidenceLink[]
    ): EvidenceStatus;

design.md "4. 명시적 가정과 모호성 해소" 9번(선택 재검토 단위)에 따라, 선택 가능한 목업
응답 DOM에는 ``claimId``가 부여되어 있고 클라이언트는 선택 범위와 겹치는 독립_주장
식별자 목록(``SELECT_CLAIMS`` 명령의 ``claimIds``)과 선택 문구(``text``)를 서버에
전달한다. 이 모듈은 자유 생성 텍스트를 분석하지 않고, 전달된 ``claimId`` 목록을
``ReviewableClaim.document_order``로 문서 순서를 재구성해 중복 없이(exact-once) 재검토
대상으로 확정한다.

## 이 태스크(12.1)의 범위

- :func:`select_overlapping_claims` — 요구사항 9.7, Property 25. 선택 범위와 겹치는
  ``claimId``를 ``document_order`` 기준 문서 순서로 정확히 한 번씩 추출한다. 알려지지
  않은 claim ID와 중복 참조는 무시한다(레코드_격리와 유사하게 유효한 나머지만 사용).
- :func:`is_selection_pending` — 요구사항 9.4, 9.5, 9.12, Property 28. 선택
  문구가 공백 문자로만 구성되거나(9.12) 겹치는 유효_주장이 하나도 없으면(9.4,
  "현재 목업_응답 범위 밖") 선택 대기로 판정한다.
- :func:`classify_claim_evidence` — 요구사항 9.8~9.11.
  결정_근거(``purpose=DECISION``)만 판정에 사용한다. 충돌하는 결정_근거가 하나라도
  있으면 최우선으로 ``근거_충돌``이다. 충돌이 없고 전체 지지(``relation=SUPPORTS ∧
  coverage=FULL``) 결정_근거가 하나 이상이면 ``근거_일치``다. 그 외(부분 지지만
  있거나 결정_근거가 전혀 없음)에는 ``근거_부족``이다.
- :func:`review_claim` — 요구사항 9.12, 9.13. 판정한 근거_상태와 함께, 그 상태를 실제로
  결정한 결정_근거 집합(``근거_일치``면 전체 지지 SUPPORTS/FULL, ``근거_충돌``이면
  CONTRADICTS, ``근거_부족``이면 결정한 근거 없음)과 ``purpose=REFERENCE``인
  참고_출처를 분리해 반환한다.
- :func:`review_selection` — 위 세 함수를 조합해 ``SelectionReviewResult``를 만든다.
  선택 대기 상태이면 ``claims=()``로 재검토 결과를 빈 집합으로 유지한다(요구사항 9.5).
- :func:`resolve_selection_explanation` — 요구사항 9.14, 9.15, Property 27. 상세 설명
  실행 시 ``SelectionExplanationFixture``의 법률 용어·문맥·판례_쟁점 필드를 그대로
  반환한다(합성하지 않음). 대응하는 fixture가 없거나, 있어도 내용이 비어 있어(법률
  용어·문맥·쟁점 모두 없음) 선택 문구의 의미를 확인할 수 없으면 `목업 자료에서 확인할
  수 없음` 표시 정책 문구와 목업_데이터_레코드에 사전 정의된 추가 필요 정보만 반환한다.

## 이 태스크가 하지 않는 것

- ``SelectionReviewFixture``·``SelectionExplanationFixture`` 자체의 생성
  (fixture 책임).
- 브라우저 DOM에서 선택 범위와 ``claimId``를 매핑하는 처리(클라이언트_웹_계층 책임,
  design.md 4절 9번). 이 모듈은 클라이언트가 이미 산출한 ``claimId`` 목록만 입력으로
  받는다.
- 출처 이동·강조(요구사항 9.17, ``SourceViewer``/클라이언트 책임).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from domain.enums import EvidenceStatus
from domain.ids import ClaimId

from data.models_common import DisplayPolicyRecord
from data.models_selection import (
    ClaimReviewOutcome,
    LegalTermExplanationEntry,
    ReviewableClaim,
    SelectionExplanationFixture,
    SelectionReviewResult,
)
from data.models_source import ClaimEvidenceLink

__all__ = [
    "select_overlapping_claims",
    "is_selection_pending",
    "classify_claim_evidence",
    "review_claim",
    "review_selection",
    "SelectionExplanationDisplay",
    "SelectionExplanationPolicyMissingError",
    "resolve_selection_explanation",
]


_EXPLANATION_NOT_FOUND_KEY = "EXPLANATION_NOT_FOUND"


# --------------------------------------------------------------------------
# 독립 주장 exact-once 추출 (요구사항 9.7, Property 25)
# --------------------------------------------------------------------------


def _is_blank_selection(text: str) -> bool:
    """요구사항 9.4/9.12: 공백 문자로만 구성되거나 빈 문자열이면 참이다."""

    return len(text.strip()) == 0


def select_overlapping_claims(
    selected_claim_ids: Sequence[ClaimId],
    claims: Sequence[ReviewableClaim],
) -> Tuple[ReviewableClaim, ...]:
    """``selected_claim_ids``와 겹치는 ``claims``를 문서 순서로 exact-once 추출한다.

    ``selected_claim_ids``에 같은 ID가 여러 번 나타나거나(같은 claim의 여러 DOM span
    선택, design.md Property 25 경계 사례) ``claims``에 존재하지 않는 ID가 섞여 있어도
    안전하게 무시하고, 최종 결과는 ``ReviewableClaim.document_order`` 오름차순으로
    정렬한다(선택이 문서 순서와 다르게 들어와도 항상 문서 순서로 재검토한다).
    """

    claims_by_id: Mapping[ClaimId, ReviewableClaim] = {
        claim.id: claim for claim in claims
    }
    seen: Set[ClaimId] = set()
    matched: List[ReviewableClaim] = []
    for claim_id in selected_claim_ids:
        if claim_id in seen:
            continue
        claim = claims_by_id.get(claim_id)
        if claim is None:
            continue
        seen.add(claim_id)
        matched.append(claim)
    return tuple(sorted(matched, key=lambda claim: claim.document_order))


def is_selection_pending(
    selected_text: str,
    selected_claim_ids: Sequence[ClaimId],
    claims: Sequence[ReviewableClaim],
) -> bool:
    """요구사항 9.4/9.5/9.12: 선택_재검토 상태가 선택 대기여야 하는지 판정한다.

    선택 문구가 공백 문자로만 구성되거나(9.12), 겹치는 유효 독립_주장이 하나도 없으면
    (9.4, "현재 목업_응답 범위 밖") 선택 대기다.
    """

    if _is_blank_selection(selected_text):
        return True
    return len(select_overlapping_claims(selected_claim_ids, claims)) == 0


# --------------------------------------------------------------------------
# 근거_상태 분류와 결정/참고 출처 partition (요구사항 9.8~9.13, Property 26)
# --------------------------------------------------------------------------


def classify_claim_evidence(
    evidence: Sequence[ClaimEvidenceLink],
) -> EvidenceStatus:
    """``evidence``(하나의 독립_주장에 연결된 전체 증거)로 근거_상태를 판정한다.

    ``purpose="DECISION"``인 결정_근거만 판정에 사용한다(``purpose="REFERENCE"``인
    참고_출처는 근거_상태를 직접 결정하지 않는다, 요구사항 9.13). 충돌(``relation=
    "CONTRADICTS"``)이 최우선이며, 충돌이 없고 전체 지지(``relation="SUPPORTS" ∧
    coverage="FULL"``) 결정_근거가 하나 이상이면 근거_일치, 그 외에는 근거_부족이다
    (모듈 docstring, design.md ``classifyClaim`` 계약).
    """

    decision_evidence = [
        item for item in evidence if item.purpose == "DECISION"
    ]

    if any(item.relation == "CONTRADICTS" for item in decision_evidence):
        return EvidenceStatus.CONFLICT

    if any(
        item.relation == "SUPPORTS" and item.coverage == "FULL"
        for item in decision_evidence
    ):
        return EvidenceStatus.MATCH

    return EvidenceStatus.INSUFFICIENT


def _decision_evidence_for_status(
    evidence: Sequence[ClaimEvidenceLink], status: EvidenceStatus
) -> Tuple[ClaimEvidenceLink, ...]:
    """요구사항 9.12: 근거_상태를 실제로 결정한 결정_근거 집합만 반환한다.

    근거_부족은 근거_상태를 결정한 결정_근거가 없으므로(요구사항 9.11 "결정_근거는
    없고 ... 관련만 있으면") 빈 튜플을 반환한다.
    """

    decision_evidence = [
        item for item in evidence if item.purpose == "DECISION"
    ]
    if status is EvidenceStatus.CONFLICT:
        return tuple(
            item
            for item in decision_evidence
            if item.relation == "CONTRADICTS"
        )
    if status is EvidenceStatus.MATCH:
        return tuple(
            item
            for item in decision_evidence
            if item.relation == "SUPPORTS" and item.coverage == "FULL"
        )
    return ()


def _reference_sources(
    evidence: Sequence[ClaimEvidenceLink],
) -> Tuple[ClaimEvidenceLink, ...]:
    """요구사항 9.13: ``purpose="REFERENCE"``인 참고_출처를 결정_근거와 분리해 반환."""

    return tuple(item for item in evidence if item.purpose == "REFERENCE")


def review_claim(claim: ReviewableClaim) -> ClaimReviewOutcome:
    """하나의 ``ReviewableClaim``을 근거_상태·결정_근거·참고_출처로 판정한다."""

    status = classify_claim_evidence(claim.evidence)
    decision_evidence = _decision_evidence_for_status(claim.evidence, status)
    reference_sources = _reference_sources(claim.evidence)
    return ClaimReviewOutcome(
        claim_id=claim.id,
        status=status,
        decision_evidence=decision_evidence,
        reference_sources=reference_sources,
    )


def review_selection(
    selected_text: str,
    selected_claim_ids: Sequence[ClaimId],
    claims: Sequence[ReviewableClaim],
) -> SelectionReviewResult:
    """선택_재검토를 실행해 ``SelectionReviewResult``를 반환한다.

    선택 대기 상태(요구사항 9.4/9.5/9.12)이면 ``claims=()``로 재검토 결과를 빈
    집합으로 유지한다. 그 외에는 :func:`select_overlapping_claims`로 문서 순서
    exact-once 추출한 각 독립_주장을 :func:`review_claim`으로 판정한다
    (요구사항 9.7~9.13, Property 25/26).
    """

    if is_selection_pending(selected_text, selected_claim_ids, claims):
        return SelectionReviewResult(selected_text=selected_text, claims=())

    overlapping = select_overlapping_claims(selected_claim_ids, claims)
    outcomes = tuple(review_claim(claim) for claim in overlapping)
    return SelectionReviewResult(selected_text=selected_text, claims=outcomes)


# --------------------------------------------------------------------------
# 상세 설명 fixture 충실성과 fallback (요구사항 9.14/9.15, Property 27)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SelectionExplanationDisplay:
    """상세 설명 화면 표시용 결과.

    ``found=True``이면 ``legal_terms``·``context``·``issues``는 대응하는
    :class:`~data.models_selection.SelectionExplanationFixture`의 값을 변경 없이
    담는다(요구사항 9.14, Property 27 "fixture와 같음"). ``found=False``이면 선택
    문구의 의미를 목업_데이터셋에서 확인할 수 없는 경우이며, ``not_found_text``에
    `목업 자료에서 확인할 수 없음` 표시 정책 문구가 채워지고 ``legal_terms``·
    ``issues``는 비며 ``context``는 ``None``이다. 이 경우에도 fixture에 사전
    정의된 ``additional_information_needed``가 있으면 그대로 유지한다(요구사항 9.15).
    """

    claim_id: ClaimId
    found: bool
    legal_terms: Tuple[LegalTermExplanationEntry, ...]
    context: Optional[str]
    issues: Tuple[str, ...]
    additional_information_needed: Tuple[str, ...]
    not_found_text: Optional[str] = None


class SelectionExplanationPolicyMissingError(ValueError):
    """``status_labels``에 ``key="EXPLANATION_NOT_FOUND"`` 레코드가 없을 때 발생한다.

    유효한 목업_데이터셋에는 이 표시 정책 레코드가 항상 존재해야 하므로, 이 예외는
    검증을 우회한 호출에 대해서만 발생해야 한다.
    """


def _find_policy_text_by_key(
    records: Sequence[DisplayPolicyRecord], key: str
) -> str:
    for record in records:
        if record.key == key:
            return record.text
    raise SelectionExplanationPolicyMissingError(
        f"status_labels에 key={key!r} 레코드가 없습니다."
    )


def _has_confirmable_content(fixture: SelectionExplanationFixture) -> bool:
    """법률 용어·문맥·쟁점 중 하나라도 있으면(의미를 확인할 수 있음) 참이다."""

    return (
        bool(fixture.legal_terms)
        or bool(fixture.issues)
        or fixture.context is not None
    )


def resolve_selection_explanation(
    claim_id: ClaimId,
    explanations: Sequence[SelectionExplanationFixture],
    status_labels: Sequence[DisplayPolicyRecord],
) -> SelectionExplanationDisplay:
    """``claim_id``에 대응하는 상세 설명을 fixture 충실성 또는 fallback으로 반환한다.

    대응하는 :class:`SelectionExplanationFixture`가 없거나, 있어도 법률 용어·
    문맥·쟁점이 모두 비어 있어(:func:`_has_confirmable_content`가 ``False``) 선택
    문구의 의미를 확인할 수 없으면 요구사항 9.15에 따라 `목업 자료에서 확인할 수
    없음` 문구와 fixture에 사전 정의된(있다면) ``additional_information_needed``만
    반환한다.
    """

    fixture_by_claim: Dict[ClaimId, SelectionExplanationFixture] = {
        explanation.claim_id: explanation for explanation in explanations
    }
    fixture = fixture_by_claim.get(claim_id)

    if fixture is None or not _has_confirmable_content(fixture):
        not_found_text = _find_policy_text_by_key(
            status_labels, _EXPLANATION_NOT_FOUND_KEY
        )
        additional_information_needed = (
            fixture.additional_information_needed
            if fixture is not None
            else ()
        )
        return SelectionExplanationDisplay(
            claim_id=claim_id,
            found=False,
            legal_terms=(),
            context=None,
            issues=(),
            additional_information_needed=additional_information_needed,
            not_found_text=not_found_text,
        )

    return SelectionExplanationDisplay(
        claim_id=claim_id,
        found=True,
        legal_terms=fixture.legal_terms,
        context=fixture.context,
        issues=fixture.issues,
        additional_information_needed=fixture.additional_information_needed,
        not_found_text=None,
    )
