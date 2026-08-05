"""
Part 3: AI 분석 및 요약·시각화 모듈 API.

판례 검색(RAG) 결과를 근거로 Gemini에게 적법성 분석/3단계 요약/리스크/
Fact Diff/타임라인/판례 적법·위법 분류를 한 번에 생성하게 하고, 결과를
프론트엔드가 바로 렌더링할 수 있는 형태로 조립한다.
"""
from fastapi import APIRouter

from app.models.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    FactCheckRequest,
    FactCheckResponse,
    PrecedentHit,
)
from app.services.gemini_service import (
    PrecedentContext,
    analyze_situation,
    fact_check_or_explain,
)
from app.services.search_service import search_precedents
from app.taxonomy import category_by_key

router = APIRouter()


@router.post("", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    category_key = request.category
    if not category_key or category_by_key(category_key) is None:
        category_key = "uncategorized"

    _, hits = search_precedents(
        query=request.situation, category=None, top_k=request.top_k
    )

    contexts = [
        PrecedentContext(
            id=hit.id,
            title=hit.title,
            case_no=hit.case_no,
            court=hit.court,
            date=hit.date,
            snippet=hit.summary_snippet,
        )
        for hit in hits
    ]

    llm_result = analyze_situation(
        situation=request.situation, category=category_key, precedents=contexts
    )

    classification_by_id = {
        c.precedent_id: c.is_lawful_example
        for c in llm_result.precedent_classifications
    }

    hits_by_id: dict[str, PrecedentHit] = {}
    for hit in hits:
        classified = classification_by_id.get(hit.id, hit.is_lawful_example)
        hits_by_id[hit.id] = hit.model_copy(
            update={"is_lawful_example": classified}
        )

    similar_precedents = list(hits_by_id.values())
    lawful_examples = [
        h for h in similar_precedents if h.is_lawful_example is True
    ]
    unlawful_examples = [
        h for h in similar_precedents if h.is_lawful_example is False
    ]

    return AnalysisResponse(
        situation=request.situation,
        category=category_key,
        verdict=llm_result.verdict,
        summary=llm_result.summary,
        risk_badges=llm_result.risk_badges,
        similar_precedents=similar_precedents,
        lawful_examples=lawful_examples,
        unlawful_examples=unlawful_examples,
        fact_diffs=llm_result.fact_diffs,
        timeline=llm_result.timeline,
    )


@router.post("/fact-check", response_model=FactCheckResponse)
def fact_check(request: FactCheckRequest) -> FactCheckResponse:
    """요약문 내 드래그한 텍스트에 대한 재검토(Fact-Check)/자세히 설명."""
    result = fact_check_or_explain(
        situation=request.situation,
        selected_text=request.selected_text,
        mode=request.mode,
    )
    return FactCheckResponse(result=result)
