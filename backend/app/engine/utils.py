"""Utility functions for the pricing engine. Pure functions — no DB access."""
import math
from typing import Any


def round_half_up(x: float, decimals: int = 0) -> float:
    """Round using round-half-up convention (not Python's banker's rounding).

    Example: round_half_up(0.125, 2) = 0.13, not 0.12.
    """
    multiplier = 10 ** decimals
    return math.floor(x * multiplier + 0.5) / multiplier


def safe_avg(values: list[float | int]) -> float:
    """Average that returns 0.0 for empty lists instead of raising."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns default instead of raising on zero denominator."""
    if denominator == 0:
        return default
    return numerator / denominator
