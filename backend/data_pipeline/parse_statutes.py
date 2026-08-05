"""
Part 2: 조문 파싱 및 API 연동 - 법령 PDF 파싱 모듈.

statute/세부법령/*.pdf (경범죄처벌법, 식품위생법, 청소년보호법 및 각 시행령/시행규칙)를
읽어 조문 단위로 분리한 뒤, 인덱싱에 사용할 JSON 레코드 목록으로 변환한다.

사용법:
    python -m data_pipeline.parse_statutes           # statute_processed.json 저장
    python -m data_pipeline.parse_statutes --print    # 결과를 콘솔에 요약 출력
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from pypdf import PdfReader

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
STATUTE_DIR = PROJECT_ROOT / "statute" / "세부법령"
OUTPUT_PATH = BACKEND_DIR / "data_processed" / "statutes.json"

# 파일명에서 법령명/법령종류/공포일자를 추출하기 위한 패턴
# 예: "경범죄 처벌법(법률)(제14908호)(20171024).pdf"
FILENAME_PATTERN = re.compile(
    r"^(?P<name>.+?)\((?P<kind>법률|대통령령|총리령|행정안전부령)\)\((?P<num>제\d+호)\)\((?P<date>\d{8})\)"
)

# 조문 헤더 패턴: "제3조(경범죄의 종류)" 또는 "제9조의2(...)"
ARTICLE_PATTERN = re.compile(r"(제\d+조(?:의\d+)?\s*\([^)]{1,40}\))")

# 페이지 머리/꼬리에 반복 삽입되는 "법제처 N 국가법령정보센터" 같은 잡음 라인
NOISE_LINE_PATTERN = re.compile(r"^법제처\s+\d+\s+국가법령정보센터$")


@dataclass
class StatuteArticle:
    id: str                # 예: "경범죄 처벌법::제3조"
    law_name: str          # 예: "경범죄 처벌법"
    law_kind: str          # 법률/대통령령/총리령/행정안전부령
    promulgation_date: str  # YYYY-MM-DD
    article_no: str        # 예: "제3조"
    article_title: str     # 예: "경범죄의 종류"
    content: str           # 조문 본문
    source_file: str


def parse_filename(pdf_path: Path) -> tuple[str, str, str]:
    """파일명에서 (법령명, 법령종류, 공포일자) 를 추출."""
    m = FILENAME_PATTERN.match(pdf_path.stem)
    if not m:
        # 패턴이 안 맞으면 파일명 전체를 법령명으로 사용
        return pdf_path.stem, "", ""
    name = m.group("name").strip()
    kind = m.group("kind")
    date_raw = m.group("date")
    date_fmt = f"{date_raw[0:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
    return name, kind, date_fmt


def extract_clean_text(pdf_path: Path) -> str:
    """PDF에서 텍스트를 추출하고 머리/꼬리 잡음 라인을 제거해 하나의 문자열로 합친다."""
    reader = PdfReader(str(pdf_path))
    law_title_guess = parse_filename(pdf_path)[0]

    lines: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        for raw_line in page_text.split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            if NOISE_LINE_PATTERN.match(line):
                continue
            if line == law_title_guess:
                continue
            lines.append(line)
    return " ".join(lines)


def split_into_articles(full_text: str) -> list[tuple[str, str, str]]:
    """전체 텍스트를 조문 단위로 분리.

    반환: [(조문번호, 조문제목, 본문), ...]
    부칙(부칙 <제...>)이나 목차/장 제목 등은 조문 헤더가 아니므로 본문에 포함된 채로 남는다.
    """
    parts = ARTICLE_PATTERN.split(full_text)
    articles: list[tuple[str, str, str]] = []

    # parts[0]은 첫 조문 이전의 서두(시행일, 소관부처 등) - 스킵
    # parts[1], parts[2] 가 (헤더, 본문) 쌍으로 반복됨
    i = 1
    while i + 1 < len(parts):
        header = parts[i].strip()
        body = parts[i + 1].strip()
        header_match = re.match(r"(제\d+조(?:의\d+)?)\s*\(([^)]{1,40})\)", header)
        if header_match:
            article_no = header_match.group(1)
            article_title = header_match.group(2)
            articles.append((article_no, article_title, body))
        i += 2
    return articles


def parse_statute_pdf(pdf_path: Path) -> list[StatuteArticle]:
    law_name, law_kind, promulgation_date = parse_filename(pdf_path)
    full_text = extract_clean_text(pdf_path)
    articles = split_into_articles(full_text)

    # 부칙(附則)에서 조문 번호가 "제1조"부터 다시 시작되어 본문과 겹치는 경우가 있어,
    # 같은 (법령명, 조문번호) 조합이 반복되면 ID에 순번을 붙여 충돌을 방지한다.
    seen_counts: dict[str, int] = {}
    records: list[StatuteArticle] = []
    for article_no, article_title, body in articles:
        base_key = f"{law_name}::{article_no}"
        seen_counts[base_key] = seen_counts.get(base_key, 0) + 1
        occurrence = seen_counts[base_key]
        unique_id = base_key if occurrence == 1 else f"{base_key}#{occurrence}"

        records.append(
            StatuteArticle(
                id=unique_id,
                law_name=law_name,
                law_kind=law_kind,
                promulgation_date=promulgation_date,
                article_no=article_no,
                article_title=article_title,
                content=body,
                source_file=pdf_path.name,
            )
        )
    return records


def parse_all_statutes(statute_dir: Path = STATUTE_DIR) -> list[StatuteArticle]:
    all_records: list[StatuteArticle] = []
    for pdf_path in sorted(statute_dir.glob("*.pdf")):
        records = parse_statute_pdf(pdf_path)
        print(f"  {pdf_path.name}: {len(records)}개 조문 추출")
        all_records.extend(records)
    return all_records


def main() -> None:
    parser = argparse.ArgumentParser(description="법령 PDF 파싱")
    parser.add_argument("--print", dest="do_print", action="store_true", help="결과 요약을 콘솔에 출력")
    args = parser.parse_args()

    print(f"법령 PDF 파싱 시작: {STATUTE_DIR}")
    records = parse_all_statutes()
    print(f"총 {len(records)}개 조문 추출 완료")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, ensure_ascii=False, indent=2)
    print(f"저장 완료: {OUTPUT_PATH}")

    if args.do_print:
        for r in records[:10]:
            print(f"[{r.law_name}] {r.article_no}({r.article_title}): {r.content[:80]}...")


if __name__ == "__main__":
    main()
