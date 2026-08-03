"""HTTP routing and safe failure examples for the WSGI server."""
from __future__ import annotations

from io import BytesIO
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from web.config import load_deployment_settings
from web.server import MockWebApplication, create_application

_STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"
_EXTERNAL_ORIGIN_PATTERN = re.compile(r"(?:https?:)?//(?!localhost|127\.0\.0\.1|0\.0\.0\.0)[\w.-]+")


def _request(app: MockWebApplication, method: str, path: str, body: bytes = b"", content_type: str = "") -> Tuple[str, Dict[str, str], bytes]:
    captured: List[Any] = []

    def start_response(status: str, headers: List[Tuple[str, str]]) -> None:
        captured.extend((status, dict(headers)))

    response = b"".join(app({"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_TYPE": content_type, "CONTENT_LENGTH": str(len(body)), "wsgi.input": BytesIO(body)}, start_response))
    return captured[0], captured[1], response


def _safe_error(body: bytes) -> Dict[str, Any]:
    payload = json.loads(body)
    assert set(payload) == {"error"}
    assert set(payload["error"]) in ({"code", "message", "retryable"}, {"code", "message", "retryable", "retryAction"})
    assert payload["error"]["message"] == "요청을 처리할 수 없습니다."
    return payload["error"]


def test_entry_results_refresh_and_static_asset_return_200(validated_mock_dataset: object) -> None:
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    for path in ("/", "/results", "/static/app.js"):
        status, _, _ = _request(app, "GET", path)
        assert status == "200 OK"


def test_supported_query_returns_fixture_provenance(validated_mock_dataset: object) -> None:
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    raw = validated_mock_dataset.queries[0].variants[0].raw_example  # type: ignore[attr-defined]
    status, headers, body = _request(app, "POST", "/api/query", json.dumps({"query": raw}).encode(), "application/json")
    payload = json.loads(body)
    assert status == "200 OK"
    assert headers["Content-Type"].startswith("application/json")
    assert payload["provenance"]["query"] == [str(validated_mock_dataset.queries[0].id)]  # type: ignore[attr-defined]
    assert set(payload["provenance"]["cases"]) == {str(case["case_id"]) for case in payload["search"]["cases"]}
    assert payload["provenance"]["responseClaims"]


def test_invalid_api_body_is_rejected_without_processing_query(validated_mock_dataset: object) -> None:
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    status, _, body = _request(app, "POST", "/api/query", b'{"query": 5}', "application/json")
    assert status == "400 Bad Request"
    error = _safe_error(body)
    assert error == {"code": "INVALID_REQUEST", "message": "요청을 처리할 수 없습니다.", "retryable": False}


def test_safe_http_errors_are_sanitized_and_mark_retryability(validated_mock_dataset: object) -> None:
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    cases = [
        ("POST", "/api/query", b"", "text/plain", "415 Unsupported Media Type", "UNSUPPORTED_MEDIA_TYPE", False),
        ("GET", "/api/query", b"", "", "405 Method Not Allowed", "METHOD_NOT_ALLOWED", False),
        ("GET", "/missing", b"", "", "404 Not Found", "NOT_FOUND", False),
    ]
    for method, path, body, content_type, expected_status, code, retryable in cases:
        status, _, response = _request(app, method, path, body, content_type)
        error = _safe_error(response)
        assert status == expected_status
        assert error["code"] == code
        assert error["retryable"] is retryable
        assert "retryAction" not in error


def test_dataset_unavailable_and_internal_failures_are_retryable_and_safe(validated_mock_dataset: object) -> None:
    unavailable = MockWebApplication(None)
    status, _, body = _request(unavailable, "GET", "/")
    error = _safe_error(body)
    assert status == "503 Service Unavailable"
    assert error == {"code": "SERVICE_UNAVAILABLE", "message": "요청을 처리할 수 없습니다.", "retryable": True, "retryAction": "retry"}

    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    app._page = lambda path, start_response: (_ for _ in ()).throw(RuntimeError("secret=abc query=private"))  # type: ignore[method-assign]
    status, _, body = _request(app, "GET", "/")
    error = _safe_error(body)
    assert status == "500 Internal Server Error"
    assert error == {"code": "INTERNAL_ERROR", "message": "요청을 처리할 수 없습니다.", "retryable": True, "retryAction": "retry"}
    assert b"secret" not in body and b"private" not in body


