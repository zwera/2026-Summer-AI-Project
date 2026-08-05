"""
Part 2: 판례 마크다운 파싱 모듈.

precedent/{경범죄,식품,청소년}/1심 판례/*.md (crawl_precedents.py가 생성한 형식)를
읽어 메타데이터 + 섹션별 본문으로 구조화한다.

'1심 판례' 폴더가 각 법률 영역의 canonical 전체 목록이며, 그 옆의 법률명 하위 폴더는
crawl_precedents.py의 검색 방식(JO 검색 vs 키워드 검색) 차이로 생긴 부분집합이라
파싱 대상에서 제외한다.

사용법:
    python -m data_pipeline.parse_precedents           # precedents.json 저장
    python -m data_pipeline.parse_precedents --print    # 결과를 콘솔에 요약 출력
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
PRECEDENT_DIR = PROJECT_ROOT / "precedent"
OUTPUT_PATH = BACKEND_DIR / "data_processed" / "precedents.json"

# 각 법률 영역(폴더명)에서 실제로 파싱할 하위 폴더명 (canonical 전체 목록)
AREA_SUBDIR = "1심 판례"

METADATA_FIELD_PATTERN = re.compile(r"^-\s*\*\*(?P<key>[^*]+)\*\*:\s*(?P<value>.*)$")


@dataclass
class PrecedentRecord:
    id: str                    # 판례일련번호(ID) 또는 파일명 기반 fallback
    title: str
    case_no: str
    date: str
    court: str
    case_type: str
    judgment_type: str
    instance: str = ""          # 심급 (없을 수 있음)
    law_area: str = ""          # 검색 기준 법률 (경범죄/식품/청소년)
    source_link: str = ""
    summary: str = ""            # 판시사항
    gist: str = ""               # 판결요지
    ref_articles: str = ""       # 참조조문
    ref_precedents: str = ""     # 참조판례 (optional)
    full_text: str = ""          # 전문
    source_file: str = ""
    category: str = ""           # 경범죄/식품/청소년 (폴더 기준)


SECTION_KEY_MAP = {
    "판시사항": "summary",
    "판결요지": "gist",
    "참조조문": "ref_articles",
    "참조판례": "ref_precedents",
    "전문": "full_text",
}


def parse_markdown_precedent(md_path: Path, category: str) -> Optional[PrecedentRecord]:
    text = md_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    if not lines or not lines[0].startswith("# "):
        # index.md 등 형식이 다른 파일은 스킵
        return None

    title = lines[0][2:].strip()

    metadata: dict[str, str] = {}
    i = 1
    # 메타데이터 블록 (- **key**: value) 수집
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("## "):
            break
        m = METADATA_FIELD_PATTERN.match(line)
        if m:
            metadata[m.group("key").strip()] = m.group("value").strip()
        i += 1

    # 섹션(## 헤더) 수집
    sections: dict[str, str] = {}
    current_key: Optional[str] = None
    current_lines: list[str] = []
    for line in lines[i:]:
        header_match = re.match(r"^##\s+(.+)$", line.strip())
        if header_match:
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = header_match.group(1).strip()
            current_lines = []
        elif line.strip() == "---":
            # 문서 하단 구분선(및 출처 안내) 도달 시 섹션 수집 종료
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
                current_key = None
            break
        else:
            if current_key is not None:
                current_lines.append(line)
    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    prec_id = metadata.get("판례일련번호(ID)", "") or md_path.stem

    record = PrecedentRecord(
        id=prec_id,
        title=title,
        case_no=metadata.get("사건번호", ""),
        date=metadata.get("선고일자", ""),
        court=metadata.get("법원명", ""),
        case_type=metadata.get("사건종류", ""),
        judgment_type=metadata.get("판결유형", ""),
        instance=metadata.get("심급", ""),
        law_area=metadata.get("검색 기준 법률", category),
        source_link=metadata.get("원문 링크", ""),
        source_file=str(md_path.relative_to(PROJECT_ROOT)),
        category=category,
    )
    for header, field_name in SECTION_KEY_MAP.items():
        if header in sections:
            setattr(record, field_name, sections[header])

    return record


def parse_all_precedents(precedent_dir: Path = PRECEDENT_DIR) -> list[PrecedentRecord]:
    records: list[PrecedentRecord] = []
    if not precedent_dir.exists():
        return records

    for category_dir in sorted(precedent_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        area_dir = category_dir / AREA_SUBDIR
        if not area_dir.exists():
            continue
        category = category_dir.name
        count = 0
        for md_path in sorted(area_dir.glob("*.md")):
            if md_path.name == "index.md":
                continue
            record = parse_markdown_precedent(md_path, category)
            if record is not None:
                records.append(record)
                count += 1
        print(f"  {category}/{AREA_SUBDIR}: {count}건 파싱")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="판례 마크다운 파싱")
    parser.add_argument("--print", dest="do_print", action="store_true", help="결과 요약을 콘솔에 출력")
    args = parser.parse_args()

    print(f"판례 마크다운 파싱 시작: {PRECEDENT_DIR}")
    records = parse_all_precedents()
    print(f"총 {len(records)}건 파싱 완료")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, ensure_ascii=False, indent=2)
    print(f"저장 완료: {OUTPUT_PATH}")

    if args.do_print:
        for r in records[:5]:
            print(f"[{r.category}] {r.case_no} {r.title} ({r.date}) - summary_len={len(r.summary)}")


if __name__ == "__main__":
    main()
