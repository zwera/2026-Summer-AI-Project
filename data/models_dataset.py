"""목업 데이터셋 루트 모델.

``design.md`` Data Models 1절의 ``MockDataset``을 정의한다. 이 dataclass는 신뢰되지 않은
원본 구조를 담는 그릇일 뿐이며, 구조·교차 참조·불변식 검증을 통과해야만 만들 수 있는
불투명 ``ValidatedDataset``(task 2.x ``DatasetValidator``에서 구현)과는 다르다. 이 모듈은
검증을 수행하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

from domain.ids import DatasetId

from data.models_case import CaseRecord
from data.models_common import (
    IsoDate,
    LegalTermMapping,
    MockDisplayPolicies,
    ScenarioDefinition,
)
from data.models_query import QueryFixture
from data.models_selection import SelectionReviewFixture
from data.models_source import ResponseTemplate, SourceRecord
from data.models_statute import StatuteRecord, StatuteVersion
from data.models_timeline import VoiceFixture

TargetCoverageLabel = Literal["공개적으로 확인 가능한 제1심·항소심·상고심 판례"]
ImplementedCoverageLabel = Literal["사전에 정의된 목업 전체 심급 판례 샘플"]

LEGAL_SAFETY_NOTICE_TEXT: Literal[
    "본 서비스는 수사 및 법률 업무의 정보 정리·검토를 지원하기 위한 목업 데이터 기반 시연용 프로토타입입니다. 제공 결과는 담당자의 검토와 관계 법령 및 내부 절차에 따른 판단을 보조하며, 최종 법률 판단·수사 판단·공식 업무 결정을 대체하지 않습니다."
] = "본 서비스는 수사 및 법률 업무의 정보 정리·검토를 지원하기 위한 목업 데이터 기반 시연용 프로토타입입니다. 제공 결과는 담당자의 검토와 관계 법령 및 내부 절차에 따른 판단을 보조하며, 최종 법률 판단·수사 판단·공식 업무 결정을 대체하지 않습니다."
"""design.md ``MockDataset.legalSafetyNotice``의 정확한 문구(법률_안전_고지문, 요구사항 1.7)."""

INSTANCE_CAUTION_NOTICE_TEXT: Literal[
    "판례는 심급 및 절차 경과에 따라 결론이 달라질 수 있으므로, 상급심 판단과 확정 여부를 함께 확인해야 합니다."
] = "판례는 심급 및 절차 경과에 따라 결론이 달라질 수 있으므로, 상급심 판단과 확정 여부를 함께 확인해야 합니다."
"""design.md ``MockDataset.instanceCautionNotice``의 정확한 문구(요구사항 12.4, task 1.2)."""

NO_REALTIME_SYNC_LABEL_TEXT: Literal["실시간 판례·법령 동기화 없음"] = "실시간 판례·법령 동기화 없음"
"""design.md ``MockDataset.noRealtimeSyncLabel``의 정확한 문구(요구사항 1.8)."""

TARGET_COVERAGE_LABEL_TEXT: TargetCoverageLabel = "공개적으로 확인 가능한 제1심·항소심·상고심 판례"
IMPLEMENTED_COVERAGE_LABEL_TEXT: ImplementedCoverageLabel = "사전에 정의된 목업 전체 심급 판례 샘플"


@dataclass(frozen=True)
class MockDataset:
    """서버 배포물에 번들되는 전체 목업 데이터셋. design.md Data Models 1절 ``MockDataset``.

    이 dataclass 자체는 신뢰되지 않은 구조다. 화면 값의 근거로 쓰기 전에 항상
    ``DatasetValidator``(task 2.x)의 구조·교차 참조 검증을 통과해 ``ValidatedDataset``으로
    변환해야 한다.
    """

    schema_version: str
    dataset_id: DatasetId
    dataset_version: str
    normalization_version: str
    as_of_date: IsoDate
    target_coverage_label: TargetCoverageLabel
    implemented_coverage_label: ImplementedCoverageLabel
    legal_safety_notice: str
    instance_caution_notice: str
    no_realtime_sync_label: str
    scenarios: Tuple[ScenarioDefinition, ...]
    queries: Tuple[QueryFixture, ...]
    term_mappings: Tuple[LegalTermMapping, ...]
    cases: Tuple[CaseRecord, ...]
    statutes: Tuple[StatuteRecord, ...]
    statute_versions: Tuple[StatuteVersion, ...]
    sources: Tuple[SourceRecord, ...]
    response_templates: Tuple[ResponseTemplate, ...]
    review_fixtures: Tuple[SelectionReviewFixture, ...]
    voice_fixtures: Tuple[VoiceFixture, ...]
    display_policies: MockDisplayPolicies
