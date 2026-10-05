"""Small statistics helpers for Tally (Chapter 11's coverage example)."""


def mean(xs: list[float]) -> float:
    """Arithmetic mean; raises ValueError on an empty list."""
    if not xs:
        raise ValueError("mean of empty list")
    return sum(xs) / len(xs)


def median(xs: list[float]) -> float:
    """Median; raises ValueError on an empty list."""
    if not xs:
        raise ValueError("median of empty list")
    s = sorted(xs)
    mid = len(s) // 2
    if len(s) % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2


def clamp(x: float, lo: float, hi: float) -> float:
    """Limit x to the closed interval [lo, hi].

    Returns lo if x < lo, hi if x > hi, otherwise x.
    """
    return max(lo, min(hi, x))
