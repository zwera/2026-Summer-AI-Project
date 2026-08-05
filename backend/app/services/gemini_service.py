"""
Gemini(2.5 Flash 기본값) 호출 서비스.

Part 1(대화형 절차 보완 충분성 판단), Part 3(적법성 분석/3단계 요약/리스크/타임라인/
판례 적법·위법 분류, 텍스트 드래그 Fact-Check/설명)에서 필요한 LLM 호출을 모두
이 모듈에서 담당한다. 구조화된 JSON 출력이 필요한 곳은 response_schema를 지정해
google-genai SDK가 pydantic 모델로 직접 파싱해주는 기능(response.parsed)을 사용한다.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import get_settings
from app.models.schemas import (
    ChatResponse,
    ChatTurn,
    FactDiff,
    LegalityVerdict,
    RiskBadge,
    ThreeTierSummary,
    TimelineEvent,
)
from app.taxonomy import JOB_CATEGORIES


@lru_cache
def get_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def _model_name() -> str:
    return get_settings().gemini_model


def _category_guide() -> str:
    lines = [f"- {c.key} ({c.label}): {c.description}" for c in JOB_CATEGORIES]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Part 1: 대화형 절차 보완 (정보 충분성 판단)
# ---------------------------------------------------------------------------

def judge_chat_sufficiency(history: list[ChatTurn]) -> ChatResponse:
    """대화 이력을 보고 적법성 판단에 필요한 정보가 충분한지 판단한다.

    부족하면 후속 질문을 생성하고, 충분하면 상황 요약과 카테고리를 함께 반환한다.
    """
    conversation_text = "\n".join(
        f"[{turn.role}] {turn.content}" for turn in history
    )

    prompt = f"""당신은 경찰관의 현장 대응이 법적으로 적법한지 검증하기 위해 사실관계를
확인하는 보조 도구입니다. 아래는 경찰관과의 대화 이력입니다.

=== 대화 이력 ===
{conversation_text}
=== 대화 이력 끝 ===

다음 공무집행 시나리오 카테고리 중 하나로 상황을 분류할 수 있는지도 함께 판단하세요:
{_category_guide()}

이 대화 이력만으로 "법적 적법성 판단"에 필요한 핵심 사실관계
(예: 현장 상황, 상대방의 행동, 경찰관이 취한 조치, 조치 전후 절차 이행 여부,
시간 순서 등)가 충분한지 판단하세요.

- 정보가 부족하면 sufficient=false로 하고, 가장 중요한 확인 질문 1개를
  follow_up_question에 담고, 부족한 항목들을 missing_points에 나열하세요.
- 정보가 충분하면 sufficient=true로 하고, 대화 내용을 3~6문장의 사실관계
  요약으로 situation_summary에 작성하고, category에 가장 적절한 카테고리
  key(예: field_control)를 넣으세요.
- 이미 2회 이상 후속 질문을 주고받았다면, 완벽하지 않아도 무리하게 질문을
  반복하지 말고 sufficient=true로 판단해 실무 진행을 우선하세요.
"""

    response = get_client().models.generate_content(
        model=_model_name(),
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ChatResponse,
            temperature=0.2,
        ),
    )
    result = response.parsed
    if isinstance(result, ChatResponse):
        return result
    return ChatResponse.model_validate(result)


# ---------------------------------------------------------------------------
# Part 3: 적법성 분석 + 3단계 요약 + 리스크 + Fact Diff + 타임라인 + 판례 분류
# ---------------------------------------------------------------------------

class PrecedentClassification(BaseModel):
    precedent_id: str = Field(
        ..., description="분류 대상 판례의 id (검색 결과에서 전달된 값과 동일)"
    )
    is_lawful_example: Optional[bool] = Field(
        None,
        description=(
            "해당 판례가 사용자 상황 대비 '적법 사례'(True)인지 "
            "'위법 사례'(False)인지. 판단 불가하면 null."
        ),
    )
    reason: str = Field(..., description="분류 근거 한 줄 요약")


class LLMAnalysisOutput(BaseModel):
    verdict: LegalityVerdict
    summary: ThreeTierSummary
    risk_badges: list[RiskBadge]
    fact_diffs: list[FactDiff]
    timeline: list[TimelineEvent]
    precedent_classifications: list[PrecedentClassification] = Field(
        default_factory=list
    )


class PrecedentContext(BaseModel):
    """analyze_situation에 전달할 검색된 판례 요약 컨텍스트."""
    id: str
    title: str
    case_no: str
    court: str
    date: str
    snippet: str


def analyze_situation(
    situation: str,
    category: str,
    precedents: list[PrecedentContext],
) -> LLMAnalysisOutput:
    """상황 설명 + 검색된 판례들을 근거로 적법성 분석 전체를 한 번에 생성한다."""
    precedent_block = "\n\n".join(
        f"[판례 id={p.id}] {p.title} ({p.case_no}, {p.court}, {p.date})\n"
        f"{p.snippet}"
        for p in precedents
    ) or "(검색된 관련 판례 없음)"

    prompt = f"""당신은 경찰관 공무집행의 적법성을 검토하는 법률 보조 AI입니다.
