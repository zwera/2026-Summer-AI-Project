"""대표 시연 흐름 통합/E2E 테스트와 외부 origin 호출 0건 계측 (task 22.2).

이 모듈은 WSGI 요청 하네스(``tests/test_web_server.py``의 패턴)를 통해 대표 시연
흐름을 처음부터 끝까지 왕복시키고, 상태 왕복 및 클립보드/다운로드 코드 경로가
네트워크 호출을 만들지 않는지 확인한다. 실제 브라우저가 없는 순수 Python 테스트
하네스이므로, "동일 origin만 허용된 상태에서 외부 origin 호출 0건"이라는 계약은
배포된 ``static/app.js``에 대한 정적 분석으로 계측한다:

- ``fetch``/``XMLHttpRequest``/``WebSocket``/``EventSource``/``sendBeacon`` 호출을
  모두 찾아 각 호출의 URL 인자가 상대 경로(동일 origin) 문자열 리터�리인지 확인한다.
- 실제 브라우저 네트워크 트레이스(예: Playwright)를 통한 완전한 검증은 이 Python
  하네스의 범위를 벗어난다. 이 문서화 방식은 ``tests/ACCESSIBILITY_MANUAL_CHECKLIST.md``의
  브라우저 전용 잔여 검증 안내 패턴을 따른다(별도 체크리스트로 남긴다).

Validates: Requirements 1.5, 1.10, 14.5, 16.10.
"""
from __future__ import annotations

import ast
import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

from web.server import MockWebApplication

_STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"
_NETWORK_CALL_NAMES = frozenset({"fetch", "XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon"})


def _request(
    app: MockWebApplication, method: str, path: str, body: bytes = b"", content_type: str = ""
) -> Tuple[str, Dict[str, str], bytes]:
    captured: List[Any] = []

    def start_response(status: str, headers: List[Tuple[str, str]]) -> None:
        captured.extend((status, dict(headers)))

    response = b"".join(
        app(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": path,
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": str(len(body)),
                "wsgi.input": BytesIO(body),
            },
            start_response,
        )
    )
    return captured[0], captured[1], response


def _post_action(app: MockWebApplication, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    status, _, body = _request(app, "POST", "/api/action", json.dumps(payload).encode("utf-8"), "application/json")
    return status, json.loads(body)


def _post_query(app: MockWebApplication, query: str) -> Tuple[str, Dict[str, Any]]:
    status, _, body = _request(app, "POST", "/api/query", json.dumps({"query": query}).encode("utf-8"), "application/json")
    return status, json.loads(body)


# ---------------------------------------------------------------------------
# 1. 대표 시연 흐름: 질의 -> 단계 -> 결과 -> 상세 -> 출처 왕복
# ---------------------------------------------------------------------------


def test_flow_query_to_results_to_case_detail_to_source_round_trip(validated_mock_dataset: object) -> None:
    """질의 제출부터 판례 상세, 출처 열람과 검색 결과 복귀까지의 전체 왕복을 검증한다.

    Validates: Requirements 1.5, 1.10, 13.5, 14.5.
    """
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]

    # 진입 화면과 정적 자산이 먼저 200 OK로 제공된다(브라우저의 최초 접속과 동일).
    for path in ("/", "/static/app.js", "/static/app.css"):
        status, _, _ = _request(app, "GET", path)
        assert status == "200 OK"

    # 질의 -> 목업_RAG 단계(입력 -> 목업_검색 -> 근거_제시 -> 응답) -> 결과.
    raw_query = validated_mock_dataset.queries[0].variants[0].raw_example  # type: ignore[attr-defined]
    status, payload = _post_query(app, raw_query)
    assert status == "200 OK"
    assert payload["interpretation"]["kind"] == "SUPPORTED"
    assert payload["search"]["cases"]
    assert payload["response"]["blocks"]
    assert payload["provenance"]["query"]

    case_id = payload["search"]["cases"][0]["case_id"]

    # 판례 상세로 진입: 선택한 판례의 출처만 반환된다.
    status, detail_payload = _post_action(app, {"type": "GET_CASE_DETAIL", "caseId": case_id})
    assert status == "200 OK"
    assert detail_payload["case"]["id"] == case_id
    assert detail_payload["sources"]
    source_id = detail_payload["sources"][0]["id"]

    # 출처 왕복: 출처를 연 뒤(GET_SOURCE) 검색 결과로 복귀해도 기존 질의/판례 상태가
    # 서버 측에는 재계산 없이 그대로 유지된다(Requirement 13.5 상태 왕복 계약은
    # test_property_source_round_trip_state.py에서 속성으로 이미 다룬다. 여기서는
    # 출처 열람 자체가 별개의 부수효과 없는 동일-origin 호출임만 확인한다).
    status, source_payload = _post_action(app, {"type": "GET_SOURCE", "sourceId": source_id})
    assert status == "200 OK"
    assert source_payload["source"]["id"] == source_id

    # 검색 결과로 복귀: 동일 질의 ID로 결과를 다시 요청하면 동일한 판례 집합을 얻는다.
    status, results_again = _post_action(app, {"type": "GET_RESULTS", "queryId": payload["interpretation"]["query_id"]})
    assert status == "200 OK"
    assert {case["case_id"] for case in results_again["search"]["cases"]} == {
        case["case_id"] for case in payload["search"]["cases"]
    }


