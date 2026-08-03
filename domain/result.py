"""``Result[T, E]`` 판별 유니온.

설계 문서(Components and Interfaces > 핵심 포트와 함수 시그니처)의 다음 계약 의사코드를
Python으로 구현한다::

    type Result<T, E> =
      | { ok: true; value: T }
      | { ok: false; error: E };

``Ok``와 ``Err``는 판별 필드 ``ok``로 구분되는 불변(frozen) dataclass다. 두 클래스 모두
``Result`` 프로토콜에 부합하도록 ``ok`` 필드를 갖는다. 도메인 함수는 예외를 던지는 대신
이 타입을 반환해 실패를 명시적으로 표현한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Ok(Generic[T]):
    """성공 결과. ``value``에 성공 값을 담는다."""

    value: T
    ok: bool = True

    def __post_init__(self) -> None:
        if not self.ok:
            raise ValueError("Ok.ok must be True")


@dataclass(frozen=True)
class Err(Generic[E]):
    """실패 결과. ``error``에 오류 값을 담는다."""

    error: E
    ok: bool = False

    def __post_init__(self) -> None:
        if self.ok:
            raise ValueError("Err.ok must be False")


Result = Union[Ok[T], Err[E]]
"""성공(``Ok[T]``) 또는 실패(``Err[E]``)를 판별 필드 ``ok``로 구분하는 유니온 타입."""


def is_ok(result: "Result[T, E]") -> bool:
    """``result``가 ``Ok``인지 여부를 반환한다."""

    return result.ok


def is_err(result: "Result[T, E]") -> bool:
    """``result``가 ``Err``인지 여부를 반환한다."""

    return not result.ok
