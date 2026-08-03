"""``domain.appellate_projection`` 단위 테스트 (task 11.2).

상급심·확정 정보 projection이 ``CaseRecord.appellate``/``CaseRecord.finality``를
재계산 없이 그대로 옮기는지, ``state``/``finality``가 ``정보_없음``일 때 각각 상세
배열이 비고 배지가 생성되지 않는지(요구사항 12.6~12.9, 12.11, 12.12)를 검증한다.
"""

from __future__ import annotations

from domain.appellate_projection import (
    project_appellate_information,
    project_case_appeal,
    project_finality_badge,
)
from domain.ids import CaseId
from data.models_case import AppellateInformation
from fixtures.mock_dataset import build_mock_dataset


def _by_id(case_id: str):
    dataset = build_mock_dataset()
    by_id = {case.id: case for case in dataset.cases}
    return by_id[CaseId(case_id)]


# --------------------------------------------------------------------------
# project_appellate_information
# --------------------------------------------------------------------------


def test_present_appellate_information_projects_decision_fields_verbatim() -> None:
    case = _by_id("case-arrest-lawful")
    assert case.appellate.state == "PRESENT"

    projection = project_appellate_information(case.appellate)

    assert projection.state == "PRESENT"
    assert len(projection.decisions) == len(case.appellate.decisions)
    for expected, actual in zip(case.appellate.decisions, projection.decisions):
        assert actual.case_number == expected.case_number
        assert actual.instance == expected.instance
        assert actual.court_name == expected.court_name
        assert actual.decision_date == expected.decision_date
        assert actual.outcome == expected.outcome
        assert actual.relation_to_lower_instance == expected.relation_to_lower_instance
        assert actual.source_ids == expected.source_ids


def test_no_information_appellate_state_has_empty_decisions() -> None:
    appellate = AppellateInformation(state="정보_없음", decisions=())

    projection = project_appellate_information(appellate)

    assert projection.state == "정보_없음"
    assert projection.decisions == ()


def test_unlawful_case_without_appeal_data_is_no_information() -> None:
    case = _by_id("case-arrest-unlawful")
    assert case.appellate.state == "정보_없음"

    projection = project_appellate_information(case.appellate)

    assert projection.state == "정보_없음"
    assert projection.decisions == ()


# --------------------------------------------------------------------------
# project_finality_badge
# --------------------------------------------------------------------------


def test_finality_confirmed_yields_exactly_one_badge() -> None:
    badge = project_finality_badge("확정")
    assert badge is not None
    assert badge.finality == "확정"


def test_finality_unconfirmed_yields_exactly_one_badge() -> None:
    badge = project_finality_badge("미확정")
    assert badge is not None
    assert badge.finality == "미확정"


def test_finality_no_information_yields_no_badge() -> None:
    badge = project_finality_badge("정보_없음")
    assert badge is None


# --------------------------------------------------------------------------
# project_case_appeal
# --------------------------------------------------------------------------


def test_case_appeal_projection_combines_appellate_and_finality_from_same_case() -> None:
    case = _by_id("case-arrest-lawful")

    projection = project_case_appeal(case)

    assert projection.case_id == case.id
    assert projection.appellate.state == case.appellate.state
    assert projection.finality == case.finality
    # 이 판례는 fixture상 "미확정"이므로 배지가 정확히 하나 생성된다.
    assert case.finality == "미확정"
    assert projection.finality_badge is not None
    assert projection.finality_badge.finality == "미확정"


def test_case_appeal_projection_with_no_information_finality_has_no_badge() -> None:
    case = _by_id("case-arrest-unlawful")
    # unlawful arrest 판례는 fixture상 finality="확정"이므로, 정보_없음 사례를 직접 구성한다.
    from dataclasses import replace

    info_none_case = replace(case, finality="정보_없음")  # type: ignore[arg-type]

    projection = project_case_appeal(info_none_case)

    assert projection.finality == "정보_없음"
    assert projection.finality_badge is None


def test_case_appeal_projection_does_not_infer_values_beyond_source_case() -> None:
    case = _by_id("case-arrest-unlawful")
    assert case.appellate.state == "정보_없음"

    projection = project_case_appeal(case)

    # 상급심_정보가 정보_없음이면 상세 결정 배열은 비어 있어야 하며, 임의 값이 채워지지
    # 않아야 한다(요구사항 12.11, 12.12).
    assert projection.appellate.decisions == ()