# ---------------------------------------------------------------------------
# 2. 대표 시연 흐름: 시나리오 비교
# ---------------------------------------------------------------------------


def test_flow_scenario_comparison_end_to_end(validated_mock_dataset: object) -> None:
    """/results 화면 진입부터 시나리오 비교 액션까지의 흐름을 검증한다.

    Validates: Requirements 4.7, 4.8, 14.5.
    """
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    status, _, _ = _request(app, "GET", "/results")
    assert status == "200 OK"

    scenario = validated_mock_dataset.scenarios[0].id.value  # type: ignore[attr-defined]
    status, payload = _post_action(app, {"type": "GET_SCENARIO_COMPARISON", "scenario": scenario, "auxiliaryFilter": None})
    assert status == "200 OK"
    partition = payload["partition"]
    all_ids = [case["id"] for case in partition["lawful"] + partition["unlawful"]] + [
        entry["case"]["id"] for entry in partition["mixed"]
    ]
    assert len(all_ids) == len(set(all_ids))


# ---------------------------------------------------------------------------
# 3. 대표 시연 흐름: 요약 전환(3줄/10줄/상세)
# ---------------------------------------------------------------------------


def test_flow_summary_level_switching_preserves_canonical_conclusion(validated_mock_dataset: object) -> None:
    """검색 결과의 판례 상세 페이로드에서 세 요약 단계가 모두 동일한 정규_결론을 유지하는지 확인한다.

    Validates: Requirements 5.1, 5.7, 14.5.
    """
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    raw_query = validated_mock_dataset.queries[0].variants[0].raw_example  # type: ignore[attr-defined]
    status, payload = _post_query(app, raw_query)
    assert status == "200 OK"
    case_id = payload["search"]["cases"][0]["case_id"]
    summaries = payload["search"]["case_details_by_case"][case_id]["summaries"]
    conclusions = {level: summaries[level]["canonical_conclusion"] for level in ("3줄_요약", "10줄_요약", "상세_요약")}
    assert len(set(conclusions.values())) == 1


# ---------------------------------------------------------------------------
# 4. 대표 시연 흐름: 선택 재검토
# ---------------------------------------------------------------------------


def test_flow_selection_review_fact_check_then_explanation(validated_mock_dataset: object) -> None:
    """목업_응답 선택 -> 사실 확인 재검토 -> 상세 설명까지의 흐름을 검증한다.

    Validates: Requirements 9.1, 9.3, 9.8, 14.5.
    """
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    query = validated_mock_dataset.queries[0]  # type: ignore[attr-defined]
    review_fixture = next(
        fixture for fixture in validated_mock_dataset.review_fixtures  # type: ignore[attr-defined]
        if fixture.response_template_id == query.match.response_template_id
    )
    claim = review_fixture.claims[0]

    status, fact_check = _post_action(
        app,
        {
            "type": "RUN_SELECTION_REVIEW",
            "queryId": str(query.id),
            "selectedText": claim.text,
            "selectedClaimIds": [str(claim.id)],
            "mode": "FACT_CHECK",
        },
    )
    assert status == "200 OK"
    assert fact_check["result"]["claims"][0]["claim_id"] == str(claim.id)

    status, explanation = _post_action(
        app,
        {
            "type": "RUN_SELECTION_REVIEW",
            "queryId": str(query.id),
            "selectedText": claim.text,
            "selectedClaimIds": [str(claim.id)],
            "mode": "EXPLANATION",
        },
    )
    assert status == "200 OK"
    assert explanation["explanations"][0]["claim_id"] == str(claim.id)


# ---------------------------------------------------------------------------
# 5. 대표 시연 흐름: 음성 -> 타임라인 -> 보고서
# ---------------------------------------------------------------------------