아래 "현장 상황"과 "관련 판례"를 근거로 적법성을 분석하세요.

=== 현장 상황 (카테고리: {category}) ===
{situation}

=== 관련 판례 (벡터 검색 결과) ===
{precedent_block}

다음을 모두 작성하세요:

1. verdict: 적법/위법 가능성에 대한 결론(적법, 위법 가능성 높음, 위법 가능성 있음,
   판단 보류 중 하나)과 그 근거(reasoning), 판단에 사용한 핵심 기준(key_criteria).
   상급심에서 결론이 달라질 수 있음을 감안해 신중하게 판단하세요.

2. summary (3단계 실무 언어 구조화 요약):
   - three_line: 현장에서 즉시 확인 가능한 3줄 요약 (결론 + 핵심 기준)
   - ten_line: 보고서 작성용 10줄 내외 요약 (사실관계 + 판단 근거)
   - full_text: 사건 개요/법원 판단/현장 참고 핵심 포인트를 포함한 상세 설명
     (실제 판결문이 아니라 종합 분석 전문)

3. risk_badges: 국가배상, 직권남용, 법령개정, 절차위반 등 리스크 요소를
   type/level(low/medium/high)/description으로 나열. 리스크가 없으면 빈 배열.

4. fact_diffs: 현장 상황과 관련 판례들의 사실관계 차이점을 point/user_situation/
   precedent_fact/is_critical로 나열. 결론에 영향을 주는 핵심 차이는
   is_critical=true로 표시.

5. timeline: 현장 상황을 시간 순서대로 재구성한 사건 진행 목록. order(1부터),
   timestamp_label(상대적/절대적 시점 표기), description, 그 시점에 문제되는
   legal_issue(없으면 null).

6. precedent_classifications: 위에 제시된 각 판례 id에 대해, 그 판례가 현재
   상황과 비교했을 때 "적법 사례"(경찰 조치가 적법하다고 인정된 사례)인지
   "위법 사례"(위법하다고 판단된 사례)인지 is_lawful_example로 분류하고
   reason에 한 줄 근거를 쓰세요. 판례가 없으면 빈 배열.
"""

    response = get_client().models.generate_content(
        model=_model_name(),
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMAnalysisOutput,
            temperature=0.3,
        ),
    )
    result = response.parsed
    if isinstance(result, LLMAnalysisOutput):
        return result
    return LLMAnalysisOutput.model_validate(result)


# ---------------------------------------------------------------------------
# Part 3: Contextual AI 인터랙션 (텍스트 드래그 재검토/자세히 설명)
# ---------------------------------------------------------------------------

def fact_check_or_explain(
    situation: str, selected_text: str, mode: Literal["fact_check", "explain"]
) -> str:
    if mode == "fact_check":
        instruction = (
            "선택된 문장이 위 상황 설명 및 일반적인 법리에 비추어 사실과 맞는지, "
            "과장되거나 근거가 부족한 부분은 없는지 재검토하세요. "
            "문제가 없다면 그렇다고 명시하고, 문제가 있다면 구체적으로 지적하세요."
        )
    else:
        instruction = (
            "선택된 문장에 사용된 법률 용어나 판단 기준을 현장 경찰관이 이해하기 쉽게 "
            "구체적인 예시를 들어 자세히 설명하세요."
        )

    prompt = f"""당신은 경찰관 공무집행 적법성 분석 결과를 보조 설명하는 AI입니다.

=== 전체 상황/분석 컨텍스트 ===
{situation}

=== 사용자가 드래그하여 선택한 문장 ===
"{selected_text}"

{instruction}
3~6문장 내로 간결하게 답하세요.
"""

    response = get_client().models.generate_content(
        model=_model_name(),
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3),
    )
    return response.text or ""
