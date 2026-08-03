"""``domain.notice_policy`` 단위 테스트 (task 16.1).

요구사항 1.6, 1.7, 1.8, 7.7, 7.8, 12.4를 검증한다.

속성 기반 테스트(Property 3, 요구사항 1.7 전체 표면 완전성)는 별도 task(16.2)의
책임이므로 여기서는 표면별 대표 예시 기반 단위 테스트만 다룬다.
"""

from __future__ import annotations

import pytest

from domain.notice_policy import (
    MissingRequiredNoticeRecordError,
    NoticeSurface,
    notice_for,
)
from fixtures.mock_dataset import build_mock_dataset

_ALL_SURFACES: tuple[NoticeSurface, ...] = (
    "APP_SHELL",
    "SEARCH_RESULTS",
    "MOCK_RESPONSE",
    "SOURCE_VIEWER",
    "REPORT_PREVIEW",
    "CLIPBOARD",
    "DOWNLOAD",
)


@pytest.fixture()
def policies():
    return build_mock_dataset().display_policies


def test_every_surface_requires_safety_notice(policies) -> None:
    """1.7: 표시/복사/내보내기되는 모든 표면은 법률_안전_고지문을 요구한다."""

    for surface in _ALL_SURFACES:
        requirement = notice_for(surface, policies)
        assert requirement.include_safety_notice is True


def test_search_results_and_mock_response_show_mock_badge(
    policies,
) -> None:
    """1.6: 검색 결과·목업_응답 화면에는 `목업 응답` 표지가 필요하다."""

    for surface in ("SEARCH_RESULTS", "MOCK_RESPONSE", "APP_SHELL"):
        assert notice_for(surface, policies).show_mock_badge is True

    no_badge_surfaces = (
        "SOURCE_VIEWER",
        "REPORT_PREVIEW",
        "CLIPBOARD",
        "DOWNLOAD",
    )
    for surface in no_badge_surfaces:
        assert notice_for(surface, policies).show_mock_badge is False


def test_result_surfaces_require_as_of_date_and_no_realtime_sync(
    policies,
) -> None:
    """1.8: 결과 화면에는 데이터_기준일과 실시간 동기화 없음 문구가 함께 필요하다."""

    surfaces = (
        "APP_SHELL",
        "SEARCH_RESULTS",
        "MOCK_RESPONSE",
        "SOURCE_VIEWER",
    )
    for surface in surfaces:
        requirement = notice_for(surface, policies)
        assert requirement.include_as_of_date is True
        assert requirement.include_no_realtime_sync is True


def test_clipboard_and_download_require_as_of_date_only(policies) -> None:
    """복사/다운로드된 본문은 데이터_기준일만 부착하면 되고, 상시 실시간 동기화 문구는
    화면 상시 노출 요구가 아니므로 요구하지 않는다."""

    for surface in ("CLIPBOARD", "DOWNLOAD"):
        requirement = notice_for(surface, policies)
        assert requirement.include_as_of_date is True
        assert requirement.include_no_realtime_sync is False


def test_only_search_results_requires_similarity_disclaimer(
    policies,
) -> None:
    """7.7, 7.8: 유사도 면책 문구는 유사도·검색 순서가 표시되는 화면에서만 필요하다."""

    result_requirement = notice_for("SEARCH_RESULTS", policies)
    assert result_requirement.include_similarity_disclaimer is True
    for surface in (
        "APP_SHELL",
        "MOCK_RESPONSE",
        "SOURCE_VIEWER",
        "REPORT_PREVIEW",
        "CLIPBOARD",
        "DOWNLOAD",
    ):
        requirement = notice_for(surface, policies)
        assert requirement.include_similarity_disclaimer is False


def test_instance_caution_required_on_lists_and_details(policies) -> None:
    """12.4: 심급·확정 주의 안내는 모든 판례 목록·상세 화면에 필요하다."""

    for surface in ("APP_SHELL", "SEARCH_RESULTS", "SOURCE_VIEWER"):
        assert notice_for(surface, policies).include_instance_caution is True

    no_caution_surfaces = (
        "MOCK_RESPONSE",
        "REPORT_PREVIEW",
        "CLIPBOARD",
        "DOWNLOAD",
    )
    for surface in no_caution_surfaces:
        assert notice_for(surface, policies).include_instance_caution is False


def test_required_policy_record_ids_reference_actual_notice_records(
    policies,
) -> None:
    """반환된 ID는 새 문구를 만들지 않고 policies.notices에서 그대로 선택한 것이다."""

    notice_ids_by_key = {record.key: record.id for record in policies.notices}
    safety_id = notice_ids_by_key["LEGAL_SAFETY_NOTICE"]
    no_sync_id = notice_ids_by_key["NO_REALTIME_SYNC"]
    instance_id = notice_ids_by_key["INSTANCE_CAUTION_NOTICE"]

    for surface in _ALL_SURFACES:
        requirement = notice_for(surface, policies)
        required = requirement.required_policy_record_ids
        assert safety_id in required

        if requirement.include_no_realtime_sync:
            assert no_sync_id in required
        else:
            assert no_sync_id not in required

        if requirement.include_instance_caution:
            assert instance_id in required
        else:
            assert instance_id not in required


def test_missing_notice_record_raises_instead_of_synthesizing_text(
    policies,
) -> None:
    """필수 NOTICE 레코드가 없으면 조용히 문구를 합성하지 않고 명시적으로 실패한다."""

    empty_notices_policies = policies.__class__(
        notices=(),
        placeholders=policies.placeholders,
        status_labels=policies.status_labels,
        similarity_warnings=policies.similarity_warnings,
    )

    with pytest.raises(MissingRequiredNoticeRecordError):
        notice_for("APP_SHELL", empty_notices_policies)