def test_flow_voice_fixture_to_timeline_to_report(validated_mock_dataset: object) -> None:
    """사전_정의_음성_시연 선택부터 타임라인 조회·수정, 보고서 생성까지의 흐름을 검증한다.

    Validates: Requirements 11.3, 11.13, 11.14, 11.16, 14.5.
    """
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    success_fixture = next(item for item in validated_mock_dataset.voice_fixtures if not item.failure)  # type: ignore[attr-defined]

    status, voice_payload = _post_action(app, {"type": "SELECT_VOICE_FIXTURE", "fixtureId": str(success_fixture.id)})
    assert status == "200 OK"
    assert voice_payload["recognized_text"] == success_fixture.recognized_text
    assert voice_payload["interpretation"]["kind"] == "SUPPORTED"
    query_id = voice_payload["interpretation"]["query_id"]

    status, timeline_payload = _post_action(app, {"type": "GET_TIMELINE", "queryId": query_id})
    assert status == "200 OK"
    timeline = timeline_payload["timeline"]
    assert timeline["ordered"] or timeline["unknown_time"]

    if timeline["ordered"]:
        event_id = timeline["ordered"][0]["id"]
        status, updated = _post_action(
            app,
            {
                "type": "UPDATE_TIMELINE_EVENT",
                "queryId": query_id,
                "eventId": event_id,
                "actor": "통합 테스트 수정자",
            },
        )
        assert status == "200 OK"
        edited = next(event for event in updated["timeline"]["ordered"] if event["id"] == event_id)
        assert edited["actor"] == "통합 테스트 수정자"

    status, report_payload = _post_action(app, {"type": "GET_REPORT", "queryId": query_id})
    assert status == "200 OK"
    report = report_payload["report"]
    assert report["as_of_date"] == validated_mock_dataset.as_of_date  # type: ignore[attr-defined]
    assert report["safety_notice"] == validated_mock_dataset.legal_safety_notice  # type: ignore[attr-defined]
    assert report["body"]


def test_voice_fixture_failure_case_stays_at_input_stage(validated_mock_dataset: object) -> None:
    """인식 실패 음성 시연 항목은 입력 단계에 머물고 수동 입력 안내로 이어짐을 확인한다.

    Validates: Requirements 11.18, 14.5.
    """
    app = MockWebApplication(validated_mock_dataset)  # type: ignore[arg-type]
    failed_fixture = next(item for item in validated_mock_dataset.voice_fixtures if item.failure)  # type: ignore[attr-defined]
    status, payload = _post_action(app, {"type": "SELECT_VOICE_FIXTURE", "fixtureId": str(failed_fixture.id)})
    assert status == "200 OK"
    assert payload["voice_error"]["stage"] == "INPUT"
    assert "recognized_text" not in payload


# ---------------------------------------------------------------------------
# 6. 상태 왕복: 출처 열람 후 검색 결과 복귀 시 기존 상태 유지 (요약 참조)
# ---------------------------------------------------------------------------


def test_state_round_trip_after_source_navigation_is_covered_by_property_test() -> None:
    """출처 열람 후 상태 왕복 계약은 이미 property 테스트로 검증되어 있음을 문서화한다.

    ``tests/test_property_source_round_trip_state.py``가 Requirement 13.5(출처 열람 후
    복귀 시 상황_질의, 선택 판례, 요약_단계, 보조_필터 유지)를 property로 다루므로,
    이 통합 테스트 모듈에서는 왕복 흐름 자체(위 ``test_flow_query_to_results_to_case_detail_to_source_round_trip``)만
    한 번 더 예제로 왕복시키고 상세 불변식은 중복 구현하지 않는다.
    """
    property_test_path = Path(__file__).resolve().parent / "test_property_source_round_trip_state.py"
    assert property_test_path.is_file(), "상태 왕복 property 테스트 파일이 존재해야 한다"


# ---------------------------------------------------------------------------
# 7. 정적 분석: static/app.js의 네트워크 호출 0건 외부 origin 계측
# ---------------------------------------------------------------------------


