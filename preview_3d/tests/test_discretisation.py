"""Tests for s-runner discretisation."""

import pytest

from preview_3d.geometry.discretisation import generate_s_runner


class TestGenerateSRunner:
    """S-runner generates sample points along a road segment."""

    def test_basic_generation(self):
        result = generate_s_runner(step=1.0, length=5.0)
        assert result == pytest.approx([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])

    def test_always_includes_endpoint(self):
        result = generate_s_runner(step=0.3, length=1.0)
        assert result[-1] == pytest.approx(1.0)
        assert result[0] == pytest.approx(0.0)

    def test_with_start_offset(self):
        result = generate_s_runner(step=1.0, length=3.0, start=2.0)
        assert result == pytest.approx([2.0, 3.0, 4.0, 5.0])

    def test_no_duplicate_endpoint(self):
        # When length is exact multiple of step, don't duplicate last point
        result = generate_s_runner(step=0.5, length=2.0)
        assert len(result) == len(set(round(x, 10) for x in result))

    def test_zero_length(self):
        result = generate_s_runner(step=0.2, length=0.0)
        assert result == pytest.approx([0.0])

    def test_step_larger_than_length(self):
        result = generate_s_runner(step=10.0, length=3.0)
        assert result == pytest.approx([0.0, 3.0])

    def test_default_step(self):
        result = generate_s_runner(length=1.0)
        # Default step is 0.2, so: 0, 0.2, 0.4, 0.6, 0.8, 1.0
        assert len(result) == 6
        assert result[0] == pytest.approx(0.0)
        assert result[-1] == pytest.approx(1.0)

    def test_extra_points_merged(self):
        result = generate_s_runner(step=1.0, length=5.0, extra_points=[2.5, 3.5])
        assert 2.5 in result
        assert 3.5 in result
        # Still sorted
        assert result == sorted(result)

    def test_extra_points_deduplicated(self):
        result = generate_s_runner(step=1.0, length=5.0, extra_points=[2.0, 3.0])
        # 2.0 and 3.0 are already in the regular grid, no duplicates
        assert len(result) == len(set(round(x, 10) for x in result))
