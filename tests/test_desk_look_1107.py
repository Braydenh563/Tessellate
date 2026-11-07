"""INBOX 1692 (i): "You, from your name" was ticked in the desk companion's Look menu and the figure stayed Atlas.
A chosen look reaches the drawn figure or says why: the figure is re-read (bounded) while the app window has not
drawn it yet, a reason is logged whenever your own companion gets no frames, and the Companion panel says in one
line that frames are being drawn or could not be. Fake app window, fake runner, fixed clock."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessellate.core import desk_companion as dc
from tessellate.core.overlay import capture
from tests.test_desk_companion import prefs  # noqa: F401
from tests.test_desk_own_companion_1684 import Clock, FakePage, look_data
from tests.test_desk_overlay_wiring import FakeRunner, over  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch, tmp_path):
    monkeypatch.setattr(capture, "cache_root", lambda: tmp_path)
    monkeypatch.setattr(dc.time, "sleep", lambda s: None)


def held_draws(monkeypatch) -> list:
    held: list = []
    real = dc.jobs.thread
    monkeypatch.setattr(dc.jobs, "thread", lambda name, target, stop=None: held.append(target) if name == "desk-frames" else real(name, target, stop))
    return held


def test_a_figure_the_page_has_not_redrawn_yet_is_read_again_until_it_changes(over, monkeypatch) -> None:  # noqa: F811
    held = held_draws(monkeypatch)
    answers = [look_data(who="me", atlas=True, sig="old"), look_data(who="me", sig=""), look_data(who="me", sig="mine")]
    reads: list[int] = []

    def run(script):
        if script == dc.LOOK_SCRIPT:
            reads.append(1)
            return json.dumps(answers[min(len(reads) - 1, 2)])
        return None

    over.main_window.evaluate_js = run
    over.set_main_hidden(True)
    assert len(reads) == 3 and len(held) == 1  # the third read had the figure, so its frames are asked for
    assert capture.key_for("mine") in over._rendering  # noqa: SLF001


def test_the_reread_is_bounded_when_the_page_never_draws_it_and_the_reason_is_logged(over, caplog) -> None:  # noqa: F811
    reads: list[int] = []

    def run(script):
        if script == dc.LOOK_SCRIPT:
            reads.append(1)
            return json.dumps(look_data(who="me", atlas=True))
        return None

    over.main_window.evaluate_js = run
    with caplog.at_level("INFO"):
        over.set_main_hidden(True)
    assert 1 < len(reads) <= dc.FIGURE_READS
    assert "Atlas stays" in caplog.text and "'me'" in caplog.text
    assert FakeRunner.started[0].look in ("masculine", "feminine")


def test_the_default_persona_is_atlas_on_purpose_and_is_not_reread(over) -> None:  # noqa: F811
    reads: list[int] = []

    def run(script):
        if script == dc.LOOK_SCRIPT:
            reads.append(1)
            return json.dumps(look_data(who="persona", atlas=True))
        return None

    over.main_window.evaluate_js = run
    over.set_main_hidden(True)
    assert len(reads) == 1


def test_the_panel_says_when_frames_are_being_drawn_and_when_they_could_not_be(over, monkeypatch) -> None:  # noqa: F811
    held = held_draws(monkeypatch)
    page = FakePage()
    state = {"locked": False, "who": "me", "look": "auto", "presets": []}

    def run(script):
        if script == dc.LOOK_SCRIPT:
            return json.dumps(look_data())
        if script == dc.COMPANION_SCRIPT:
            return json.dumps(state)
        return page(script)

    over.main_window.evaluate_js = run
    api = dc.DeskApi(over)
    assert "note" not in api.companion_choices()
    over.set_main_hidden(True)
    note = api.companion_choices()["note"]
    assert note == "Summoning your companion to the desk. Atlas keeps you company until it arrives."  # Intent moved: the owner, 2026-11-07, "drawing is too technical", so the line says summoning.

    def silent(script):
        if script == dc.LOOK_SCRIPT:
            return json.dumps(look_data())
        return json.dumps(state) if script == dc.COMPANION_SCRIPT else None

    over.main_window.evaluate_js = silent
    clock = Clock()
    real = capture.fetch_frames
    monkeypatch.setattr(capture, "fetch_frames", lambda ask: real(ask, sleep=clock.sleep, clock=clock))
    held.pop()()  # the worker runs against a page that does not answer
    failed = api.companion_choices()["note"]
    assert failed == "Your companion could not be summoned to the desk yet, so Atlas stays. It will try again."
    for text in (note, failed):
        assert chr(0x2014) not in text and "!" not in text


def test_the_panel_page_shows_the_note() -> None:
    js = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
    body = js.split("async function openCompanion()", 1)[1].split("//: Run `action` first", 1)[0]
    assert "got?.note" in body and "note(got.note)" in body


# --- INBOX 1692 (k): the card instead of the figure, the bare figure on it, and a show that took many toggles ---


def test_twenty_minimise_and_restore_toggles_show_and_hide_the_figure_every_time(over) -> None:  # noqa: F811
    for i in range(20):
        over.set_main_hidden(True)
        assert over.shown and over.runner is not None and not over.overlay_failed, i
        assert over.runner.calls[-1] == "show", i
        over.set_main_hidden(False)
        assert not over.shown and over.runner.calls[-1] == "hide", i
    assert len(FakeRunner.started) == 1  # one runner served all twenty


def test_a_slow_first_start_does_not_cost_the_see_through_figure_for_good(over, caplog) -> None:  # noqa: F811
    over.box.ok = False
    with caplog.at_level("INFO"):
        over.set_main_hidden(True)
    assert over.overlay_failed and over.shown and over.window is not None  # the card, for now
    assert "did not start in time" in caplog.text
    note = over.panel_motion()["note"]
    assert "did not start in time" in note and "tries again" in note and chr(0x2014) not in note and "!" not in note
    over.set_main_hidden(True)
    assert len(FakeRunner.started) == 1  # not retried at every sync
    over.box.ok = True
    over.set_main_hidden(False)
    over.set_main_hidden(True)
    assert not over.overlay_failed and over.runner is not None and over.shown and over.runner.calls[-1] == "show"
    assert over.window is not None and over.panel and "overlay=1" in over.webview.made[-1].options["url"]


def test_the_retries_are_bounded(over) -> None:  # noqa: F811
    over.box.ok = False
    for _ in range(dc.OVERLAY_TRIES + 3):
        over.set_main_hidden(True)
        over.set_main_hidden(False)
    assert len(FakeRunner.started) == dc.OVERLAY_TRIES
    assert "tries again" not in over.panel_motion()["note"]


def test_a_drawn_companion_whose_frames_will_not_start_falls_back_to_atlas_not_the_card(over, monkeypatch) -> None:  # noqa: F811
    key = capture.key_for("abc123")
    monkeypatch.setattr(capture, "complete", lambda k, root=None: k == key)
    over.main_window.evaluate_js = lambda script: json.dumps(look_data()) if script == dc.LOOK_SCRIPT else None

    def factory(**kw):
        return FakeRunner(ok=not capture.is_key(kw["look"]), **kw)

    over._overlay_factory = factory  # noqa: SLF001
    over.set_main_hidden(True)
    assert not over.overlay_failed and over.runner is not None and over.runner.look == "masculine"
    assert over.window is not None and over.panel


def test_the_card_draws_the_figure_with_your_chosen_parts() -> None:
    js = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
    body = js.split("function draw()", 1)[1].split("// --- locked or open", 1)[0]
    assert "nameMarkOwnFor(name)" in body and "key === seedShown" in body  # same name, new parts: drawn again
    assert "characterFor(name).figure()" in body


def test_a_start_that_was_only_slow_is_tried_again_in_a_due_sync_without_a_restore(over, monkeypatch) -> None:  # noqa: F811
    """The owner's log: the host timed out, then every minimise used the card. A later due sync tries the figure again."""
    clock = {"t": 1000.0}
    monkeypatch.setattr(over, "_now", lambda: clock["t"])
    over.box.ok = False
    over.set_main_hidden(True)
    assert over.overlay_failed and over.shown
    over.box.ok = True  # the host would now report ready in time
    over.set_main_hidden(True)
    assert over.overlay_failed and len(FakeRunner.started) == 1  # inside the gap
    clock["t"] += dc.OVERLAY_RETRY_GAP + 1
    over.set_main_hidden(True)
    assert not over.overlay_failed and over.runner is not None and over.runner.calls[-1] == "show"
    assert len(FakeRunner.started) == 2 and over.panel  # the card window is gone, the quick panel is the window
