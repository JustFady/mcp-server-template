import pytest

from mcp_template.ratelimit import SlidingWindow


def test_limit_and_window_expiry():
    clock = [0.0]
    w = SlidingWindow(limit=3, window_seconds=60, now=lambda: clock[0])
    assert all(w.allow("a") for _ in range(3))
    assert not w.allow("a")
    assert w.allow("b")                      # keys are independent
    assert 59 <= w.retry_after("a") <= 60
    clock[0] = 61
    assert w.allow("a")                      # window slid
    assert w.retry_after("a") == 0.0


def test_rejects_bad_limit():
    with pytest.raises(ValueError):
        SlidingWindow(limit=0)
