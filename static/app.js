/* Session-scoped screen state recovery (no persistent storage).
 * All state lives only in window.sessionStorage, which the browser already scopes to
 * one tab/window for the lifetime of the browsing session (never written to disk,
 * never sent to a server). If sessionStorage is unavailable (disabled, private-mode
 * restrictions, quota errors) or the state needed to restore the current screen is
 * missing, callers fall back to the entry screen and the fixed notice text below.
 */
const PoliceBotSessionState = (() => {
  "use strict";
  const STORAGE_KEY = "policeBotScreenState_v1";
  const RESET_NOTICE_TEXT = "임시 화면 상태가 초기화되었습니다.";

  const readState = () => {
    try {
      const raw = window.sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_) {
      return null;
    }
  };
  const writeState = (patch) => {
    try {
      const current = readState() || {};
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ ...current, ...patch }));
      return true;
    } catch (_) {
      return false;
    }
  };
  const clearState = () => { try { window.sessionStorage.removeItem(STORAGE_KEY); } catch (_) { /* ignore */ } };

  return { readState, writeState, clearState, RESET_NOTICE_TEXT };
})();

/* Safe error display (task 21.1): the browser shows the HTTP status, the
 * server's generalized message, and the retryable flag returned by the Python
 * web server without alteration, marks any incomplete mock-RAG stage as
 * `미완료`, and never fabricates a legal conclusion the server did not return
 * (requirements 13.13, 13.15, 18.11, 18.12). Public/legal/privacy notices and
 * entry-screen navigation always stay visible in the shared AppShell, and an
 * explicit entry-screen link is repeated next to every error panel.
 */
const PoliceBotErrorDisplay = (() => {
  "use strict";
  const STAGE_ORDER = [
    { code: "INPUT", label: "입력" },
    { code: "MOCK_SEARCH", label: "목업_검색" },
    { code: "EVIDENCE", label: "근거_제시" },
    { code: "RESPONSE", label: "응답" },
  ];

  /* Structured error thrown by requestJson() for non-2xx HTTP responses, carrying
   * the server's own status/error contract unmodified. */
  class SafeHttpError extends Error {
    constructor(status, errorBody) {
      super("safe_http_error");
      this.status = status;
      this.error = errorBody;
    }
  }

  const requestJson = async (path, payload) => {
    const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new SafeHttpError(`${response.status} ${response.statusText}`.trim(), body.error || null);
    return body;
  };

  const node = (tag, text) => { const value = document.createElement(tag); value.textContent = text; return value; };

  const entryScreenLink = () => {
    const link = node("a", "진입 화면으로 이동");
    link.href = "/";
    link.className = "error-panel__entry-link";
    return link;
  };

  const stageList = (failedStage) => {
    const list = document.createElement("ul");
    list.className = "error-panel__stages";
    const failedIndex = STAGE_ORDER.findIndex((stage) => stage.code === failedStage);
    STAGE_ORDER.forEach((stage, index) => {
      const item = document.createElement("li");
      const status = failedIndex === -1 ? "" : index < failedIndex ? "완료" : index === failedIndex ? "실패" : "미완료";
      item.textContent = status ? `${stage.label}: ${status}` : stage.label;
      list.append(item);
    });
    return list;
  };

  /* Render a full safe-error panel for an HTTP-level SafeHttpError (400/404/405/
   * 415/500/503). Shows the server status, message, and retryable flag exactly
   * as returned; never displays a substitute legal conclusion. */
  const renderHttpError = (container, safeHttpError) => {
    container.replaceChildren();
    const panel = document.createElement("section");
    panel.className = "error-panel"; panel.setAttribute("role", "alert");
    panel.append(node("h2", "요청을 처리할 수 없습니다"));
    panel.append(node("p", `상태: ${safeHttpError.status}`));
    const errorInfo = safeHttpError.error;
    if (errorInfo) {
      panel.append(node("p", errorInfo.message));
      panel.append(node("p", errorInfo.retryable ? "재시도 가능" : "재시도 불가"));
    } else {
      panel.append(node("p", "요청을 처리할 수 없습니다."));
      panel.append(node("p", "재시도 불가"));
    }
    panel.append(entryScreenLink());
    container.append(panel);
  };

  /* Render an in-flow mock-RAG stage error (MockRagError/VoiceDemoError embedded
   * in a 200 OK response body): mark the failed stage and every later stage
   * `미완료`, and never fabricate a legal conclusion the server did not return. */
  const renderStageError = (container, stageError) => {
    container.replaceChildren();
    const panel = document.createElement("section");
    panel.className = "error-panel"; panel.setAttribute("role", "alert");
    panel.append(node("h2", "요청을 처리할 수 없습니다"));
    panel.append(node("p", stageError.code === "VOICE_FIXTURE_UNRECOGNIZED" ? "음성 인식 불가. 수동 텍스트 입력을 이용해 주세요." : "목업 데이터가 부족하여 목업_RAG 흐름을 완료할 수 없습니다."));
    panel.append(node("p", stageError.retryable ? "재시도 가능" : "재시도 불가"));
    panel.append(stageList(stageError.stage));
    panel.append(entryScreenLink());
    container.append(panel);
  };

  return { SafeHttpError, requestJson, renderHttpError, renderStageError };
})();

/* Query history log (session-scoped, no persistent storage): every submitted
 * situation query is appended to a capped in-session list rendered in the
 * "검색 기록" sidebar. Unlike the previous behavior, the entry screen never
 * auto-refills or auto-resubmits a past query on load — the screen always
 * starts clean, and a past query is only re-run when the user explicitly
 * clicks its history entry. */
