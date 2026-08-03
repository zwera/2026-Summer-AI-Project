"""질의 fixture 데이터 모델.

``design.md`` Data Models 2절의 ``QueryFixture``, ``QueryVariant``와 관련 타입을 정의한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from domain.enums import PoliceScenario
from domain.ids import CaseId, QueryId, StatuteVersionId

from data.models_common import FactDimension, InputMode, RelationGraph
from data.models_timeline import RecognizedEvent


@dataclass(frozen=True)
class QueryVariant:
    """지원 질의의 자연어 변형 하나. design.md Data Models 2절 ``QueryVariant``."""

    id: str
    raw_example: str
    """design.md ``rawExample``."""
    normalized_key: str
    """design.md ``normalizedKey``. ``normalizeForFixtureMatch`` 결과와 정확히 대조되는 키."""
    input_mode: InputMode
    relation_graph: RelationGraph
    explicit_time_core_facts: Tuple[str, ...] = ()
    """design.md ``explicitTimeCoreFacts``."""


@dataclass(frozen=True)
class QueryMatch:
    """``QueryFixture.match``. 목업 검색이 조회할 판례/법조문/응답 template ID."""

    case_ids: Tuple[CaseId, ...]
    statute_version_ids: Tuple[StatuteVersionId, ...]
    response_template_id: str


@dataclass(frozen=True)
class SimilarityPreset:
    """query-case 쌍에 저장된 목업 유사도 값. design.md Data Models 3절 ``SimilarityPreset``.

    재계산하지 않는 사전 정의 값이며, 검색 우선순위와 동순위 정렬 키도 함께 담는다.
    """

    score: float
    search_priority: int
    tie_order: int
    similarity_factors: Tuple[str, ...]
    recency_factors: Tuple[str, ...]


@dataclass(frozen=True)
class QueryFixture:
    """지원_목업_질의 하나. design.md Data Models 2절 ``QueryFixture``."""

    id: QueryId
    scenario_ids: Tuple[PoliceScenario, ...]
    core_fact_set_id: str
    """design.md ``coreFactSetId``. 같은 값을 가진 변형은 같은 match/유사도를 가져야 한다."""
    variants: Tuple[QueryVariant, ...]
    term_mapping_ids: Tuple[str, ...]
    canonical_relations: RelationGraph
    match: QueryMatch
    recognized_events: Tuple[RecognizedEvent, ...]
    fact_values: Mapping[FactDimension, Optional[str]]
    """design.md ``factValues``. ``Record<FactDimension, string | null>``에 대응."""
    similarity_by_case: Mapping[CaseId, SimilarityPreset]
    """design.md ``similarityByCase``."""
