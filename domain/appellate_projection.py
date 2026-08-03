"""상급심·확정 정보 projection (task 11.2).

``design.md`` Data Models 10절 ``AppellateInformation``/``AppellateDecision``과
"상급심과 확정 정보" 절의 규칙을 구현한다::

    interface AppellateInformation {
      state: "PRESENT" | "정보_없음";
      decisions: readonly AppellateDecision[];
    }

    interface AppellateDecision {
      caseNumber: string;
      instance: "항소심" | "상고심";
      courtName: string;
      decisionDate: IsoDate;
      outcome: string;
      relationToLowerInstance: "유지" | "변경";
      sourceIds: readonly SourceId[];
    }

`state=정보_없음`이면 decisions는 빈 배열이어야 한다. `finality=정보_없음`이면 확정·미확정
배지를 생성하지 않는다(요구사항 12.8, 12.9, 12.11, 12.12, Property 37).

## 이 모듈의 범위

이 태스크(11.2)는 **재계산 없는 그대로의 projection**만 다룬다. ``CaseRecord.appellate``와
``CaseRecord.finality``는 이미 fixture에 사전 선언된 값이며(task 1.2), 이 모듈은:

- ``AppellateInformation.state`` PRESENT/정보_없음 판정 자체를 다시 계산하지 않는다.
  ``data.validated_dataset``의 검증기(task 2.x)가 ``state="정보_없음"`` ⇒ ``decisions == ()``
  불변식을 이미 강제하므로(``INVALID_APPELLATE_STATE`` 등 진단), 이 모듈은 그 불변식을
  전제로 각 결정의 사건번호·심급·선고일·법원명·결과·원심 대비 관계·출처_식별자를 그대로
  옮긴다(요구사항 12.6, 12.7, 12.11 "정보_없음 상태에서 상급심 사건번호·심급·선고일·결과를
  정보_없음으로 유지").
- ``finality``가 ``"정보_없음"``이면 확정·미확정 배지를 **생성하지 않는다**(요구사항 12.8,
  12.9, 12.13, 12.17) — :func:`project_finality_badge`는 이 경우 ``None``을 반환하며,
  ``"확정"``/``"미확정"``일 때만 정확히 하나의 :class:`FinalityBadgeProjection`을 반환한다.
  이 이진 반환 형태(정확히 하나의 배지 또는 배지 없음) 자체가 "확정 또는 미확정 중 하나의
  배지, 정보_없음이면 두 배지 모두 0개"(Property 37)를 구조적으로 보장한다 — 두 배지가
  동시에 생성되는 경로가 코드에 존재하지 않는다.
- 목업 데이터에 없는 값을 추론하지 않는다(요구사항 12.12): 이 모듈은 ``CaseRecord``에 이미
  선언된 필드만 옮기며, 결측 필드를 채우거나 기본값으로 대체하는 로직이 없다.

인용 검증(``citationsForClaim``, task 6.x), 목록 카드 표시 로직(``ResultList`` UI, task 19.2),
법령 기준 상태 재판정(``classifyLawStatus``, task 11.1)은 이 모듈의 책임이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from domain.ids import CaseId, SourceId

from data.models_case import AppellateInformation, CaseRecord
from data.models_common import (
    AppellateInstance,
    AppellateState,
    Finality,
    IsoDate,
    RelationToLowerInstance,
)

__all__ = [
    "AppellateDecisionProjection",
    "AppellateInformationProjection",
    "FinalityBadgeProjection",
    "CaseAppealProjection",
    "project_appellate_information",
    "project_finality_badge",
    "project_case_appeal",
]


@dataclass(frozen=True)
class AppellateDecisionProjection:
    """상급심 결정 하나의 projection. design.md ``AppellateDecision``의 필드를
    ``CaseRecord.appellate.decisions``에서 재계산 없이 그대로 옮긴다(요구사항 12.6, 12.7).
    """

    case_number: str
    instance: AppellateInstance
    court_name: str
    decision_date: IsoDate
    outcome: str
    relation_to_lower_instance: RelationToLowerInstance
    """심급 체인상 이 결정의 직전 하급심(원심) 대비 관계. ``"유지"`` 또는 ``"변경"``."""
    source_ids: Tuple[SourceId, ...]


@dataclass(frozen=True)
class AppellateInformationProjection:
    """상급심_정보 projection. design.md ``AppellateInformation``.

    ``state="정보_없음"``이면 ``decisions``는 반드시 빈 튜플이다(요구사항 12.8, 12.11 —
    이 불변식은 :func:`project_appellate_information`이 새로 만드는 것이 아니라, 데이터셋
    검증기가 이미 보장한 ``CaseRecord.appellate``의 불변식을 그대로 옮긴 결과다).
    """

    state: AppellateState
    decisions: Tuple[AppellateDecisionProjection, ...]


@dataclass(frozen=True)
class FinalityBadgeProjection:
    """확정·미확정 배지 하나. ``finality``가 ``"확정"`` 또는 ``"미확정"``일 때만 존재한다.

    ``finality="정보_없음"``에 대응하는 배지 값은 존재하지 않는다 — 이 클래스의 인스턴스가
    생성되지 않고 :func:`project_finality_badge`가 ``None``을 반환하는 것 자체가 "배지를
    생성하지 않는다"(요구사항 12.8, 12.9, 12.13, 12.17)를 나타낸다.
    """

    finality: Finality
    """``"확정"`` 또는 ``"미확정"``만 유효한 값이다(``project_finality_badge``가 보장)."""


@dataclass(frozen=True)
class CaseAppealProjection:
    """판례 하나의 상급심·확정 정보 projection. 목록 카드의 `상급심 정보 요약`과
    `확정 여부`(요구사항 12.5, 12.15~12.17), 상세 화면의 `AppealStatusPanel`(요구사항
    12.6~12.9, 12.11, 12.12)이 공유하는 단일 소스다.
    """

    case_id: CaseId
    appellate: AppellateInformationProjection
    finality: Finality
    finality_badge: Optional[FinalityBadgeProjection]
    """``finality``가 정보_없음이면 ``None``(배지 미생성). 그 외에는 정확히 하나의 배지."""


def project_appellate_information(
    appellate: AppellateInformation,
) -> AppellateInformationProjection:
    """``CaseRecord.appellate``를 재계산 없이 그대로 :class:`AppellateInformationProjection`으로
    옮긴다. ``state``와 ``decisions``의 개수·순서를 변경하지 않는다(요구사항 12.6, 12.11, 12.12).
    """

    decisions = tuple(
        AppellateDecisionProjection(
            case_number=decision.case_number,
            instance=decision.instance,
            court_name=decision.court_name,
            decision_date=decision.decision_date,
            outcome=decision.outcome,
            relation_to_lower_instance=decision.relation_to_lower_instance,
            source_ids=decision.source_ids,
        )
        for decision in appellate.decisions
    )
    return AppellateInformationProjection(state=appellate.state, decisions=decisions)


def project_finality_badge(finality: Finality) -> Optional[FinalityBadgeProjection]:
    """``finality`` 값에서 표시용 배지를 판정한다.

    ``finality="정보_없음"``이면 ``None``을 반환한다 — 클라이언트_웹_계층이 확정·미확정
    배지를 표시 건수 0건으로 유지할 수 있게 한다(요구사항 12.8, 12.9, 12.13, 12.17). 그 외
    (``"확정"``/``"미확정"``)에는 정확히 그 값을 담은 :class:`FinalityBadgeProjection` 하나를
    반환한다. 목업에 없는 값을 새로 만들지 않는다(요구사항 12.12) — 입력값 그대로 감쌀 뿐이다.
    """

    if finality == "정보_없음":
        return None
    return FinalityBadgeProjection(finality=finality)


def project_case_appeal(case: CaseRecord) -> CaseAppealProjection:
    """판례 ``case``의 상급심·확정 정보를 하나의 :class:`CaseAppealProjection`으로 조립한다.

    목록 카드(요구사항 12.5, 12.15~12.17)와 상세 패널(요구사항 12.6~12.9, 12.11, 12.12)이
    같은 값을 재계산 없이 공유하도록, ``case.appellate``와 ``case.finality``를 그대로
    :func:`project_appellate_information`/:func:`project_finality_badge`에 위임한다.
    """

    return CaseAppealProjection(
        case_id=case.id,
        appellate=project_appellate_information(case.appellate),
        finality=case.finality,
        finality_badge=project_finality_badge(case.finality),
    )
