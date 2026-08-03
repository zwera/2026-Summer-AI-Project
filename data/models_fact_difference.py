"""핵심 사실관계 차이와 유사도 경고 projection 데이터 모델.

``design.md`` Data Models 8절의 ``FactDifference``, ``SimilarityWarningProjection``을
정의한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from domain.ids import SourceId

from data.models_common import FactDimension, SimilarityWarningKey


@dataclass(frozen=True)
class FactDifference:
    """상황_질의와 판례 사이의 핵심_사실관계_차이 하나. design.md Data Models 8절.

    ``user_fact``·``case_fact``·``conclusion_impact``가 ``None``이면 화면에서 각각
    독립적으로 ``확인 필요``로 표시한다(요구사항 8.4~8.6). ``could_change_conclusion``이
    참이면 유사도 점수보다 앞선 경고 항목으로 배치한다(요구사항 8.10).
    """

    id: str
    dimension: FactDimension
    user_fact: Optional[str]
    case_fact: Optional[str]
    conclusion_impact: Optional[str]
    could_change_conclusion: bool
    display_priority: int
    source_ids: Tuple[SourceId, ...]


@dataclass(frozen=True)
class SimilarityWarningProjection:
    """유사도_점수 구간에 대응하는 경고 projection. design.md Data Models 8절."""

    policy_record_id: str
    key: SimilarityWarningKey
    text: str
