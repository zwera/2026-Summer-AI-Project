"""``domain.selection_review`` 단위 테스트 (task 12.1).

요구사항 9.3~9.12, 9.14, 9.15, 1.9, 15.6을 검증한다.

- :func:`select_overlapping_claims`: 겹치는 claimId의 문서 순서 exact-once 추출.
- :func:`is_selection_pending`: 공백 선택·범위 밖 선택의 선택 대기 판정.
- :func:`classify_claim_evidence`: 충돌 우선 → 근거_충돌, 전체 지지 → 근거_일치,
  그 외 → 근거_부족.
- :func:`review_claim`/:func:`review_selection`: 결정_근거·참고_출처 partition과
  ``SelectionReviewResult`` 조립.
- :func:`resolve_selection_explanation`: fixture 충실성과
  `목업 자료에서 확인할 수 없음` fallback.

속성 기반 테스트(Property 25~28)는 별도 task(12.2~12.5)의 책임이므로 여기서는
대표 예시 기반 단위 테스트만 다룬다.
"""

from __future__ import annotations

from domain.enums import EvidenceStatus
from domain.ids import ClaimId, SourceId
from domain.selection_review import (
    SelectionExplanationPolicyMissingError,
    classify_claim_evidence,
    is_selection_pending,
    resolve_selection_explanation,
    review_claim,
    review_selection,
    select_overlapping_claims,
)
from data.models_common import DisplayPolicyRecord, SourceAnchorId
from data.models_selection import (
    LegalTermExplanationEntry,
    ReviewableClaim,
    SelectionExplanationFixture,
)
from data.models_source import ClaimEvidenceLink


def _link(
    source: str,
    *,
    purpose: str = "DECISION",
    relation: str = "SUPPORTS",
    coverage: str = "FULL",
) -> ClaimEvidenceLink:
    return ClaimEvidenceLink(
        source_id=SourceId(source),
        anchor_id=SourceAnchorId(f"{source}-anchor-1"),
        purpose=purpose,  # type: ignore[arg-type]
        relation=relation,  # type: ignore[arg-type]
        coverage=coverage,  # type: ignore[arg-type]
    )


def _claim(
    claim_id: str, order: int, *links: ClaimEvidenceLink
) -> ReviewableClaim:
    return ReviewableClaim(
        id=ClaimId(claim_id),
        text=f"주장 {claim_id}",
        document_order=order,
        evidence=tuple(links),
    )


class TestSelectOverlappingClaims:
    def test_extracts_in_document_order_and_deduplicates(self) -> None:
        """9.7/Property 25: 겹치는 claimId는 문서 순서로 정확히 한 번 나타난다."""

        claim_a = _claim("claim-a", 1)
        claim_b = _claim("claim-b", 2)
        claims = (claim_b, claim_a)  # fixture 순서가 문서 순서와 달라도 됨.

        result = select_overlapping_claims(
            [ClaimId("claim-b"), ClaimId("claim-a"), ClaimId("claim-a")],
            claims,
        )

        assert [c.id for c in result] == [
            ClaimId("claim-a"),
            ClaimId("claim-b"),
        ]

    def test_ignores_unknown_claim_ids(self) -> None:
        claim_a = _claim("claim-a", 1)
        result = select_overlapping_claims(
            [ClaimId("claim-a"), ClaimId("claim-unknown")], [claim_a]
        )
        assert result == (claim_a,)

    def test_empty_selection_returns_empty(self) -> None:
        claim_a = _claim("claim-a", 1)
        assert select_overlapping_claims([], [claim_a]) == ()


class TestIsSelectionPending:
    def test_blank_text_is_pending(self) -> None:
        """9.12/Property 28: 공백 문자로만 구성된 선택은 선택 대기다."""

        claim_a = _claim("claim-a", 1)
        assert is_selection_pending(
            "   \t\n", [ClaimId("claim-a")], [claim_a]
        )

    def test_out_of_range_selection_is_pending(self) -> None:
        """9.4: 겹치는 유효 독립_주장이 없으면 선택 대기다."""

        claim_a = _claim("claim-a", 1)
        assert is_selection_pending(
            "텍스트", [ClaimId("claim-unknown")], [claim_a]
        )

    def test_nonblank_overlapping_selection_is_not_pending(self) -> None:
        claim_a = _claim("claim-a", 1)
        assert not is_selection_pending(
            "텍스트", [ClaimId("claim-a")], [claim_a]
        )


class TestClassifyClaimEvidence:
    def test_no_evidence_is_insufficient(self) -> None:
        """9.11: 결정_근거도 참고_출처도 없으면 근거_부족이다."""

        assert classify_claim_evidence(()) == EvidenceStatus.INSUFFICIENT

    def test_full_support_without_conflict_is_match(self) -> None:
        """9.9: 전체 지지 결정_근거가 있고 충돌이 없으면 근거_일치다."""

        evidence = (_link("source-a", relation="SUPPORTS", coverage="FULL"),)
        assert classify_claim_evidence(evidence) == EvidenceStatus.MATCH

    def test_conflict_takes_priority_over_full_support(self) -> None:
        """9.10: 충돌하는 결정_근거가 있으면 전체 지지가 있어도 근거_충돌이다."""

        evidence = (
            _link("source-a", relation="SUPPORTS", coverage="FULL"),
            _link("source-b", relation="CONTRADICTS", coverage="FULL"),
        )
        assert classify_claim_evidence(evidence) == EvidenceStatus.CONFLICT

    def test_partial_support_only_is_insufficient(self) -> None:
        """9.11: 부분 지지만 있고 전체 지지·충돌이 없으면 근거_부족이다."""

        evidence = (
            _link("source-a", relation="SUPPORTS", coverage="PARTIAL"),
        )
        assert classify_claim_evidence(evidence) == EvidenceStatus.INSUFFICIENT

    def test_reference_only_evidence_is_insufficient(self) -> None:
        """9.13: 결정_근거는 없고 참고_출처만 있으면 근거_부족이다."""

        evidence = (
            _link("source-a", purpose="REFERENCE", relation="RELATED"),
        )
        assert classify_claim_evidence(evidence) == EvidenceStatus.INSUFFICIENT


