"""데이터 모델 공통 타입.

``design.md`` "Data Models" 절에서 여러 인터페이스가 공유하는 리터럴 타입, 식별자,
관계 그래프(``RelationGraph``/``RelationEdge``), 법률 용어 대응(``LegalTermMapping``),
표시 정책 레코드(``DisplayPolicyRecord``/``SimilarityWarningPolicyRecord``/
``MockDisplayPolicies``)를 정의한다.

``domain.ids``·``domain.enums``에 이미 정의된 타입(``Result``, 7종 branded ID,
``PoliceScenario`` 등 열거형)은 재정의하지 않고 그대로 가져와 사용한다(task 1.1).
필드명은 Python 관례에 따라 snake_case를 쓰되, 각 클래스/필드 docstring에 대응하는
``design.md`` TypeScript 필드명을 병기해 추적성을 유지한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NewType, Optional, Tuple, Union

from domain.enums import PoliceScenario

IsoDate = str
"""``YYYY-MM-DD`` 형식을 기대하는 날짜 문자열(design.md ``IsoDate``).

형식·유효성 검증은 이 모듈의 책임이 아니라 데이터셋 검증기(task 2.x ``DatasetValidator``)의
책임이다. 이 계층은 타입 표시만 제공한다.
"""

IsoDateTime = str
"""ISO 8601 날짜/시간 문자열(design.md ``IsoDateTime``). 형식 검증은 검증기가 담당한다."""

SourceAnchorId = NewType("SourceAnchorId", str)
"""``SourceAnchor`` 레코드를 하나의 ``SourceRecord`` 안에서 가리키는 식별자.

``domain.ids``의 7종 branded ID(task 1.1에서 확정)에는 포함되지 않으므로 이 데이터 계층
모듈에서 새로 선언한다. 런타임에는 일반 ``str``과 동일하게 동작한다.
"""

VoiceFixtureId = NewType("VoiceFixtureId", str)
"""``VoiceFixture`` 레코드를 가리키는 식별자. ``domain.ids``의 7종 ID와 별개로 선언한다."""

Instance = Literal["1심", "항소심", "상고심"]
"""판례의 심급. design.md Data Models 3절 ``CaseRecord.instance``."""

AppellateInstance = Literal["항소심", "상고심"]
"""상급심 결정의 심급. design.md Data Models 10절 ``AppellateDecision.instance``."""

InstanceRelation = Literal["하급심", "상급심"]
"""``RelatedInstanceRef.relation``. 기준 판례 대비 연결된 판례의 심급 관계."""

RelationToLowerInstance = Literal["유지", "변경"]
"""``AppellateDecision.relationToLowerInstance``. 원심(직전 하급심) 대비 관계."""

Finality = Literal["확정", "미확정", "정보_없음"]
"""``CaseRecord.finality``."""

AppellateState = Literal["PRESENT", "정보_없음"]
"""``AppellateInformation.state``."""

CourtFinding = Literal["PROBLEM", "LAWFUL", "AMBIGUOUS"]
"""``ActionJudgment.courtFinding``."""

DisplayPolicyKind = Literal["NOTICE", "PLACEHOLDER", "STATUS_LABEL"]
"""``DisplayPolicyRecord.kind``."""

SimilarityWarningKey = Literal["HIGH", "MEDIUM", "LOW"]
"""``SimilarityWarningPolicyRecord.key``."""

InputMode = Literal["TEXT", "VOICE_FIXTURE"]
"""``QueryVariant.inputMode``."""

SourceOwnerType = Literal["CASE", "STATUTE"]
"""``SourceRecord.owner.type``."""

SourceKind = Literal["JUDGMENT_EXCERPT", "STATUTE_TEXT"]
"""``SourceRecord.sourceKind``."""

ClaimEvidencePurpose = Literal["DECISION", "REFERENCE"]
"""``ClaimEvidenceLink.purpose``."""

ClaimEvidenceRelation = Literal["SUPPORTS", "CONTRADICTS", "RELATED"]
"""``ClaimEvidenceLink.relation``."""

ClaimEvidenceCoverage = Literal["FULL", "PARTIAL", "NONE"]
"""``ClaimEvidenceLink.coverage``."""

FactDimension = Literal[
    "체포 시점",
    "영장 유무",
    "동행 자발성",
    "권리 고지 여부",
    "물리력 정도",
    "증거 확보 방식",
    "기타",
]
"""design.md Data Models 8절 ``FactDimension``."""


@dataclass(frozen=True)
class ActorActionEdge:
    """``RelationEdge`` 중 ``ACTOR_ACTION`` 변형. 사람과 행위의 관계를 표현한다."""

    type: Literal["ACTOR_ACTION"]
    actor: str
    action: str


@dataclass(frozen=True)
class ActionTimeEdge:
    """``RelationEdge`` 중 ``ACTION_TIME`` 변형. 행위와 시점의 관계를 표현한다."""

    type: Literal["ACTION_TIME"]
    action: str
    time: str


@dataclass(frozen=True)
class NegationTargetEdge:
    """``RelationEdge`` 중 ``NEGATION_TARGET`` 변형. 부정 표현과 부정 대상의 관계를 표현한다."""

    type: Literal["NEGATION_TARGET"]
    negation: str
    target: str


RelationEdge = Union[ActorActionEdge, ActionTimeEdge, NegationTargetEdge]
"""design.md Data Models 2절 ``RelationEdge`` 판별 유니온.