const PoliceBotQueryHistory = (() => {
  "use strict";
  const STORAGE_KEY = "policeBotQueryHistory_v1";
  const MAX_ENTRIES = 20;

  const read = () => {
    try {
      const raw = window.sessionStorage.getItem(STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  };
  const append = (entry) => {
    try {
      const next = [entry, ...read()].slice(0, MAX_ENTRIES);
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    } catch (_) {
      return read();
    }
  };
  const clear = () => { try { window.sessionStorage.removeItem(STORAGE_KEY); } catch (_) { /* ignore */ } };

  return { read, append, clear };
})();

/* Same-origin UI interaction only: the Python server determines all legal results. */
(() => {
  "use strict";
  const form = document.querySelector("#situation-form");
  const queryInput = document.querySelector("#situation-query");
  const voiceSelect = document.querySelector("#voice-fixture");
  const voiceButton = document.querySelector("#voice-select-button");
  const feedback = document.querySelector("#query-feedback");
  const historyList = document.querySelector("#query-history-list");
  const lengthCounter = document.querySelector("#situation-length");
  const quickPickButtons = document.querySelectorAll(".quick-pick");
  if (!form || !queryInput || !voiceSelect || !voiceButton || !feedback) return;

  /* Character counter and quick-pick fill-in: purely presentational, no legal
   * interpretation happens on the client. Quick-pick buttons insert the exact
   * server-provided supported example phrase (fixtures/mock_dataset.py raw_example)
   * for the given scenario; they do not invent new wording. */
  const updateLengthCounter = () => { if (lengthCounter) lengthCounter.textContent = `${queryInput.value.length} / 500`; };
  queryInput.addEventListener("input", updateLengthCounter);
  updateLengthCounter();
  quickPickButtons.forEach((button) => {
    button.addEventListener("click", () => {
      queryInput.value = button.dataset.query || "";
      updateLengthCounter();
      queryInput.focus();
    });
  });

  let currentQueryId = null;
  const historyStatusLabel = { SUPPORTED: "인식됨", BLANK: "입력 없음", UNSUPPORTED: "미지원", INTERPRETATION_CHECK_NEEDED: "확인 필요" };
  const renderHistory = () => {
    if (!historyList) return;
    historyList.replaceChildren();
    PoliceBotQueryHistory.read().forEach((entry) => {
      const item = document.createElement("li"); item.className = "query-history__item";
      const button = document.createElement("button"); button.type = "button"; button.textContent = entry.query;
      const statusSpan = document.createElement("span");
      statusSpan.className = `query-history__status ${entry.kind === "SUPPORTED" ? "query-history__status--supported" : "query-history__status--other"}`;
      statusSpan.textContent = historyStatusLabel[entry.kind] || entry.kind;
      const time = document.createElement("time"); time.textContent = new Date(entry.timestamp).toLocaleTimeString();
      button.append(document.createElement("br"), statusSpan);
      button.addEventListener("click", () => {
        queryInput.value = entry.query;
        form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true }));
        queryInput.focus();
      });
      item.append(button, time);
      historyList.append(item);
    });
  };
  const recordHistory = (query, kind) => {
    if (!query || !query.trim()) return;
    PoliceBotQueryHistory.append({ query, kind, timestamp: new Date().toISOString() });
    renderHistory();
  };
  const clearHistoryButton = document.createElement("button");
  clearHistoryButton.type = "button"; clearHistoryButton.className = "query-history__clear"; clearHistoryButton.textContent = "기록 지우기";
  clearHistoryButton.addEventListener("click", () => { PoliceBotQueryHistory.clear(); renderHistory(); });
  if (historyList) historyList.insertAdjacentElement("afterend", clearHistoryButton);
  const request = PoliceBotErrorDisplay.requestJson;
  const element = (tag, text) => { const node = document.createElement(tag); node.textContent = text; return node; };
  const resetFeedback = () => { feedback.replaceChildren(); };
  const addField = (card, label, value) => { const row = element("p", ""); row.className = "result-card__field"; row.append(element("strong", `${label}: `), document.createTextNode(value)); card.append(row); };
  const renderEmpty = (heading) => { const section = document.createElement("section"); section.className = "empty-results"; section.append(element("h3", heading), element("p", "일치하는 목업 자료 없음")); return section; };

  const renderReview = (panel, payload) => {
    const output = panel.querySelector(".selection-review__output"); output.replaceChildren();
    if (payload.selection_pending) { output.append(element("p", "텍스트를 선택한 뒤 재검토 작업을 선택해 주세요.")); return; }
    if (payload.mode === "FACT_CHECK") {
      payload.result.claims.forEach((claim) => { const item = document.createElement("article"); item.className = "review-claim"; item.append(element("h4", `${claim.claim_id} · ${claim.status}`)); const decision = element("p", `결정 근거: ${claim.decision_evidence.length ? claim.decision_evidence.map((source) => source.source_id).join(", ") : "없음"}`); const reference = element("p", `참고 출처: ${claim.reference_sources.length ? claim.reference_sources.map((source) => source.source_id).join(", ") : "없음"}`); item.append(decision, reference); output.append(item); });
    } else payload.explanations.forEach((explanation) => { const item = document.createElement("article"); item.className = "review-claim"; item.append(element("h4", explanation.claim_id)); if (!explanation.found) item.append(element("p", explanation.not_found_text)); explanation.legal_terms.forEach((term) => item.append(element("p", `${term.term}: ${term.explanation}`))); if (explanation.context) item.append(element("p", `문맥: ${explanation.context}`)); if (explanation.issues.length) item.append(element("p", `판례 쟁점: ${explanation.issues.join(", ")}`)); if (explanation.additional_information_needed.length) item.append(element("p", `추가 필요 정보: ${explanation.additional_information_needed.join(", ")}`)); output.append(item); });
  };

  const renderResponse = (response) => {
    const section = document.createElement("section"); section.className = "mock-response"; section.setAttribute("aria-label", "목업 응답 선택 재검토"); section.append(element("h2", "목업 응답"));
    const text = document.createElement("div"); text.className = "mock-response__text";
    response.blocks.forEach((block) => { const paragraph = element("p", block.text); if (block.type === "LEGAL_CLAIM") { paragraph.className = "response-claim"; paragraph.dataset.claimId = block.claim_id; paragraph.tabIndex = 0; const button = element("button", "현재 문장 재검토"); button.type = "button"; button.className = "claim-review-trigger"; button.dataset.claimId = block.claim_id; paragraph.append(" ", button); const sourceContainer = document.createElement("div"); sourceContainer.className = "case-detail__sources citation-sources"; (block.citation_links || []).forEach((link) => { const citation = element("button", `출처 보기 (${link.source_id})`); citation.type = "button"; citation.className = "citation-link"; citation.addEventListener("click", () => showCitationSource(link.source_id, link.anchor_id, sourceContainer, paragraph)); paragraph.append(" ", citation); }); text.append(paragraph); if ((block.citation_links || []).length) text.append(sourceContainer); return; } text.append(paragraph); });
    const panel = document.createElement("section"); panel.className = "selection-review"; panel.hidden = true; panel.append(element("h3", "선택 영역 재검토")); const selected = element("p", ""); selected.className = "selection-review__selected"; const actions = document.createElement("div"); actions.className = "selection-review__actions"; const fact = element("button", "사실 확인 재검토"); fact.type = "button"; fact.dataset.mode = "FACT_CHECK"; const explain = element("button", "상세 설명"); explain.type = "button"; explain.dataset.mode = "EXPLANATION"; actions.append(fact, explain); const output = document.createElement("div"); output.className = "selection-review__output"; output.setAttribute("role", "status"); panel.append(selected, actions, output);
    let selection = { text: "", claimIds: [] };
    const setSelection = (next) => { selection = next; panel.hidden = false; selected.textContent = next.text ? `선택 문구: ${next.text}` : "선택한 텍스트가 없습니다."; output.replaceChildren(); };
    const captureSelection = () => { const range = window.getSelection(); const selectedText = range ? range.toString() : ""; const claimIds = range && range.rangeCount ? [...text.querySelectorAll(".response-claim")].filter((claim) => range.getRangeAt(0).intersectsNode(claim)).map((claim) => claim.dataset.claimId) : []; setSelection({ text: selectedText, claimIds }); };
    text.addEventListener("mouseup", captureSelection); text.addEventListener("keyup", captureSelection); text.addEventListener("contextmenu", (event) => { captureSelection(); if (selection.text.trim()) { event.preventDefault(); panel.querySelector("button")?.focus(); } });
    text.addEventListener("click", (event) => { const trigger = event.target.closest(".claim-review-trigger"); if (trigger) { const claim = trigger.closest(".response-claim"); setSelection({ text: claim.childNodes[0].textContent.trim(), claimIds: [trigger.dataset.claimId] }); fact.focus(); } });
    actions.addEventListener("click", async (event) => { const button = event.target.closest("button[data-mode]"); if (!button || !currentQueryId) return; output.textContent = "재검토 중입니다."; try { const payload = await request("/api/action", { type: "RUN_SELECTION_REVIEW", queryId: currentQueryId, selectedText: selection.text, selectedClaimIds: selection.claimIds, mode: button.dataset.mode }); renderReview(panel, payload); } catch (_) { output.textContent = "요청을 처리할 수 없습니다. 텍스트를 다시 선택해 주세요."; } });
    section.append(text, panel); feedback.append(section);
  };

  /* Full-text source viewers: shared between the case detail panel and inline citation links. */
  const sourceViewerCache = new Map();
  const buildSourceBody = (source) => {
    const body = document.createElement("div"); body.className = "source-body";
    const anchors = [...source.anchors].slice().sort((a, b) => a.start_offset - b.start_offset);
    let cursor = 0;
    anchors.forEach((anchor) => {
      if (anchor.start_offset > cursor) body.append(document.createTextNode(source.body.slice(cursor, anchor.start_offset)));
      const span = document.createElement("span"); span.className = "source-anchor"; span.dataset.anchorId = anchor.id; span.tabIndex = -1;
      span.textContent = source.body.slice(anchor.start_offset, anchor.end_offset); body.append(span);
      cursor = anchor.end_offset;
    });
    if (cursor < source.body.length) body.append(document.createTextNode(source.body.slice(cursor)));
    return body;
  };
  const buildSourceViewer = (source, openByDefault) => {
    const details = document.createElement("details"); details.className = "source-viewer"; details.dataset.sourceId = source.id; details.open = Boolean(openByDefault);
    details.append(element("summary", source.title), buildSourceBody(source));
    sourceViewerCache.set(source.id, details);
    return details;
  };
  const highlightAnchorAndReturn = (viewer, anchorId, returnTarget) => {
    viewer.open = true;
    const body = viewer.querySelector(".source-body");
    body.querySelectorAll(".source-anchor--highlight").forEach((span) => span.classList.remove("source-anchor--highlight"));
    const oldReturn = body.querySelector(".source-return"); if (oldReturn) oldReturn.remove();
    const target = body.querySelector(`.source-anchor[data-anchor-id="${CSS.escape(anchorId)}"]`);
    if (target) { target.classList.add("source-anchor--highlight"); target.scrollIntoView({ block: "center" }); target.focus(); }
    const returnButton = element("button", "돌아가기"); returnButton.type = "button"; returnButton.className = "source-return";
    returnButton.addEventListener("click", () => { returnTarget.scrollIntoView({ block: "center" }); returnTarget.focus(); });
    body.append(returnButton);
  };
  const showCitationSource = async (sourceId, anchorId, anchorContainer, returnTarget) => {
    let viewer = sourceViewerCache.get(sourceId);
    if (!viewer) {
      const payload = await request("/api/action", { type: "GET_SOURCE", sourceId });
      if (!payload.source) { const error = element("p", payload.source_error || "출처 데이터 오류"); error.className = "source-error"; anchorContainer.append(error); return; }
      viewer = buildSourceViewer(payload.source, false);
      anchorContainer.append(viewer);
    }
    highlightAnchorAndReturn(viewer, anchorId, returnTarget);
  };
  const renderFullTextSection = (caseId, container) => {
    container.replaceChildren(element("p", "전문을 불러오는 중입니다."));
    request("/api/action", { type: "GET_CASE_DETAIL", caseId }).then((payload) => {
      container.replaceChildren();
      if (payload.source_error) { const error = element("p", payload.source_error.display_text || "출처 데이터 오류"); error.className = "source-error"; container.append(error); }
      (payload.sources || []).forEach((source) => container.append(buildSourceViewer(source, false)));
      if (!payload.sources || !payload.sources.length) if (!payload.source_error) container.append(element("p", "전문 자료 없음"));
    }).catch(() => { container.replaceChildren(element("p", "전문을 불러올 수 없습니다.")); });
  };

  const renderCaseDetail = (detail, caseId) => { const panel = document.createElement("section"); panel.className = "case-detail"; panel.append(element("h5", "판례 상세")); const tabs = document.createElement("div"); tabs.className = "summary-tabs"; const body = document.createElement("div"); const showSummary = (level) => { const summary = detail.summaries[level]; body.replaceChildren(); (summary.lines.length ? summary.lines : summary.detailed_sections).forEach((line) => body.append(element("p", `${line.key}: ${line.text}`))); body.append(element("p", `법원 결론: ${summary.canonical_conclusion}`)); }; ["3줄_요약", "10줄_요약", "상세_요약"].forEach((level, index) => { const button = element("button", level); button.type = "button"; button.setAttribute("aria-selected", String(index === 0)); button.addEventListener("click", () => { [...tabs.children].forEach((tab) => tab.setAttribute("aria-selected", "false")); button.setAttribute("aria-selected", "true"); showSummary(level); }); tabs.append(button); }); showSummary("3줄_요약"); const summary = document.createElement("section"); summary.append(element("h6", "단계별 요약"), tabs, body); const risks = document.createElement("section"); risks.append(element("h6", "개인 책임 위험")); detail.risk_axes.forEach((axis) => risks.append(element("p", `${axis.label}: ${axis.status}`))); detail.action_badges.forEach((item) => { const badge = element("span", `${item.badge.state === "문제_행동" ? "⚠" : item.badge.state === "적법_행동" ? "✓" : "ⓘ"} ${item.badge.state}`); badge.className = `action-badge action-badge--${item.badge.state}`; risks.append(element("p", item.action_text + " "), badge); }); const differences = document.createElement("section"); differences.append(element("h6", "유사도·핵심 사실 차이"), Object.assign(element("p", detail.similarity_warning.text), { className: "result-card__warning" })); detail.fact_differences.forEach((item) => differences.append(element("p", `${item.dimension}: 사용자 사실 ${item.user_fact} / 판례 사실 ${item.case_fact} / 결론 영향 ${item.conclusion_impact}`))); const law = document.createElement("section"); law.append(element("h6", "법령 상태"), element("p", `법령 기준: ${detail.law_basis_status}`), element("p", "판례와 법령의 최신성은 데이터 기준일에 고정된 목업 정보입니다.")); detail.statutes.forEach((item) => law.append(element("p", `${item.citation_label} · 개정일 ${item.revision_date} · 시행일 ${item.effective_date}`))); if (detail.old_law) detail.old_law.revision_summaries.forEach((value) => law.append(element("p", `개정 내용: ${value}`))); const appeal = document.createElement("section"); appeal.append(element("h6", "상급심·확정 정보")); if (detail.appeal.appellate.state === "정보_없음") appeal.append(element("p", "상급심 정보: 정보_없음")); else detail.appeal.appellate.decisions.forEach((decision) => { const line = element("p", `${decision.instance} ${decision.case_number} · ${decision.outcome}`); if (decision.relation_to_lower_instance === "변경") { line.className = "appeal-changed"; line.append(document.createTextNode(` — 원심 결과(${detail.lower_instance_outcome})에서 변경`)); } appeal.append(line); }); appeal.append(element("p", `확정 여부: ${detail.appeal.finality}`)); const fullText = document.createElement("section"); fullText.className = "case-detail__section case-detail__full-text"; fullText.append(element("h6", "전문")); const fullTextBody = document.createElement("div"); fullTextBody.className = "case-detail__sources"; fullText.append(fullTextBody); if (caseId) renderFullTextSection(caseId, fullTextBody); panel.append(summary, risks, differences, law, appeal, fullText); return panel; };

  const renderResults = (search) => { const results = document.createElement("section"); results.className = "search-results"; results.setAttribute("aria-label", "목업 검색 결과"); results.append(element("h2", "목업 응답 · 검색 결과"), element("p", "유사도 점수와 검색 순서는 사전 정의된 목업 값이며, 현재 시연에서는 실제 운영 환경의 산식이나 판례 적합성·정확성을 보증하지 않습니다.")); const cases = document.createElement("section"); cases.append(element("h3", "판례")); if (!search.cases.length) cases.append(renderEmpty("판례")); search.cases.forEach((item) => { const card = document.createElement("article"); card.className = "result-card case-card"; card.append(element("h4", item.case_number)); const appeal = (search.appeals_by_case || {})[item.case_id]; const warning = item.similarity_warning || item.fact_difference_warning; if (warning) card.append(Object.assign(element("p", warning.text || warning), { className: "result-card__warning" })); addField(card, "법원", item.court_name); addField(card, "심급", item.instance); addField(card, "선고일", item.decision_date); addField(card, "경찰 직무 시나리오", item.scenario_ids.join(", ")); addField(card, "유사도", `${item.similarity_score}%`); addField(card, "적법성", item.legality_status); addField(card, "법령 기준", item.law_basis_status); addField(card, "해당 심급 인정 죄명", item.instance_recognized_charge); addField(card, "해당 심급 재판 결과", item.instance_outcome); addField(card, "상급심 정보 요약", !appeal || appeal.appellate.state === "정보_없음" ? "정보_없음" : appeal.appellate.decisions.map((decision) => `${decision.instance} ${decision.case_number} · ${decision.outcome}`).join(" / ")); if (appeal && appeal.finality_badge) { const badge = element("span", appeal.finality_badge.finality); badge.className = "finality-badge"; card.append(badge); } else addField(card, "확정 여부", "정보_없음"); const detail = (search.case_details_by_case || {})[item.case_id]; if (detail) { const detailToggle = element("button", "상세 보기"); detailToggle.type = "button"; detailToggle.className = "case-detail-toggle"; detailToggle.setAttribute("aria-expanded", "false"); const detailPanel = renderCaseDetail(detail, item.case_id); detailPanel.hidden = true; detailToggle.addEventListener("click", () => { detailPanel.hidden = !detailPanel.hidden; detailToggle.setAttribute("aria-expanded", String(!detailPanel.hidden)); detailToggle.textContent = detailPanel.hidden ? "상세 보기" : "상세 접기"; }); card.append(detailToggle, detailPanel); } cases.append(card); }); const statutes = document.createElement("section"); statutes.append(element("h3", "법조문")); if (!search.statutes.length) statutes.append(renderEmpty("법조문")); search.statutes.forEach((item) => { const card = document.createElement("article"); card.className = "result-card statute-card"; card.append(element("h4", item.law_name)); addField(card, "조·항·호", [item.article, item.paragraph, item.item].filter(Boolean).join(" ")); addField(card, "시행일", item.effective_date || "정보_없음"); statutes.append(card); }); results.append(cases, statutes); feedback.append(results); };
  const showInterpretation = (interpretation) => { resetFeedback(); currentQueryId = interpretation?.kind === "SUPPORTED" ? interpretation.query_id : null; if (!interpretation) return; if (interpretation.kind === "SUPPORTED") { feedback.append(element("h2", "표현과 법률 검색어 대응")); const list = document.createElement("ul"); interpretation.term_correspondences.forEach((item) => list.append(element("li", `${item.field_expression} ↔ ${item.legal_search_terms.join(", ")}`))); feedback.append(list, element("p", "관계 보존: 확인됨")); return; } if (interpretation.kind === "BLANK") feedback.append(element("p", "상황을 입력해 주세요.")); else if (interpretation.kind === "INTERPRETATION_CHECK_NEEDED") feedback.append(element("h2", "해석 확인 필요"), element("p", `원문 표현: ${interpretation.raw}`)); else if (interpretation.kind === "UNSUPPORTED") feedback.append(element("h2", "목업에서 지원하지 않는 질의"), element("p", `입력: ${interpretation.raw}`)); };
  form.addEventListener("submit", async (event) => { event.preventDefault(); try { const payload = await request("/api/query", { query: queryInput.value }); if (payload.rag_error) { PoliceBotErrorDisplay.renderStageError(feedback, payload.rag_error); return; } showInterpretation(payload.interpretation); if (payload.search) renderResults(payload.search); if (payload.response) renderResponse(payload.response); if (payload.interpretation?.kind === "SUPPORTED") document.dispatchEvent(new CustomEvent("timeline:load", { detail: { queryId: payload.interpretation.query_id } })); recordHistory(queryInput.value, payload.interpretation?.kind); } catch (error) { if (error instanceof PoliceBotErrorDisplay.SafeHttpError) { PoliceBotErrorDisplay.renderHttpError(feedback, error); return; } resetFeedback(); const message = element("p", "요청을 처리할 수 없습니다. 다시 시도해 주세요."); message.setAttribute("role", "alert"); feedback.append(message); } });
  voiceButton.addEventListener("click", async () => { if (!voiceSelect.value) { resetFeedback(); const notice = element("p", "음성 시연 항목을 선택해 주세요."); notice.setAttribute("role", "status"); feedback.append(notice); return; } try { const payload = await request("/api/action", { type: "SELECT_VOICE_FIXTURE", fixtureId: voiceSelect.value }); if (payload.voice_error) { PoliceBotErrorDisplay.renderStageError(feedback, payload.voice_error); return; } if (payload.recognized_text !== undefined) { queryInput.value = payload.recognized_text; updateLengthCounter(); showInterpretation(payload.interpretation); const recognized = element("p", `인식 텍스트: ${payload.recognized_text}`); recognized.setAttribute("role", "status"); feedback.prepend(recognized); if (payload.interpretation?.kind === "SUPPORTED") document.dispatchEvent(new CustomEvent("timeline:load", { detail: { queryId: payload.interpretation.query_id, recognizedText: payload.recognized_text } })); recordHistory(payload.recognized_text, payload.interpretation?.kind); } else { const error = element("p", "음성 인식 불가. 수동 텍스트 입력을 이용해 주세요."); error.setAttribute("role", "alert"); feedback.append(error); } } catch (error) { if (error instanceof PoliceBotErrorDisplay.SafeHttpError) { PoliceBotErrorDisplay.renderHttpError(feedback, error); return; } resetFeedback(); const message = element("p", "요청을 처리할 수 없습니다. 수동 텍스트 입력을 이용해 주세요."); message.setAttribute("role", "alert"); feedback.append(message); } });

  /* Footer shortcut buttons: no new logic, just navigate to/trigger existing
   * on-screen affordances (first case's source viewer, the report generator
   * inside the timeline section). If no results/timeline exist yet, tell the
   * user to run a query first instead of fabricating a target. */
  const footerViewSource = document.querySelector("#footer-view-source");
  const footerBuildReport = document.querySelector("#footer-build-report");
  const footerNotice = (text) => {
    const existing = feedback.querySelector(".footer-shortcut-notice");
    if (existing) existing.remove();
    const notice = element("p", text);
    notice.className = "footer-shortcut-notice"; notice.setAttribute("role", "status");
    feedback.prepend(notice);
  };
  if (footerViewSource) {
    footerViewSource.addEventListener("click", () => {
      const toggle = document.querySelector(".case-detail-toggle");
      if (!toggle) { footerNotice("먼저 상황을 입력해 판례 검색 결과를 확인해 주세요."); return; }
      if (toggle.getAttribute("aria-expanded") === "false") toggle.click();
      toggle.scrollIntoView({ block: "center" });
      toggle.focus();
    });
  }
  if (footerBuildReport) {
    footerBuildReport.addEventListener("click", () => {
      const generateButton = document.querySelector(".report-preview button[type='button']:first-of-type");
      if (!generateButton) { footerNotice("먼저 지원되는 상황을 입력해 사실관계 타임라인을 불러와 주세요."); return; }
      generateButton.scrollIntoView({ block: "center" });
      generateButton.click();
      generateButton.focus();
    });
  }

  renderHistory();
})();

