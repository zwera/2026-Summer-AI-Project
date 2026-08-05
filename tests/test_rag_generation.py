"""rag.generation(리포트 생성)에 대한 단위 테스트.

실제 Gemini API를 호출하지 않고, ``genai.Client``와 동일한 표면(``models.generate_content``)을
갖는 가짜 클라이언트를 주입해 프롬프트 조립과 응답 파싱만 검증한다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from rag.config import RagSettings
from rag.generation import LegalityReport, _format_context, generate_report
from rag.schemas import SearchHit

_VALID_REPORT_JSON = json.dumps(
    {
        "overall_assessment": "주의 요망",
        "key_risks": ["미란다 원칙 고지 시점이 늦었을 가능성"],
        "reasoning": "발췌 1에 따르면 절차상 문제가 있을 수 있습니다.",
        "cited_precedents": [
            {"case_number": "2019고단4541", "court_name": "수원지법안산지원", "relevance_summary": "유사 사실관계"}
        ],
        "timeline": [
            {"time_label": "14:00", "action": "현장 출동", "procedural_note": None},
        ],
    },
    ensure_ascii=False,
)


@dataclass
class _FakeResponse:
    text: str


class _FakeModels:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.last_call_kwargs: Dict[str, Any] = {}

    def generate_content(self, **kwargs: Any) -> _FakeResponse:
        self.last_call_kwargs = kwargs
        return _FakeResponse(text=self._response_text)


class _FakeClient:
    def __init__(self, response_text: str) -> None:
        self.models = _FakeModels(response_text)


def _settings() -> RagSettings:
    return RagSettings(
        gemini_api_key="fake-key-not-used",
        chroma_path=Path("unused"),
        precedent_root=Path("unused"),
        statute_root=Path("unused"),
    )


def _sample_hit() -> SearchHit:
    return SearchHit(
        chunk_id="precedent:a.md#s0-0",
        doc_id="precedent:a.md",
        doc_type="PRECEDENT",
        text="판시사항 발췌 본문",
        metadata={"case_number": "2019고단4541", "court_name": "수원지법안산지원"},
        distance=0.05,
    )


def test_generate_report_parses_valid_json_into_legality_report() -> None:
    fake_client = _FakeClient(_VALID_REPORT_JSON)
    report = generate_report(_settings(), "새벽 집회 신고", [_sample_hit()], client=fake_client)

    assert isinstance(report, LegalityReport)
    assert report.overall_assessment == "주의 요망"
    assert report.cited_precedents[0].case_number == "2019고단4541"
    assert report.timeline[0].time_label == "14:00"
    assert report.timeline[0].procedural_note is None


def test_generate_report_sends_situation_text_and_context_in_prompt() -> None:
    fake_client = _FakeClient(_VALID_REPORT_JSON)
    hit = _sample_hit()
    generate_report(_settings(), "새벽 집회 신고", [hit], client=fake_client)

    sent_contents = fake_client.models.last_call_kwargs["contents"]
    assert "새벽 집회 신고" in sent_contents
    assert hit.text in sent_contents
    assert hit.metadata["case_number"] in sent_contents


def test_generate_report_uses_configured_generation_model() -> None:
    fake_client = _FakeClient(_VALID_REPORT_JSON)
    settings = _settings()
    generate_report(settings, "질의", [_sample_hit()], client=fake_client)
    assert fake_client.models.last_call_kwargs["model"] == settings.generation_model


def test_format_context_includes_every_hit_label_and_text() -> None:
    hits = [_sample_hit()]
    context_text = _format_context(hits)
    assert "판시사항 발췌 본문" in context_text
    assert "2019고단4541" in context_text
