/* 실제 RAG(Gemini + Chroma) 연동 스크립트.
 *
 * 이 파일은 목업 시연 흐름(app.js)과 완전히 분리되어 있으며, 별도로 실행 중인
 * FastAPI 서버(rag/api.py, 기본 http://127.0.0.1:8001)를 외부 origin으로 호출한다.
 * 목업 계층의 "외부 origin 호출 0건" 요구사항(app.js 전용 정적 분석 테스트,
 * tests/test_integration_e2e_external_origin.py)을 지키기 위해, 실제 원격 호출은
 * 반드시 이 파일에만 두고 app.js에는 절대 추가하지 않는다.
 *
 * 사용자가 "실제 AI(Gemini) 분석도 함께 요청" 체크박스를 선택하지 않으면 이 스크립트는
 * 아무 네트워크 호출도 하지 않는다(opt-in). RAG 서버가 꺼져 있거나 오류를 반환해도
 * 목업 흐름(판단 근거 확인 등)은 전혀 영향을 받지 않는다.
 */
(() => {
  "use strict";
  // 기본값은 로컬 개발 환경에서 `uvicorn rag.api:app --port 8001`로 실행한 서버를 가정한다.
  // 다른 호스트/포트에서 실행 중이면 window.POLICE_BOT_RAG_BASE_URL을 설정해 덮어쓸 수 있다.
  const RAG_BASE_URL = window.POLICE_BOT_RAG_BASE_URL || "http://127.0.0.1:8001";

  const toggle = document.querySelector("#real-rag-toggle");
  const panel = document.querySelector("#real-rag-panel");
  const queryInput = document.querySelector("#situation-query");
  if (!toggle || !panel || !queryInput) return;

  const node = (tag, text) => { const value = document.createElement(tag); if (text !== undefined) value.textContent = text; return value; };

  const renderLoading = () => {
    panel.hidden = false;
    panel.replaceChildren(node("p", "실제 AI(Gemini) 분석 중입니다. 검색과 리포트 생성에 몇 초에서 수십 초가 걸릴 수 있습니다."));
  };

  const renderError = (message) => {
    panel.hidden = false;
    const box = document.createElement("section");
    box.className = "real-rag-panel__error";
    box.setAttribute("role", "alert");
    box.append(node("h3", "실제 AI 분석을 완료할 수 없습니다"), node("p", message));
    panel.replaceChildren(box);
  };

  const renderHits = (hits) => {
    const section = document.createElement("section");
    section.className = "real-rag-panel__hits";
    section.append(node("h4", "실제 검색된 판례·법령 발췌"));
    if (!hits.length) { section.append(node("p", "관련 발췌를 찾지 못했습니다.")); return section; }
    hits.forEach((hit) => {
      const item = document.createElement("article");
      item.className = "real-rag-hit";
      const label = hit.doc_type === "PRECEDENT"
        ? `판례 · ${hit.metadata.case_number || hit.doc_id} · ${hit.metadata.court_name || ""}`
        : `법령 · ${hit.metadata.title || hit.doc_id} · ${hit.metadata.article || ""}`;
      item.append(node("h5", label));
      const excerpt = node("p", hit.text.length > 300 ? `${hit.text.slice(0, 300)}...` : hit.text);
      excerpt.className = "real-rag-hit__excerpt";
      item.append(excerpt);
      section.append(item);
    });
    return section;
  };

  const renderReport = (report) => {
    const section = document.createElement("section");
    section.className = "real-rag-panel__report";
    section.append(node("h4", "AI 적법성 분석 리포트"));
    const assessment = node("p", `종합 평가: ${report.overall_assessment}`);
    const assessmentKey = report.overall_assessment.replace(/\s+/g, "_");
    assessment.className = `real-rag-assessment real-rag-assessment--${assessmentKey}`;
    section.append(assessment);
    if (report.key_risks.length) {
      section.append(node("h5", "핵심 리스크"));
      const list = document.createElement("ul");
      report.key_risks.forEach((risk) => list.append(node("li", risk)));
      section.append(list);
    }
    section.append(node("h5", "근거 설명"), node("p", report.reasoning));
    if (report.cited_precedents.length) {
      section.append(node("h5", "근거 판례"));
      const list = document.createElement("ul");
      report.cited_precedents.forEach((item) => list.append(node("li", `${item.case_number} (${item.court_name}) - ${item.relevance_summary}`)));
      section.append(list);
    }
    if (report.timeline.length) {
      section.append(node("h5", "AI가 추출한 타임라인"));
      const list = document.createElement("ul");
      report.timeline.forEach((event) => {
        const text = event.procedural_note ? `${event.time_label} - ${event.action} (${event.procedural_note})` : `${event.time_label} - ${event.action}`;
        list.append(node("li", text));
      });
      section.append(list);
    }
    return section;
  };

  const renderResult = (payload) => {
    panel.hidden = false;
    panel.replaceChildren();
    const disclaimer = node("p", "이 결과는 실제 Gemini AI와 판례·법령 데이터로 생성되었습니다. 최종 법률 판단은 관계 법령과 담당자 검토가 필요합니다.");
    disclaimer.className = "real-rag-panel__disclaimer";
    panel.append(disclaimer);
    panel.append(renderHits(payload.hits));
    if (payload.report) panel.append(renderReport(payload.report));
  };

  const runQuery = async (queryText) => {
    if (!toggle.checked || !queryText.trim()) return;
    renderLoading();
    try {
      const response = await fetch(`${RAG_BASE_URL}/api/rag/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: queryText, top_k: 8, include_report: true }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        renderError(body.detail || `서버 오류 (상태: ${response.status})`);
        return;
      }
      renderResult(body);
    } catch (_) {
      renderError(
        "실제 RAG 서버에 연결할 수 없습니다. 로컬에서 'uvicorn rag.api:app --port 8001'로 서버가 실행 중인지 확인해 주세요."
      );
    }
  };

  document.addEventListener("workflow:query-submitted", () => { runQuery(queryInput.value); });
})();
