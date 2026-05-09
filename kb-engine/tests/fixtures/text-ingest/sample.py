"""Sample Python file for text-ingest tests.

Two top-level functions, one class with two methods. The chunker should
emit one chunk per top-level definition (the class is one chunk regardless
of how many methods it contains).
"""
from __future__ import annotations


def add(a: int, b: int) -> int:
    """Return the sum of two ints."""
    return a + b


def multiply(a: int, b: int) -> int:
    """Return the product of two ints."""
    return a * b


class Calculator:
    """A trivial stateful calculator used to exercise class chunking."""

    def __init__(self, start: int = 0) -> None:
        self.value = start

    def add(self, x: int) -> int:
        self.value += x
        return self.value

    def reset(self) -> None:
        self.value = 0
