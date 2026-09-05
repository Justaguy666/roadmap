"""
Result monad — lightweight Ok/Err type for explicit error propagation.

Keeps domain services free from exception-based flow control.

Usage::

    def divide(a: float, b: float) -> Result[float, str]:
        if b == 0:
            return Err("division by zero")
        return Ok(a / b)

    result = divide(10, 2)
    match result:
        case Ok(value):
            print(value)
        case Err(error):
            print(f"Error: {error}")
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


@dataclass(frozen=True)
class Ok(Generic[T]):
    """Successful result wrapping a value."""

    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def unwrap_or(self, default: T) -> T:  # noqa: ARG002
        return self.value

    def map(self, fn: Callable[[T], U]) -> Ok[U]:
        return Ok(fn(self.value))

    def __bool__(self) -> bool:
        return True


@dataclass(frozen=True)
class Err(Generic[E]):
    """Failed result wrapping an error."""

    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> None:
        raise ValueError(f"Called unwrap() on Err: {self.error}")

    def unwrap_or(self, default: object) -> object:
        return default

    def map(self, fn: object) -> Err[E]:  # noqa: ARG002
        return self

    def __bool__(self) -> bool:
        return False


# Type alias for convenience
Result = Ok[T] | Err[E]
