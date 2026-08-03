"""Property 11: 직무 시나리오 fixture의 적법·위법 최소 coverage (task 2.3).

``design.md`` Correctness Properties 절 "Property 11: 직무 시나리오 fixture의 적법·위법
최소 coverage":

    For all 검증을 통과한 데이터셋에 대해, 8개 각 직무 시나리오에는 적법 판례가 한 건
    이상, 위법 판례가 한 건 이상 존재해야 한다.

``Validates: Requirements 4.9``

## tasks.md와 design.md의 요구사항 번호 불일치 (보고 사항)

``tasks.md``의 task 2.3 항목 헤더에는 "**Validates: Requirements 4.7**"라고 적혀 있지만,
``design.md`` Correctness Properties 절의 "Property 11" 자체 정의는
"**Validates: Requirements 4.7**"이 아니라 실제로는 그 다음 문장에서 요구사항 4.9(
"THE 경찰_판례_AI_봇 SHALL 각 경찰_직무_시나리오에 적법 판례 한 건 이상과 위법 판례 한 건
이상을 목업_데이터_레코드로 제공한다")를 다루고 있다. ``design.md``를 직접 대조한 결과는
다음과 같다.

- ``design.md``의 "### Property 11" 섹션 본문에 적힌 문구는
  ``**Validates: Requirements 4.7**``이다(문서 원문 그대로).
- 그런데 요구사항 4.7의 실제 내용은 "WHEN 경찰_직무_시나리오 비교 화면이 표시되면, THE
  클라이언트_웹_계층 SHALL Python_기준_구현이 선택한 경찰_직무_시나리오에 반환한 모든
  판례를 세 구분 영역 전체에 누락 없이 표시한다"이며, 이는 UI projection 완전성에 관한
  내용으로 Property 10(시나리오·적법성 분류의 완전한 partition)이 다루는 주제다.
- 반면 "적법 1건 이상·위법 1건 이상 coverage"라는 Property 11의 서술 그대로의 요구사항은
  요구사항 4.9("THE 경찰_판례_AI_봇 SHALL 각 경찰_직무_시나리오에 적법 판례 한 건 이상과
  위법 판례 한 건 이상을 목업_데이터_레코드로 제공한다")이다.
- Requirements Traceability 표(design.md 하단)에서도 "4. 직무 시나리오" 행이
  ``P10–P12``에 매핑되어 있어 Property 11이 요구사항 4 그룹(4.9 포함)에 속함을 뒷받침한다.

즉 ``design.md``의 Property 11 헤더 문구 자체가 "4.7"이라고 적혀 있지만 이는 design.md
내부의 오기로 보이며, Property 11 서술과 실제로 부합하는 요구사항은 4.9다. 이 테스트는
Property 11의 서술(coverage 불변식)을 그대로 검증하며, docstring에는 design.md 원문 표기
"Requirements 4.7"과 실제 내용상 부합하는 "Requirements 4.9"를 모두 기록해 둔다. 이
불일치는 orchestrator/사용자에게 그대로 보고하며 이 테스트가 요구사항 문서를 수정하지는
않는다.

## Hypothesis 사용 방식

Property의 "for all"은 8개 ``PoliceScenario`` 값 전체에 대한 전량(exhaustive) 검사이므로
무작위 입력 공간이 필요하지 않다. 그럼에도 설계 문서의 테스트 관례("모든 속성 테스트는
성숙한 Python PBT 라이브러리로 최소 100회 실행")를 그대로 따르기 위해
``st.sampled_from(PoliceScenario)``로 8개 값을 생성기 입력으로 사용하고
``max_examples=100``을 지정한다. Hypothesis는 유한 집합 strategy에서 값을 반복 샘플링해
100회 실행을 채운다(각 실행은 8개 값 중 하나를 재사용하지만, 8개 값 전체가 최소 1회 이상
커버되므로 전량 검사 성질은 그대로 보존된다).
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from data.validated_dataset import ValidatedDataset
from domain.enums import LegalityStatus, PoliceScenario


# Feature: police-case-law-ai-bot, Property 11: 직무 시나리오 fixture의 적법·위법 최소 coverage
#
# ``validated_mock_dataset``는 tests/conftest.py의 session-scope fixture다. Hypothesis는
# session/module 범위 fixture를 재사용 가능한 값으로 취급해 매 example마다 재생성하지
# 않으므로(함수 범위 fixture와 달리 예제 간 상태를 공유해도 안전하다), 여기서는
# ``function_scoped_fixture`` health check를 끌 필요 없이 그대로 주입받는다.
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(scenario=st.sampled_from(PoliceScenario))
def test_every_scenario_has_lawful_and_unlawful_case_in_validated_dataset(
    validated_mock_dataset: ValidatedDataset, scenario: PoliceScenario
) -> None:
    """검증을 통과한 데이터셋에서 각 시나리오는 적법·위법 판례를 각 1건 이상 가져야 한다.

    **Validates: Requirements 4.9** (design.md Property 11 서술과 부합. design.md의
    Property 11 헤더 문구는 "Requirements 4.7"이라고 표기되어 있으나 위 모듈 docstring의
    불일치 설명을 참조.)
    """

    matching = [case for case in validated_mock_dataset.cases if scenario in case.scenario_ids]
    lawful_count = sum(1 for case in matching if case.legality_status is LegalityStatus.LAWFUL)
    unlawful_count = sum(1 for case in matching if case.legality_status is LegalityStatus.UNLAWFUL)

    assert lawful_count >= 1, f"{scenario.value} 시나리오에 적법 판례가 1건 이상 있어야 한다"
    assert unlawful_count >= 1, f"{scenario.value} 시나리오에 위법 판례가 1건 이상 있어야 한다"