``domain.result.Ok``/``Err``와 동일하게 판별 필드(``type``)로 구분되는 세 변형의 합집합이다.
"""


@dataclass(frozen=True)
class RelationGraph:
    """사람·행위·시점·부정 관계 그래프. design.md Data Models 2절 ``RelationGraph``.

    관계 동등성은 (``relationsPreserved``에서) edge의 정규화된 집합으로 비교하므로,
    ``actors``/``actions``/``times``/``negations`` 배열의 순서는 화면 표시가 필요한 경우에만
    의미가 있다.
    """

    actors: Tuple[str, ...]
    actions: Tuple[str, ...]
    times: Tuple[str, ...]
    negations: Tuple[str, ...]
    edges: Tuple[RelationEdge, ...]


@dataclass(frozen=True)
class LegalTermMapping:
    """경찰_현장_표현 ↔ 법률_검색어 대응. design.md Data Models 2절 ``LegalTermMapping``."""

    id: str
    field_expression: str
    """design.md ``fieldExpression``. 경찰 현장에서 쓰는 비법률적 표현."""
    legal_search_terms: Tuple[str, ...]
    """design.md ``legalSearchTerms``."""
    relation_graph_before: RelationGraph
    """design.md ``relationGraphBefore``."""
    relation_graph_after: Union[RelationGraph, Tuple[RelationGraph, ...]]
    """design.md ``relationGraphAfter``. 복수 해석이 가능하면 여러 ``RelationGraph``의 튜플이다."""
    unsupported_fragments: Tuple[str, ...]
    """design.md ``unsupportedFragments``."""


@dataclass(frozen=True)
class DisplayPolicyRecord:
    """고정 고지·결측·상태 문구를 나타내는 표시 정책 레코드. design.md Data Models 1절.

    안전 고지, ``정보_없음``, ``분류_불가``, ``확인 필요``, ``확인되지 않음``, 데이터 오류
    문구는 모두 이 레코드로 표현하며, 분류 함수는 문자열을 직접 만들지 않고 이 레코드의
    ``id``를 선택한다.
    """

    id: str
    kind: DisplayPolicyKind
    key: str
    text: str
    summary_label: Optional[str] = None
    """design.md ``summaryLabel``. 좁은 화면 상시 노출용 1줄 요약 라벨(선택)."""
    full_text: Optional[str] = None
    """design.md ``fullText``. 접근 가능한 펼침 영역에 표시할 전체 문구(선택)."""


@dataclass(frozen=True)
class SimilarityWarningPolicyRecord:
    """유사도 경고 구간 표시 정책. design.md Data Models 1절 ``SimilarityWarningPolicyRecord``."""

    id: str
    kind: Literal["SIMILARITY_WARNING"]
    key: SimilarityWarningKey
    min_inclusive: float
    text: Literal[
        "높은 유사도 — 핵심 차이 확인 필요",
        "중간 유사도 — 직접 적용 전 사실관계 재검토 필요",
        "낮은 유사도 — 결론 근거로 사용 금지",
    ]
    max_inclusive: Optional[float] = None
    max_exclusive: Optional[float] = None


@dataclass(frozen=True)
class MockDisplayPolicies:
    """표시 정책 레코드 묶음. design.md Data Models 1절 ``MockDisplayPolicies``."""

    notices: Tuple[DisplayPolicyRecord, ...]
    placeholders: Tuple[DisplayPolicyRecord, ...]
    status_labels: Tuple[DisplayPolicyRecord, ...]
    similarity_warnings: Tuple[SimilarityWarningPolicyRecord, ...]


@dataclass(frozen=True)
class ScenarioDefinition:
    """경찰_직무_시나리오 탐색 항목 정의. design.md ``MockDataset.scenarios``.

    design.md는 ``readonly ScenarioDefinition[]``를 참조하지만 이 인터페이스의 필드를
    별도로 명세하지 않는다. 요구사항 4.1·4.2가 요구하는 최소 정보(시나리오 식별자와 화면
    표시 라벨)만 담는 최소 유효 해석이다.
    """

    id: PoliceScenario
    label: str
