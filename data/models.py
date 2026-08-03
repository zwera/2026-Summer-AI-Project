"""목업 데이터셋·표시 정책 데이터 모델 재노출 모듈.

이 모듈은 ``data.models_*`` 하위 모듈에 나눠 정의한 dataclass·타입을 한 곳에서
임포트할 수 있게 재노출(re-export)한다. 실제 정의는 각 하위 모듈에 있으며, 이 파일은
새 타입을 정의하지 않는다.

하위 모듈 구성:

- ``data.models_common``: 공통 리터럴, ``RelationGraph``/``RelationEdge``,
  ``LegalTermMapping``, 표시 정책 레코드(``DisplayPolicyRecord`` 등).
- ``data.models_query``: ``QueryFixture``, ``QueryVariant``, ``SimilarityPreset``.
- ``data.models_case``: ``CaseRecord``, ``RelatedInstanceRef``, ``AppellateInformation``.
- ``data.models_statute``: ``StatuteRecord``, ``StatuteVersion``, ``AppliedStatuteRef``.
- ``data.models_source``: ``SourceRecord``, ``SourceAnchor``, ``ResponseTemplate``.
- ``data.models_summary``: ``SummaryBundle``과 요약 관련 타입.
- ``data.models_risk``: ``PersonalLiabilityRisk``, ``ActionJudgment``, 행동 배지.
- ``data.models_fact_difference``: ``FactDifference``, 유사도 경고 projection.
- ``data.models_timeline``: ``VoiceFixture``, ``RecognizedEvent``, ``ReportDocument``.
- ``data.models_selection``: ``SelectionReviewFixture``와 관련 타입.
- ``data.models_dataset``: ``MockDataset`` 루트.
"""

from __future__ import annotations

from data.models_case import (
    AppellateDecision,
    AppellateInformation,
    CaseRecord,
    RelatedInstanceRef,
)
from data.models_common import (
    ActionTimeEdge,
    ActorActionEdge,
    AppellateInstance,
    AppellateState,
    ClaimEvidenceCoverage,
    ClaimEvidencePurpose,
    ClaimEvidenceRelation,
    CourtFinding,
    DisplayPolicyKind,
    DisplayPolicyRecord,
    FactDimension,
    Finality,
    Instance,
    InstanceRelation,
    InputMode,
    IsoDate,
    IsoDateTime,
    LegalTermMapping,
    MockDisplayPolicies,
    NegationTargetEdge,
    RelationEdge,
    RelationGraph,
    RelationToLowerInstance,
    ScenarioDefinition,
    SimilarityWarningKey,
    SimilarityWarningPolicyRecord,
    SourceAnchorId,
    SourceKind,
    SourceOwnerType,
    VoiceFixtureId,
)
from data.models_dataset import (
    IMPLEMENTED_COVERAGE_LABEL_TEXT,
    INSTANCE_CAUTION_NOTICE_TEXT,
    LEGAL_SAFETY_NOTICE_TEXT,
    NO_REALTIME_SYNC_LABEL_TEXT,
    TARGET_COVERAGE_LABEL_TEXT,
    ImplementedCoverageLabel,
    MockDataset,
    TargetCoverageLabel,
)
from data.models_fact_difference import FactDifference, SimilarityWarningProjection
from data.models_query import QueryFixture, QueryMatch, QueryVariant, SimilarityPreset
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
    CriminalLiabilityRisk,
    CustodialViolenceStatus,
    DisciplineStatus,
    PersonalLiabilityRisk,
    RiskAssessment,
    RiskFallback,
)
from data.models_selection import (
    ClaimReviewOutcome,
    LegalTermExplanationEntry,
    ReviewableClaim,
    SelectionExplanationFixture,
    SelectionReviewFixture,
    SelectionReviewResult,
)
from data.models_source import (
    ClaimEvidenceLink,
    LegalClaimBlock,
    ResponseBlock,
    ResponseTemplate,
    SourceAnchor,
    SourceOwner,
    SourceRecord,
    TextBlock,
)
from data.models_statute import AppliedStatuteRef, StatuteRecord, StatuteVersion
from data.models_summary import (
    DetailedSummarySection,
    DetailedSummarySubsection,
    FieldTermExplanation,
    SummaryBundle,
    SummaryLine,
    SummarySectionKey,
)
from data.models_timeline import (
    EventAmbiguity,
    IssueLink,
    RecognizedEvent,
    RelativeTime,
    ReportDocument,
    TimelineProjection,
    VoiceFixture,
)

__all__ = [
    "AbuseOfAuthorityStatus",
    "ActionBadgeLawful",
    "ActionBadgeNoInformation",
    "ActionBadgeProblem",
    "ActionBadgeProjection",
    "ActionBadgeUnclassifiable",
    "ActionJudgment",
    "ActionTimeEdge",
    "ActorActionEdge",
    "AppellateDecision",
    "AppellateInformation",
    "AppellateInstance",
    "AppellateState",
    "AppliedStatuteRef",
    "CaseRecord",
    "CivilStatus",
    "ClaimEvidenceCoverage",
    "ClaimEvidenceLink",
    "ClaimEvidencePurpose",
    "ClaimEvidenceRelation",
    "ClaimReviewOutcome",
    "ClassifiedEvidence",
    "CourtFinding",
    "CriminalLiabilityRisk",
    "CustodialViolenceStatus",
    "DetailedSummarySection",
    "DetailedSummarySubsection",
    "DisciplineStatus",
    "DisplayPolicyKind",
    "DisplayPolicyRecord",
    "EventAmbiguity",
    "FactDifference",
    "FactDimension",
    "FieldTermExplanation",
    "Finality",
    "IMPLEMENTED_COVERAGE_LABEL_TEXT",
    "INSTANCE_CAUTION_NOTICE_TEXT",
    "ImplementedCoverageLabel",
    "Instance",
    "InstanceRelation",
    "InputMode",
    "IsoDate",
    "IsoDateTime",
    "IssueLink",
    "LEGAL_SAFETY_NOTICE_TEXT",
    "LegalClaimBlock",
    "LegalTermExplanationEntry",
    "LegalTermMapping",
    "MockDataset",
    "MockDisplayPolicies",
    "NO_REALTIME_SYNC_LABEL_TEXT",
    "NegationTargetEdge",
    "PersonalLiabilityRisk",
    "QueryFixture",
    "QueryMatch",
    "QueryVariant",
    "RecognizedEvent",
    "RelatedInstanceRef",
    "RelationEdge",
    "RelationGraph",
    "RelationToLowerInstance",
    "RelativeTime",
    "ReportDocument",
    "ResponseBlock",
    "ResponseTemplate",
    "ReviewableClaim",
    "RiskAssessment",
    "RiskFallback",
    "ScenarioDefinition",
    "SelectionExplanationFixture",
    "SelectionReviewFixture",
    "SelectionReviewResult",
    "SimilarityPreset",
    "SimilarityWarningKey",
    "SimilarityWarningPolicyRecord",
    "SimilarityWarningProjection",
    "SourceAnchor",
    "SourceAnchorId",
    "SourceKind",
    "SourceOwner",
    "SourceOwnerType",
    "SourceRecord",
    "StatuteRecord",
    "StatuteVersion",
    "SummaryBundle",
    "SummaryLine",
    "SummarySectionKey",
    "TARGET_COVERAGE_LABEL_TEXT",
    "TargetCoverageLabel",
    "TextBlock",
    "TimelineProjection",
    "VoiceFixture",
    "VoiceFixtureId",
]
