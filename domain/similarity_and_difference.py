"""유사도 경고 구간·핵심 사실관계 차이 projection과 결정적 차이 우선 (task 10.1).

``design.md`` "핵심 포트와 함수 시그니처"의 다음 계약을 구현한다::

    function similarityWarning(
      score: number,
      policies: readonly SimilarityWarningPolicyRecord[]
    ): SimilarityWarningPolicyRecord;

    function orderFactDifferences(
      score: number,
      differences: readonly FactDifference[]
    ): readonly FactDifference[];

그리고 "4.6 유사도 경고와 사실 차이" 절의 규칙을 구현한다.

- ``[80,100]``: `높은 유사도 — 핵심 차이 확인 필요`
- ``[50,80)``: `중간 유사도 — 직접 적용 전 사실관계 재검토 필요`
- ``[0,50)``: `낮은 유사도 — 결론 근거로 사용 금지`
- 높은 유사도이고 ``couldChangeConclusion=true``인 사실 차이가 있으면 점수보다 먼저
  경고 영역에 배치한다.
- 사용자 사실, 판례 사실, 결론 영향 중 fixture 값이 없는 필드는 각각 `확인 필요`로
  표시한다. 유사도는 적법성, 결론, 해당 심급 인정 죄명, 해당 심급 재판 결과를 바꾸지
  않는다.

## 이 태스크(10.1)의 범위

- :func:`similarity_warning` — 요구사항 8.7~8.9. ``score``가 속하는 구간의
  :class:`~data.models_common.SimilarityWarningPolicyRecord`를 정확히 하나 선택한다.
  새 문구를 만들지 않고 ``policies``에서 고른다(design.md "결정 규칙은 어떤 레코드
  ID를 선택할지만 정하며 새로운 문구나 법률 결론을 생성하지 않는다").
- :func:`order_fact_differences` — 요구사항 8.10. ``could_change_conclusion=True``인
  차이를 ``False``인 차이보다 앞에 배치하고, 각 그룹 안에서는
  ``(display_priority, id)`` 오름차순 안정 정렬을 적용한다(design.md "결정적 차이는
  ``couldChangeConclusion=true`` 후 ``displayPriority``, ``id`` 순으로 배치한다").
  ``score`` 인자는 design.md 시그니처와의 계약 일치를 위해 받지만, 정렬 자체는
  유사도 구간과 무관하게 항상 결정적 차이를 우선한다 — "높은 유사도"라는 서술은
  결정적 차이가 실제로 나타나는 대표적 맥락일 뿐, 8.10 인수 기준 자체와 이후
  Property 22("높은 구간에 ``couldChangeConclusion=true`` 차이가 있으면 그 차이는
  점수보다 먼저 표시되어야 한다")는 구간에 관계없이 결정적 차이 우선 배치를
  요구한다.
- :func:`resolve_fact_difference_display` — 요구사항 8.4~8.6. ``user_fact``·
  ``case_fact``·``conclusion_impact`` 중 ``None``인 필드만 독립적으로 표시 정책
  ``확인 필요`` 문구로 치환한다(다른 필드에 영향 없음). 문자열을 새로 만들지 않고
  ``placeholders``에서 ``key == "확인 필요"`` 레코드의 ``text``를 재사용한다.
- 요구사항 8.11(적법성_상태·법원_결론·해당_심급_재판_결과가 유사도_점수와 독립)은 이
  모듈이 유사도·차이만 다루고 그 세 canonical 필드를 읽거나 파생시키지 않는다는
  사실 자체로 만족된다 — 이 모듈에는 그 필드들을 입력으로도 받지 않는다.

## 이 태스크가 하지 않는 것

- ``FactDifference`` 자체의 생성(fixture 책임, ``fixtures/mock_dataset.py``).
- 유사도_점수의 재계산이나 격리(task 5.2 ``sortCasesDeterministically`` 책임).
- 클라이언트 표시 순서 재해석(요구사항 8.13, 클라이언트_웹_계층은 이 모듈이 반환한
  순서를 변경 없이 표시해야 한다).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from data.models_common import DisplayPolicyRecord, SimilarityWarningPolicyRecord
from data.models_fact_difference import FactDifference

__all__ = [
    "NoMatchingSimilarityWarningError",
    "similarity_warning",
    "order_fact_differences",
    "DisplayFactDifference",
    "resolve_fact_difference_display",
]


class NoMatchingSimilarityWarningError(ValueError):
    """``policies``에 ``score``를 포함하는 구간의 레코드가 없을 때 발생한다.

    유효한 목업_데이터셋은 검증기(task 2.2, ``data.validator_domain``)가 ``[0, 100]``을
    gap 없이·중첩 없이 덮는 유사도 경고 구간 3개를 보장하므로, 이 예외는 유효하지 않은
    ``policies``(부트 검증을 우회한 호출)에 대해서만 발생해야 한다. 조용히 임의 문구를
    합성하는 대신 명시적으로 실패한다.
    """


def similarity_warning(
    score: float, policies: Sequence[SimilarityWarningPolicyRecord]
) -> SimilarityWarningPolicyRecord:
    """``score``가 속하는 구간의 ``SimilarityWarningPolicyRecord``를 반환한다.

    각 레코드는 ``min_inclusive``와 (``max_inclusive`` 또는 ``max_exclusive``) 중 정확히
    하나로 구간을 선언한다(``data.validator_structural``가 검증). ``max_inclusive``가
    선언되면 ``min_inclusive <= score <= max_inclusive``, ``max_exclusive``가 선언되면
    ``min_inclusive <= score < max_exclusive``로 판정한다. 여러 레코드가 매칭되면(유효한
    데이터셋에서는 발생하지 않아야 함) ``policies`` 순서상 첫 번째를 반환해 결정성을
    유지한다.
    """

    for record in policies:
        if score < record.min_inclusive:
            continue
        if record.max_inclusive is not None:
            if score <= record.max_inclusive:
                return record
            continue
        if record.max_exclusive is not None:
            if score < record.max_exclusive:
                return record
            continue
    message = (
        f"score={score!r}에 매칭되는 SimilarityWarningPolicyRecord가 없습니다."
    )
    raise NoMatchingSimilarityWarningError(message)


def order_fact_differences(
    score: float, differences: Sequence[FactDifference]
) -> Tuple[FactDifference, ...]:
    """``differences``를 결정적 차이 우선·``(display_priority, id)`` 순으로 정렬한다.

    ``score``는 design.md 계약 시그니처와의 일치를 위해 받으며, 정렬 로직 자체는
    구간과 무관하게 항상 ``could_change_conclusion=True``인 차이를 먼저 배치한다
    (모듈 docstring 참조).
    """

    del score  # 정렬 자체는 구간과 무관하다(모듈 docstring 참조). 계약 시그니처 유지용.

    def _sort_key(difference: FactDifference) -> Tuple[int, int, str]:
        decisive_first = 0 if difference.could_change_conclusion else 1
        return (decisive_first, difference.display_priority, difference.id)

    return tuple(sorted(differences, key=_sort_key))


_CONFIRMATION_NEEDED_KEY = "확인 필요"


@dataclass(frozen=True)
class DisplayFactDifference:
    """화면 표시용 :class:`~data.models_fact_difference.FactDifference`.

    ``user_fact``·``case_fact``·``conclusion_impact``는 원본이 ``None``이면 표시 정책
    ``확인 필요`` 문구로 치환된 값이다. 다른 필드(``id``·``dimension``·
    ``could_change_conclusion``·``display_priority``·``source_ids``)는 원본과 동일하다.
    """

    id: str
    dimension: str
    user_fact: str
    case_fact: str
    conclusion_impact: str
    could_change_conclusion: bool
    display_priority: int
    source_ids: Tuple[str, ...]


def _find_confirmation_needed_text(
    placeholders: Sequence[DisplayPolicyRecord],
) -> str:
    for record in placeholders:
        if record.key == _CONFIRMATION_NEEDED_KEY:
            return record.text
    message = (
        f"placeholders에 key={_CONFIRMATION_NEEDED_KEY!r} 레코드가 없습니다."
    )
    raise NoMatchingSimilarityWarningError(message)


def resolve_fact_difference_display(
    difference: FactDifference, placeholders: Sequence[DisplayPolicyRecord]
) -> DisplayFactDifference:
    """``difference``의 ``None`` 필드만 독립적으로 `확인 필요`로 치환한다(요구사항 8.4~8.6).

    ``user_fact``·``case_fact``·``conclusion_impact``는 서로 영향을 주지 않고 각자
    ``None``일 때만 ``placeholders``의 ``확인 필요`` 레코드 문구로 치환된다. 값이 있는
    필드는 원본 문자열을 그대로 유지한다.
    """

    has_missing_field = (
        difference.user_fact is None
        or difference.case_fact is None
        or difference.conclusion_impact is None
    )
    confirmation_needed_text: Optional[str] = None
    if has_missing_field:
        confirmation_needed_text = _find_confirmation_needed_text(placeholders)

    def _resolve(value: Optional[str]) -> str:
        if value is not None:
            return value
        assert confirmation_needed_text is not None
        return confirmation_needed_text

    return DisplayFactDifference(
        id=difference.id,
        dimension=difference.dimension,
        user_fact=_resolve(difference.user_fact),
        case_fact=_resolve(difference.case_fact),
        conclusion_impact=_resolve(difference.conclusion_impact),
        could_change_conclusion=difference.could_change_conclusion,
        display_priority=difference.display_priority,
        source_ids=tuple(str(source_id) for source_id in difference.source_ids),
    )
