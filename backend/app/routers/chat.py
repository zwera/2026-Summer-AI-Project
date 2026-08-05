"""
Part 1: 대화형 절차 보완 (Interactive Feedback Loop) API.
"""
from fastapi import APIRouter

from app.models.schemas import ChatRequest, ChatResponse
from app.services.gemini_service import judge_chat_sufficiency

router = APIRouter()


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """대화 이력을 보고 적법성 판단에 필요한 정보가 충분한지 판단한다.

    부족하면 follow_up_question을 반환해 클라이언트가 추가 질문을 사용자에게
    보여주고, 충분하면 situation_summary/category를 반환해 분석(Part 3) 요청에
    바로 사용할 수 있도록 한다.
    """
    return judge_chat_sufficiency(request.history)