def test_server_error_statuses_return_only_safe_error_contracts_and_dataset_failure_has_no_legal_results(
    validated_mock_dataset: object,
) -> None:
    """Validates: Requirements 18.1, 18.5, 18.6, 18.7."""
    sensitive = "비공개 질의와 secret=not-for-response"
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    cases = [
        ("POST", "/api/query", b'{"query": 1}', "application/json", "400 Bad Request", "INVALID_REQUEST"),
        ("POST", "/api/query", b'{"query": "x"}', "text/plain", "415 Unsupported Media Type", "UNSUPPORTED_MEDIA_TYPE"),
        ("GET", "/api/query", b"", "", "405 Method Not Allowed", "METHOD_NOT_ALLOWED"),
        ("GET", "/not-defined", b"", "", "404 Not Found", "NOT_FOUND"),
    ]
    for method, path, body, content_type, expected_status, expected_code in cases:
        status, _, response = _request(app, method, path, body, content_type)
        error = _safe_error(response)
        assert status == expected_status
        assert error["code"] == expected_code
        assert error["retryable"] is False
        assert b"search" not in response and b"response" not in response
        assert sensitive.encode("utf-8") not in response

    app._page = lambda path, start_response: (_ for _ in ()).throw(RuntimeError(sensitive))  # type: ignore[method-assign]
    status, _, response = _request(app, "GET", "/")
    error = _safe_error(response)
    assert status == "500 Internal Server Error"
    assert error["code"] == "INTERNAL_ERROR"
    assert error["retryable"] is True
    assert b"search" not in response and b"response" not in response
    assert sensitive.encode("utf-8") not in response

    unavailable = MockWebApplication(None)
    status, _, response = _request(unavailable, "POST", "/api/query", b'{"query":"ignored"}', "application/json")
    error = _safe_error(response)
    assert status == "503 Service Unavailable"
    assert error["code"] == "SERVICE_UNAVAILABLE"
    assert error["retryable"] is True
    assert error["retryAction"] == "retry"
    payload = json.loads(response)
    assert "search" not in payload and "response" not in payload and "report" not in payload


def test_legal_output_and_mock_rag_result_are_deterministic_across_deployment_settings() -> None:
    """Validates: Requirements 16.3, 16.10."""
    first_settings = load_deployment_settings({
        "POLICE_BOT_PUBLIC_URL": "http://127.0.0.1:8000",
        "POLICE_BOT_HOST": "127.0.0.1",
        "POLICE_BOT_PORT": "8000",
        "POLICE_BOT_HTTPS_ENABLED": "false",
        "POLICE_BOT_RUN_MODE": "development",
    })
    second_settings = load_deployment_settings({
        "POLICE_BOT_PUBLIC_URL": "https://demo.example.test",
        "POLICE_BOT_HOST": "0.0.0.0",
        "POLICE_BOT_PORT": "8443",
        "POLICE_BOT_HTTPS_ENABLED": "true",
        "POLICE_BOT_RUN_MODE": "production",
    })
    assert first_settings != second_settings

    first_app, second_app = create_application(), create_application()
    raw = first_app._dataset.queries[0].variants[0].raw_example  # type: ignore[union-attr]
    request_body = json.dumps({"query": raw}).encode("utf-8")
    first_status, _, first_response = _request(first_app, "POST", "/api/query", request_body, "application/json")
    second_status, _, second_response = _request(second_app, "POST", "/api/query", request_body, "application/json")

    assert first_status == second_status == "200 OK"
    first_payload, second_payload = json.loads(first_response), json.loads(second_response)
    assert first_payload == second_payload
    assert first_payload["search"]
    assert first_payload["response"]
    assert first_payload["provenance"]


