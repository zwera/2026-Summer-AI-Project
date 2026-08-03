"""법조문과 버전 데이터 모델.

``design.md`` Data Models 4절의 ``StatuteRecord``, ``StatuteVersion``,
``AppliedStatuteRef``를 정의한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from domain.ids import SourceId, StatuteVersionId

from data.models_common import IsoDate


@dataclass(frozen=True)
class StatuteVersion:
    """법조문의 특정 버전(개정 시점 기준). design.md Data Models 4절 ``StatuteVersion``."""

    id: StatuteVersionId
    statute_id: str
    article: str
    text_source_id: SourceId
    paragraph: Optional[str] = None
    item: Optional[str] = None
    revision_date: Optional[IsoDate] = None
    """design.md ``revisionDate``. 누락이면 화면에서 ``정보_없음``으로 표시한다(요구사항 10.3)."""
    effective_date: Optional[IsoDate] = None
    """design.md ``effectiveDate``. 누락이면 화면에서 ``정보_없음``으로 표시한다(요구사항 10.3)."""
    version_label: Optional[str] = None
    revision_summary: Optional[str] = None
    """design.md ``revisionSummary``. 구법_기준 판례에 연결되는 개정 설명(요구사항 10.10)."""


@dataclass(frozen=True)
class StatuteRecord:
    """하나의 법령. design.md Data Models 4절 ``StatuteRecord``."""

    id: str
    law_name: str
    version_ids: Tuple[StatuteVersionId, ...]
    current_version_id_at_as_of: Optional[StatuteVersionId] = None
    """design.md ``currentVersionIdAtAsOf``. 데이터_기준일의 현행_법령 버전."""


@dataclass(frozen=True)
class AppliedStatuteRef:
    """판례가 인용한 법조문 참조. design.md Data Models 4절 ``AppliedStatuteRef``.

    ``statute_version_id`` 또는 ``source_id``가 없으면 법령_기준_상태 판정에서 판별불가
    처리 대상이 될 수 있다(요구사항 10.8).
    """

    citation_label: str
    statute_version_id: Optional[StatuteVersionId] = None
    source_id: Optional[SourceId] = None
