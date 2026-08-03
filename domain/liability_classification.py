"""위험 4축 분류와 단일 행동 배지 판정 (task 9.1).

``design.md`` "핵심 포트와 함수 시그니처"의 다음 계약을 구현한다::

    function classifyEvidence<TStatus extends string>(
      evidence: readonly ClassifiedEvidence<TStatus>[]
    ): TStatus | "NO_INFORMATION" | "UNCLASSIFIABLE";

그리고 "책임 위험과 행동 배지"(``design.md`` 4.5절)의 규칙을 구현한다:

- 위험 축별 판단 출처가 0개면 ``정보_없음``이다.
- 유효 출처가 한 상태로 만장일치하면 그 상태다.
- 서로 충돌하거나 단일 상태로 매핑할 수 없으면 ``분류_불가``다.
- 행동 판단 출처가 모두 문제 판단이면 ``문제_행동``, 모두 적법 판단이면 ``적법_행동``,
  없으면 ``정보_없음``, 충돌하면 ``분류_불가``다.

이 모듈은 ``TStatus | "NO_INFORMATION" | "UNCLASSIFIABLE"``의 한국어 대응인
``RiskFallback = Literal["정보_없음", "분류_불가"]``(``data.models_risk``)를 그대로 재사용해
반환한다(요구사항 15.6 — 새로운 문구를 만들지 않고 기존 리터럴/표시 정책과 일치하는 값만
반환한다).

## ``classify_evidence`` — 위험_판정_축 (요구사항 6.1~6.9)

:func:`classify_evidence`는 하나의 위험_판정_축(민사 국가배상, 형사 직권남용, 형사
독직폭행, 징계 중 하나)에 연결된 :class:`~data.models_risk.ClassifiedEvidence` 전체를
입력받아 다음 절차로 판정한다(``design.md`` Property 16 "집합 cardinality 기반 참조
classifier: 0→NO, distinct status 1→그 상태, 2+→UNCLASSIFIABLE"과 동일):

1. ``supports_status``가 ``None``이 아닌(특정 상태를 지지하는) 근거만 "유효 근거"로
   취급한다. ``supports_status=None``인 근거는 "이 근거가 특정 상태를 지지하지 않는다"
   (``data.models_risk.ClassifiedEvidence`` docstring)는 뜻이므로 판정에 참여하지 않는다.
2. 유효 근거가 0개면 ``정보_없음``이다(요구사항 6.8 "위험_판정_축을 판단할 목업_출처가
   없으면 ... 정보_없음으로 판정한다"). 반환하는 출처_식별자 집합은 빈 튜플이다.
3. 유효 근거의 ``supports_status`` distinct 값이 정확히 1개면 그 상태로 만장일치이므로
   해당 상태를 반환한다(요구사항 6.2~6.6). 반환하는 출처_식별자 집합은 유효 근거의
   ``source_id``를 최초 등장 순서로 중복 제거한 튜플이다(요구사항 6.7 "정보_없음 이외의
   ... 상태를 반환하면 ... 판정에 사용한 출처_식별자 집합을 함께 반환한다").
4. 유효 근거의 distinct 상태가 2개 이상이면 서로 충돌하므로 ``분류_불가``다(요구사항 6.9
   "서로 충돌하거나 하나의 상태를 결정할 수 없으면"). 이때도 요구사항 6.7에 따라 판정(충돌
   확인)에 사용한 모든 유효 근거의 출처_식별자 집합을 반환한다(6.7은 "정보_없음 이외의"
   모든 상태에 적용되며 분류_불가도 포함된다).

## ``classify_action_badge`` — 행동_배지_상태 (요구사항 6.10~6.14)

:func:`classify_action_badge`는 하나의 경찰 행동을 판단하는
:class:`~data.models_risk.ActionJudgment` 전체(그 행동을 판단하는 목업_출처들의 개별
판단)를 입력받아 판정한다. 위험_판정_축과 달리 ``CourtFinding``에는 명시적 "모호" 값
(``"AMBIGUOUS"``)이 있으므로, 단순 distinct-cardinality 규칙이 아니라 "전체가 PROBLEM" /
"전체가 LAWFUL" / "그 외(빈 값 제외)" 세 갈래로 판정한다:

- 입력이 비어 있으면(판단할 목업_출처가 없음) ``정보_없음``이다(요구사항 6.12).
- 모든 판단이 ``PROBLEM``이면 ``문제_행동``이고 사용한 출처_식별자를 반환한다(요구사항 6.10).
- 모든 판단이 ``LAWFUL``이면 ``적법_행동``이고 사용한 출처_식별자를 반환한다(요구사항 6.11).
- 그 외(``PROBLEM``과 ``LAWFUL``이 섞이거나, ``AMBIGUOUS``가 하나라도 있으면)에는
  ``분류_불가``다(요구사항 6.13 "서로 충돌하거나 적법과 문제 중 하나로 분류할 수 없으면").
  ``AMBIGUOUS`` 판단이 하나라도 있으면 나머지 판단이 전부 같은 값이어도 "적법과 문제 중
  하나로 분류할 수 없다"에 해당하므로 ``분류_불가``로 판정한다(``design.md`` Property 17
  "ambiguous 단독" 경계 사례).

하나의 행동에는 이 함수가 반환하는 정확히 하나의
:class:`~data.models_risk.ActionBadgeProjection` 변형만 대응한다(요구사항 6.14, 6.9).
"""

