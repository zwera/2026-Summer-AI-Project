"""판례 레코드와 상급심·확정 정보 데이터 모델.

``design.md`` Data Models 3절의 ``CaseRecord``, ``RelatedInstanceRef``와 10절의
``AppellateInformation``, ``AppellateDecision``을 정의한다.

요구사항 4.1·4.9·16.1·16.2와 task 1.2 지시에 따라 ``CaseRecord.instance``는
``"1심" | "항소심" | "상고심"``으로 제한하고, 동일 사건의 심급 연결은
``relatedInstances``(``RelatedInstanceRef`` 목록)로, 상급심 결정의 원심 대비 관계는
``AppellateDecision.relationToLowerInstance``(``"유지" | "변경"``)로 표현한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from domain.enums import LawBasisStatus, LegalityStatus, PoliceScenario, TraditionalCaseArea
from domain.ids import CaseId, QueryId, SourceId

from data.models_common import (
    AppellateInstance,
    AppellateState,
    Finality,
    Instance,
    InstanceRelation,
    IsoDate,
    RelationToLowerInstance,
)
from data.models_fact_difference import FactDifference
from data.models_risk import ActionJudgment, PersonalLiabilityRisk
from data.models_statute import AppliedStatuteRef
from data.models_summary import SummaryBundle


@dataclass(frozen=True)
class RelatedInstanceRef:
    """동일 사건의 다른 심급 판례에 대한 연결. design.md Data Models 3절 ``RelatedInstanceRef``."""

    case_id: CaseId
    instance: Instance
    relation: InstanceRelation


@dataclass(frozen=True)
class AppellateDecision:
    """상급심(항소심/상고심) 결정 하나. design.md Data Models 10절 ``AppellateDecision``.

    ``relation_to_lower_instance``는 이 결정의 직전 하급심(원심) 대비 관계를 나타낸다.
    """

    case_number: str
    instance: AppellateInstance
    court_name: str
    decision_date: IsoDate
    outcome: str
    relation_to_lower_instance: RelationToLowerInstance
    source_ids: Tuple[SourceId, ...]


@dataclass(frozen=True)
class AppellateInformation:
    """상급심_정보. design.md Data Models 10절 ``AppellateInformation``.

    ``state="정보_없음"``이면 ``decisions``는 반드시 빈 튜플이어야 한다(요구사항 12.8,
    12.11, Property 37).
    """

    state: AppellateState
    decisions: Tuple[AppellateDecision, ...]


@dataclass(frozen=True)
class CaseRecord:
    """판례 하나의 전체 레코드. design.md Data Models 3절 ``CaseRecord``."""

    id: CaseId
    court_name: str
    instance: Instance
    case_number: str
    decision_date: IsoDate
    scenario_ids: Tuple[PoliceScenario, ...]
    legality_status: LegalityStatus
    action_judgments: Tuple[ActionJudgment, ...]
    source_ids: Tuple[SourceId, ...]
    applied_statutes: Tuple[AppliedStatuteRef, ...]
    expected_law_basis_status: LawBasisStatus
    """design.md ``expectedLawBasisStatus``."""
    summaries: SummaryBundle
    instance_recognized_charge: Optional[str]
    """design.md ``instanceRecognizedCharge``. 해당_심급_인정_죄명."""
    instance_outcome: Optional[str]
    """design.md ``instanceOutcome``. 해당_심급_재판_결과."""
    liability: PersonalLiabilityRisk
    related_instances: Tuple[RelatedInstanceRef, ...]
    appellate: AppellateInformation
    finality: Finality
    fact_differences_by_query: Mapping[QueryId, Tuple[FactDifference, ...]]
    """design.md ``factDifferencesByQuery``. ``Record<QueryId, readonly FactDifference[]>``."""
    traditional_areas: Optional[Tuple[TraditionalCaseArea, ...]] = None
