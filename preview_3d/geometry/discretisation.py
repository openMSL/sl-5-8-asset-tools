"""S-runner discretisation for sampling road geometry along s-coordinate."""

from __future__ import annotations

DEFAULT_STEP: float = 0.2  # meters


def generate_s_runner(
    length: float,
    step: float = DEFAULT_STEP,
    start: float = 0.0,
    extra_points: list[float] | None = None,
) -> list[float]:
    """Generate sample s-positions along a road segment.

    Args:
        length: Length of the segment.
        step: Spacing between sample points (default 0.2m).
        start: Starting s-coordinate.
        extra_points: Additional s-values to include (e.g. road mark boundaries).

    Returns:
        Sorted, deduplicated list of s-positions from start to start+length.
    """
    end = start + length

    if length <= 0.0:
        return [start]

    # Build regular grid
    points: set[float] = set()
    current = start
    while current < end - 1e-10:
        points.add(round(current, 10))
        current += step
    points.add(round(end, 10))

    # Merge extra points within range
    if extra_points:
        for p in extra_points:
            if start - 1e-10 <= p <= end + 1e-10:
                points.add(round(p, 10))

    return sorted(points)
