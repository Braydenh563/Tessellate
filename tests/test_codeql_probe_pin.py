"""CodeQL bisect probe: pin_clock reachable from one test, no lint."""


def test_pin_clock_is_called(monkeypatch):
    from datetime import datetime

    from tests._clock import pin_clock

    pin_clock(monkeypatch, datetime(2026, 8, 1, 9, 0))
