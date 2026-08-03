"""식별자(branded ID) 타입에 대한 단위 테스트.

``NewType`` 기반 branded ID는 런타임에는 일반 ``str``과 동일하게 동작해야 하므로, 값 동등성과
문자열 상호운용성을 확인한다. 타입 구분 자체(mypy가 CaseId와 SourceId를 섞어 쓰는 것을 막는
효과)는 정적 타입 검사로만 확인 가능하므로 별도로 ``mypy``를 실행해 검증한다.
"""

from __future__ import annotations

from domain.ids import (
    CaseId,
    ClaimId,
    DatasetId,
    EventId,
    QueryId,
    SourceId,
    StatuteVersionId,
)


def test_ids_behave_as_plain_strings_at_runtime() -> None:
    case_id = CaseId("case-001")
    assert case_id == "case-001"
    assert isinstance(case_id, str)


def test_all_id_constructors_accept_and_preserve_string_value() -> None:
    values = {
        DatasetId("dataset-1"): "dataset-1",
        QueryId("query-1"): "query-1",
        CaseId("case-1"): "case-1",
        StatuteVersionId("statute-version-1"): "statute-version-1",
        SourceId("source-1"): "source-1",
        ClaimId("claim-1"): "claim-1",
        EventId("event-1"): "event-1",
    }
    for constructed, expected in values.items():
        assert constructed == expected


def test_ids_are_usable_as_dict_keys_and_set_members() -> None:
    ids = {CaseId("a"), CaseId("b"), CaseId("a")}
    assert ids == {"a", "b"}