class TestReviewClaimPartition:
    def test_match_decision_and_reference_are_disjoint(self) -> None:
        """9.12/9.13, Property 26: 결정_근거와 참고_출처는 서로소로 반환된다."""

        decision = _link(
            "source-decision", relation="SUPPORTS", coverage="FULL"
        )
        reference = _link(
            "source-reference", purpose="REFERENCE", relation="RELATED"
        )
        claim = _claim("claim-a", 1, decision, reference)

        outcome = review_claim(claim)

        assert outcome.status == EvidenceStatus.MATCH
        assert outcome.decision_evidence == (decision,)
        assert outcome.reference_sources == (reference,)

    def test_conflict_decision_evidence_only_includes_contradicts(
        self,
    ) -> None:
        supports = _link("source-a", relation="SUPPORTS", coverage="FULL")
        contradicts = _link(
            "source-b", relation="CONTRADICTS", coverage="FULL"
        )
        claim = _claim("claim-a", 1, supports, contradicts)

        outcome = review_claim(claim)

        assert outcome.status == EvidenceStatus.CONFLICT
        assert outcome.decision_evidence == (contradicts,)

    def test_insufficient_has_no_decision_evidence(self) -> None:
        partial = _link("source-a", relation="SUPPORTS", coverage="PARTIAL")
        claim = _claim("claim-a", 1, partial)

        outcome = review_claim(claim)

        assert outcome.status == EvidenceStatus.INSUFFICIENT
        assert outcome.decision_evidence == ()


class TestReviewSelection:
    def test_pending_selection_yields_empty_claims(self) -> None:
        """9.5: 선택 대기 상태이면 재검토 결과는 빈 집합이다."""

        claim_a = _claim("claim-a", 1, _link("source-a"))
        result = review_selection("   ", [ClaimId("claim-a")], [claim_a])
        assert result.claims == ()

    def test_active_selection_reviews_each_overlapping_claim_once(
        self,
    ) -> None:
        claim_a = _claim("claim-a", 1, _link("source-a"))
        claim_b = _claim("claim-b", 2, _link("source-b"))
        result = review_selection(
            "선택 문구",
            [ClaimId("claim-b"), ClaimId("claim-a")],
            [claim_a, claim_b],
        )
        assert [outcome.claim_id for outcome in result.claims] == [
            ClaimId("claim-a"),
            ClaimId("claim-b"),
        ]


_STATUS_LABELS = (
    DisplayPolicyRecord(
        id="status-explanation-not-found",
        kind="STATUS_LABEL",
        key="EXPLANATION_NOT_FOUND",
        text="목업 자료에서 확인할 수 없음",
    ),
)


class TestResolveSelectionExplanation:
    def test_returns_fixture_content_unchanged_when_confirmable(
        self,
    ) -> None:
        """9.14, Property 27: fixture가 있으면 값을 그대로 반환한다."""

        fixture = SelectionExplanationFixture(
            claim_id=ClaimId("claim-a"),
            legal_terms=(
                LegalTermExplanationEntry(term="현행범체포", explanation="설명"),
            ),
            issues=("체포 요건",),
            additional_information_needed=(),
            context="문맥",
        )

        display = resolve_selection_explanation(
            ClaimId("claim-a"), [fixture], _STATUS_LABELS
        )

        assert display.found is True
        assert display.legal_terms == fixture.legal_terms
        assert display.context == "문맥"
        assert display.issues == ("체포 요건",)
        assert display.not_found_text is None

    def test_missing_fixture_falls_back_to_not_found_text(self) -> None:
        """9.15: fixture가 없으면 `목업 자료에서 확인할 수 없음`을 반환한다."""

        display = resolve_selection_explanation(
            ClaimId("claim-missing"), [], _STATUS_LABELS
        )

        assert display.found is False
        assert display.legal_terms == ()
        assert display.context is None
        assert display.not_found_text == "목업 자료에서 확인할 수 없음"

    def test_empty_fixture_content_falls_back_but_keeps_additional_info(
        self,
    ) -> None:
        """9.15: 내용이 비어 있으면 fallback하되 추가 필요 정보는 유지한다."""

        fixture = SelectionExplanationFixture(
            claim_id=ClaimId("claim-a"),
            legal_terms=(),
            issues=(),
            additional_information_needed=("사건 발생 시각 확인 필요",),
            context=None,
        )

        display = resolve_selection_explanation(
            ClaimId("claim-a"), [fixture], _STATUS_LABELS
        )

        assert display.found is False
        assert display.additional_information_needed == (
            "사건 발생 시각 확인 필요",
        )

    def test_missing_policy_record_raises(self) -> None:
        try:
            resolve_selection_explanation(ClaimId("claim-missing"), [], ())
        except SelectionExplanationPolicyMissingError:
            pass
        else:
            raise AssertionError(
                "expected SelectionExplanationPolicyMissingError"
            )
