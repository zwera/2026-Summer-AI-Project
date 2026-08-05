"""Examples for the server-rendered common AppShell (task 18.1)."""
from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Tuple

from web.server import MockWebApplication


def _page(
    app: MockWebApplication, path: str
) -> Tuple[str, Dict[str, str], str]:
    captured: List[Any] = []

    def start_response(status: str, headers: List[Tuple[str, str]]) -> None:
        captured.extend((status, dict(headers)))

    environ = {
        "REQUEST_METHOD": "GET", "PATH_INFO": path, "CONTENT_LENGTH": "0",
        "wsgi.input": BytesIO(),
    }
    body = b"".join(app(environ, start_response))
    return captured[0], captured[1], body.decode("utf-8")


def test_entry_and_results_show_shared_notices_scope_and_navigation(
    validated_mock_dataset: object,
) -> None:
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    for path in ("/", "/results"):
        status, _, page = _page(app, path)
        assert status == "200 OK"
        for required in (
            "목업 응답", "데이터 기준일", "실시간 판례·법령 동기화 없음",
            "목표 데이터 범위", "공개적으로 확인 가능한 제1심·항소심·상고심 판례",
            "현재 구현 데이터 범위", "사전에 정의된 목업 전체 심급 판례 샘플",
            "상급심 판단과 확정 여부를 함께 확인해야 합니다.",
            "공개 배포 고지", "법률 안전 고지", "개인정보 처리 고지",
            "상황 검색", "직무 시나리오",
        ):
            assert required in page
        assert "<details open>" in page


def test_app_shell_uses_local_responsive_stylesheet(
    validated_mock_dataset: object,
) -> None:
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    _, _, page = _page(app, "/")
    assert "<meta name='viewport' content='width=device-width, initial-scale=1'>" in page
    assert "href='/static/app.css'" in page

    status, headers, css = _page(app, "/static/app.css")
    assert status == "200 OK"
    assert headers["Content-Type"].startswith("text/css")
    assert "min-width: 320px" in css
    assert "@media (max-width: 700px)" in css
    assert "overflow-x: hidden" in css


def test_entry_has_situation_input_voice_demo_and_local_client_script(
    validated_mock_dataset: object,
) -> None:
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    _, _, page = _page(app, "/")
    for required in (
        "id='situation-form'", "id='situation-query'", "음성 입력",
        "id='voice-record-button'", "음성으로 입력", "id='query-feedback'",
    ):
        assert required in page
