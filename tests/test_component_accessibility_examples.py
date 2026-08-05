"""Component/accessibility example tests for task 21.3.

Validates: Requirements 14.5, 14.6, 6.15, 5.10, 3.12

There is no in-process browser DOM in this Python-only test environment (the client
layer is intentionally HTML + CSS + minimal vanilla JavaScript with no bundler/build
step - see ``design.md``'s technology constraints). These example tests therefore
follow the same pattern already used by ``test_app_shell.py``,
``test_accessibility_session_recovery.py`` and ``test_error_display.py``: they fetch
the server-rendered HTML and the shipped ``/static/app.js``/``/static/app.css`` assets
through the WSGI harness and assert that the required behavioral contracts are present
in the shipped source.

Covered here as static/server-side example checks:
  - Fixed notice text (14.6): instance caution notice, empty-state text.
  - Full-text initial collapse (3.9/3.12): case-detail and inline citation source
    viewers default to closed.
  - Summary tabs / full-text independence (5.10): the summary tab switcher only
    replaces the summary body, never the separate full-text section.
  - Empty state (3.12): fixed "일치하는 목업 자료 없음" text for empty case/statute lists.
  - Action badge non-color-only distinction (6.15): badges carry a text/icon prefix
    in addition to color, and forced-colors mode adds a visible border.
  - Two selection-review actions (9.1/9.2): "사실 확인 재검토" and "상세 설명" buttons.
  - Source focus round trip (3.14/13.5): highlight-and-return affordance.
  - Appellate-change emphasis (12.13/12.14): `.appeal-changed` styling and text.
  - Copy/voice failure fallback (11.16/11.17/11.20): manual fallback text kept visible.

What this module intentionally does NOT attempt (see the accessibility checklist file
committed alongside it, ``tests/ACCESSIBILITY_MANUAL_CHECKLIST.md``): real keyboard
navigation/focus-order verification, `role="status"`/`role="alert"` live announcement
timing, and axe-core (or equivalent) automated accessibility scans. Those require a
real browser DOM/assistive-technology stack and cannot be exercised by this Python
test harness.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Tuple

from web.server import MockWebApplication


def _page(app: MockWebApplication, path: str) -> Tuple[str, Dict[str, str], str]:
    captured: List[Any] = []

    def start_response(status: str, headers: List[Tuple[str, str]]) -> None:
        captured.extend((status, dict(headers)))

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "CONTENT_LENGTH": "0",
        "wsgi.input": BytesIO(),
    }
    body = b"".join(app(environ, start_response))
    return captured[0], captured[1], body.decode("utf-8")


def test_fixed_instance_caution_notice_text_is_present(
    validated_mock_dataset: object,
) -> None:
    """Requirement 14.6/12.1-12.4: the fixed instance/finality caution notice text
    must appear verbatim on the shared AppShell."""
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    _, _, page = _page(app, "/")
    assert (
        "판례는 심급 및 절차 경과에 따라 결론이 달라질 수 있으므로, "
        "상급심 판단과 확정 여부를 함께 확인해야 합니다."
    ) in page


def test_fixed_empty_results_text_is_shipped_in_client_script() -> None:
    """Requirement 3.12/14.6: the empty-state text is fixed and shared for both the
    case and statute result lists (`renderEmpty`)."""
    app_js = _read_static_source("app.js")
    assert "일치하는 목업 자료 없음" in app_js
    start = app_js.index("const renderEmpty = ")
    end = app_js.index(";", app_js.index("return section", start))
    assert "일치하는 목업 자료 없음" in app_js[start:end]


def test_full_text_source_viewers_default_to_closed() -> None:
    """Requirement 3.9/3.12: both the case-detail full-text section and inline
    citation source viewers must start collapsed (`details.open = false`)."""
    app_js = _read_static_source("app.js")

    # Case detail full-text section: renderFullTextSection(caseId, container) ->
    # buildSourceViewer(source, false) for every source in the panel.
    full_text_start = app_js.index("const renderFullTextSection = ")
    full_text_end = app_js.index("};", full_text_start)
    full_text_body = app_js[full_text_start:full_text_end]
    assert "buildSourceViewer(source, false)" in full_text_body

    # Inline citation viewer opened via showCitationSource() also starts closed;
    # highlightAnchorAndReturn() is what opens it once a specific citation is chosen.
    citation_start = app_js.index("const showCitationSource = ")
    citation_end = app_js.index("};", citation_start)
    citation_body = app_js[citation_start:citation_end]
    assert "buildSourceViewer(payload.source, false)" in citation_body

    # buildSourceViewer itself honors the openByDefault flag via `details.open`.
    builder_start = app_js.index("const buildSourceViewer = ")
    builder_end = app_js.index("};", builder_start)
    assert "details.open = Boolean(openByDefault)" in app_js[builder_start:builder_end]


def test_summary_tabs_only_replace_summary_body_not_full_text_section() -> None:
    """Requirement 5.10: switching between 3/10/detailed summary tabs must only
    touch the summary body element; the full-text section is built and appended
    separately and is never re-rendered or hidden by `showSummary`."""
    app_js = _read_static_source("app.js")

    detail_start = app_js.index("const renderCaseDetail = ")
    detail_end = app_js.index("return panel; }", detail_start)
    detail_body = app_js[detail_start:detail_end]

    show_summary_start = detail_body.index("const showSummary = ")
    show_summary_end = detail_body.index("};", show_summary_start)
    show_summary_body = detail_body[show_summary_start:show_summary_end]
    assert "body.replaceChildren()" in show_summary_body
    assert "fullText" not in show_summary_body
    assert "fullTextBody" not in show_summary_body

    # The full-text section is a separate DOM subtree appended once per case detail,
    # independent of which summary tab is active.
    assert "fullText.append(element(\"h6\", \"전문\"))" in detail_body
    assert "panel.append(summary, risks, differences, law, appeal, fullText)" in detail_body


def test_action_badges_are_distinguished_by_text_and_icon_not_color_alone() -> None:
    """Requirement 6.15: each personal-liability action badge label is prefixed with
    a distinct icon/text glyph (not conveyed by color alone), and forced-colors mode
    adds a visible border to the badge in addition to its color."""
    app_js = _read_static_source("app.js")
    detail_start = app_js.index("const renderCaseDetail = ")
    detail_end = app_js.index("return panel; }", detail_start)
    badge_body = app_js[detail_start:detail_end]
    assert 'item.badge.state === "문제_행동" ? "⚠"' in badge_body
    assert 'item.badge.state === "적법_행동" ? "✓"' in badge_body
    assert '"ⓘ"' in badge_body
    assert 'badge.className = `action-badge action-badge--${item.badge.state}`' in badge_body

    app_css = _read_static_source("app.css")
    assert ".action-badge--문제_행동" in app_css
    assert ".action-badge--적법_행동" in app_css
    assert ".action-badge--정보_없음, .action-badge--분류_불가" in app_css
    forced_colors_start = app_css.index("@media (forced-colors: active)")
    forced_colors_end = app_css.index("}\n}", forced_colors_start) + 2
    assert ".action-badge" in app_css[forced_colors_start:forced_colors_end]
    assert "border: 1px solid CanvasText" in app_css[forced_colors_start:forced_colors_end]


def test_selection_review_offers_exactly_two_named_actions() -> None:
    """Requirement 9.1/9.2: the selection review panel must expose both "사실 확인
    재검토" and "상세 설명" actions, mapped to the FACT_CHECK/EXPLANATION modes."""
    app_js = _read_static_source("app.js")
    render_response_start = app_js.index("const renderResponse = ")
    render_response_end = app_js.index("section.append(text, panel)", render_response_start)
    body = app_js[render_response_start:render_response_end]
    assert 'element("button", "사실 확인 재검토")' in body
    assert 'fact.dataset.mode = "FACT_CHECK"' in body
    assert 'element("button", "상세 설명")' in body
    assert 'explain.dataset.mode = "EXPLANATION"' in body


