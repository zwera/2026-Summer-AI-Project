"""선택 영역 재검토 fixture 데이터 모델.

``design.md`` Data Models 9절의 ``SelectionReviewFixture``, ``ReviewableClaim``,
``SelectionExplanationFixture``, ``SelectionReviewResult``를 정의한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from domain.enums import EvidenceStatus
from domain.ids import ClaimId

from data.models_source import ClaimEvidenceLink


@dataclass(frozen=True)
class LegalTermExplanationEntry:
    """``SelectionExplanationFixture.legalTerms`` 항목."""

    term: str
    explanation: str


@dataclass(frozen=True)
class ReviewableClaim:
    """선택 재검토 대상이 되는 독립_주장. design.md Data Models 9절 ``ReviewableClaim``."""

    id: ClaimId
    text: str
    document_order: int
    evidence: Tuple[ClaimEvidenceLink, ...]


@dataclass(frozen=True)
class SelectionExplanationFixture:
    """``상세 설명`` 작업의 사전 정의 결과. design.md Data Models 9절."""

    claim_id: ClaimId
    legal_terms: Tuple[LegalTermExplanationEntry, ...]
    issues: Tuple[str, ...]
    additional_information_needed: Tuple[str, ...]
    context: Optional[str] = None


@dataclass(frozen=True)
class SelectionReviewFixture:
    """하나의 ``ResponseTemplate``에 대응하는 선택 재검토 fixture. design.md ``SelectionReviewFixture``."""

    response_template_id: str
    claims: Tuple[ReviewableClaim, ...]
    explanations: Tuple[SelectionExplanationFixture, ...]


@dataclass(frozen=True)
class ClaimReviewOutcome:
    """``SelectionReviewResult.claims`` 항목."""

    claim_id: ClaimId
    status: EvidenceStatus
    decision_evidence: Tuple[ClaimEvidenceLink, ...]
    reference_sources: Tuple[ClaimEvidenceLink, ...]


@dataclass(frozen=True)
class SelectionReviewResult:
    """선택_재검토 실행 결과. design.md Data Models 9절 ``SelectionReviewResult``."""

    selected_text: str
    claims: Tuple[ClaimReviewOutcome, ...]