def test_request_logs_only_allowlisted_metadata_and_never_sensitive_content(
    validated_mock_dataset: object, caplog: Any
) -> None:
    """Raw queries, selections, and report text must not enter application logs."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    sensitive_query = "비공개 사건 설명: 홍길동의 주소"
    selected_text = "선택한 민감 문구"
    report_text = "보고서용 사실관계 본문"

    with caplog.at_level(logging.INFO, logger="web.server"):
        status, _, _ = _request(
            app,
            "POST",
            "/api/query",
            json.dumps(
                {"query": sensitive_query, "selection": selected_text, "report": report_text}
            ).encode("utf-8"),
            "application/json",
        )

    assert status == "200 OK"
    records = [record for record in caplog.records if record.name == "web.server"]
    assert len(records) == 1
    metadata = records[0].request_metadata
    assert set(metadata) == {"method", "path", "status", "content_length"}
    assert metadata["method"] == "POST"
    assert metadata["path"] == "/api/query"
    assert metadata["status"] == "200"
    rendered_log = caplog.text
    for sensitive_value in (sensitive_query, selected_text, report_text):
        assert sensitive_value not in rendered_log


def test_voice_fixture_action_returns_recognized_text_verbatim_or_manual_input_error(
    validated_mock_dataset: object,
) -> None:
    """Validates: Requirements 11.20, 15.8, 15.10."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    success = next(item for item in validated_mock_dataset.voice_fixtures if not item.failure)  # type: ignore[attr-defined]
    status, _, body = _request(
        app, "POST", "/api/action",
        json.dumps({"type": "SELECT_VOICE_FIXTURE", "fixtureId": str(success.id)}).encode("utf-8"),
        "application/json",
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["recognized_text"] == success.recognized_text
    assert payload["interpretation"]["kind"] == "SUPPORTED"
    assert payload["provenance"]["voiceFixture"] == [str(success.id)]

    failed = next(item for item in validated_mock_dataset.voice_fixtures if item.failure)  # type: ignore[attr-defined]
    status, _, body = _request(
        app, "POST", "/api/action",
        json.dumps({"type": "SELECT_VOICE_FIXTURE", "fixtureId": str(failed.id)}).encode("utf-8"),
        "application/json",
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["voice_error"]["stage"] == "INPUT"
    assert "recognized_text" not in payload


def test_scenario_comparison_returns_server_partition_and_auxiliary_intersection(
    validated_mock_dataset: object,
) -> None:
    """Validates: Requirements 4.1, 4.5, 4.7, 4.11, 4.13."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    scenario = validated_mock_dataset.scenarios[0].id.value  # type: ignore[attr-defined]
    body = json.dumps({
        "type": "GET_SCENARIO_COMPARISON",
        "scenario": scenario,
        "auxiliaryFilter": "형사",
    }).encode("utf-8")
    status, _, response = _request(app, "POST", "/api/action", body, "application/json")
    payload = json.loads(response)

    assert status == "200 OK"
    assert payload["scenario"] == scenario
    assert payload["auxiliaryFilter"] == "형사"
    partition = payload["partition"]
    returned = partition["lawful"] + partition["unlawful"] + [entry["case"] for entry in partition["mixed"]]
    assert all(scenario in case["scenario_ids"] for case in returned)
    assert all("형사" in (case["traditional_areas"] or []) for case in returned)
    ids = [case["id"] for case in returned]
    assert len(ids) == len(set(ids))


def test_search_payload_includes_display_ready_appeal_and_finality_card_values(
    validated_mock_dataset: object,
) -> None:
    """Validates: Requirements 12.15, 12.16, 12.17."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    raw = validated_mock_dataset.queries[0].variants[0].raw_example  # type: ignore[attr-defined]
    status, _, body = _request(app, "POST", "/api/query", json.dumps({"query": raw}).encode(), "application/json")
    payload = json.loads(body)
    assert status == "200 OK"
    appeals = payload["search"]["appeals_by_case"]
    assert set(appeals) == {case["case_id"] for case in payload["search"]["cases"]}
    for appeal in appeals.values():
        if appeal["appellate"]["state"] == "정보_없음":
            assert appeal["appellate"]["decisions"] == []
        if appeal["finality"] == "정보_없음":
            assert appeal["finality_badge"] is None
        else:
            assert appeal["finality_badge"]["finality"] == appeal["finality"]


def test_case_detail_returns_only_selected_case_sources_and_provenance(
    validated_mock_dataset: object,
) -> None:
    """Validates: Requirements 3.9, 3.14, 5.10, 13.5."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    case = validated_mock_dataset.cases[0]  # type: ignore[attr-defined]
    status, _, body = _request(
        app,
        "POST",
        "/api/action",
        json.dumps({"type": "GET_CASE_DETAIL", "caseId": str(case.id)}).encode(),
        "application/json",
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["case"]["id"] == str(case.id)
    assert payload["provenance"]["case"] == [str(case.id)]
    assert [source["id"] for source in payload["sources"]] == [str(source_id) for source_id in case.source_ids]
    for source in payload["sources"]:
        assert source["owner"]["type"] == "CASE"
        assert source["owner"]["id"] == str(case.id)
        assert source["anchors"]


def test_case_detail_rejects_unknown_case_id(validated_mock_dataset: object) -> None:
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    status, _, body = _request(
        app, "POST", "/api/action", b'{"type":"GET_CASE_DETAIL","caseId":"missing"}', "application/json"
    )
    assert status == "400 Bad Request"
    assert _safe_error(body)["code"] == "INVALID_REQUEST"


def test_selection_review_action_validates_current_response_and_returns_fixture_results(
    validated_mock_dataset: object,
) -> None:
    """Validates: Requirements 9.1, 9.2, 9.3, 9.16."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    query = validated_mock_dataset.queries[0]  # type: ignore[attr-defined]
    review_fixture = next(
        fixture for fixture in validated_mock_dataset.review_fixtures  # type: ignore[attr-defined]
        if fixture.response_template_id == query.match.response_template_id
    )
    claim = review_fixture.claims[0]
    body = json.dumps({
        "type": "RUN_SELECTION_REVIEW",
        "queryId": str(query.id),
        "selectedText": claim.text,
        "selectedClaimIds": [str(claim.id)],
        "mode": "FACT_CHECK",
    }).encode("utf-8")
    status, _, response = _request(app, "POST", "/api/action", body, "application/json")
    payload = json.loads(response)
    assert status == "200 OK"
    assert payload["selection_pending"] is False
    assert payload["result"]["claims"][0]["claim_id"] == str(claim.id)
    assert payload["result"]["claims"][0]["status"] == "근거_일치"

    explanation_body = json.dumps({**json.loads(body), "mode": "EXPLANATION"}).encode("utf-8")
    status, _, response = _request(app, "POST", "/api/action", explanation_body, "application/json")
    explanation = json.loads(response)
    assert status == "200 OK"
    assert explanation["explanations"][0]["claim_id"] == str(claim.id)
    assert explanation["explanations"][0]["found"] is True

    invalid_body = json.dumps({**json.loads(body), "selectedClaimIds": ["foreign-claim"]}).encode("utf-8")
    status, _, response = _request(app, "POST", "/api/action", invalid_body, "application/json")
    assert status == "400 Bad Request"
    assert _safe_error(response)["code"] == "INVALID_REQUEST"


def test_timeline_actions_return_fixture_projection_and_apply_edit(
    validated_mock_dataset: object,
) -> None:
    """Validates: Requirements 11.13, 11.20, 15.7."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    query = next(query for query in validated_mock_dataset.queries if query.recognized_events)  # type: ignore[attr-defined]
    status, _, body = _request(
        app, "POST", "/api/action", json.dumps({"type": "GET_TIMELINE", "queryId": str(query.id)}).encode(), "application/json"
    )
    payload = json.loads(body)
    assert status == "200 OK"
    timeline = payload["timeline"]
    assert [event["id"] for event in timeline["ordered"]] == ["event-arrest-custody", "event-arrest-notice"]
    assert timeline["unknown_time"][0]["issue_projection"]["no_issue_label"] == "연결 쟁점 없음"
    assert timeline["ordered"][0]["issue_projection"]["issues"][0]["source_ids"] == ["source-arrest-lawful"]

    status, _, body = _request(
        app, "POST", "/api/action", json.dumps({
            "type": "UPDATE_TIMELINE_EVENT", "queryId": str(query.id), "eventId": "event-arrest-notice",
            "explicitTime": "2024-01-01T13:50:00", "actor": "수정 경찰관", "action": "수정 고지", "originalText": "수정된 원문",
        }).encode(), "application/json"
    )
    updated = json.loads(body)
    assert status == "200 OK"
    edited = updated["timeline"]["ordered"][0]
    assert edited["id"] == "event-arrest-notice"
    assert (edited["explicit_time"], edited["actor"], edited["action"], edited["original_text"]) == (
        "2024-01-01T13:50:00", "수정 경찰관", "수정 고지", "수정된 원문"
    )


def test_report_action_returns_unmodified_body_with_as_of_date_and_notice_and_reflects_edits(
    validated_mock_dataset: object,
) -> None:
    """Validates: Requirements 11.14, 11.15, 11.16, 1.7."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    query = next(query for query in validated_mock_dataset.queries if query.recognized_events)  # type: ignore[attr-defined]

    status, _, body = _request(
        app, "POST", "/api/action", json.dumps({"type": "GET_REPORT", "queryId": str(query.id)}).encode(), "application/json"
    )
    payload = json.loads(body)
    assert status == "200 OK"
    report = payload["report"]
    assert report["as_of_date"] == validated_mock_dataset.as_of_date  # type: ignore[attr-defined]
    assert report["safety_notice"] == validated_mock_dataset.legal_safety_notice  # type: ignore[attr-defined]
    assert report["body"].endswith(f"데이터 기준일: {validated_mock_dataset.as_of_date}\n{validated_mock_dataset.legal_safety_notice}")  # type: ignore[attr-defined]
    assert set(report["event_ids"]) == {str(event.id) for event in query.recognized_events}

    status, _, body = _request(
        app, "POST", "/api/action", json.dumps({
            "type": "GET_REPORT", "queryId": str(query.id),
            "events": [{"eventId": "event-arrest-notice", "originalText": "보고서용 수정 원문"}],
        }).encode(), "application/json"
    )
    edited_report = json.loads(body)["report"]
    assert status == "200 OK"
    assert "보고서용 수정 원문" in edited_report["body"]


def test_report_action_rejects_invalid_query_id(validated_mock_dataset: object) -> None:
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    status, _, body = _request(
        app, "POST", "/api/action", json.dumps({"type": "GET_REPORT", "queryId": "not-a-real-query"}).encode(), "application/json"
    )
    assert status == "400 Bad Request"
    assert _safe_error(body)["code"] == "INVALID_REQUEST"


def test_case_detail_isolates_cross_case_source_ids_as_source_error(
    validated_mock_dataset: object,
) -> None:
    """Validates: Requirements 3.14, 13.5."""
    import dataclasses

    case_a = validated_mock_dataset.cases[0]  # type: ignore[attr-defined]
    case_b = validated_mock_dataset.cases[1]  # type: ignore[attr-defined]
    foreign_source_id = case_b.source_ids[0]
    tampered_case = dataclasses.replace(case_a, source_ids=case_a.source_ids + (foreign_source_id,))
    tampered_cases = tuple(
        tampered_case if case.id == case_a.id else case
        for case in validated_mock_dataset.cases  # type: ignore[attr-defined]
    )
    tampered_dataset = dataclasses.replace(validated_mock_dataset, cases=tampered_cases)  # type: ignore[misc]

    app = MockWebApplication(tampered_dataset)  # type: ignore[arg-type]
    status, _, body = _request(
        app,
        "POST",
        "/api/action",
        json.dumps({"type": "GET_CASE_DETAIL", "caseId": str(case_a.id)}).encode(),
        "application/json",
    )
    payload = json.loads(body)

    assert status == "200 OK"
    assert [source["id"] for source in payload["sources"]] == [str(source_id) for source_id in case_a.source_ids]
    assert payload["source_error"]["code"] == "SOURCE_DATA_ERROR"
    assert payload["source_error"]["sourceIds"] == [str(foreign_source_id)]


def test_all_responses_include_same_origin_csp_header(validated_mock_dataset: object) -> None:
    """Validates: Requirements 1.5, 1.10, 1.12, 14.1, 14.2."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    for method, path, body, content_type in (
        ("GET", "/", b"", ""),
        ("GET", "/results", b"", ""),
        ("GET", "/static/app.js", b"", ""),
        ("GET", "/static/app.css", b"", ""),
    ):
        _, headers, _ = _request(app, method, path, body, content_type)
        assert headers["Content-Security-Policy"] == "default-src 'self'; connect-src 'self'"

    raw = validated_mock_dataset.queries[0].variants[0].raw_example  # type: ignore[attr-defined]
    _, headers, _ = _request(app, "POST", "/api/query", json.dumps({"query": raw}).encode(), "application/json")
    assert headers["Content-Security-Policy"] == "default-src 'self'; connect-src 'self'"

    unavailable = MockWebApplication(None)
    _, headers, _ = _request(unavailable, "GET", "/")
    assert headers["Content-Security-Policy"] == "default-src 'self'; connect-src 'self'"


def test_static_assets_and_rendered_html_have_no_external_origin_references(
    validated_mock_dataset: object,
) -> None:
    """No CDN, remote font/icon, external <script src>, or service worker registration
    may exist in shipped static assets or server-rendered HTML.

    Validates: Requirements 1.5, 1.10, 1.12, 14.1, 14.2.
    """
    for static_file in ("app.js", "app.css"):
        text = (_STATIC_ROOT / static_file).read_text(encoding="utf-8")
        assert not _EXTERNAL_ORIGIN_PATTERN.search(text), f"external origin reference found in {static_file}"
        assert "serviceWorker" not in text
        assert "navigator.serviceWorker" not in text

    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    for path in ("/", "/results"):
        _, _, body = _request(app, "GET", path)
        html = body.decode("utf-8")
        assert not _EXTERNAL_ORIGIN_PATTERN.search(html), f"external origin reference found in {path} HTML"
        assert "serviceWorker" not in html
