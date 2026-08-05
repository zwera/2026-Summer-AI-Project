"""검색 결과를 컨텍스트로 Gemini에게 적법성 분석 리포트와 타임라인을 생성시킨다.

``google-genai``의 구조화 출력(``response_mime_type="application/json"`` +
``response_schema``)을 사용해 자유 텍스트 대신 검증 가능한 JSON을 받는다.
"""
from __future__ import annotations

from typing import List, Literal, Optional, Sequence

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from rag.config import RagSettings
from rag.schemas import SearchHit

OverallAssessment = Literal["적법", "주의 요망", "위법 위험 높음"]


class CitedPrecedent(BaseModel):
    """리포트가 근거로 인용하는 판례 한 건."""

    case_number: str = Field(description="사건번호")
    court_name: str = Field(description="법원명")
    relevance_summary: str = Field(description="이 판례가 왜 관련 있는지에 대한 한두 문장 요약")


class TimelineEvent(BaseModel):
    """현장 대응 타임라인의 조치 항목 하나."""

    time_label: str = Field(description="시간 표기(예: '14:00' 또는 '시점 미상')")
    action: str = Field(description="해당 시점에 이루어진 조치 내용")
    procedural_note: Optional[str] = Field(
        default=None, description="절차 누락·주의사항이 있으면 기재, 없으면 null"
    )


class LegalityReport(BaseModel):
    """적법성 평가 리포트 전체 구조."""

    overall_assessment: OverallAssessment = Field(description="종합 평가: 적법 / 주의 요망 / 위법 위험 높음")
    key_risks: List[str] = Field(description="핵심 리스크·절차적 결함 목록(없으면 빈 배열)")
    reasoning: str = Field(description="종합 평가에 대한 근거 설명(3~6문장)")
    cited_precedents: List[CitedPrecedent] = Field(description="근거로 사용한 판례 목록")
    timeline: List[TimelineEvent] = Field(description="입력 상황에서 추출한 시간대별 조치 타임라인")


_SYSTEM_INSTRUCTION = (
    "당신은 대한민국 경찰관의 공무집행 적법성을 판례와 법령에 근거해 검토하는 보조 도구입니다. "
    "제공된 '검색된 판례/법령 발췌'만을 근거로 답변하고, 발췌에 없는 사실이나 법령을 지어내지 마세요. "
    "근거가 부족하면 그 사실을 reasoning에 명시하고 overall_assessment를 '주의 요망'으로 두세요. "
    "이 리포트는 실제 법률 자문이 아닌 시연/보조 도구이며, 최종 판단은 관계 법령과 담당자 검토가 필요합니다."
)


def _format_context(hits: Sequence[SearchHit]) -> str:
    lines = ["## 검색된 판례/법령 발췌"]
    for index, hit in enumerate(hits, start=1):
        label = hit.metadata.get("case_number") or hit.metadata.get("article") or hit.doc_id
        lines.append(f"### 발췌 {index} ({hit.doc_type}, {label})")
        lines.append(hit.text.strip())
        lines.append("")
    return "\n".join(lines)


def generate_report(
    settings: RagSettings,
    situation_text: str,
    hits: Sequence[SearchHit],
    *,
    client: Optional[genai.Client] = None,
) -> LegalityReport:
    """검색 결과(hits)를 컨텍스트로 적법성 리포트 + 타임라인을 생성한다."""
    active_client = client if client is not None else genai.Client(api_key=settings.gemini_api_key)
    context_text = _format_context(hits)
    prompt = (
        f"## 현장 상황 입력\n{situation_text.strip()}\n\n"
        f"{context_text}\n\n"
        "위 발췌를 근거로 이 현장 대응의 적법성 평가 리포트와 시간대별 타임라인을 JSON으로 작성하세요."
    )
    response = active_client.models.generate_content(
        model=settings.generation_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=LegalityReport,
            temperature=0.2,
        ),
    )
    return LegalityReport.model_validate_json(response.text)
