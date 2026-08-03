"""``domain.result.Result[T, E]`` 판별 유니온에 대한 단위 테스트."""

from __future__ import annotations

import pytest

from domain.result import Err, Ok, is_err, is_ok


def test_ok_holds_value_and_discriminant_true() -> None:
    result = Ok(42)
    assert result.ok is True
    assert result.value == 42


def test_err_holds_error_and_discriminant_false() -> None:
    result = Err("실패 사유")
    assert result.ok is False
    assert result.error == "실패 사유"


def test_is_ok_and_is_err_discriminate_correctly() -> None:
    ok_result = Ok(1)
    err_result: Err[str] = Err("오류")

    assert is_ok(ok_result) is True
    assert is_err(ok_result) is False
    assert is_ok(err_result) is False
    assert is_err(err_result) is True


def test_ok_rejects_false_discriminant() -> None:
    with pytest.raises(ValueError):
        Ok(1, ok=False)


def test_err_rejects_true_discriminant() -> None:
    with pytest.raises(ValueError):
        Err("x", ok=True)


def test_ok_and_err_are_frozen() -> None:
    result = Ok(1)
    with pytest.raises(Exception):
        result.value = 2  # type: ignore[misc]
