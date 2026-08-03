"""``domain.liability_classification`` 단위 테스트 (task 9.1).

요구사항 6.1~6.14를 검증한다.

- :func:`classify_evidence`: 위험_판정_축의 0/1/2+ distinct 상태 판정과 사용한
  출처_식별자 반환(6.2~6.9).
- :func:`classify_action_badge`: 행동_배지_상태의 만장일치/충돌/모호/빈 판정
  (6.10~6.14).

속성 기반 테스트(Property 16, 17)는 별도 task(9.2, 9.3)의 책임이므로 여기서는
대표 예시 기반 단위 테스트만 다룬다.
"""

from __future__ import annotations

from typing import Optional, TypeVar

from domain.ids import SourceId
from domain.liability_classification import (
    classify_action_badge,
    classify_evidence,
)
from data.models_common import SourceAnchorId
from data.models_risk import (
    AbuseOfAuthorityStatus,
    ActionJudgment,
    ClassifiedEvidence,
    CivilStatus,
    CustodialViolenceStatus,
    DisciplineStatus,
)

_T = TypeVar(
    "_T",
    CivilStatus,
    AbuseOfAuthorityStatus,
    CustodialViolenceStatus,
    DisciplineStatus,
)


def _evidence(source_id: str, status: Optional[_T]) -> ClassifiedEvidence[_T]:
    return ClassifiedEvidence(
        source_id=SourceId(source_id),
        anchor_id=SourceAnchorId(f"{source_id}-anchor-1"),
        supports_status=status,
    )


class TestClassifyEvidence:
    def test_empty_evidence_is_no_information(self) -> None:
        """6.8: 판단할 목업_출처가 없으면 정보_없음이다."""

        status, source_ids = classify_evidence([])
        assert status == "정보_없음"
        assert source_ids == ()

    def test_single_status_unanimous_returns_status_and_sources(self) -> None:
        """6.2~6.6: 유효 출처가 한 상태로 만장일치하면 그 상태와 출처를 반환."""

        evidence = [
            _evidence("source-a", "국가배상_인정"),
            _evidence("source-b", "국가배상_인정"),
        ]
        status, source_ids = classify_evidence(evidence)
        assert status == "국가배상_인정"
        assert source_ids == (SourceId("source-a"), SourceId("source-b"))

    def test_conflicting_statuses_are_unclassifiable(self) -> None:
        """6.9: 서로 충돌하면 분류_불가다."""

        evidence = [
            _evidence("source-a", "국가배상_인정"),
            _evidence("source-b", "국가배상_기각"),
        ]
        status, source_ids = classify_evidence(evidence)
        assert status == "분류_불가"
        assert set(source_ids) == {SourceId("source-a"), SourceId("source-b")}

    def test_evidence_with_none_supports_status_is_excluded(self) -> None:
        """supports_status=None인 근거는 지지하지 않으므로 판정에서 제외."""

        discipline_evidence: list[ClassifiedEvidence[DisciplineStatus]] = [
            _evidence("source-a", None),
            _evidence("source-b", "징계_인정"),
        ]
        status, source_ids = classify_evidence(discipline_evidence)
        assert status == "징계_인정"
        assert source_ids == (SourceId("source-b"),)

    def test_all_none_supports_status_is_no_information(self) -> None:
        evidence = [_evidence("source-a", None), _evidence("source-b", None)]
        status, source_ids = classify_evidence(evidence)
        assert status == "정보_없음"
        assert source_ids == ()

    def test_duplicate_source_id_deduplicated_preserving_order(self) -> None:
        evidence = [
            _evidence("source-a", "해당"),
            _evidence("source-a", "해당"),
            _evidence("source-b", "해당"),
        ]
        status, source_ids = classify_evidence(evidence)
        assert status == "해당"
        assert source_ids == (SourceId("source-a"), SourceId("source-b"))


def _judgment(source_id: str, court_finding: str) -> ActionJudgment:
    return ActionJudgment(
        action_id="action-1",
        action_text="현행범 체포 과정의 물리력 행사",
        court_finding=court_finding,  # type: ignore[arg-type]
        source_ids=(SourceId(source_id),),
    )


class TestClassifyActionBadge:
    def test_no_judgments_is_no_information(self) -> None:
        """6.12: 판단할 목업_출처가 없으면 정보_없음이다."""

        badge = classify_action_badge([])
        assert badge.state == "정보_없음"

    def test_all_problem_judgments_yield_problem_badge(self) -> None:
        """6.10: 모두 문제 판단이면 문제_행동이고 출처_식별자를 연결한다."""

        judgments = [
            _judgment("source-a", "PROBLEM"),
            _judgment("source-b", "PROBLEM"),
        ]
        badge = classify_action_badge(judgments)
        assert badge.state == "문제_행동"
        expected = (SourceId("source-a"), SourceId("source-b"))
        actual = badge.source_ids
        assert actual == expected

    def test_all_lawful_judgments_yield_lawful_badge(self) -> None:
        """6.11: 모두 적법 판단이면 적법_행동이고 출처_식별자를 연결한다."""

        judgments = [_judgment("source-a", "LAWFUL")]
        badge = classify_action_badge(judgments)
        assert badge.state == "적법_행동"
        actual = badge.source_ids
        assert actual == (SourceId("source-a"),)

    def test_mixed_problem_and_lawful_is_unclassifiable(self) -> None:
        """6.13: 문제/적법이 섞이면 분류_불가다."""

        judgments = [
            _judgment("source-a", "PROBLEM"),
            _judgment("source-b", "LAWFUL"),
        ]
        badge = classify_action_badge(judgments)
        assert badge.state == "분류_불가"

    def test_ambiguous_alone_is_unclassifiable(self) -> None:
        """모호 판단만 있어도 적법/문제로 분류할 수 없어 분류_불가다."""

        judgments = [_judgment("source-a", "AMBIGUOUS")]
        badge = classify_action_badge(judgments)
        assert badge.state == "분류_불가"

    def test_ambiguous_mixed_with_lawful_is_unclassifiable(self) -> None:
        judgments = [
            _judgment("source-a", "LAWFUL"),
            _judgment("source-b", "AMBIGUOUS"),
        ]
        badge = classify_action_badge(judgments)
        assert badge.state == "분류_불가"

    def test_exactly_one_badge_variant_per_action(self) -> None:
        """6.14: 하나의 행동에는 정확히 하나의 행동_배지_상태만 판정된다."""

        possible_states = {"문제_행동", "적법_행동", "정보_없음", "분류_불가"}
        cases = [
            [],
            [_judgment("source-a", "PROBLEM")],
            [_judgment("source-a", "LAWFUL")],
            [
                _judgment("source-a", "PROBLEM"),
                _judgment("source-b", "LAWFUL"),
            ],
        ]
        for judgments in cases:
            badge = classify_action_badge(judgments)
            assert badge.state in possible_states
