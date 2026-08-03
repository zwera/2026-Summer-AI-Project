"""Client-side safe error display examples (task 21.1).

There is no JavaScript runtime in this Python-only test environment, so this module
follows the existing pattern used by ``test_app_shell.py``/``test_deployment_configuration.py``:
it fetches the bundled ``/static/app.js``/``/static/app.css`` assets through the WSGI
application and asserts that the required safe-error-display behavior is present in the
shipped client code, plus that the server-rendered AppShell keeps its notices and entry
navigation visible regardless of in-page error state (requirement 18.12 is otherwise
covered by ``test_app_shell.py``'s unconditional AppShell assertions).
"""
from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Tuple

from web.server import MockWebApplication


def _asset(app: MockWebApplication, path: str) -> Tuple[str, Dict[str, str], str]:
    captured: List[Any] = []

    def start_response(status: str, headers: List[Tuple[str, str]]) -> None:
        captured.extend((status, dict(headers)))

    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": path, "CONTENT_LENGTH": "0", "wsgi.input": BytesIO()}
    body = b"".join(app(environ, start_response))
    return captured[0], captured[1], body.decode("utf-8")


def test_client_script_displays_server_http_status_message_and_retry_flag_unaltered(
    validated_mock_dataset: object,
) -> None:
    """Validates: Requirements 13.13, 13.15, 18.11, 18.12."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    status, _, script = _asset(app, "/static/app.js")
    assert status == "200 OK"

    # A dedicated error-display helper wraps every same-origin JSON request and
    # surfaces the server's own HTTP status, generalized message, and retryable
    # flag without rewriting or fabricating any of them.
    assert "class SafeHttpError" in script
    assert "renderHttpError" in script
    assert "renderStageError" in script
    assert "safeHttpError.status" in script
    assert "errorInfo.message" in script
    assert "errorInfo.retryable" in script

    # In-flow mock-RAG stage errors (rag_error/voice_error embedded in a 200 OK
    # response body) are routed to the same safe display instead of being treated
    # as ordinary results, and no substitute legal conclusion is ever rendered from
    # them: the panel only shows fixed status/stage/retry text, never search or
    # response fields.
    assert "payload.rag_error" in script
    assert "payload.voice_error" in script

    # Incomplete stages downstream of the failure are labeled with the fixed
    # `미완료` text required by 13.13/13.15, and no case/statute results are drawn
    # from the stage-error object itself.
    assert "미완료" in script

    # An explicit entry-screen navigation affordance accompanies every error panel.
    assert "error-panel__entry-link" in script
    assert 'link.href = "/"' in script

    status, _, css = _asset(app, "/static/app.css")
    assert status == "200 OK"
    assert ".error-panel" in css


def test_error_panel_never_renders_search_or_response_fields_for_stage_errors(
    validated_mock_dataset: object,
) -> None:
    """The stage-error renderer must not reference search/response payload fields,
    keeping the substitute-legal-conclusion count at zero (18.12/13.15)."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    _, _, script = _asset(app, "/static/app.js")

    start = script.index("const renderStageError = (container, stageError)")
    end = script.index("};", start)
    body = script[start:end]
    assert "payload.search" not in body
    assert "payload.response" not in body
    assert "case_number" not in body


def test_entry_and_results_pages_keep_public_legal_privacy_notices_and_navigation(
    validated_mock_dataset: object,
) -> None:
    """The server-rendered AppShell notices/navigation stay outside #query-feedback,
    so they remain visible even while an error panel occupies the feedback region
    (requirement 18.12)."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    for path in ("/", "/results"):
        status, _, page = _asset(app, path)
        assert status == "200 OK"
        for required in (
            "공개 배포 고지", "법률 안전 고지", "개인정보 처리 고지",
            "href='/'", "상황 검색", "직무 시나리오",
        ):
            assert required in page