/* Results screen (/results): scenario comparison controller (tasks 19.1/19.4).
 * Requests the server-computed lawful/unlawful/mixed partition for the selected
 * scenario and auxiliary filter, and renders it read-only (no client-side
 * recomputation of legal classification). Also owns session-scoped state
 * capture/restore and the reset notice for this screen. */
(() => {
  "use strict";
  const scenarioSelect = document.querySelector("#scenario-select");
  const auxiliarySelect = document.querySelector("#auxiliary-filter");
  const status = document.querySelector("#scenario-status");
  const comparison = document.querySelector("#scenario-comparison");
  if (!scenarioSelect || !auxiliarySelect || !status || !comparison) return;

  const request = async (payload) => (await fetch("/api/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })).json();
  const node = (tag, text) => { const value = document.createElement(tag); if (text !== undefined) value.textContent = text; return value; };

  const caseCard = (item, groupLabel) => {
    const card = document.createElement("article"); card.className = "scenario-case-card";
    card.append(node("h3", item.case_number), node("h4", groupLabel));
    const dl = document.createElement("dl");
    const field = (label, value) => { const row = document.createElement("div"); row.append(node("dt", label), node("dd", value ?? "정보_없음")); dl.append(row); };
    field("법원", item.court_name);
    field("심급", item.instance);
    field("선고일", item.decision_date);
    field("경찰 직무 시나리오", (item.scenario_ids || []).join(", "));
    field("해당 심급 인정 죄명", item.instance_recognized_charge);
    field("해당 심급 재판 결과", item.instance_outcome);
    card.append(dl);
    return card;
  };

  const mixedCaseCard = (entry) => {
    const card = caseCard(entry.case, "판단_혼재");
    const list = document.createElement("ul"); list.className = "action-judgments";
    (entry.action_judgments || []).forEach((judgment) => {
      const item = document.createElement("li");
      item.append(node("span", judgment.action_text), node("span", judgment.court_finding));
      list.append(item);
    });
    card.append(list);
    return card;
  };

  const comparisonColumn = (heading, count, cards) => {
    const column = document.createElement("section"); column.className = "comparison-column";
    const headingNode = node("h2", `${heading} `);
    headingNode.append(Object.assign(node("span", `${count}건`), { className: "result-count" }));
    column.append(headingNode);
    const cardsWrapper = document.createElement("div"); cardsWrapper.className = "comparison-cards";
    if (!cards.length) cardsWrapper.append(Object.assign(node("p", "일치하는 목업 자료 없음"), { className: "empty-results" }));
    cards.forEach((card) => cardsWrapper.append(card));
    column.append(cardsWrapper);
    return column;
  };

  const renderComparison = (partition) => {
    comparison.replaceChildren();
    const lawfulCards = partition.lawful.map((item) => caseCard(item, "적법"));
    const unlawfulCards = partition.unlawful.map((item) => caseCard(item, "위법"));
    const mixedCards = partition.mixed.map(mixedCaseCard);

    const tabs = document.createElement("div"); tabs.className = "comparison-tabs"; tabs.setAttribute("role", "tablist");
    const columns = document.createElement("div"); columns.className = "comparison-columns";
    const definitions = [
      { key: "lawful", label: "적법", count: lawfulCards.length, cards: lawfulCards },
      { key: "unlawful", label: "위법", count: unlawfulCards.length, cards: unlawfulCards },
      { key: "mixed", label: "판단 혼재", count: mixedCards.length, cards: mixedCards },
    ];
    const columnElements = definitions.map((definition) => comparisonColumn(definition.label, definition.count, definition.cards));
    columnElements.forEach((column, index) => { column.id = `comparison-column-${definitions[index].key}`; if (index === 0) column.classList.add("is-active"); });

    definitions.forEach((definition, index) => {
      const tab = node("button", `${definition.label} (${definition.count})`);
      tab.type = "button"; tab.setAttribute("role", "tab"); tab.setAttribute("aria-selected", String(index === 0));
      tab.setAttribute("aria-controls", `comparison-column-${definition.key}`);
      tab.addEventListener("click", () => {
        [...tabs.children].forEach((other) => other.setAttribute("aria-selected", "false"));
        tab.setAttribute("aria-selected", "true");
        columnElements.forEach((column) => column.classList.remove("is-active"));
        columnElements[index].classList.add("is-active");
      });
      tabs.append(tab);
    });

    columns.append(...columnElements);
    comparison.append(tabs, columns);
  };

  const loadComparison = async () => {
    if (!scenarioSelect.value) return;
    status.textContent = "시나리오를 불러오는 중입니다.";
    comparison.replaceChildren();
    try {
      const payload = await request({
        type: "GET_SCENARIO_COMPARISON",
        scenario: scenarioSelect.value,
        auxiliaryFilter: auxiliarySelect.value || null,
      });
      renderComparison(payload.partition);
      status.textContent = `${payload.scenario} 비교 결과를 불러왔습니다.`;
    } catch (_) {
      status.textContent = "시나리오 비교 결과를 불러올 수 없습니다. 다시 시도해 주세요.";
    }
  };

  const announce = (text, isAlert) => {
    const notice = document.createElement("p");
    notice.setAttribute("role", isAlert ? "alert" : "status");
    notice.className = "session-restore-notice";
    notice.textContent = text;
    status.insertAdjacentElement("afterend", notice);
  };

  const persist = () => PoliceBotSessionState.writeState({
    results: { scenario: scenarioSelect.value, auxiliaryFilter: auxiliarySelect.value || null },
    hadResultsState: true,
  });
  scenarioSelect.addEventListener("change", () => { persist(); loadComparison(); });
  auxiliarySelect.addEventListener("change", () => { persist(); loadComparison(); });

  const state = PoliceBotSessionState.readState();
  if (state && state.results && state.results.scenario) {
    scenarioSelect.value = state.results.scenario;
    auxiliarySelect.value = state.results.auxiliaryFilter || "";
    announce("이전 화면 상태를 복구했습니다.", false);
  } else if (state && state.hadResultsState) {
    announce(PoliceBotSessionState.RESET_NOTICE_TEXT, false);
  }
  loadComparison();
})();

/* Timeline editor: renders server-projected events and sends edits back to Python. */
(() => {
  "use strict";
  const feedback = document.querySelector("#query-feedback");
  if (!feedback) return;
  const request = async (payload) => (await fetch("/api/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })).json();
  const node = (tag, text) => { const value = document.createElement(tag); value.textContent = text; return value; };
  const field = (label, value, type = "text") => { const labelNode = node("label", label); const input = document.createElement("input"); input.type = type; input.value = value || ""; labelNode.append(input); return { labelNode, input }; };

  const showSource = async (sourceId, target) => {
    const payload = await request({ type: "GET_SOURCE", sourceId });
    target.replaceChildren();
    if (!payload.source) { target.append(node("p", payload.source_error || "출처 데이터 오류")); return; }
    const source = payload.source; const title = node("h4", source.title); const body = node("p", source.body);
    body.className = "timeline-source__body"; body.tabIndex = -1; target.append(title, body); body.focus();
  };
  const issueList = (event) => {
    const section = document.createElement("section"); section.className = "timeline-issues"; section.append(node("h4", "연결 쟁점·출처"));
    const issues = event.issue_projection.issues;
    if (!issues.length) { section.append(node("p", event.issue_projection.no_issue_label)); return section; }
    issues.forEach((issue) => { const item = node("p", issue.issue); issue.source_ids.forEach((sourceId) => { const button = node("button", `출처 ${sourceId} 보기`); button.type = "button"; button.addEventListener("click", () => showSource(sourceId, section.querySelector(".timeline-source"))); item.append(document.createTextNode(" "), button); }); section.append(item); });
    const source = document.createElement("div"); source.className = "timeline-source"; source.setAttribute("aria-live", "polite"); section.append(source); return section;
  };
  const eventCard = (event, queryId, groupLabel) => {
    const card = document.createElement("article"); card.className = "timeline-event"; card.dataset.eventId = event.id;
    card.append(node("p", groupLabel), node("h3", event.action));
    const before = node("p", `수정 전: ${event.original_text}`); before.className = "timeline-event__before"; card.append(before);
    const form = document.createElement("form"); form.className = "timeline-edit-form";
    const time = field("시간", event.explicit_time || "", "datetime-local"); const actor = field("주체", event.actor || ""); const action = field("행위", event.action); const original = field("행위 원문", event.original_text);
    [time, actor, action, original].forEach(({ labelNode }) => form.append(labelNode)); const save = node("button", "수정 반영"); save.type = "submit"; form.append(save);
    const status = node("p", ""); status.className = "timeline-edit-status"; status.setAttribute("role", "status"); form.append(status);
    form.addEventListener("submit", async (e) => { e.preventDefault(); status.textContent = "수정 중입니다."; try { const result = await request({ type: "UPDATE_TIMELINE_EVENT", queryId, eventId: event.id, explicitTime: time.input.value || null, actor: actor.input.value || null, action: action.input.value, originalText: original.input.value }); renderTimeline(result, queryId); } catch (_) { status.textContent = "수정에 실패했습니다. 현재 화면을 유지합니다."; } });
    card.append(form, issueList(event)); if (event.ambiguity) { const warning = node("p", `사용자 확인 필요: ${event.ambiguity.alternatives.join(" / ")}`); warning.className = "timeline-ambiguity"; card.append(warning); } return card;
  };
  const renderTimeline = (payload, queryId) => {
    const old = feedback.querySelector("#timeline"); if (old) old.remove();
    const timeline = payload.timeline; if (!timeline) return;
    const section = document.createElement("section"); section.id = "timeline"; section.className = "timeline-editor"; section.setAttribute("aria-label", "사실관계 타임라인"); section.append(node("h2", "사실관계 타임라인"), node("p", "인식 텍스트와 서버가 정렬한 사건을 표시합니다. 수정 내용은 보고서용 사실관계에도 반영됩니다."));
    const ordered = document.createElement("section"); ordered.append(node("h3", "시간순 사건")); timeline.ordered.forEach((event) => ordered.append(eventCard(event, queryId, `시간: ${event.explicit_time || event.resolved_sort_time}`)));
    const unknown = document.createElement("section"); unknown.append(node("h3", "시점 미상")); if (!timeline.unknown_time.length) unknown.append(node("p", "시점 미상 사건 없음")); timeline.unknown_time.forEach((event) => unknown.append(eventCard(event, queryId, "시점 미상")));
    section.append(ordered, unknown, buildReportSection(queryId)); feedback.append(section);
  };
  const loadTimeline = async (queryId, recognizedText) => { try { const payload = await request({ type: "GET_TIMELINE", queryId }); if (recognizedText) { const info = node("p", `인식 텍스트: ${recognizedText}`); info.className = "timeline-recognized-text"; feedback.append(info); } renderTimeline(payload, queryId); } catch (_) { /* Query feedback already remains visible. */ } };
  document.addEventListener("timeline:load", (event) => loadTimeline(event.detail.queryId, event.detail.recognizedText));

  /* Report preview/copy/download (LocalExportPort, task 20.3). The server-built body,
     as-of date, and legal safety notice are copied/downloaded unchanged. Copy and
     download failures leave the report body and timeline untouched and offer a
     manual selectable-text fallback (requirements 11.15, 11.16, 11.17, 1.7). */
  const buildReportSection = (queryId) => {
    const section = document.createElement("section"); section.className = "report-preview"; section.setAttribute("aria-label", "보고서 미리보기");
    section.append(node("h3", "보고서 미리보기"));
    const generateButton = node("button", "보고서 생성"); generateButton.type = "button";
    const status = node("p", ""); status.className = "report-status"; status.setAttribute("role", "status");
    const preview = document.createElement("pre"); preview.className = "report-preview__body"; preview.hidden = true;
    const actions = document.createElement("div"); actions.className = "report-preview__actions"; actions.hidden = true;
    const copyButton = node("button", "복사"); copyButton.type = "button";
    const downloadButton = node("button", "다운로드 (.txt)"); downloadButton.type = "button";
    const manualFallback = node("p", "복사/다운로드를 사용할 수 없는 경우, 위 보고서 본문을 직접 선택해 복사해 주세요.");
    manualFallback.className = "report-preview__manual-fallback"; manualFallback.hidden = true;
    actions.append(copyButton, downloadButton);

    let currentReport = null;

    generateButton.addEventListener("click", async () => {
      status.textContent = "보고서를 생성하는 중입니다.";
      try {
        const payload = await request({ type: "GET_REPORT", queryId });
        if (!payload.report) { status.textContent = "보고서를 생성할 수 없습니다. 사실관계 타임라인은 그대로 유지됩니다."; return; }
        currentReport = payload.report;
        preview.textContent = currentReport.body; preview.hidden = false;
        preview.setAttribute("tabindex", "0");
        actions.hidden = false; manualFallback.hidden = true;
        status.textContent = "보고서를 생성했습니다.";
      } catch (_) {
        status.textContent = "보고서를 생성할 수 없습니다. 사실관계 타임라인은 그대로 유지됩니다.";
      }
    });

    copyButton.addEventListener("click", async () => {
      if (!currentReport) return;
      try {
        if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("clipboard_unavailable");
        await navigator.clipboard.writeText(currentReport.body);
        status.textContent = "보고서 본문을 복사했습니다."; manualFallback.hidden = true;
      } catch (_) {
        status.textContent = "복사에 실패했습니다. 보고서 본문과 사실관계 타임라인은 그대로 유지됩니다.";
        manualFallback.hidden = false;
      }
    });

    downloadButton.addEventListener("click", () => {
      if (!currentReport) return;
      try {
        const blob = new Blob([currentReport.body], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a"); link.href = url; link.download = "report-facts.txt";
        document.body.append(link); link.click(); link.remove();
        URL.revokeObjectURL(url);
        status.textContent = "보고서를 UTF-8 텍스트 파일로 다운로드했습니다."; manualFallback.hidden = true;
      } catch (_) {
        status.textContent = "다운로드에 실패했습니다. 보고서 본문과 사실관계 타임라인은 그대로 유지됩니다.";
        manualFallback.hidden = false;
      }
    });

    section.append(generateButton, status, preview, actions, manualFallback);
    return section;
  };
})();
