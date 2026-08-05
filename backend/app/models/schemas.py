"""
API 요청/응답 스키마 (pydantic).
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 공통
# ---------------------------------------------------------------------------

class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


# ---------------------------------------------------------------------------
# Part 1: 대화형 절차 보완 (Interactive Feedback Loop)
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """대화 이력을 받아 정보 충분성을 판단합니다."""
    history: list[ChatTurn] = Field(
        ..., description="현재까지의 대화 이력 (가장 최근 사용자 발화 포함)"
    )


class ChatResponse(BaseModel):
    sufficient: bool = Field(..., description="법적 적법성 판단에 필요한 정보가 충분한지 여부")
    follow_up_question: Optional[str] = Field(
        None, description="정보가 부족할 때 추가로 물어볼 질문"
    )
    missing_points: list[str] = Field(
        default_factory=list, description="부족하다고 판단된 확인 항목 목록"
    )
    situation_summary: Optional[str] = Field(
        None, description="정보가 충분할 때, 지금까지의 대화를 정리한 상황 요약(사실관계)"
    )
    category: Optional[str] = Field(
        None, description="정보가 충분할 때 추정되는 공무집행 시나리오 카테고리"
    )


# ---------------------------------------------------------------------------
# Part 2: 판례 검색 (RAG)
# ---------------------------------------------------------------------------

class PrecedentHit(BaseModel):
    id: str
    title: str
    case_no: str
    date: str
    court: str
    category: str
    is_lawful_example: Optional[bool] = Field(
        None, description="적법 사례(True)/위법 사례(False)/미분류(None)"
    )
    similarity: float = Field(..., description="사용자 상황과의 유사도 (0~100 %)")
    summary_snippet: str = Field("", description="판시사항/판결요지 일부 미리보기")
    source_path: str = ""


class SearchRequest(BaseModel):
    query: str = Field(..., description="검색할 상황 설명 또는 키워드")
    category: Optional[str] = Field(None, description="공무집행 시나리오 카테고리 필터")
    top_k: int = Field(5, ge=1, le=20)


class SearchResponse(BaseModel):
    query: str
    normalized_query: str = Field("", description="법률 용어로 보정된 질의")
    results: list[PrecedentHit]


# ---------------------------------------------------------------------------
# Part 3: AI 분석 및 요약 (3단계 구조화 요약 + 리스크 + 타임라인)
# ---------------------------------------------------------------------------

class ThreeTierSummary(BaseModel):
    three_line: str = Field(..., description="3줄 요약: 결론 + 핵심 기준")
    ten_line: str = Field(..., description="10줄 요약: 사실관계 + 판단 근거")
    full_text: str = Field(..., description="판결문 전문 또는 종합 전문 요약")


class RiskBadge(BaseModel):
    type: Literal["국가배상", "직권남용", "법령개정", "절차위반", "기타"]
    level: Literal["low", "medium", "high"]
    description: str


class FactDiff(BaseModel):
    point: str = Field(..., description="비교 대상이 되는 사실관계 항목")
    user_situation: str
    precedent_fact: str
    is_critical: bool = Field(
        ..., description="결론에 영향을 줄 수 있는 핵심 차이인지 여부"
    )


class TimelineEvent(BaseModel):
    order: int
    timestamp_label: str = Field(
        ..., description="상대적/절대적 시점 표기 (예: '최초 신고 시', '10:32경')"
    )
    description: str
    legal_issue: Optional[str] = Field(
        None, description="해당 시점에서 문제되는 법적 쟁점"
    )


class LegalityVerdict(BaseModel):
    verdict: Literal["적법", "위법 가능성 높음", "위법 가능성 있음", "판단 보류"]
    reasoning: str
    key_criteria: list[str] = Field(
        default_factory=list, description="판단에 사용된 핵심 기준"
    )


class AnalysisRequest(BaseModel):
    situation: str = Field(..., description="정리된 상황 설명 (사실관계)")
    category: Optional[str] = Field(None, description="공무집행 시나리오 카테고리")
    top_k: int = Field(5, ge=1, le=10)


class AnalysisResponse(BaseModel):
    situation: str
    category: str
    verdict: LegalityVerdict
    summary: ThreeTierSummary
    risk_badges: list[RiskBadge]
    similar_precedents: list[PrecedentHit]
    lawful_examples: list[PrecedentHit]
    unlawful_examples: list[PrecedentHit]
    fact_diffs: list[FactDiff]
    timeline: list[TimelineEvent]


class FactCheckRequest(BaseModel):
    """요약문 내 드래그한 텍스트에 대한 재검토/자세히 설명 요청."""
    situation: str
    selected_text: str
    mode: Literal["fact_check", "explain"]


class FactCheckResponse(BaseModel):
    result: str
