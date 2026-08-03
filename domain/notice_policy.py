"""법률 고지 노출 정책: `NoticeSurface`별 필수 고지 결정 (task 16.1).

``design.md`` "Components and Interfaces > 5. 법률 고지 노출 정책" 절의 다음 계약
의사코드를 Python으로 구현한다::

    type NoticeSurface =
      | "APP_SHELL"
      | "SEARCH_RESULTS"
      | "MOCK_RESPONSE"
      | "SOURCE_VIEWER"
      | "REPORT_PREVIEW"
      | "CLIPBOARD"
      | "DOWNLOAD";

    interface NoticeRequirement {
      showMockBadge: boolean;
      includeSafetyNotice: boolean;
      includeAsOfDate: boolean;
      includeNoRealtimeSync: boolean;
      includeSimilarityDisclaimer: boolean;
      includeInstanceCaution: boolean;
      requiredPolicyRecordIds: readonly string[];
    }

    function noticeFor(
      surface: NoticeSurface,
      policies: MockDisplayPolicies
    ): NoticeRequirement;

``notice_for``는 순수 함수다. 새 고지 문구를 만들지 않고, 각 표면에 필요한 고지 종류를
정하는 고정 진리표만으로 어떤 ``DisplayPolicyRecord.id``가 필요한지 ``policies``에서
선택한다(design.md "결정 규칙은 어떤 레코드 ID를 선택할지만 정하며 새로운 문구나 법률
결론을 생성하지 않는다"와 동일한 원칙).

## 표면 × 고지 진리표 (요구사항 1.6, 1.7, 1.8, 7.7, 7.8, 12.4)

- ``show_mock_badge`` (요구사항 1.6): `목업 응답` 표지는 검색 결과와 목업_응답 화면에서만
  요구된다 — ``SEARCH_RESULTS``, ``MOCK_RESPONSE``. 공통 셸(``APP_SHELL``)도 상시 노출되는
  공통 표지를 렌더링하는 책임을 지므로 함께 요구한다(design.md 컴포넌트 표 ``AppShell``
  행: "공통 목업 표지, 기준일, 안전 고지, 범위 표지").
- ``include_safety_notice`` (요구사항 1.7): 목업_응답, 목업_출처 또는 보고서용_사실관계가
  표시·복사·내보내기되는 모든 표면에서 요구된다 — 이 모듈의 7개 표면 전체.
- ``include_as_of_date``/``include_no_realtime_sync`` (요구사항 1.8): 결과_화면
  (검색 결과·목업_응답·목업_출처·보고서용_사실관계 표시)과 공통 셸에서 데이터_기준일과
  `실시간 판례·법령 동기화 없음`을 요구한다. ``CLIPBOARD``/``DOWNLOAD``는 요구사항 11.16에
  따라 데이터_기준일만 본문에 부착하면 되므로 ``include_no_realtime_sync``는 요구하지
  않는다(화면 상시 노출 문구가 아니라 내보낸 텍스트 본문이기 때문).
- ``include_similarity_disclaimer`` (요구사항 7.7, 7.8): 유사도_점수와 검색_우선순위가
  표시되는 ``SEARCH_RESULTS``에서만 요구된다.
- ``include_instance_caution`` (요구사항 12.4): "모든 판례 목록과 상세 화면"이 대상이므로
  판례 목록(``SEARCH_RESULTS``)과 판례 상세(``SOURCE_VIEWER``)에서 요구된다. 공통 셸도
  판례 목록·상세를 감싸는 상시 노출 셸이므로 함께 요구한다.

## 이 태스크(16.1)의 범위

- :func:`notice_for` — 표면별 6개 boolean 플래그와, 그 플래그들이 요구하는
  ``DisplayPolicyRecord.id`` 목록(``required_policy_record_ids``)을 ``policies``에서
  선택해 반환한다. 새 문구를 만들지 않는다.

## 이 태스크가 하지 않는 것

- 클라이언트 화면에서 실제로 고지를 렌더링하는 것(task 18.1, 19.x, 20.3의 책임).
- ``policies``의 유효성(유일성, 필수 레코드 존재)을 검증하는 것(``data.validator_domain``,
  task 2.2의 책임). 이 모듈은 유효한 ``MockDisplayPolicies``를 전제로 한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Tuple

from data.models_common import MockDisplayPolicies

__all__ = [
    "NoticeSurface",
    "NoticeRequirement",
    "MissingRequiredNoticeRecordError",
    "notice_for",
]

NoticeSurface = Literal[
    "APP_SHELL",
    "SEARCH_RESULTS",
    "MOCK_RESPONSE",
    "SOURCE_VIEWER",
    "REPORT_PREVIEW",
    "CLIPBOARD",
    "DOWNLOAD",
]
"""design.md ``NoticeSurface`` 유니온과 동일한 7개 표면."""


@dataclass(frozen=True)
class NoticeRequirement:
    """표면 하나에 필요한 고지 요구. design.md ``NoticeRequirement``."""

    show_mock_badge: bool
    include_safety_notice: bool
    include_as_of_date: bool
    include_no_realtime_sync: bool
    include_similarity_disclaimer: bool
    include_instance_caution: bool
    required_policy_record_ids: Tuple[str, ...]


class MissingRequiredNoticeRecordError(ValueError):
    """플래그가 요구하는 고지 ``NOTICE`` 레코드가 ``policies.notices``에 없을 때 발생한다.

    유효한 목업_데이터셋은 검증기(task 2.2)가 ``LEGAL_SAFETY_NOTICE``·
    ``NO_REALTIME_SYNC``·``INSTANCE_CAUTION_NOTICE`` 키를 갖는 고정 고지 레코드의
    존재를 보장하므로, 이 예외는 유효하지 않은 ``policies``(부트 검증을 우회한 호출)에
    대해서만 발생해야 한다. 조용히 임의 문구를 합성하는 대신 명시적으로 실패한다.
    """


_LEGAL_SAFETY_NOTICE_KEY = "LEGAL_SAFETY_NOTICE"
_NO_REALTIME_SYNC_KEY = "NO_REALTIME_SYNC"
_INSTANCE_CAUTION_NOTICE_KEY = "INSTANCE_CAUTION_NOTICE"


@dataclass(frozen=True)
class _SurfaceFlags:
    show_mock_badge: bool
    include_safety_notice: bool
    include_as_of_date: bool
    include_no_realtime_sync: bool
    include_similarity_disclaimer: bool
    include_instance_caution: bool


_SURFACE_FLAGS: Mapping[NoticeSurface, _SurfaceFlags] = {
    "APP_SHELL": _SurfaceFlags(
        show_mock_badge=True,
        include_safety_notice=True,
        include_as_of_date=True,
        include_no_realtime_sync=True,
        include_similarity_disclaimer=False,
        include_instance_caution=True,
    ),
    "SEARCH_RESULTS": _SurfaceFlags(
        show_mock_badge=True,
        include_safety_notice=True,
        include_as_of_date=True,
        include_no_realtime_sync=True,
        include_similarity_disclaimer=True,
        include_instance_caution=True,
    ),
    "MOCK_RESPONSE": _SurfaceFlags(
        show_mock_badge=True,
        include_safety_notice=True,
        include_as_of_date=True,
        include_no_realtime_sync=True,
        include_similarity_disclaimer=False,
        include_instance_caution=False,
    ),
    "SOURCE_VIEWER": _SurfaceFlags(
        show_mock_badge=False,
        include_safety_notice=True,
        include_as_of_date=True,
        include_no_realtime_sync=True,
        include_similarity_disclaimer=False,
        include_instance_caution=True,
    ),
    "REPORT_PREVIEW": _SurfaceFlags(
        show_mock_badge=False,
        include_safety_notice=True,
        include_as_of_date=True,
        include_no_realtime_sync=True,
        include_similarity_disclaimer=False,
        include_instance_caution=False,
    ),
    "CLIPBOARD": _SurfaceFlags(
        show_mock_badge=False,
        include_safety_notice=True,
        include_as_of_date=True,
        include_no_realtime_sync=False,
        include_similarity_disclaimer=False,
        include_instance_caution=False,
    ),
    "DOWNLOAD": _SurfaceFlags(
        show_mock_badge=False,
        include_safety_notice=True,
        include_as_of_date=True,
        include_no_realtime_sync=False,
        include_similarity_disclaimer=False,
        include_instance_caution=False,
    ),
}


def _find_notice_record_id(policies: MockDisplayPolicies, key: str) -> str:
    for record in policies.notices:
        if record.key == key:
            return record.id
    message = f"policies.notices에 key={key!r} 레코드가 없습니다."
    raise MissingRequiredNoticeRecordError(message)


def notice_for(
    surface: NoticeSurface, policies: MockDisplayPolicies
) -> NoticeRequirement:
    """``surface``에 필요한 :class:`NoticeRequirement`를 반환한다.

    6개 boolean 플래그는 모듈 docstring의 고정 진리표에서 결정되며, ``policies``의
    내용과 무관하다. ``required_policy_record_ids``는 그 플래그들 중 ``NOTICE`` 종류
    레코드(안전 고지·실시간 동기화 없음·심급 주의)에 대응하는 플래그가 참인 것만
    ``policies.notices``에서 조회해 ``(안전 고지, 실시간 동기화 없음, 심급 주의)``
    고정 순서로 반환한다. 어떤 문구도 새로 만들지 않는다.
    """

    flags = _SURFACE_FLAGS[surface]

    required_ids: list[str] = []
    if flags.include_safety_notice:
        required_ids.append(
            _find_notice_record_id(policies, _LEGAL_SAFETY_NOTICE_KEY)
        )
    if flags.include_no_realtime_sync:
        required_ids.append(
            _find_notice_record_id(policies, _NO_REALTIME_SYNC_KEY)
        )
    if flags.include_instance_caution:
        required_ids.append(
            _find_notice_record_id(policies, _INSTANCE_CAUTION_NOTICE_KEY)
        )

    return NoticeRequirement(
        show_mock_badge=flags.show_mock_badge,
        include_safety_notice=flags.include_safety_notice,
        include_as_of_date=flags.include_as_of_date,
        include_no_realtime_sync=flags.include_no_realtime_sync,
        include_similarity_disclaimer=flags.include_similarity_disclaimer,
        include_instance_caution=flags.include_instance_caution,
        required_policy_record_ids=tuple(required_ids),
    )
