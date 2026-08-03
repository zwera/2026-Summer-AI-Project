"""공통 pytest fixture.

Property 기반 테스트에서 반복적으로 필요한 검증된 목업 데이터셋(``ValidatedDataset``)을
한 곳에서 제공한다. 각 property 테스트 모듈은 이 fixture를 재사용해 매번
``build_mock_dataset()`` + ``validate_dataset()`` 호출 코드를 중복하지 않는다.

이 fixture는 실제 시연 fixture(``fixtures.mock_dataset.build_mock_dataset``)를 그대로
검증한 결과를 제공한다. Property 11처럼 "검증을 통과한 데이터셋"에 대한 전역 불변식을
확인하는 테스트에 적합하다. 개별 mutation을 주입해 특정 위반을 확인하는 테스트(예:
``test_validated_dataset.py``)는 이 fixture를 사용하지 않고 각자 필요한 mutation을
직접 만든다.
"""

from __future__ import annotations

import pytest

from data.validated_dataset import ValidatedDataset, validate_dataset
from domain.result import Ok
from fixtures.mock_dataset import build_mock_dataset


@pytest.fixture(scope="session")
def validated_mock_dataset() -> ValidatedDataset:
    """실제 시연 fixture를 검증한 ``ValidatedDataset``을 반환한다.

    fixture 자체와 그 검증 결과는 읽기 전용(불변 dataclass)이므로 세션 범위에서 한 번만
    빌드·검증해 재사용해도 테스트 간 격리에 영향을 주지 않는다.
    """

    result = validate_dataset(build_mock_dataset())
    assert isinstance(result, Ok), f"실제 시연 fixture 검증 실패(치명 진단 존재): {result}"
    return result.value
