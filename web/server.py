"""Same-deployment WSGI routing for the mock legal demonstration.

This module deliberately depends only on the validated, bundled fixture and existing
Python domain projections. It exposes browser routes (``/``, ``/results``) and
same-origin JSON commands (``/api/query``, ``/api/action``), and never contacts an
external service. Legal values are accompanied by record IDs that identify their
fixture provenance.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from html import escape
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple
from wsgiref.simple_server import make_server

from data.fixture_repository import FixtureRepository
from web.config import DeploymentSettings, load_deployment_settings
from data.validated_dataset import ValidatedDataset, validate_dataset
from domain.mock_search import SearchProjection, run_mock_search
from domain.appellate_projection import project_case_appeal
from domain.enums import PoliceScenario, SummaryLevel, TraditionalCaseArea
from domain.law_status import old_law_basis_display, statute_date_display
from domain.liability_classification import classify_action_badge, classify_evidence
from domain.similarity_and_difference import (
    order_fact_differences,
    resolve_fact_difference_display,
    similarity_warning,
)
from domain.summary_projection import project_summary
from domain.query_interpretation import SupportedQueryInterpretation, interpret_query
from domain.scenario_classification import filter_scenario_intersection, partition_scenario_cases
from domain.local_voice_demo import recognize_voice_fixture
from domain.response_projection import ResponseTemplateProjection, project_response_template
from domain.citations import SOURCE_DATA_ERROR_TEXT
from domain.selection_review import resolve_selection_explanation, review_selection
from data.models_common import VoiceFixtureId
from domain.ids import ClaimId
from domain.result import Ok
from domain.timeline import TimelineState, UpdateEventCommand, project_event_issues, update_timeline_event
from domain.report import build_report_facts
from domain.ids import EventId
from fixtures.mock_dataset import build_mock_dataset

StartResponse = Callable[[str, List[Tuple[str, str]]], Callable[[bytes], object]]

__all__ = ["MockWebApplication", "create_application", "run_server"]

_STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"
# Same-origin-only deployment: allow same-origin web app communication and static
# assets, block all external-origin connections (requirements 1.5, 1.10, 1.12, 14.1, 14.2).
_CONTENT_SECURITY_POLICY = "default-src 'self'; connect-src 'self'"
_LOGGER = logging.getLogger(__name__)
_SAFE_LOG_METADATA = frozenset({"method", "path", "status", "content_length"})


def _safe_request_metadata(environ: Mapping[str, Any], status: str) -> Dict[str, str]:
    """Return an allowlisted diagnostic record without reading request content."""
    try:
        content_length = str(max(0, int(str(environ.get("CONTENT_LENGTH", "0")))))
    except ValueError:
        content_length = "invalid"
    values = {
        "method": str(environ.get("REQUEST_METHOD", "GET")).upper(),
        "path": str(environ.get("PATH_INFO", "/")),
        "status": status.split(" ", 1)[0],
        "content_length": content_length,
    }
    return {key: values[key] for key in _SAFE_LOG_METADATA}


def _log_request_metadata(environ: Mapping[str, Any], status: str) -> None:
    """Persist only request metadata, never query, selection, report, or response text."""
    _LOGGER.info("web_request", extra={"request_metadata": _safe_request_metadata(environ, status)})


def _json_value(value: Any) -> Any:
    """Convert immutable domain dataclasses/enums/IDs into JSON-safe values."""
    if is_dataclass(value):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_json_value(item) for item in value]
    return getattr(value, "value", value)


def _html(title: str, body: str) -> bytes:
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{escape(title)}</title><link rel='stylesheet' href='/static/app.css'>"
        "<script defer src='/static/app.js'></script></head>"
        f"<body>{body}</body></html>"
    ).encode("utf-8")


_PUBLIC_DEPLOYMENT_NOTICE = (
    "이 웹 애플리케이션은 수사 및 법률 업무의 정보 정리·검토를 지원하기 위한 시연용 "
    "프로토타입입니다. 제공되는 데이터와 결과는 사전 정의된 목업 데이터에 기반하며, 실제 "
    "사건의 최종 법률 판단·수사 판단 또는 공식 업무 결정을 대체하지 않습니다. 실제 업무 "
    "적용 시에는 관계 법령, 내부 절차 및 담당 전문가의 검토가 필요합니다."
)
_PRIVACY_NOTICE = (
    "입력한 상황 질의, 선택 문구 및 보고서 본문은 영구 저장하거나 외부 분석·제3자 공유·"
    "애플리케이션 로그에 기록하지 않습니다."
)


def _app_shell(dataset: ValidatedDataset, route: str, content: str) -> str:
    """Render the shared, visible AppShell using only bundled dataset metadata."""
    metadata = dataset
    is_results = route == "RESULTS"
    query_current = " aria-current='page'" if not is_results else ""
    results_current = " aria-current='page'" if is_results else ""
    return f"""
    <a class='skip-link' href='#main-content'>본문으로 건너뛰기</a>
    <header class='app-shell__header'>
      <div class='shell-container'>
        <div class='brand-row'>
          <a class='brand' href='/'>경찰 판례·법령 AI 봇</a>
          <span class='mock-badge' aria-label='목업 응답'>목업 응답</span>
        </div>
        <nav class='global-nav' aria-label='전역 탐색'>
          <a href='/'{query_current}>상황 검색</a>
          <a href='/results'{results_current}>직무 시나리오</a>
        </nav>
        <section class='scope-summary' aria-label='데이터 범위와 기준'>
          <span><strong>데이터 기준일</strong> {escape(str(metadata.as_of_date))}</span>
          <span>{escape(metadata.no_realtime_sync_label)}</span>
          <dl class='coverage-labels'>
            <div><dt>목표 데이터 범위</dt><dd>{escape(metadata.target_coverage_label)}</dd></div>
            <div><dt>현재 구현 데이터 범위</dt><dd>{escape(metadata.implemented_coverage_label)}</dd></div>
          </dl>
        </section>
      </div>
    </header>
    <main id='main-content' class='shell-container app-shell__main'>
      {content}
      <aside class='instance-caution' aria-label='심급 및 확정 여부 안내'>
        {escape(metadata.instance_caution_notice)}
      </aside>
      <section class='notice-panel' aria-label='시연 및 개인정보 고지'>
        <details open><summary>공개 배포 고지</summary><p>{_PUBLIC_DEPLOYMENT_NOTICE}</p></details>
        <details open><summary>법률 안전 고지</summary><p>{escape(metadata.legal_safety_notice)}</p></details>
        <details open><summary>개인정보 처리 고지</summary><p>{_PRIVACY_NOTICE}</p></details>
      </section>
    </main>
    """


class MockWebApplication:
    """A refresh-safe WSGI application with sanitized, deterministic failures."""

    def __init__(self, dataset: Optional[ValidatedDataset]) -> None:
        self._dataset = dataset
        self._available = dataset is not None
        self._repo = FixtureRepository(dataset) if dataset is not None else None
        self._queries = {query.id: query for query in dataset.queries} if dataset is not None else {}
        self._templates = {template.id: template for template in dataset.response_templates} if dataset is not None else {}
        self._review_fixtures = {
            fixture.response_template_id: fixture for fixture in dataset.review_fixtures
        } if dataset is not None else {}

    def __call__(self, environ: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        response_status = "500 Internal Server Error"

        def tracked_start_response(status: str, headers: List[Tuple[str, str]]) -> Callable[[bytes], object]:
            nonlocal response_status
            response_status = status
            return start_response(status, headers)

        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        try:
            if not self._is_defined_path(path):
                return self._safe_error(tracked_start_response, "404 Not Found", "NOT_FOUND", retryable=False)
            if not self._method_allowed(path, method):
                return self._safe_error(tracked_start_response, "405 Method Not Allowed", "METHOD_NOT_ALLOWED", retryable=False)
            if not self._available:
                return self._safe_error(tracked_start_response, "503 Service Unavailable", "SERVICE_UNAVAILABLE", retryable=True)
            if path in ("/", "/results"):
                return self._page(path, tracked_start_response)
            if path.startswith("/static/"):
                return self._static(path, tracked_start_response)
            if path == "/api/query":
                return self._query(environ, tracked_start_response)
            return self._action(environ, tracked_start_response)
        except Exception:
            # Do not reflect exception details, configuration, or request contents.
            return self._safe_error(tracked_start_response, "500 Internal Server Error", "INTERNAL_ERROR", retryable=True)
        finally:
            _log_request_metadata(environ, response_status)

    @staticmethod
    def _is_defined_path(path: str) -> bool:
        return path in ("/", "/results", "/api/query", "/api/action") or path.startswith("/static/")

    @staticmethod
    def _method_allowed(path: str, method: str) -> bool:
        if path in ("/", "/results") or path.startswith("/static/"):
            return method == "GET"
        return method == "POST"

    def _page(self, path: str, start_response: StartResponse) -> Iterable[bytes]:
        assert self._dataset is not None
        if path == "/results":
            scenario_options = "".join(
                f"<option value='{escape(str(scenario.id.value))}'>{escape(str(scenario.id.value))}</option>"
                for scenario in self._dataset.scenarios
            )
            content = f"""
            <section class='page-intro scenario-explorer' aria-labelledby='page-title'>
              <p class='eyebrow'>직무 시나리오</p><h1 id='page-title'>적법·위법 판례 비교</h1>
              <p>선택한 시나리오의 서버 분류 결과를 적법, 위법, 판단 혼재로 나누어 표시합니다.</p>
              <div class='scenario-controls'>
                <label for='scenario-select'>경찰 직무 시나리오</label>
                <select id='scenario-select'>{scenario_options}</select>
                <label for='auxiliary-filter'>보조 필터</label>
                <select id='auxiliary-filter'>
                  <option value=''>전체 분야</option><option value='형사'>형사</option>
                  <option value='민사'>민사</option><option value='행정'>행정</option>
                </select>
              </div>
              <p id='scenario-status' class='scenario-status' role='status'>시나리오를 불러오는 중입니다.</p>
              <section id='scenario-comparison' class='scenario-comparison' aria-label='적법성 비교 결과'></section>
            </section>
            """
            route = "RESULTS"
        else:
            voice_options = "".join(
                f"<option value='{escape(str(voice.id))}'>{escape(voice.label)}</option>"
                for voice in self._dataset.voice_fixtures
            )
            content = f"""
            <div class='entry-layout'>
              <section class='page-intro situation-input' aria-labelledby='page-title'>
                <p class='eyebrow'>시연용 웹 애플리케이션</p><h1 id='page-title'>경찰 판례·법령 AI 봇</h1>
                <p>현장 상황을 입력해 사전에 정의된 목업 자료를 검토합니다.</p>
                <form id='situation-form' novalidate>
                  <label for='situation-query'>상황 입력</label>
                  <textarea id='situation-query' name='query' rows='4' required aria-describedby='situation-help'></textarea>
                  <p id='situation-help'>사건번호나 죄명 대신 현장 상황을 입력하세요.</p>
                  <button type='submit'>목업 자료 확인</button>
                </form>
                <section class='voice-demo' aria-labelledby='voice-demo-title'>
                  <h2 id='voice-demo-title'>사전 정의 음성 시연</h2>
                  <label for='voice-fixture'>음성 시연 항목</label>
                  <select id='voice-fixture' name='voiceFixtureId'>
                    <option value=''>선택하세요</option>{voice_options}
                  </select>
                  <button id='voice-select-button' type='button'>인식 텍스트 불러오기</button>
                  <p>실제 음성 인식이나 마이크 입력은 사용하지 않습니다.</p>
                </section>
                <section id='query-feedback' class='query-feedback' aria-live='polite' aria-label='질의 해석 결과'></section>
              </section>
              <aside class='query-history' aria-label='검색 기록'>
                <h2>검색 기록</h2>
                <p>같은 브라우저 세션 동안 실행한 상황 질의만 표시됩니다. 새 브라우저 세션에서는 저장되지 않습니다.</p>
                <ul id='query-history-list' class='query-history__list'></ul>
              </aside>
            </div>
            """
            route = "QUERY"
        body = _app_shell(self._dataset, route, content)
        return self._bytes(start_response, "200 OK", "text/html; charset=utf-8", _html("경찰 판례·법령 AI 봇", body))

    def _static(self, path: str, start_response: StartResponse) -> Iterable[bytes]:
        relative = path.removeprefix("/static/")
        candidate = (_STATIC_ROOT / relative).resolve()
        if _STATIC_ROOT not in candidate.parents or not candidate.is_file():
            return self._safe_error(start_response, "404 Not Found", "NOT_FOUND", retryable=False)
        content_type = "application/javascript; charset=utf-8" if candidate.suffix == ".js" else "text/css; charset=utf-8"
        return self._bytes(start_response, "200 OK", content_type, candidate.read_bytes())

    def _query(self, environ: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        payload, error_status = self._request_json(environ)
        if error_status is not None:
            return self._safe_error(start_response, error_status, "UNSUPPORTED_MEDIA_TYPE" if error_status.startswith("415") else "INVALID_REQUEST", retryable=False)
        if payload is None or not isinstance(payload.get("query"), str):
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        assert self._dataset is not None and self._repo is not None
        interpretation = interpret_query(payload["query"], self._dataset)
        response: Dict[str, Any] = {"interpretation": _json_value(interpretation), "provenance": {}}
        if isinstance(interpretation, SupportedQueryInterpretation):
            query = self._queries[interpretation.query_id]
            search_result = run_mock_search(query, self._repo)
            if isinstance(search_result, Ok):
                search = search_result.value
                response["search"] = self._search_payload(search)
                response["response"] = _json_value(self._response_for(query.match.response_template_id))
                response["provenance"] = self._provenance(query.id, search, query.match.response_template_id)
            else:
                response["rag_error"] = _json_value(search_result.error)
        return self._json(start_response, "200 OK", response)

    def _action(self, environ: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        payload, error_status = self._request_json(environ)
        if error_status is not None:
            return self._safe_error(start_response, error_status, "UNSUPPORTED_MEDIA_TYPE" if error_status.startswith("415") else "INVALID_REQUEST", retryable=False)
        if payload is None or not isinstance(payload.get("type"), str):
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        if payload["type"] == "SELECT_VOICE_FIXTURE":
            return self._select_voice_fixture(payload, start_response)
        if payload["type"] == "GET_SCENARIO_COMPARISON":
            return self._scenario_comparison(payload, start_response)
        if payload["type"] == "GET_CASE_DETAIL":
            return self._case_detail(payload, start_response)
        if payload["type"] == "RUN_SELECTION_REVIEW":
            return self._selection_review(payload, start_response)
        if payload["type"] == "GET_TIMELINE":
            return self._timeline(payload, start_response)
        if payload["type"] == "UPDATE_TIMELINE_EVENT":
            return self._update_timeline_event(payload, start_response)
        if payload["type"] == "GET_REPORT":
            return self._report(payload, start_response)
        if payload["type"] == "GET_SOURCE":
            return self._source(payload, start_response)
        if payload["type"] != "GET_RESULTS" or not isinstance(payload.get("queryId"), str):
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        query = self._queries.get(payload["queryId"])
        if query is None:
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        assert self._repo is not None
        result = run_mock_search(query, self._repo)
        if not isinstance(result, Ok):
            return self._json(start_response, "200 OK", {"rag_error": _json_value(result.error), "provenance": {}})
        return self._json(start_response, "200 OK", {"search": self._search_payload(result.value), "response": _json_value(self._response_for(query.match.response_template_id)), "provenance": self._provenance(query.id, result.value, query.match.response_template_id)})

    def _selection_review(self, payload: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        """Validate a current response selection and return fixture-backed review data."""
        query_id, selected_text = payload.get("queryId"), payload.get("selectedText")
        selected_claim_ids, mode = payload.get("selectedClaimIds"), payload.get("mode")
        if not isinstance(query_id, str) or not isinstance(selected_text, str) or not isinstance(selected_claim_ids, list) or not all(isinstance(value, str) for value in selected_claim_ids) or mode not in ("FACT_CHECK", "EXPLANATION"):
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        query = self._queries.get(query_id)
        fixture = self._review_fixtures.get(query.match.response_template_id) if query is not None else None
        if fixture is None:
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        claim_ids = tuple(ClaimId(value) for value in selected_claim_ids)
        known_claim_ids = {claim.id for claim in fixture.claims}
        if selected_text.strip() and (not claim_ids or any(claim_id not in known_claim_ids for claim_id in claim_ids)):
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        if mode == "FACT_CHECK":
            result = review_selection(selected_text, claim_ids, fixture.claims)
            return self._json(start_response, "200 OK", {"mode": mode, "result": _json_value(result), "selection_pending": not result.claims, "provenance": {"reviewFixture": [fixture.response_template_id], "claims": [str(claim.claim_id) for claim in result.claims]}})
        displays = tuple(resolve_selection_explanation(claim_id, fixture.explanations, self._dataset.display_policies.status_labels) for claim_id in claim_ids if claim_id in known_claim_ids)
        return self._json(start_response, "200 OK", {"mode": mode, "explanations": _json_value(displays), "selection_pending": not selected_text.strip() or not displays, "provenance": {"reviewFixture": [fixture.response_template_id], "claims": [str(display.claim_id) for display in displays]}})

    def _case_detail(self, payload: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        """Return one selected fixture case with its own full-text source records."""
        case_id = payload.get("caseId")
        if not isinstance(case_id, str) or self._repo is None:
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        case = self._repo.get_case(case_id)
        if case is None:
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        sources = tuple(
            source for source_id in case.source_ids
            if (source := self._repo.get_source(source_id)) is not None
        )
        return self._json(start_response, "200 OK", {
            "case": _json_value(case),
            "sources": _json_value(sources),
            "provenance": {"case": [str(case.id)], "sources": [str(source.id) for source in sources]},
        })

    def _timeline(self, payload: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        query_id = payload.get("queryId")
        if not isinstance(query_id, str) or query_id not in self._queries:
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        state = TimelineState(events=self._queries[query_id].recognized_events)
        return self._json(start_response, "200 OK", self._timeline_payload(query_id, state))

    def _update_timeline_event(self, payload: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        query_id, event_id = payload.get("queryId"), payload.get("eventId")
        if not isinstance(query_id, str) or not isinstance(event_id, str) or query_id not in self._queries:
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        allowed = ("action", "actor", "originalText", "explicitTime")
        if any(key in payload and payload[key] is not None and not isinstance(payload[key], str) for key in allowed):
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        try:
            state = update_timeline_event(TimelineState(events=self._queries[query_id].recognized_events), UpdateEventCommand(
                event_id=EventId(event_id), action=payload.get("action"), actor=payload.get("actor"),
                original_text=payload.get("originalText"), explicit_time=payload.get("explicitTime"),
            ))
        except ValueError:
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        return self._json(start_response, "200 OK", self._timeline_payload(query_id, state))

    def _report(self, payload: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        """Build the reusable report body from the current (possibly edited) timeline.

        The client receives the exact body, as-of date, and legal safety notice to
        copy/download unchanged; it never assembles report text itself.
        """
        query_id = payload.get("queryId")
        if not isinstance(query_id, str) or query_id not in self._queries:
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        events_payload = payload.get("events")
        if events_payload is not None and not isinstance(events_payload, list):
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        state = TimelineState(events=self._queries[query_id].recognized_events)
        if events_payload:
            for update in events_payload:
                if not isinstance(update, dict) or not isinstance(update.get("eventId"), str):
                    return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
                try:
                    state = update_timeline_event(state, UpdateEventCommand(
                        event_id=EventId(update["eventId"]), action=update.get("action"),
                        actor=update.get("actor"), original_text=update.get("originalText"),
                        explicit_time=update.get("explicitTime"),
                    ))
                except ValueError:
                    return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        assert self._dataset is not None
        report = build_report_facts(state.projection, self._dataset, self._dataset.legal_safety_notice)
        return self._json(start_response, "200 OK", {
            "queryId": query_id,
            "report": _json_value(report),
            "provenance": {"query": [query_id], "events": [str(event.id) for event in state.events]},
        })

    @staticmethod
    def _timeline_payload(query_id: str, state: TimelineState) -> Dict[str, Any]:
        projection = state.projection
        def event_payload(event: Any) -> Dict[str, Any]:
            value = _json_value(event)
            value["issue_projection"] = _json_value(project_event_issues(event))
            return value
        return {
            "queryId": query_id,
            "timeline": {"ordered": [event_payload(event) for event in projection.ordered], "unknown_time": [event_payload(event) for event in projection.unknown_time]},
            "provenance": {"query": [query_id], "events": [str(event.id) for event in state.events]},
        }

    def _source(self, payload: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        source_id = payload.get("sourceId")
        if not isinstance(source_id, str):
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        assert self._repo is not None
        source = self._repo.get_source(source_id)
        if source is None:
            return self._json(start_response, "200 OK", {"source_error": "출처 데이터 오류", "provenance": {}})
        return self._json(start_response, "200 OK", {"source": _json_value(source), "provenance": {"source": [source_id]}})

    def _case_detail(self, payload: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        """Return one fixture-backed case and its own full-text sources.

        The browser receives display-ready fixture records and source anchors; it
        only controls disclosure, scrolling, highlighting, and focus restoration.
        Invalid or cross-case source IDs are isolated instead of being exposed.
        """
        case_id = payload.get("caseId")
        if not isinstance(case_id, str):
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        assert self._repo is not None
        case = self._repo.get_case(case_id)
        if case is None:
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        sources = []
        invalid_source_ids = []
        for source_id in case.source_ids:
            source = self._repo.get_source(source_id)
            if source is None or source.owner.type != "CASE" or str(source.owner.id) != str(case.id):
                invalid_source_ids.append(str(source_id))
                continue
            sources.append(_json_value(source))
        response: Dict[str, Any] = {
            "case": _json_value(case),
            "sources": sources,
            "provenance": {"case": [str(case.id)], "sources": [str(source["id"]) for source in sources]},
        }
        if invalid_source_ids:
            response["source_error"] = {"code": "SOURCE_DATA_ERROR", "display_text": SOURCE_DATA_ERROR_TEXT, "sourceIds": invalid_source_ids}
        return self._json(start_response, "200 OK", response)

    def _scenario_comparison(self, payload: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        """Return a fixture-backed legality partition; the browser only renders it."""
        scenario_value = payload.get("scenario")
        auxiliary_value = payload.get("auxiliaryFilter")
        if not isinstance(scenario_value, str) or (auxiliary_value is not None and not isinstance(auxiliary_value, str)):
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        try:
            scenario = PoliceScenario(scenario_value)
            auxiliary = TraditionalCaseArea(auxiliary_value) if auxiliary_value else None
        except ValueError:
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        assert self._dataset is not None
        filtered = filter_scenario_intersection(self._dataset.cases, scenario, auxiliary)
        partition = partition_scenario_cases(filtered, scenario)
        return self._json(start_response, "200 OK", {
            "scenario": scenario.value,
            "auxiliaryFilter": auxiliary.value if auxiliary is not None else None,
            "partition": _json_value(partition),
            "provenance": {
                "scenario": [scenario.value],
                "cases": [str(case.id) for case in filtered],
            },
        })

    def _select_voice_fixture(self, payload: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        """Return only fixture-backed voice recognition text and its interpretation."""
        fixture_id = payload.get("fixtureId")
        if not isinstance(fixture_id, str) or not fixture_id:
            return self._safe_error(start_response, "400 Bad Request", "INVALID_REQUEST", retryable=False)
        assert self._dataset is not None and self._repo is not None
        recognition = recognize_voice_fixture(VoiceFixtureId(fixture_id), self._repo)
        if not isinstance(recognition, Ok):
            return self._json(start_response, "200 OK", {"voice_error": _json_value(recognition.error), "provenance": {"voiceFixture": [fixture_id]}})
        interpretation = interpret_query(recognition.value.text, self._dataset)
        return self._json(start_response, "200 OK", {
            "recognized_text": recognition.value.text,
            "interpretation": _json_value(interpretation),
            "provenance": {"voiceFixture": [fixture_id]},
        })

    def _response_for(self, template_id: str) -> ResponseTemplateProjection:
        return project_response_template(self._templates[template_id])

    def _provenance(self, query_id: str, search: SearchProjection, template_id: str) -> Dict[str, Any]:
        """Associate every server-returned legal display group with fixture record IDs."""
        cases = {str(case.case_id): [str(case.case_id)] for case in search.cases}
        statutes = {str(statute.statute_version_id): [str(statute.statute_version_id)] for statute in search.statutes}
        template = self._response_for(template_id)
        claims = {str(block.claim_id): [str(block.claim_id), *[str(c.source_id) for c in block.direct_citations]] for block in template.blocks if hasattr(block, "claim_id")}
        return {"query": [str(query_id)], "cases": cases, "statutes": statutes, "responseClaims": claims}

    def _search_payload(self, search: SearchProjection) -> Dict[str, Any]:
        """Serialize search data plus fixture-derived appellate card details.

        The client receives display-ready values only and does not derive appeal or
        finality state from a case ID.
        """
        assert self._repo is not None
        payload = _json_value(search)
        payload["appeals_by_case"] = {
            str(case.case_id): _json_value(project_case_appeal(self._repo.get_case(case.case_id)))
            for case in search.cases
            if self._repo.get_case(case.case_id) is not None
        }
        payload["case_details_by_case"] = {
            str(case.case_id): self._case_detail_payload(
                self._repo.get_case(case.case_id), case.similarity_score, search
            )
            for case in search.cases
            if self._repo.get_case(case.case_id) is not None
        }
        return payload

    def _case_detail_payload(self, case: Any, score: float, search: SearchProjection) -> Dict[str, Any]:
        """Build display-ready detail data exclusively from Python projections.

        The client receives ordered summary, risk, difference, law, and appeal values
        and only renders them; it does not classify or reorder legal information.
        """
        assert self._dataset is not None and self._repo is not None
        summaries = {
            level.value: _json_value(project_summary(
                case.summaries, level, self._dataset.display_policies.placeholders
            ))
            for level in SummaryLevel
        }
        risk = case.liability
        risk_axes = (
            ("민사 국가배상", classify_evidence(risk.civil.evidence)),
            ("형사 직권남용", classify_evidence(risk.criminal.abuse_of_authority.evidence)),
            ("형사 독직폭행", classify_evidence(risk.criminal.custodial_violence.evidence)),
            ("징계", classify_evidence(risk.discipline.evidence)),
        )
        matching_query = next(
            (query for query in self._dataset.queries if case.id in query.match.case_ids),
            None,
        )
        differences = order_fact_differences(
            score,
            case.fact_differences_by_query.get(
                matching_query.id if matching_query is not None else None, ()
            ),
        )
        statutes = []
        for reference in case.applied_statutes:
            version = self._repo.get_statute_version(reference.statute_version_id) if reference.statute_version_id else None
            if version is not None:
                statutes.append({"citation_label": reference.citation_label, **_json_value(statute_date_display(version))})
        statute_versions_by_id = {version.id: version for version in self._dataset.statute_versions}
        old_law = old_law_basis_display(case.expected_law_basis_status, case.applied_statutes, statute_versions_by_id)
        return {
            "summaries": summaries,
            "risk_axes": [{"label": label, "status": status, "source_ids": source_ids} for label, (status, source_ids) in risk_axes],
            "action_badges": [
                {"action_text": judgment.action_text, "badge": _json_value(classify_action_badge((judgment,)))}
                for judgment in case.action_judgments
            ],
            "similarity_warning": _json_value(similarity_warning(score, self._dataset.display_policies.similarity_warnings)),
            "fact_differences": [_json_value(resolve_fact_difference_display(item, self._dataset.display_policies.placeholders)) for item in differences],
            "law_basis_status": case.expected_law_basis_status.value,
            "old_law": _json_value(old_law) if old_law is not None else None,
            "statutes": statutes,
            "appeal": _json_value(project_case_appeal(case)),
            "lower_instance_outcome": case.instance_outcome or "확인되지 않음",
        }
    @staticmethod
    def _request_json(environ: Mapping[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if str(environ.get("CONTENT_TYPE", "")).split(";", 1)[0].strip() != "application/json":
            return None, "415 Unsupported Media Type"
        try:
            length = int(str(environ.get("CONTENT_LENGTH", "0")))
            raw = environ["wsgi.input"].read(length)
            parsed = json.loads(raw.decode("utf-8"))
            return (parsed if isinstance(parsed, dict) else None), None
        except (KeyError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return None, "400 Bad Request"

    def _safe_error(self, start_response: StartResponse, status: str, code: str, *, retryable: bool) -> Iterable[bytes]:
        """Return a fixed, non-legal error contract without reflected request data."""
        payload: Dict[str, Any] = {
            "error": {"code": code, "message": "요청을 처리할 수 없습니다.", "retryable": retryable}
        }
        if retryable:
            payload["error"]["retryAction"] = "retry"
        return self._json(start_response, status, payload)

    @staticmethod
    def _bytes(start_response: StartResponse, status: str, content_type: str, body: bytes) -> Iterable[bytes]:
        start_response(status, [
            ("Content-Type", content_type),
            ("Content-Length", str(len(body))),
            ("Content-Security-Policy", _CONTENT_SECURITY_POLICY),
        ])
        return [body]

    def _json(self, start_response: StartResponse, status: str, payload: Dict[str, Any]) -> Iterable[bytes]:
        return self._bytes(start_response, status, "application/json; charset=utf-8", json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def create_application() -> MockWebApplication:
    """Build a fresh application from the bundled fixture at each process start."""
    validated = validate_dataset(build_mock_dataset())
    if not isinstance(validated, Ok):
        raise RuntimeError("Bundled mock dataset failed validation")
    return MockWebApplication(validated.value)


def run_server(settings: Optional[DeploymentSettings] = None) -> None:
    """Start the WSGI server using only non-secret deployment settings."""
    deployment = settings if settings is not None else load_deployment_settings()
    application = create_application()
    with make_server(deployment.host, deployment.port, application) as server:
        server.serve_forever()


if __name__ == "__main__":
    run_server()
