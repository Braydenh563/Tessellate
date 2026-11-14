"""The Chrome_WidgetWin teardown error is non-fatal and a restart relaunches (L-world-class-117)."""

from __future__ import annotations

import pytest

from tessellate.core import window_teardown as wt

NOISE = "Failed to unregister class Chrome_WidgetWin_0. Error = 1411"


def test_the_known_message_is_benign_alone_or_repeated():
    assert wt.is_benign_teardown(NOISE)
    assert wt.is_benign_teardown(f"{NOISE}\n\n{NOISE}\n")


def test_any_other_line_makes_it_a_real_error():
    assert not wt.is_benign_teardown(f"{NOISE}\nTraceback (most recent call last):")
    assert not wt.is_benign_teardown("")
    assert not wt.is_benign_teardown("Failed to unregister class Other. Error = 5")


def test_a_clean_close_does_not_relaunch():
    calls = []
    assert wt.run_window(lambda: None, restarting=True, relaunch=lambda: calls.append(1)) == "closed"
    assert calls == []


def test_the_noise_in_a_restarted_copy_relaunches_once():
    calls = []

    def start():
        raise RuntimeError(NOISE)

    assert wt.run_window(start, restarting=True, relaunch=lambda: calls.append(1)) == "relaunched"
    assert calls == [1]


def test_the_noise_in_a_normal_run_is_swallowed_without_relaunch():
    calls = []

    def start():
        raise RuntimeError(NOISE)

    assert wt.run_window(start, restarting=False, relaunch=lambda: calls.append(1)) == "benign"
    assert calls == []


def test_a_real_failure_and_a_type_error_still_propagate():
    def boom():
        raise RuntimeError("WebView2 initialization failed")

    with pytest.raises(RuntimeError):
        wt.run_window(boom, restarting=True, relaunch=lambda: None)

    def old():
        raise TypeError("unexpected keyword")

    with pytest.raises(TypeError):
        wt.run_window(old, restarting=True, relaunch=lambda: None)