def test_source_focus_highlight_and_return_round_trip_is_implemented() -> None:
    """Requirement 3.14/13.5: choosing a citation must open the source viewer,
    highlight the specific anchor, move focus there, and offer a "돌아가기" control
    that returns focus to the originating citation."""
    app_js = _read_static_source("app.js")
    fn_start = app_js.index("const highlightAnchorAndReturn = ")
    fn_end = app_js.index("};", fn_start)
    body = app_js[fn_start:fn_end]
    assert "viewer.open = true" in body
    assert 'classList.add("source-anchor--highlight")' in body
    assert "target.focus()" in body
    assert 'element("button", "돌아가기")' in body
    assert "returnTarget.focus()" in body

    app_css = _read_static_source("app.css")
    assert ".source-anchor--highlight" in app_css


def test_appellate_relation_changed_decision_is_visually_and_textually_emphasized() -> None:
    """Requirement 12.13/12.14: an appellate decision whose `relation_to_lower_instance`
    is "변경" must render with a distinct `.appeal-changed` class and an explicit
    "원심 결과(...)에서 변경" text, not color alone."""
    app_js = _read_static_source("app.js")
    detail_start = app_js.index("const renderCaseDetail = ")
    detail_end = app_js.index("return panel; }", detail_start)
    body = app_js[detail_start:detail_end]
    assert 'decision.relation_to_lower_instance === "변경"' in body
    assert 'line.className = "appeal-changed"' in body
    assert "에서 변경" in body

    app_css = _read_static_source("app.css")
    assert ".appeal-changed {" in app_css