from __future__ import annotations

from typing import Sequence, Set, Tuple, TypeVar, Union

from domain.ids import SourceId

from data.models_risk import (
    AbuseOfAuthorityStatus,
    ActionBadgeLawful,
    ActionBadgeNoInformation,
    ActionBadgeProblem,
    ActionBadgeProjection,
    ActionBadgeUnclassifiable,
    ActionJudgment,
    CivilStatus,
    ClassifiedEvidence,
    CustodialViolenceStatus,
    DisciplineStatus,
    RiskFallback,
)

__all__ = [
    "classify_evidence",
    "classify_action_badge",
]

T = TypeVar(
    "T",
    CivilStatus,
    AbuseOfAuthorityStatus,
    CustodialViolenceStatus,
    DisciplineStatus,
)


def _dedupe_source_ids(source_ids: Sequence[SourceId]) -> Tuple[SourceId, ...]:
    """``source_ids``를 최초 등장 순서를 유지하며 중복 제거한다."""

    seen: Set[SourceId] = set()
    result: list[SourceId] = []
    for source_id in source_ids:
        if source_id not in seen:
            seen.add(source_id)
            result.append(source_id)
    return tuple(result)


def classify_evidence(
    evidence: Sequence[ClassifiedEvidence[T]],
) -> Tuple[Union[T, RiskFallback], Tuple[SourceId, ...]]:
    """하나의 위험_판정_축을 ``evidence``로 판정한다.

    반환값은 ``(판정 상태, 판정에 사용한 출처_식별자 집합)`` 튜플이다. 모듈 docstring
    "``classify_evidence`` — 위험_판정_축" 절의 절차를 그대로 구현한다. ``design.md``의
    ``classifyEvidence<TStatus>(evidence)`` 계약에 대응하며, 반환값에 사용한 출처
    정보를 함께 담아 요구사항 6.7을 만족한다.
    """

    valid_statuses: list[T] = []
    valid_source_ids: list[SourceId] = []
    for item in evidence:
        if item.supports_status is not None:
            valid_statuses.append(item.supports_status)
            valid_source_ids.append(item.source_id)

    if not valid_statuses:
        return "정보_없음", ()

    distinct_statuses = set(valid_statuses)
    source_ids = _dedupe_source_ids(valid_source_ids)

    if len(distinct_statuses) == 1:
        (status,) = distinct_statuses
        return status, source_ids

    return "분류_불가", source_ids


def classify_action_badge(
    judgments: Sequence[ActionJudgment],
) -> ActionBadgeProjection:
    """하나의 경찰 행동을 판단하는 ``judgments``로 행동_배지_상태를 판정한다.

    ``judgments``는 같은 행동을 판단하는 목업_출처들의 개별 :class:`ActionJudgment`
    전체여야 한다(호출자가 행동 단위로 미리 그룹화해서 전달한다). 모듈 docstring
    "``classify_action_badge`` — 행동_배지_상태" 절의 절차를 그대로 구현한다.
    """

    if not judgments:
        return ActionBadgeNoInformation(state="정보_없음")

    findings = {judgment.court_finding for judgment in judgments}
    source_ids = _dedupe_source_ids(
        [
            source_id
            for judgment in judgments
            for source_id in judgment.source_ids
        ]
    )

    if findings == {"PROBLEM"}:
        return ActionBadgeProblem(state="문제_행동", source_ids=source_ids)
    if findings == {"LAWFUL"}:
        return ActionBadgeLawful(state="적법_행동", source_ids=source_ids)
    return ActionBadgeUnclassifiable(state="분류_불가")
