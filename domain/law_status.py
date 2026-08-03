"""법령_기준_상태 분류와 날짜·구법 표시 (task 11.1).

``design.md`` "핵심 포트와 함수 시그니처"의 다음 계약을 구현한다::

    function classifyLawStatus(
      applied: readonly AppliedStatuteRef[],
      statutes: ReadonlyMap<StatuteVersionId, StatuteVersion>,
      asOfDate: IsoDate
    ): LawBasisStatus;

그리고 "법령 상태"(4.4) 절의 의사코드와 Property 29~31을 구현한다::

    classifyLawStatus(appliedVersions, currentVersionsAtAsOf):
      if appliedVersions is empty:
        return INDETERMINATE
      if any required amendment/effective/applied version is missing or incomparable:
        return INDETERMINATE
      if every applied version id equals its statute's current version id:
        return CURRENT
      return OLD

## 두 시그니처 사이의 차이와 선택 근거

"핵심 포트와 함수 시그니처" 절은 세 번째 매개변수로 ``asOfDate``를 나열하지만, 4.4절의
실제 알고리즘은 ``currentVersionsAtAsOf``(법령별 데이터_기준일 현행 버전 ID 맵)를 직접
입력으로 받는다. ``data.models_statute.StatuteRecord.current_version_id_at_as_of``가 이미
데이터_기준일 기준으로 사전 계산된 값이므로(요구사항 10.6 "데이터_기준일의 현행_법령
버전"), 이 모듈은 4.4절의 문자 그대로의 알고리즘을 따르며 ``asOfDate`` 자체를 다시 받지
않는다 — 호출자(``domain.mock_search`` 이후 태스크 또는 향후 판례 상세 조립 계층)가
``FixtureRepository``에서 얻은 ``StatuteRecord``들로부터 이 맵을 구성해 전달한다. 이는
계약 위반이 아니라 "데이터_기준일 반영"이 이미 fixture 계산 단계에서 끝난 값을 재사용하는
것이며, 날짜를 다시 비교하거나 추론하지 않는다(요구사항 10.8 "누락된 날짜를 추론하지
않고").

## 보수적(comparable) 판정 규칙

적용 법조문 참조 하나가 다음 중 하나라도 만족하지 못하면 그 판례 전체가 비교 불가로
취급되어 :attr:`~domain.enums.LawBasisStatus.INDETERMINATE`를 반환한다(요구사항 10.8,
design.md "적용 법조문 참조가 비어 있거나 revisionDate, effectiveDate, 적용 버전 또는
비교 대상 현행 버전 중 하나라도 없어 비교할 수 없으면 판별 불가다"):

1. ``statute_version_id``가 ``None``이 아니다.
2. 그 ID가 ``statutes`` 맵에서 실제 :class:`~data.models_statute.StatuteVersion`으로
   해석된다.
3. 해석된 버전의 ``revision_date``와 ``effective_date``가 모두 존재한다.
4. 해당 법령(``version.statute_id``)의 데이터_기준일 현행 버전 ID가
   ``current_version_ids_at_as_of``에 존재하고 ``None``이 아니다.

모든 적용 참조가 비교 가능하면, 각 적용 참조의 ``statute_version_id``가 해당 법령의 현행
버전 ID와 전부 같을 때만 :attr:`~domain.enums.LawBasisStatus.CURRENT_LAW_BASIS`를
반환한다(요구사항 10.6). 하나 이상 다르면(비교 가능한 범위에서, 현행 버전보다 이전이라는
뜻) :attr:`~domain.enums.LawBasisStatus.OLD_LAW_BASIS`를 반환한다(요구사항 10.7). 적용
참조가 비어 있으면 첫 단계에서 곧바로 판별불가다(요구사항 10.8). 판별불가를 현행 또는
구법으로 추정하지 않는다(요구사항 10.11, design.md "판별 불가를 현행 또는 구법으로
추정하지 않는다").

## 날짜 필드별 정보_없음 표시 (요구사항 10.2, 10.3)

:func:`statute_date_display`는 하나의 :class:`~data.models_statute.StatuteVersion`의
``revision_date``·``effective_date`` 중 존재하는 값은 그대로, 누락된 값만 개별적으로
``정보_없음``으로 대체한 projection을 만든다(design.md "누락된 날짜 필드는 화면에서
개별적으로 정보 없음으로 표시한다"). 두 필드는 서로 독립적으로 처리되어, 한 필드가
없어도 다른 필드는 그대로 노출된다(Property 29).

## 구법 기준 배지·개정 설명 연결 (요구사항 10.10)

:func:`old_law_basis_display`는 :func:`classify_law_status`의 결과가
``OLD_LAW_BASIS``일 때만 ``구법 기준`` 배지와, 적용된 법조문 버전들의 fixture
``revision_summary`` 값을 문서 순서로 중복 없이 모아 반환한다(Property 31 "구법_기준으로
유효하게 분류된 판례에 대해, projection은 `구법 기준` 배지와 관련 법조문의 fixture
개정 내용을 함께 포함해야 한다"). 다른 상태(``CURRENT_LAW_BASIS``·``INDETERMINATE``)에는
``None``을 반환해, 구법이 아닌 판례에 이 배지가 잘못 붙는 일이 없게 한다. 개정 설명이
fixture에 없는 적용 법조문 버전은 조용히 건너뛴다 — 새 문구를 만들어 내지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Optional, Sequence, Tuple, Union

from domain.enums import LawBasisStatus
from domain.ids import StatuteVersionId

from data.models_common import IsoDate
from data.models_statute import AppliedStatuteRef, StatuteVersion

__all__ = [
    "StatuteDateDisplay",
    "OldLawBasisDisplay",
    "classify_law_status",
    "statute_date_display",
    "old_law_basis_display",
]


def classify_law_status(
    applied: Sequence[AppliedStatuteRef],
    statutes: Mapping[StatuteVersionId, StatuteVersion],
    current_version_ids_at_as_of: Mapping[str, Optional[StatuteVersionId]],
) -> LawBasisStatus:
    """``applied``가 인용한 법조문 버전들을 데이터_기준일 현행 버전과 비교해
    :class:`~domain.enums.LawBasisStatus`를 보수적으로 판정한다.

    ``current_version_ids_at_as_of``는 법령 ID(``StatuteVersion.statute_id``)를
    데이터_기준일 현행 :class:`~domain.ids.StatuteVersionId`(없으면 ``None``)로 매핑한다
    (design.md 4.4절 ``currentVersionsAtAsOf``에 대응, 모듈 docstring 참조).

    비교에 필요한 값이 하나라도 없거나 비교할 수 없으면 :attr:`LawBasisStatus.INDETERMINATE`
    를 반환하며(요구사항 10.8), 판별불가를 현행 또는 구법으로 추정하지 않는다(요구사항
    10.11).
    """

    if not applied:
        return LawBasisStatus.INDETERMINATE

    current_version_ids: list[StatuteVersionId] = []

    for ref in applied:
        if ref.statute_version_id is None:
            return LawBasisStatus.INDETERMINATE

        version = statutes.get(ref.statute_version_id)
        if version is None:
            return LawBasisStatus.INDETERMINATE

        if version.revision_date is None or version.effective_date is None:
            return LawBasisStatus.INDETERMINATE

        current_version_id = current_version_ids_at_as_of.get(version.statute_id)
        if current_version_id is None:
            return LawBasisStatus.INDETERMINATE

        current_version_ids.append(current_version_id)

    all_current = all(
        ref.statute_version_id == current_version_id
        for ref, current_version_id in zip(applied, current_version_ids)
    )
    if all_current:
        return LawBasisStatus.CURRENT_LAW_BASIS
    return LawBasisStatus.OLD_LAW_BASIS


@dataclass(frozen=True)
class StatuteDateDisplay:
    """법조문 버전 하나의 날짜 표시 projection. 요구사항 10.2, 10.3.

    ``revision_date``·``effective_date``는 fixture에 값이 있으면 그대로, 없으면 각각
    독립적으로 ``"정보_없음"``이다.
    """

    revision_date: Union[IsoDate, Literal["정보_없음"]]
    effective_date: Union[IsoDate, Literal["정보_없음"]]


def statute_date_display(version: StatuteVersion) -> StatuteDateDisplay:
    """``version``의 개정일·시행일 중 누락된 필드만 ``정보_없음``으로 대체해 반환한다.

    존재하는 날짜는 재계산 없이 그대로 옮기고, 누락된 필드만 개별적으로 대체한다(요구사항
    10.2 "최신 개정일과 시행일이 존재하면 ... 그대로 반환한다", 10.3 "없으면 ... 누락된
    날짜 필드를 정보_없음으로 반환한다").
    """

    return StatuteDateDisplay(
        revision_date=version.revision_date if version.revision_date is not None else "정보_없음",
        effective_date=version.effective_date if version.effective_date is not None else "정보_없음",
    )


@dataclass(frozen=True)
class OldLawBasisDisplay:
    """구법_기준 판례에 연결되는 배지와 개정 설명. 요구사항 10.10.

    ``revision_summaries``는 문서(``applied``) 순서로 중복 없이 모은 fixture
    ``revisionSummary`` 값이다. fixture에 개정 설명이 없는 적용 법조문 버전은 건너뛴다.
    """

    badge_label: Literal["구법 기준"]
    revision_summaries: Tuple[str, ...]


def old_law_basis_display(
    law_basis_status: LawBasisStatus,
    applied: Sequence[AppliedStatuteRef],
    statutes: Mapping[StatuteVersionId, StatuteVersion],
) -> Optional[OldLawBasisDisplay]:
    """``law_basis_status``가 ``OLD_LAW_BASIS``일 때만 구법 기준 배지·개정 설명을 만든다.

    다른 상태에는 ``None``을 반환해 현행법_기준·법령_상태_판별불가 판례에 이 배지가 붙지
    않게 한다(요구사항 10.10은 구법_기준 판례에만 적용된다). 개정 설명이 없는 적용 법조문
    버전은 조용히 제외하며 새 문구를 만들지 않는다.
    """

    if law_basis_status is not LawBasisStatus.OLD_LAW_BASIS:
        return None

    seen: set[str] = set()
    revision_summaries: list[str] = []
    for ref in applied:
        if ref.statute_version_id is None:
            continue
        version = statutes.get(ref.statute_version_id)
        if version is None or version.revision_summary is None:
            continue
        if version.revision_summary in seen:
            continue
        seen.add(version.revision_summary)
        revision_summaries.append(version.revision_summary)

    return OldLawBasisDisplay(badge_label="구법 기준", revision_summaries=tuple(revision_summaries))
