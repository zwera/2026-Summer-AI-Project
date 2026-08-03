"""경찰_직무_시나리오별 적법성 partition과 보조_필터 교집합 (task 7.1).

``design.md`` "핵심 포트와 함수 시그니처"의 ``filterScenarioIntersection``과
Components 표 ``ScenarioExplorer`` 행, 그리고 Property 10~12를 구현한다.

- :func:`partition_scenario_cases` — 요구사항 4.6 "선택한 경찰_직무_시나리오의 판례를
  적법, 위법 및 판단_혼재의 세 집합으로 분할하여 반환한다"와 4.8 "각 판례를 적법성_상태와
  일치하는 하나의 구분 영역에 정확히 한 번 표시한다"를 만족하는 서로소·완전 partition을
  만든다. 판례의 ``legality_status``가 :class:`~domain.enums.LegalityStatus`의 정확히
  하나의 멤버이므로(요구사항 4.4, ``data.models_case.CaseRecord`` 불변식), 세 갈래
  분기가 서로소이고 선택 시나리오에 매칭되는 판례 집합과 합집합이 같다는 성질은 이
  함수의 구현 자체(각 판례가 정확히 한 분기에만 들어가는 ``if``/``elif`` 없는 순차
  필터가 아니라 열거형 값 하나로 배타적 분류)에서 보장된다.
- 판단_혼재(``LegalityStatus.MIXED``) 판례는 :class:`MixedCaseJudgments`로 감싸,
  요구사항 4.10 "판례 안의 각 경찰 행위와 각 경찰 행위에 대응하는 법원 판단을 별도
  항목으로 표시한다"에 따라 ``CaseRecord.action_judgments``(행동-법원 판단 쌍 튜플)를
  그대로 보존한다. 단일 상태로 축약하지 않는다.
- :func:`filter_scenario_intersection` — 요구사항 4.12 "두 선택 조건을 모두 충족하는
  판례의 교집합만 반환한다"를 만족하는 순수 논리 AND. ``auxiliary``가 주어졌을 때
  ``case.traditional_areas``가 ``None``이면(전통적 사건 분야 정보 없음) 그 판례는
  교집합에서 제외된다.

이 모듈은 도메인 계층 전용이며 클라이언트 표시 로직(``ScenarioExplorer`` UI)이나
목업 검색·인용 로직은 다루지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from domain.enums import LegalityStatus, PoliceScenario, TraditionalCaseArea

from data.models_case import CaseRecord
from data.models_risk import ActionJudgment

__all__ = [
    "MixedCaseJudgments",
    "ScenarioPartition",
    "partition_scenario_cases",
    "filter_scenario_intersection",
]


@dataclass(frozen=True)
class MixedCaseJudgments:
    """판단_혼재 판례 하나와 그 행동-법원 판단 쌍 목록.

    요구사항 4.10에 따라 ``action_judgments``의 각 :class:`~data.models_risk.ActionJudgment`는
    별도 항목으로 보존된다(``case.action_judgments``와 동일한 튜플이며 재정렬·병합하지 않는다).
    """

    case: CaseRecord
    action_judgments: Tuple[ActionJudgment, ...]


@dataclass(frozen=True)
class ScenarioPartition:
    """선택한 경찰_직무_시나리오에 매칭되는 판례의 적법/위법/판단_혼재 서로소 partition.

    ``lawful``·``unlawful``·``mixed``(``mixed``는 :class:`MixedCaseJudgments`로 감싼 판례)
    세 컬렉션은 서로소이며, 세 컬렉션에 속한 판례 ID의 합집합은 이 시나리오에 매칭되는
    (``scenario in case.scenario_ids``) 판례 전체와 정확히 같다(요구사항 4.6, 4.8,
    design.md Property 10).
    """

    scenario: PoliceScenario
    lawful: Tuple[CaseRecord, ...]
    unlawful: Tuple[CaseRecord, ...]
    mixed: Tuple[MixedCaseJudgments, ...]


def partition_scenario_cases(
    cases: Sequence[CaseRecord], scenario: PoliceScenario
) -> ScenarioPartition:
    """``scenario``에 매칭되는 ``cases``를 적법/위법/판단_혼재 세 집합으로 분할한다.

    매칭 조건은 ``scenario in case.scenario_ids``다(요구사항 4.3에 따라 판례가 여러
    경찰_직무_시나리오에 속할 수 있으므로, 한 판례가 다른 시나리오의 partition에도
    나타날 수 있다 — 이는 이 함수가 시나리오별로 독립 호출되는 것이므로 이 함수
    자체의 서로소 성질과 무관하다). 하나의 ``scenario`` 호출 안에서는 각 매칭 판례가
    ``legality_status``와 일치하는 정확히 하나의 결과 컬렉션에만 나타난다.
    """

    lawful: list[CaseRecord] = []
    unlawful: list[CaseRecord] = []
    mixed: list[MixedCaseJudgments] = []

    for case in cases:
        if scenario not in case.scenario_ids:
            continue
        if case.legality_status is LegalityStatus.LAWFUL:
            lawful.append(case)
        elif case.legality_status is LegalityStatus.UNLAWFUL:
            unlawful.append(case)
        else:
            mixed.append(MixedCaseJudgments(case=case, action_judgments=case.action_judgments))

    return ScenarioPartition(
        scenario=scenario,
        lawful=tuple(lawful),
        unlawful=tuple(unlawful),
        mixed=tuple(mixed),
    )


def filter_scenario_intersection(
    cases: Sequence[CaseRecord],
    scenario: PoliceScenario,
    auxiliary: Optional[TraditionalCaseArea] = None,
) -> Tuple[CaseRecord, ...]:
    """``scenario``와(제공된 경우) ``auxiliary`` 보조_필터를 모두 만족하는 판례만 반환한다.

    ``design.md``의 ``filterScenarioIntersection(cases, scenario, auxiliary?)``에 대응한다.
    ``auxiliary``가 ``None``이면 시나리오 조건만 적용한다(요구사항 4.6과 동일한 매칭).
    ``auxiliary``가 주어지면 ``auxiliary in case.traditional_areas``까지 요구하는 순수
    논리 AND이며(요구사항 4.12), ``case.traditional_areas``가 ``None``인 판례는(전통적
    사건 분야 정보 없음) 이 교집합에서 제외된다.
    """

    def _matches(case: CaseRecord) -> bool:
        if scenario not in case.scenario_ids:
            return False
        if auxiliary is None:
            return True
        if case.traditional_areas is None:
            return False
        return auxiliary in case.traditional_areas

    return tuple(case for case in cases if _matches(case))