def test_report_copy_and_download_failures_keep_manual_fallback_visible() -> None:
    """Requirement 11.16/11.17: a failed clipboard copy or file download must keep
    the report body/timeline untouched and reveal the manual selectable-text
    fallback message."""
    app_js = _read_static_source("app.js")
    fn_start = app_js.index("const buildReportSection = ")
    fn_end = app_js.index("return section;", fn_start)
    body = app_js[fn_start:fn_end]

    copy_start = body.index("copyButton.addEventListener")
    copy_end = body.index("});", copy_start)
    copy_body = body[copy_start:copy_end]
    assert "복사에 실패했습니다" in copy_body
    assert "manualFallback.hidden = false" in copy_body

    download_start = body.index("downloadButton.addEventListener")
    download_end = body.index("section.append(generateButton", download_start)
    download_body = body[download_start:download_end]
    assert "다운로드에 실패했습니다" in download_body
    assert "manualFallback.hidden = false" in download_body

    assert "복사/다운로드를 사용할 수 없는 경우" in body


def test_voice_recognition_failure_offers_manual_text_input_alternative() -> None:
    """When the browser's SpeechRecognition either is unsupported or reports an
    error, the client must surface a status message and direct the user to type
    the situation manually instead of fabricating a recognition result."""
    app_js = _read_static_source("app.js")
    assert "이 브라우저는 음성 인식을 지원하지 않습니다. 상황을 직접 입력해 주세요." in app_js
    recognition_start = app_js.index('recognition.addEventListener("error"')
    recognition_end = app_js.index('recognition.addEventListener("end"', recognition_start)
    body = app_js[recognition_start:recognition_end]
    assert "상황을 직접 입력해 주세요." in body


def _read_static_source(filename: str) -> str:
    """Read a bundled static asset through the WSGI app the same way the browser
    would (rather than opening the file directly), matching the pattern used by
    ``test_app_shell.py``/``test_accessibility_session_recovery.py``."""
    from data.validated_dataset import validate_dataset
    from domain.result import Ok
    from fixtures.mock_dataset import build_mock_dataset

    result = validate_dataset(build_mock_dataset())
    assert isinstance(result, Ok)
    app = MockWebApplication(result.value)  # type: ignore[arg-type]
    _, _, source = _page(app, f"/static/{filename}")
    return source
