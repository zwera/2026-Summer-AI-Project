"""Accessibility affordances and session-scoped screen recovery (task 21.2).

Validates: Requirements 14.3, 14.4, 14.5, 14.9, 14.10, 15.9

The server-side pieces (fixed HTML structure, ``role="status"``/``role="alert"``
attributes on server-rendered elements, and the local session-recovery script/style
being served as static assets) are checked here with the same WSGI harness style as
``tests/test_app_shell.py``. Client-only behavior (writing/reading
``window.sessionStorage``, restoring form state after a refresh) requires a real
browser DOM and is out of scope for these server-side example tests; it is covered by
the manual/automated accessibility checklist in task 21.3.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Tuple

from web.server import MockWebApplication


def _page(app: MockWebApplication, path: str) -> Tuple[str, Dict[str, str], str]:
    captured: List[Any] = []

    def start_response(status: str, headers: List[Tuple[str, str]]) -> None:
        captured.extend((status, dict(headers)))

    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": path, "CONTENT_LENGTH": "0", "wsgi.input": BytesIO()}
    body = b"".join(app(environ, start_response))
    return captured[0], captured[1], body.decode("utf-8")


def test_entry_and_results_expose_skip_link_and_status_role_for_non_error_updates(
    validated_mock_dataset: object,
) -> None:
    """A keyboard skip link and non-interrupting status roles are present on both screens."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    for path in ("/", "/results"):
        _, _, page = _page(app, path)
        assert "class='skip-link' href='#main-content'" in page
        assert "id='main-content'" in page

    _, _, entry_page = _page(app, "/")
    assert "id='query-feedback' class='query-feedback' aria-live='polite'" in entry_page

    _, _, results_page = _page(app, "/results")
    assert "id='scenario-status' class='scenario-status' role='status'" in results_page


def test_static_stylesheet_declares_focus_visibility_forced_colors_and_reduced_motion(
    validated_mock_dataset: object,
) -> None:
    """Requirement 14.5/14.9: keyboard focus, non-color-only forced-colors support, and
    reduced-motion accommodation must all be declared in the shared stylesheet."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    status, headers, css = _page(app, "/static/app.css")
    assert status == "200 OK"
    assert headers["Content-Type"].startswith("text/css")
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@media (forced-colors: active)" in css
    assert ":focus-visible" in css
    # Non-color-only distinctions: forced-colors block must add visible borders/outlines,
    # not rely on background color alone.
    assert "outline: 3px solid CanvasText" in css


def test_static_client_script_defines_session_scoped_state_and_fixed_reset_notice(
    validated_mock_dataset: object,
) -> None:
    """Requirement 14.10/15.9: refresh-time recovery must use session-scoped storage only
    (no persistent storage) and fall back to the exact fixed notice text when no session
    state exists to restore the current screen."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    status, headers, script = _page(app, "/static/app.js")
    assert status == "200 OK"
    assert headers["Content-Type"].startswith("application/javascript")
    assert "window.sessionStorage" in script
    assert "localStorage" not in script
    assert "임시 화면 상태가 초기화되었습니다." in script
    # Status/alert roles are applied by the client script for RAG-safe, non-interrupting
    # updates versus data errors requiring immediate attention (Requirement 14.3/15.9).
    assert 'setAttribute("role", "alert")' in script
    assert 'setAttribute("role", "status")' in script
