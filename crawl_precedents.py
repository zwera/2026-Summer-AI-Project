"""
국가법령정보센터(law.go.kr) Open API를 이용해
특정 법률과 관련된 판례를 검색하고 마크다운 파일로 저장하는 프로그램.

사용법:
    python crawl_precedents.py

실행하면 아래 순서로 입력을 받습니다:
    1) 국가법령정보센터 API 인증키(OC) 입력
    2) 탐색하고 싶은 법률명 입력
    3) 검색할 판례 개수 입력
    4) 이 스크립트가 있는 위치에 법률명으로 된 폴더를 생성
    5) 검색된 판례를 마크다운 파일로 해당 폴더에 저장

인증키(OC)는 환경변수 LAW_OC를 미리 설정해두면 입력 단계에서 그대로 Enter만 눌러 재사용할 수 있습니다.
    (PowerShell) $env:LAW_OC="발급받은키"
"""

import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

import requests


def _fix_windows_console_encoding() -> None:
    """
    Windows 콘솔이 한글 CP949 등 legacy 코드페이지로 남아 있으면 한글 출력이
    깨지거나(mojibake) 입력이 깨지는(UnicodeDecodeError) 문제가 발생합니다.
    콘솔 코드페이지를 UTF-8(65001)로 전환하고, Python stdin/stdout/stderr도
    UTF-8로 맞춰서 어떤 터미널(cmd, PowerShell, VS Code/Kiro 통합 터미널 등)
    에서 실행하더라도 한글이 정상적으로 표시되도록 합니다.
    """
    if os.name != "nt":
        return
    try:
        import subprocess

        # stdin을 물려받지 않도록 명시적으로 분리 (리다이렉트/파이프 입력이
        # chcp 서브프로세스에 소비되어 EOFError가 나는 것을 방지)
        subprocess.run(
            ["chcp", "65001"],
            shell=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (LookupError, ValueError):
                pass

SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
DETAIL_URL = "https://www.law.go.kr/DRF/lawService.do"

REQUEST_TIMEOUT = 10  # seconds
REQUEST_DELAY = 0.3   # 요청 사이 지연 (서버 부담 완화)
MAX_DISPLAY_PER_PAGE = 100


@dataclass
class PrecedentSummary:
    id: str
    title: str
    case_no: str
    date: str
    court: str
    case_type: str
    judgment_type: str


@dataclass
class PrecedentDetail:
    id: str
    title: str
    case_no: str
    date: str
    court: str
    case_type: str
    judgment_type: str
    summary: Optional[str] = None       # 판시사항
    gist: Optional[str] = None          # 판결요지
    ref_articles: Optional[str] = None  # 참조조문
    ref_precedents: Optional[str] = None  # 참조판례
    full_text: Optional[str] = None     # 판례내용


class LawApiError(Exception):
    pass


def _request_xml(url: str, params: dict) -> ET.Element:
    resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    content = resp.content

    # 법제처 API는 인증 실패, 점검중 등의 상황에서 HTML을 반환하기도 함
    stripped = content.lstrip()[:20].lower()
    if stripped.startswith(b"<!doctype") or stripped.startswith(b"<html"):
        raise LawApiError(
            "API가 XML이 아닌 HTML 응답을 반환했습니다. "
            "인증키(OC)가 올바른지, IP 등록이 필요한 계정인지 확인해 주세요."
        )
    try:
        return ET.fromstring(content)
    except ET.ParseError as exc:
        raise LawApiError(f"XML 파싱 실패: {exc}") from exc


def search_precedents_by_law(
    oc: str, law_name: str, page: int = 1, display: int = 20
) -> tuple[int, list[PrecedentSummary]]:
    """
    특정 법률명을 참조조문으로 인용한 판례를 검색합니다. (JO = 참조법령명 검색)
    """
    params = {
        "OC": oc,
        "target": "prec",
        "type": "XML",
        "JO": law_name,
        "display": display,
        "page": page,
    }
    root = _request_xml(SEARCH_URL, params)
    total_cnt = int(root.findtext("totalCnt", "0"))

    items = []
    for prec in root.findall("prec"):
        items.append(
            PrecedentSummary(
                id=prec.findtext("판례일련번호", ""),
                title=(prec.findtext("사건명", "") or "").strip(),
                case_no=(prec.findtext("사건번호", "") or "").strip(),
                date=(prec.findtext("선고일자", "") or "").strip(),
                court=(prec.findtext("법원명", "") or "").strip(),
                case_type=(prec.findtext("사건종류명", "") or "").strip(),
                judgment_type=(prec.findtext("판결유형", "") or "").strip(),
            )
        )
    return total_cnt, items


def search_precedents_by_keyword(
    oc: str, keyword: str, page: int = 1, display: int = 20
) -> tuple[int, list[PrecedentSummary]]:
    """
    일반 키워드(사건명/판시사항 등)로 판례를 검색합니다. JO 검색 결과가 없을 때 대체용.
    """
    params = {
        "OC": oc,
        "target": "prec",
        "type": "XML",
        "query": keyword,
        "display": display,
        "page": page,
    }
    root = _request_xml(SEARCH_URL, params)
    total_cnt = int(root.findtext("totalCnt", "0"))

    items = []
    for prec in root.findall("prec"):
        items.append(
            PrecedentSummary(
                id=prec.findtext("판례일련번호", ""),
                title=(prec.findtext("사건명", "") or "").strip(),
                case_no=(prec.findtext("사건번호", "") or "").strip(),
                date=(prec.findtext("선고일자", "") or "").strip(),
                court=(prec.findtext("법원명", "") or "").strip(),
                case_type=(prec.findtext("사건종류명", "") or "").strip(),
                judgment_type=(prec.findtext("판결유형", "") or "").strip(),
            )
        )
    return total_cnt, items


def get_precedent_detail(oc: str, prec_id: str) -> PrecedentDetail:
    params = {
        "OC": oc,
        "target": "prec",
        "ID": prec_id,
        "type": "XML",
    }
    root = _request_xml(DETAIL_URL, params)
    return PrecedentDetail(
        id=root.findtext("판례정보일련번호", prec_id) or prec_id,
        title=(root.findtext("사건명", "") or "").strip(),
        case_no=(root.findtext("사건번호", "") or "").strip(),
        date=(root.findtext("선고일자", "") or "").strip(),
        court=(root.findtext("법원명", "") or "").strip(),
        case_type=(root.findtext("사건종류명", "") or "").strip(),
        judgment_type=(root.findtext("판결유형", "") or "").strip(),
        summary=root.findtext("판시사항"),
        gist=root.findtext("판결요지"),
        ref_articles=root.findtext("참조조문"),
        ref_precedents=root.findtext("참조판례"),
        full_text=root.findtext("판례내용"),
    )


def clean_text(raw: Optional[str]) -> str:
    """API가 CDATA로 내려주는 원문의 <br/> 등을 마크다운 친화적으로 정리."""
    if not raw:
        return ""
    text = raw.replace("<br/>", "\n\n").replace("<br />", "\n\n")
    # 줄마다 앞뒤 공백 정리, 연속 빈 줄 축소
    lines = [line.strip() for line in text.splitlines()]
    cleaned = []
    prev_blank = False
    for line in lines:
        if line == "":
            if prev_blank:
                continue
            prev_blank = True
        else:
            prev_blank = False
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def format_date(date_str: str) -> str:
    """YYYYMMDD 또는 YYYY.MM.DD 형태를 YYYY-MM-DD로 통일."""
    digits = re.sub(r"[^0-9]", "", date_str or "")
    if len(digits) == 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return date_str or ""


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.strip().strip(".")
    return name or "untitled"


def detail_to_markdown(law_name: str, detail: PrecedentDetail) -> str:
    date_fmt = format_date(detail.date)
    parts = [
        f"# {detail.title or '(제목 없음)'}",
        "",
        f"- **사건번호**: {detail.case_no}",
        f"- **선고일자**: {date_fmt}",
        f"- **법원명**: {detail.court}",
        f"- **사건종류**: {detail.case_type}",
        f"- **판결유형**: {detail.judgment_type}",
        f"- **검색 기준 법률**: {law_name}",
        f"- **판례일련번호(ID)**: {detail.id}",
        f"- **원문 링크**: https://www.law.go.kr/DRF/lawService.do?target=prec&ID={detail.id}&type=HTML",
        "",
    ]

    summary = clean_text(detail.summary)
    if summary:
        parts += ["## 판시사항", "", summary, ""]

    gist = clean_text(detail.gist)
    if gist:
        parts += ["## 판결요지", "", gist, ""]

    ref_articles = clean_text(detail.ref_articles)
    if ref_articles:
        parts += ["## 참조조문", "", ref_articles, ""]

    ref_precedents = clean_text(detail.ref_precedents)
    if ref_precedents:
        parts += ["## 참조판례", "", ref_precedents, ""]

    full_text = clean_text(detail.full_text)
    if full_text:
        parts += ["## 전문", "", full_text, ""]

    parts += [
        "---",
        "",
        "*본 문서는 국가법령정보센터(law.go.kr) Open API를 통해 수집된 판례 정보입니다.*",
    ]
    return "\n".join(parts)


def build_index_markdown(law_name: str, summaries: list[PrecedentSummary]) -> str:
    lines = [
        f"# '{law_name}' 관련 판례 목록",
        "",
        f"총 {len(summaries)}건",
        "",
        "| 사건번호 | 사건명 | 선고일자 | 법원명 | 파일 |",
        "|---|---|---|---|---|",
    ]
    for s in summaries:
        date_fmt = format_date(s.date)
        filename = f"{date_fmt}_{sanitize_filename(s.case_no)}.md"
        lines.append(f"| {s.case_no} | {s.title} | {date_fmt} | {s.court} | [{filename}]({filename}) |")
    return "\n".join(lines)


def crawl(oc: str, law_name: str, max_items: int, output_dir: str, page_size: int = 20) -> None:
    page_size = min(page_size, MAX_DISPLAY_PER_PAGE)

    print(f"5. '{law_name}'을 참조한 판례를 검색합니다 (JO 검색)...")
    total_cnt, first_page = search_precedents_by_law(oc, law_name, page=1, display=page_size)

    search_mode = "jo"
    if total_cnt == 0:
        print("[알림] JO(참조법령) 검색 결과가 없어 일반 키워드 검색으로 전환합니다.")
        search_mode = "keyword"
        total_cnt, first_page = search_precedents_by_keyword(oc, law_name, page=1, display=page_size)

    if total_cnt == 0:
        print("검색 결과가 없습니다. 법률명을 확인해 주세요.")
        return

    target_cnt = min(total_cnt, max_items) if max_items > 0 else total_cnt
    print(f"   전체 {total_cnt}건 중 {target_cnt}건을 수집합니다. (모드: {search_mode})")

    summaries: list[PrecedentSummary] = []
    page = 1
    while len(summaries) < target_cnt:
        if page == 1:
            batch = first_page
        else:
            time.sleep(REQUEST_DELAY)
            if search_mode == "jo":
                _, batch = search_precedents_by_law(oc, law_name, page=page, display=page_size)
            else:
                _, batch = search_precedents_by_keyword(oc, law_name, page=page, display=page_size)
        if not batch:
            break
        summaries.extend(batch)
        page += 1

    summaries = summaries[:target_cnt]

    print(f"6. 판례를 마크다운으로 변환하여 저장합니다...")
    saved = 0
    skipped = 0
    for idx, s in enumerate(summaries, start=1):
        date_fmt = format_date(s.date)
        filename = f"{date_fmt}_{sanitize_filename(s.case_no)}.md"
        filepath = os.path.join(output_dir, filename)

        if os.path.exists(filepath):
            skipped += 1
            print(f"  [{idx}/{len(summaries)}] 이미 존재함, 건너뜀: {filename}")
            continue

        try:
            time.sleep(REQUEST_DELAY)
            detail = get_precedent_detail(oc, s.id)
        except (requests.RequestException, LawApiError) as exc:
            print(f"  [{idx}/{len(summaries)}] 상세조회 실패 (ID={s.id}): {exc}")
            continue

        markdown = detail_to_markdown(law_name, detail)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown)
        saved += 1
        print(f"  [{idx}/{len(summaries)}] 저장 완료: {filename}")

    index_md = build_index_markdown(law_name, summaries)
    index_path = os.path.join(output_dir, "index.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_md)

    print()
    print(f"완료: 신규 저장 {saved}건, 기존 파일 건너뜀 {skipped}건")
    print(f"저장 위치: {os.path.abspath(output_dir)}")


def prompt_oc() -> str:
    default_oc = os.environ.get("LAW_OC", "")
    while True:
        hint = f" (Enter만 누르면 환경변수 LAW_OC 사용: {default_oc})" if default_oc else ""
        oc = input(f"1. 국가법령정보센터 API 인증키(OC)를 입력하세요{hint}: ").strip()
        if not oc:
            oc = default_oc
        if oc:
            return oc
        print("   인증키는 필수입니다. 다시 입력해 주세요.")


def prompt_law_name() -> str:
    while True:
        law_name = input("2. 탐색하고 싶은 법률명을 입력하세요 (예: 근로기준법): ").strip()
        if law_name:
            return law_name
        print("   법률명은 필수입니다. 다시 입력해 주세요.")


def prompt_max_items() -> int:
    while True:
        raw = input("3. 검색할 판례 개수를 입력하세요 (전체 수집은 0): ").strip()
        if not raw:
            print("   숫자를 입력해 주세요.")
            continue
        try:
            value = int(raw)
        except ValueError:
            print("   숫자로 입력해 주세요.")
            continue
        if value < 0:
            print("   0 이상의 숫자를 입력해 주세요.")
            continue
        return value


def prepare_output_dir(law_name: str) -> str:
    """스크립트가 위치한 폴더 아래에 법률명으로 된 폴더를 생성합니다."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, sanitize_filename(law_name))
    os.makedirs(output_dir, exist_ok=True)
    print(f"4. 저장 폴더를 준비했습니다: {output_dir}")
    return output_dir


def main() -> int:
    print("=== 국가법령정보센터 판례 수집 프로그램 ===")
    oc = prompt_oc()
    law_name = prompt_law_name()
    max_items = prompt_max_items()
    output_dir = prepare_output_dir(law_name)
    print()

    try:
        crawl(
            oc=oc,
            law_name=law_name,
            max_items=max_items,
            output_dir=output_dir,
        )
    except LawApiError as exc:
        print(f"API 오류: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"네트워크 오류: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    _fix_windows_console_encoding()
    sys.exit(main())