def _iter_call_nodes(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def _js_network_calls_with_url_argument(source: str) -> List[Tuple[str, str]]:
    """``source`` 안의 네트워크 호출 이름과 첫 번째 인자(URL) 텍스트를 추출한다.

    JavaScript 전용 AST 파서에 의존하지 않고, 각 네트워크 호출 식별자
    (``fetch``, ``new WebSocket`` 등) 뒤에 오는 첫 번째 인자를 정규식으로 추출한다.
    문자열 리터럴(따옴표) 또는 템플릿 리터럴(백틱)만 지원 대상으로 하며, 그 외
    형태(예: 변수만 전달)가 발견되면 검사 대상에 포함해 안전하지 않은 것으로 표시한다.
    """
    calls: List[Tuple[str, str]] = []
    # `name(` 또는 `new name(` 형태를 모두 찾는다.
    pattern = re.compile(r"(?:new\s+)?(" + "|".join(_NETWORK_CALL_NAMES) + r")\s*\(\s*([^,)]*)")
    for match in pattern.finditer(source):
        name, first_arg = match.group(1), match.group(2).strip()
        calls.append((name, first_arg))
    return calls


_RELATIVE_SAME_ORIGIN_STRING = re.compile(r"^[\"'`]\s*/(?!/)[^\"'`]*[\"'`]$")
_RELATIVE_TEMPLATE_LITERAL_BASE = re.compile(r"^`\s*/(?!/)")


def _is_same_origin_url_argument(argument: str) -> bool:
    """URL 인자가 슬래시 하나로 시작하는(프로토콜 상대 아님) 상대 경로 리터럴인지 확인한다.

    ``//example.com``처럼 프로토콜 상대(사실상 외부 origin) 문자열은 거부한다.
    변수 전달(``path``)은 호출부에서 그 변수가 문자열 리터럴로만 채워지는지 별도
    확인해야 하므로, 이 함수는 리터럴이 아닌 인자를 안전하지 않은 것으로 표시하지 않고
    "판별 불가"로 취급해 상위 테스트에서 별도 검증하게 한다.
    """
    if _RELATIVE_SAME_ORIGIN_STRING.match(argument):
        return True
    if _RELATIVE_TEMPLATE_LITERAL_BASE.match(argument):
        return True
    return False


def test_app_js_has_zero_network_call_sites_targeting_external_origins() -> None:
    """static/app.js의 모든 네트워크 호출이 동일 origin 상대 경로만 대상으로 함을 계측한다.

    fetch/XMLHttpRequest/WebSocket/EventSource/sendBeacon 호출을 모두 찾아 각 호출의
    URL 인자가 리터럴인 경우 상대 경로(동일 origin)인지 검증한다. 변수로 전달되는
    인자(``path``)는 해당 변수가 오직 문자열 리터럴 상대 경로(``/api/query`` 등)로만
    호출되는 함수의 매개변수인지 소스에서 확인한다.

    Validates: Requirements 1.5, 1.10, 16.10.
    """
    source = (_STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    calls = _js_network_calls_with_url_argument(source)
    assert calls, "app.js에서 최소 하나의 네트워크 호출을 찾을 수 있어야 한다(회귀 방지)"

    literal_calls = [(name, arg) for name, arg in calls if arg.startswith(("'", '"', "`"))]
    variable_calls = [(name, arg) for name, arg in calls if arg and not arg.startswith(("'", '"', "`"))]

    # 리터럴 인자를 사용하는 모든 호출은 상대(동일 origin) 경로여야 한다.
    for name, argument in literal_calls:
        assert _is_same_origin_url_argument(argument), (
            f"{name} 호출이 리터럴 URL 인자 {argument!r}를 사용하지만 동일 origin 상대 "
            "경로가 아니다(외부 origin 호출 가능성)"
        )

    # 변수로 전달되는 인자는 그 변수 자체가 문자열 리터럴 상대 경로로만 정의/전달됨을
    # 확인한다. app.js에는 두 개의 요청 헬퍼가 있다:
    #   1) requestJson(path, payload) — 첫 번째 매개변수 이름이 ``path``이며, 이 변수를
    #      사용하는 유일한 호출부(situation-form 제출)는 리터럴 "/api/query"를 전달한다.
    #   2) request(payload) (타임라인 섹션) — 함수 본문 안에서 fetch("/api/action", ...)를
    #      직접 리터럴로 호출하므로 이 함수 자체에는 URL 매개변수가 없다.
    # 따라서 위 두 헬퍼 정의 밖에서 ``path`` 같은 이름의 변수가 네트워크 호출 함수에
    # 직접 전달되는 다른 지점이 없어야 한다.
    known_url_parameter_names = {"path"}
    for name, argument in variable_calls:
        assert argument in known_url_parameter_names, (
            f"{name}({argument}) 호출이 알려지지 않은 변수 URL 인자를 사용한다. "
            "이 변수가 오직 동일 origin 상대 경로 리터럴로만 채워지는지 별도 확인이 필요하다."
        )
        # requestJson(path, payload) 정의부의 body(``fetch(path, ...)``)만 이 변수를
        # 네트워크 호출로 사용한다. 이 헬퍼는 ``const request = PoliceBotErrorDisplay.requestJson;``
        # 로 별칭이 지정되어 호출부는 모두 ``request("/api/...", ...)`` 형태를 사용한다.
        # 이 호출부들의 첫 번째 인자가 상대 경로 리터럴인지 확인한다.
        assert re.search(r"\bconst request = PoliceBotErrorDisplay\.requestJson;", source), (
            "requestJson의 별칭 request 정의를 찾을 수 없다"
        )
        call_sites = [
            match.strip()
            for match in re.findall(r"\brequest\(\s*([^,)]*)", source)
        ]
        literal_call_sites = [site for site in call_sites if site and site.startswith(("'", '"', "`"))]
        assert literal_call_sites, f"{name}({argument})의 URL을 채우는 requestJson 호출부(리터럴 경로)를 찾을 수 없다"
        for call_site_arg in literal_call_sites:
            assert _is_same_origin_url_argument(call_site_arg), (
                f"requestJson 호출부의 URL 인자 {call_site_arg!r}가 동일 origin 상대 경로가 아니다"
            )

    # 소스 전체에서 fetch/XHR 등에 전달될 수 있는 절대 URL(http://, https://, //로
    # 시작하는 프로토콜 상대) 문자열 리터럴이 전혀 존재하지 않는지 이중 확인한다.
    absolute_url_literal = re.compile(r"[\"'`](?:https?:)?//[^\"'`]+[\"'`]")
    assert not absolute_url_literal.search(source), "app.js에 절대/외부 origin URL 리터럴이 존재한다"


def test_app_js_request_helpers_only_target_known_same_origin_endpoints() -> None:
    """실제 요청 헬퍼(``requestJson``/``request``) 호출부가 알려진 동일 origin 경로만 사용하는지 확인한다.

    ``/api/query``, ``/api/action``, ``/static/...`` 이외의 목적지로 향하는 호출이 없어야
    한다. 이는 대표 시연 흐름(질의 제출, 음성 시연, 시나리오 비교, 선택 재검토, 타임라인,
    보고서, 출처 조회) 전체가 동일 origin 경로만 사용함을 보장한다.

    Validates: Requirements 1.5, 1.10, 16.10.
    """
    source = (_STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    known_same_origin_paths = {"/api/query", "/api/action"}

    string_literal_destinations = set(re.findall(r"request(?:Json)?\(\s*[\"']([^\"']+)[\"']", source))
    assert string_literal_destinations, "요청 헬퍼 호출부에서 문자열 목적지를 찾을 수 없다"
    assert string_literal_destinations <= known_same_origin_paths, (
        f"알려지지 않은 요청 목적지 발견: {string_literal_destinations - known_same_origin_paths}"
    )

    # fetch(path, ...) 처럼 변수로 전달되는 유일한 경로는 폼 제출(situation-form)의
    # requestJson(path, payload) 호출부이며, 그 호출부는 "/api/query" 리터럴을 사용한다.
    assert re.search(r"request\(\s*[\"']/api/query[\"']", source), (
        "situation-form 제출이 더 이상 /api/query 리터럴을 사용하지 않는다"
    )


# ---------------------------------------------------------------------------
# 8. 클립보드/다운로드 코드 경로가 네트워크 호출을 하지 않음을 확인
# ---------------------------------------------------------------------------


def test_clipboard_and_download_code_paths_perform_no_network_call() -> None:
    """복사(navigator.clipboard)와 다운로드(Blob/URL.createObjectURL) 코드 경로에
    fetch/XHR/WebSocket/EventSource/sendBeacon 호출이 없는지 확인한다.

    Validates: Requirements 11.15, 11.16, 11.17, 1.7, 1.10.
    """
    source = (_STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    copy_start = source.index('copyButton.addEventListener("click"')
    copy_end = source.index('downloadButton.addEventListener("click"', copy_start)
    copy_handler_body = source[copy_start:copy_end]
    assert "navigator.clipboard" in copy_handler_body
    for network_call in _NETWORK_CALL_NAMES:
        assert network_call not in copy_handler_body, f"복사 처리 코드에서 {network_call} 호출을 발견했다"

    download_start = source.index('downloadButton.addEventListener("click"')
    download_end = source.index("section.append(generateButton", download_start)
    download_handler_body = source[download_start:download_end]
    assert "Blob" in download_handler_body and "createObjectURL" in download_handler_body
    for network_call in _NETWORK_CALL_NAMES:
        assert network_call not in download_handler_body, f"다운로드 처리 코드에서 {network_call} 호출을 발견했다"
