"""출처·앵커·인용·응답 template 데이터 모델.

``design.md`` Data Models 5절의 ``SourceRecord``, ``SourceAnchor``, ``ResponseTemplate``,
``ResponseBlock``, ``ClaimEvidenceLink``를 정의한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple, Union

from domain.ids import CaseId, ClaimId, SourceId, StatuteVersionId

from data.models_common import (
    ClaimEvidenceCoverage,
    ClaimEvidencePurpose,
    ClaimEvidenceRelation,
    SourceAnchorId,
    SourceKind,
    SourceOwnerType,
)


@dataclass(frozen=True)
class SourceOwner:
    """``SourceRecord.owner``. 출처가 속한 판례 또는 법조문 버전을 가리킨다."""

    type: SourceOwnerType
    id: Union[CaseId, StatuteVersionId]


@dataclass(frozen=True)
class SourceAnchor:
    """전문 본문 안의 근거 구절 위치. design.md Data Models 5절 ``SourceAnchor``.

    ``excerpt_checksum``은 빌드 시 ``body[start_offset:end_offset]``의 해시와 일치해야
    하며, 원문 수정 후 오래된 offset이 다른 구절을 가리키는 것을 검증기가 차단한다.
    """

    id: SourceAnchorId
    start_offset: int
    end_offset: int
    excerpt_checksum: str


@dataclass(frozen=True)
class SourceRecord:
    """판례 전문 발췌 또는 법조문 원문 레코드. design.md Data Models 5절 ``SourceRecord``."""

    id: SourceId
    owner: SourceOwner
    title: str
    source_kind: SourceKind
    body: str
    anchors: Tuple[SourceAnchor, ...]


@dataclass(frozen=True)
class ClaimEvidenceLink:
    """법률 주장(claim)과 출처의 관계. design.md Data Models 5절 ``ClaimEvidenceLink``."""

    source_id: SourceId
    anchor_id: SourceAnchorId
    purpose: ClaimEvidencePurpose
    relation: ClaimEvidenceRelation
    coverage: ClaimEvidenceCoverage


@dataclass(frozen=True)
class TextBlock:
    """``ResponseBlock`` 중 ``TEXT`` 변형. 고정 안내·연결 문구를 담는다."""

    type: Literal["TEXT"]
    text: str


@dataclass(frozen=True)
class LegalClaimBlock:
    """``ResponseBlock`` 중 ``LEGAL_CLAIM`` 변형. 근거를 갖는 법률 주장 블록."""

    type: Literal["LEGAL_CLAIM"]
    claim_id: ClaimId
    text: str
    citation_links: Tuple[ClaimEvidenceLink, ...]


ResponseBlock = Union[TextBlock, LegalClaimBlock]
"""design.md Data Models 5절 ``ResponseBlock`` 판별 유니온."""


@dataclass(frozen=True)
class ResponseTemplate:
    """목업 응답 조립에 쓰이는 사전 정의 블록 묶음. design.md ``ResponseTemplate``."""

    id: str
    blocks: Tuple[ResponseBlock, ...]
