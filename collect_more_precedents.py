"""
crawl_precedents.py의 crawl() 함수를 재사용해, 비대화형으로 여러 키워드에 대해
1심 판례를 자동 수집하는 보조 스크립트.

경찰관 공무집행 적법성 검증 시나리오를 보강하기 위해
(경범죄처벌법 보충 수집 + 공무집행방해/직무유기/국가배상 신규 수집) 여러 건을 한 번에 처리한다.
1심 판별 로직은 crawl_precedents.py의 is_first_instance()를 그대로 사용한다.

사용법 (PowerShell):
    $env:LAW_OC="발급받은키"; python collect_more_precedents.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_precedents import (  # noqa: E402
    LawApiError,
    _fix_windows_console_encoding,
    crawl,
)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PRECEDENT_DIR = os.path.join(PROJECT_ROOT, "precedent")

# (검색어, 저장 폴더명, 최대 수집건수) - crawl()이 JO 검색을 먼저 시도하고
# 결과가 없으면 자동으로 키워드 검색으로 전환한다.
JOBS = [
    ("경범죄처벌법", "경범죄", 40),
    ("공무집행방해", "공무집행방해", 30),
    ("직무유기", "직무유기", 20),
    ("경찰관 직무집행 국가배상", "국가배상", 20),
]


def main() -> int:
    oc = os.environ.get("LAW_OC", "")
    if not oc:
        print("환경변수 LAW_OC가 설정되어 있지 않습니다.", file=sys.stderr)
        return 1

    for law_name, folder, max_items in JOBS:
        output_dir = os.path.join(PRECEDENT_DIR, folder, "1심 판례")
        os.makedirs(output_dir, exist_ok=True)
        print(f"\n========== '{law_name}' -> {folder}/1심 판례 (최대 {max_items}건) ==========")
        try:
            crawl(
                oc=oc,
                law_name=law_name,
                max_items=max_items,
                output_dir=output_dir,
                first_instance_only=True,
            )
        except LawApiError as exc:
            print(f"API 오류: {exc}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"오류 발생: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    _fix_windows_console_encoding()
    sys.exit(main())
