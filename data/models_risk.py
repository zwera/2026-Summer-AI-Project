"""개인 책임 위험과 행동 배지 데이터 모델.

``design.md`` Data Models 7절의 ``PersonalLiabilityRisk``, ``RiskAssessment``,
``ClassifiedEvidence``와 ``ActionJudgment``(3절)를 정의한다.

TypeScript의 제네릭 ``RiskValue<T> = T | "정보_없음" | "분류_불가"``는 Python의
``TypeVar``+``Literal`` 결합으로 완전히 표현할 수 없으므로, 각 위험 축에 특화된 리터럴
유니온을 직접 선언한다(축별 허용 상태는 요구사항 6.2~6.5에서 고정되어 있어 특화해도 계약을
그대로 보존한다).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, Optional, Tuple, TypeVar, Union

from domain.ids import SourceId

from data.models_common import CourtFinding, SourceAnchorId

CivilStatus = Literal["국가배상_인정", "국가배상_기각"]
"""design.md ``PersonalLiabilityRisk.civil``의 결정 상태(요구사항 6.2)."""

AbuseOfAuthorityStatus = Literal["해당", "불해당"]
"""형사 직권남용 위험_판정_축의 결정 상태(요구사항 6.3)."""

CustodialViolenceStatus = Literal["해당", "불해당"]
"""형사 독직폭행 위험_판정_축의 결정 상태(요구사항 6.4)."""

DisciplineStatus = Literal["징계_인정", "징계_불인정"]
"""징계 위험_판정_축의 결정 상태(요구사항 6.5)."""

RiskFallback = Literal["정보_없음", "분류_불가"]
"""모든 위험_판정_축이 공유하는 결측/충돌 상태."""

T = TypeVar("T", CivilStatus, AbuseOfAuthorityStatus, CustodialViolenceStatus, DisciplineStatus)


@dataclass(frozen=True)
class ClassifiedEvidence(Generic[T]):
    """위험_판정_축 판정에 쓰이는 개별 근거. design.md Data Models 7절 ``ClassifiedEvidence``."""

    source_id: SourceId
    anchor_id: SourceAnchorId
    supports_status: Optional[T]
    """design.md ``supportsStatus``. ``None``이면 이 근거가 특정 상태를 지지하지 않는다."""


@dataclass(frozen=True)
class RiskAssessment(Generic[T]):
    """하나의 위험_판정_축 판정 결과. design.md Data Models 7절 ``RiskAssessment``.

    ``declared``는 ``evidence``에서 다시 계산한 값과 일치해야 한다(데이터 검증기 불변식).
    불일치하면 해당 값을 숨기고 ``판례 데이터 불일치``를 표시한다.
    """

    declared: Union[T, RiskFallback]
    evidence: Tuple[ClassifiedEvidence[T], ...]


@dataclass(frozen=True)
class CriminalLiabilityRisk:
    """``PersonalLiabilityRisk.criminal``. 형사 직권남용·독직폭행 두 축을 묶는다."""

    abuse_of_authority: RiskAssessment[AbuseOfAuthorityStatus]
    custodial_violence: RiskAssessment[CustodialViolenceStatus]


@dataclass(frozen=True)
class PersonalLiabilityRisk:
    """판례 하나의 개인_책임_위험. design.md Data Models 7절 ``PersonalLiabilityRisk``."""

    civil: RiskAssessment[CivilStatus]
    criminal: CriminalLiabilityRisk
    discipline: RiskAssessment[DisciplineStatus]


@dataclass(frozen=True)
class ActionJudgment:
    """경찰 행동 하나에 대한 법원 판단. design.md Data Models 3절 ``ActionJudgment``.

    판단_혼재 판례에서 행동별 법원 판단을 분리해 표시할 때 쓰인다(요구사항 4.10).
    """

    action_id: str
    action_text: str
    court_finding: CourtFinding
    source_ids: Tuple[SourceId, ...]


@dataclass(frozen=True)
class ActionBadgeProblem:
    """``ActionBadgeProjection`` 중 ``문제_행동`` 변형."""

    state: Literal["문제_행동"]
    source_ids: Tuple[SourceId, ...]


@dataclass(frozen=True)
class ActionBadgeLawful:
    """``ActionBadgeProjection`` 중 ``적법_행동`` 변형."""

    state: Literal["적법_행동"]
    source_ids: Tuple[SourceId, ...]


@dataclass(frozen=True)
class ActionBadgeNoInformation:
    """``ActionBadgeProjection`` 중 ``정보_없음`` 변형."""

    state: Literal["정보_없음"]


@dataclass(frozen=True)
class ActionBadgeUnclassifiable:
    """``ActionBadgeProjection`` 중 ``분류_불가`` 변형."""

    state: Literal["분류_불가"]


ActionBadgeProjection = Union[
    ActionBadgeProblem,
    ActionBadgeLawful,
    ActionBadgeNoInformation,
    ActionBadgeUnclassifiable,
]
"""design.md Data Models 7절 ``ActionBadgeProjection`` 판별 유니온."""
