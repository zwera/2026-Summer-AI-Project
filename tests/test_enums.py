"""도메인 열거형에 대한 단위 테스트.

요구사항 4.1(8개 경찰_직무_시나리오), 4.4(적법성_상태 3분류), 10.5(법령_기준_상태 3분류),
5.1(요약_단계 3종), 1.3/1.4(목업_RAG_단계 4종과 순서), 9.8(근거_상태 3분류)를 값 집합과
문자열 리터럴 정확성 관점에서 검증한다.
"""

from __future__ import annotations

from domain.enums import (
    EvidenceStatus,
    LawBasisStatus,
    LegalityStatus,
    PoliceScenario,
    RagStage,
    StageStatus,
    SummaryLevel,
    TraditionalCaseArea,
)


def test_police_scenario_has_exactly_eight_values_matching_requirements() -> None:
    expected = {
        "현행범체포",
        "임의동행",
        "긴급체포",
        "압수수색",
        "미란다 원칙 고지",
        "진술거부권",
        "가정폭력 초동조치",
        "음주단속",
    }
    actual = {member.value for member in PoliceScenario}
    assert actual == expected
    assert len(PoliceScenario) == 8


def test_traditional_case_area_values() -> None:
    assert {member.value for member in TraditionalCaseArea} == {"형사", "민사", "행정"}


def test_legality_status_values() -> None:
    assert {member.value for member in LegalityStatus} == {"적법", "위법", "판단_혼재"}


def test_law_basis_status_values() -> None:
    assert {member.value for member in LawBasisStatus} == {
        "현행법_기준",
        "구법_기준",
        "법령_상태_판별불가",
    }


def test_summary_level_values() -> None:
    assert {member.value for member in SummaryLevel} == {
        "3줄_요약",
        "10줄_요약",
        "상세_요약",
    }


def test_rag_stage_values_and_order() -> None:
    assert [stage.value for stage in RagStage] == [
        "INPUT",
        "MOCK_SEARCH",
        "EVIDENCE",
        "RESPONSE",
    ]


def test_stage_status_values() -> None:
    assert {status.value for status in StageStatus} == {
        "pending",
        "active",
        "completed",
        "failed",
        "incomplete",
    }


def test_evidence_status_values() -> None:
    assert {status.value for status in EvidenceStatus} == {
        "근거_일치",
        "근거_충돌",
        "근거_부족",
    }


def test_enum_members_serialize_to_plain_string_value() -> None:
    # str Enum이므로 JSON 직렬화 시 값 문자열 그대로 사용 가능해야 한다.
    assert str(PoliceScenario.EMERGENCY_ARREST.value) == "긴급체포"
    assert PoliceScenario.EMERGENCY_ARREST.value == "긴급체포"
