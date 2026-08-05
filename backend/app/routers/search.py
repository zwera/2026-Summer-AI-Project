"""
Part 1 + Part 2: 판례 검색(RAG) API.
"""
from fastapi import APIRouter

from app.models.schemas import SearchRequest, SearchResponse
from app.services.search_service import search_precedents

router = APIRouter()


@router.post("", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    normalized, hits = search_precedents(
        query=request.query,
        category=request.category,
        top_k=request.top_k,
    )
    return SearchResponse(
        query=request.query,
        normalized_query=normalized,
        results=hits,
    )
