"""rag.schemas의 순수 함수(classify_instance)에 대한 단위 테스트.

목업 시연 계층의 테스트 스위트(tests/)에 함께 두지만, rag/ 패키지는 domain/ 등과
완전히 분리된 별도 파이프라인이다. 이 테스트는 Gemini/Chroma를 호출하지 않는다.
"""
from __future__ import annotations

import pytest

from rag.schemas import classify_instance


@pytest.mark.parametrize(
    "case_number,expected",
    [
        ("2019고단4541", "1심"),
        ("2013고정160", "1심"),
        ("95고합486", "1심"),
        ("2013구단2537", "1심"),
        ("2008구합10813", "1심"),
        ("84가합976", "1심"),
        ("2019가단100", "1심"),
        ("2019나12345", "항소심"),
        ("2019도12345", "상고심"),
        ("2019두12345", "상고심"),
        ("2019다12345", "상고심"),
        ("no-digits-here", "UNKNOWN"),
        ("", "UNKNOWN"),
    ],
)
def test_classify_instance_matches_expected_court_level(case_number: str, expected: str) -> None:
    assert classify_instance(case_number) == expected
