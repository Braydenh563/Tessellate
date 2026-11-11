"""B66 and the owner's 2026-11-10 log (22:10): the desk figure was shown and hidden four times in 16 s ("due=True ... overlay
shown", then "due=False (window away=False) ... overlay hidden", every 3 to 4 s). The cause of the flips is on the owner's
machine, so each flip of the app window's away state now says which window event made it and how long the last state held:
a flip back within a second or two is an event that fires twice, a steady 3 to 4 s is something raising and lowering the
window. Fake app window, fixed clock; the behaviour of the flip itself is unchanged."""

from __future__ import annotations

from tessellate.core import desk_companion as dc
from tests.test_desk_companion import prefs  # noqa: F401
from tests.test_desk_overlay_wiring import over  # noqa: F401


def lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if "the app window is" in r.getMessage()]


def test_each_flip_of_the_away_state_names_its_event_and_how_long_the_last_one_held(over, caplog) -> None:  # noqa: F811
    caplog.set_level("INFO", logger=dc.logger.name)
    clock = {"t": 100.0}
    over._now = lambda: clock["t"]  # noqa: SLF001
    over.set_main_hidden(True, "event minimized")
    clock["t"] += 3.5
    over.set_main_hidden(False, "event restored")
    clock["t"] += 0.4
    over.set_main_hidden(True, "hide")
    got = lines(caplog)
    assert got == [
        "desk companion: the app window is away (event minimized)",
        "desk companion: the app window is back (event restored), 3.5 s after the last change",
        "desk companion: the app window is away (hide), 0.4 s after the last change",
    ], got


def test_a_repeat_of_the_same_state_is_not_a_flip_and_is_not_logged(over, caplog) -> None:  # noqa: F811
    caplog.set_level("INFO", logger=dc.logger.name)
    over.set_main_hidden(True, "hide")
    over.set_main_hidden(True, "event minimized")
    assert len(lines(caplog)) == 1 and over.main_hidden


def test_the_wrapped_show_and_hide_pass_their_names(over, caplog) -> None:  # noqa: F811
    caplog.set_level("INFO", logger=dc.logger.name)
    over.main_window.hide()
    over.main_window.show()
    got = lines(caplog)
    assert len(got) == 2 and "(hide)" in got[0] and "(show)" in got[1], got
