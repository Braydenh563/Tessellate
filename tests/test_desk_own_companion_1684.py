"""INBOX 1684: the desk overlay draws the companions the app's picker offers (your name, the chat's persona,
your own character, saved ones), not only Atlas. The app window draws the figure's frames
(`frontend/js/desk-frames.js`), `core/overlay/capture.py` crops and keeps them per figure, `SpriteSet` reads
them as it reads a shipped look, and `DeskCompanion` asks for them when the look in force has none, with Atlas
standing in until they land. Fake app window and fake runner, a fixed clock; the real page capture is measured
by the sweep named in the CHANGELOG line."""

from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path

import pytest

from tessellate.core import desk_companion as dc
from tessellate.core.overlay import capture, sprites
from tests.test_desk_companion import prefs  # noqa: F401
from tests.test_desk_overlay_wiring import FakeRunner, over  # noqa: F401

Image = pytest.importorskip("PIL.Image")
ROOT = Path(__file__).resolve().parents[1]
CANVAS = (560, 600)


def figure_png(name: str, offset: int = 0) -> str:
    """A transparent capture with a small coloured figure in it, the arms moving by frame name."""
    im = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    wide = 120 + (len(name) % 5) * 6
    im.paste((200, 90, 70, 255), (220 + offset, 120, 220 + offset + wide, 330))
    out = io.BytesIO()
    im.save(out, format="PNG")
    return base64.b64encode(out.getvalue()).decode()


class FakePage:
    """The app window's side of `capture.fetch_frames`: loads late, draws one frame per two polls."""

    def __init__(self, names=None, loads_after=1, bad=None):
        self.queue = list(names or capture.CAPTURED)
        self.loads_after, self.bad = loads_after, bad
        self.polls = 0
        self.stopped = False

    def __call__(self, script: str):
        if script == capture.LOAD_SCRIPT:
            self.loads_after -= 1
            return "ready" if self.loads_after < 0 else "loading"
        if script == capture.START_SCRIPT:
            return str(len(self.queue))
        if script == capture.STOP_SCRIPT:
            self.stopped = True
            return "ok"
        assert script == capture.NEXT_SCRIPT
        self.polls += 1
        if self.polls % 2:
            return "wait"
        if self.bad == "error":
            return json.dumps({"error": "stand: the figure would not draw"})
        if not self.queue:
            return json.dumps({"done": True})
        name = self.queue.pop(0)
        return json.dumps({"name": name, "png": "not base64!" if self.bad == name else figure_png(name)})


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def fetch(page, clock=None):
    clock = clock or Clock()
    return capture.fetch_frames(page, sleep=clock.sleep, clock=clock)


def test_the_key_is_stable_per_figure_and_refuses_nothing_worth_keying() -> None:
    a = capture.key_for("e8e643391b59bb61")
    assert a == capture.key_for("e8e643391b59bb61") and a != capture.key_for("e8e643391b59bb62")
    assert capture.is_key(a) and not capture.is_key("masculine") and not capture.is_key("c-../..")
    assert capture.key_for("") is None and capture.key_for(None) is None and capture.key_for("x" * 300) is None


def test_the_frames_are_fetched_by_polling_a_page_that_loads_late() -> None:
    page = FakePage()
    frames = fetch(page)
    assert set(frames) == set(capture.CAPTURED) and len(frames) == 48
    assert frames["stand"].size == CANVAS and page.loads_after < 0


@pytest.mark.parametrize("bad, why", [("error", "would not draw"), ("sit", "sit was not a picture")])
def test_a_page_error_or_a_bad_picture_is_one_named_failure(bad, why) -> None:
    with pytest.raises(capture.CaptureError, match=why):
        fetch(FakePage(bad=bad))


def test_a_page_that_never_loads_or_never_answers_gives_up() -> None:
    with pytest.raises(capture.CaptureError, match="did not load"):
        fetch(FakePage(loads_after=10**6))

    class Stuck(FakePage):
        def __call__(self, script):
            return "wait" if script == capture.NEXT_SCRIPT else super().__call__(script)

    page = Stuck()
    with pytest.raises(capture.CaptureError, match="too long"):
        fetch(page)
    assert page.stopped


def test_a_set_is_cropped_to_one_box_with_cards_and_is_whole_or_absent(tmp_path) -> None:
    frames = fetch(FakePage())
    # one frame leans out: the shared box must hold it, and every frame is cut to the same size
    frames["tumble"] = capture.decode(figure_png("tumble", offset=60))
    folder = capture.write_set(capture.key_for("a"), frames, root=tmp_path)
    assert capture.complete(folder.name, root=tmp_path)
    # Intent moved (INBOX 1696 x): the optional wave swing frames are not part of a captured set.
    sizes = {Image.open(folder / f"{n}.png").size for n in (*capture.CAPTURED, *sprites.CARD_FRAMES)}
    assert len(sizes) == 1
    width, height = sizes.pop()
    assert width < CANVAS[0] and height < CANVAS[1]
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")]
    drawn = Image.open(folder / "card0.png").getchannel("A").getbbox()
    plain = Image.open(folder / "stand.png").getchannel("A").getbbox()
    assert drawn != plain  # the card was drawn over the stand


def test_a_short_cut_or_uneven_capture_writes_nothing(tmp_path) -> None:
    frames = fetch(FakePage())
    key = capture.key_for("b")
    short = {k: v for k, v in frames.items() if k != "hang"}
    with pytest.raises(ValueError, match="missing"):
        capture.write_set(key, short, root=tmp_path)
    cut = dict(frames, hop=capture.decode(figure_png("hop", offset=330)))
    with pytest.raises(ValueError, match="cut"):
        capture.write_set(key, cut, root=tmp_path)
    odd = dict(frames, hop=Image.new("RGBA", (10, 10)))
    with pytest.raises(ValueError, match="size"):
        capture.write_set(key, odd, root=tmp_path)
    assert list(tmp_path.iterdir()) == [] and not capture.complete(key, root=tmp_path)


def test_only_the_newest_sets_are_kept(tmp_path) -> None:
    frames = fetch(FakePage())
    import os

    for i in range(capture.KEEP + 3):
        folder = capture.write_set(capture.key_for(f"fig{i}"), frames, root=tmp_path)
        os.utime(folder, (1000 + i, 1000 + i))
    kept = sorted(p.name for p in tmp_path.iterdir())
    assert len(kept) == capture.KEEP and capture.key_for(f"fig{capture.KEEP + 2}") in kept and capture.key_for("fig0") not in kept


def test_a_captured_set_loads_as_a_look_that_walks(tmp_path, monkeypatch) -> None:
    key = capture.key_for("c")
    capture.write_set(key, fetch(FakePage()), root=tmp_path)
    monkeypatch.setattr(capture, "cache_root", lambda: tmp_path)
    monkeypatch.setattr(sprites, "captured_root", lambda: tmp_path)  # where a SpriteSet finds it (no import cycle)
    assert sprites.look_for(key) == key and sprites.look_for("FEMININE") == "feminine" and sprites.look_for("c-zz") == "masculine"
    spr = sprites.SpriteSet(key)
    assert spr.gait == "walk" and spr.missing() == [] and spr.walk_count() == 12 and spr.idle_count() == 24
    frame = spr.frame("stand", 96)
    assert frame.width > 0 and frame.box[2] > frame.box[0] and spr.size(192)[0] == 2 * spr.size(96)[0]
    assert spr.frame("sitblink", 96).width == spr.frame("sit", 96).width  # no charted eyes: it sits with them open
    assert sprites.SpriteSet("feminine").gait == "float"  # Atlas is unchanged


def test_the_page_names_exactly_the_frames_python_wants() -> None:
    js = (ROOT / "frontend" / "js" / "desk-frames.js").read_text(encoding="utf-8")
    walk, idle = (int(re.search(rf"DESK_{k}_N = (\d+)", js).group(1)) for k in ("WALK", "IDLE"))
    names = set(re.findall(r'\{ name: "(\w+)"', js)) | {f"walk{i}" for i in range(walk)} | {f"idle{i}" for i in range(idle)}
    # The page also renders the wave swing for the offline renderer (`name: \`wave${i}\``, a template literal
    # the scan above cannot see); a capture must not ask for it, or the first `wave0` stops it as an unknown
    # frame (review of deskframes-1108: `deskFramesStart(null)` asked for all 54).
    assert re.search(r"name: `wave\$\{i\}`", js) and not set(sprites.WAVE_FRAMES) & set(capture.CAPTURED)
    names |= set(sprites.WAVE_FRAMES)
    assert names == set(capture.CAPTURED) | set(sprites.WAVE_FRAMES), names ^ set(capture.CAPTURED)
    asked = json.loads(re.search(r"deskFramesStart\((\[.*?\])\)", capture.START_SCRIPT).group(1))
    assert asked == list(capture.CAPTURED)
    assert "lazyScript('/js/desk-frames.js')" in capture.LOAD_SCRIPT and "function lazyScript(" in (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    for fn in ("deskFramesStart", "deskFramesNext", "deskFramesStop"):
        assert f"function {fn}(" in js and fn in capture.START_SCRIPT + capture.NEXT_SCRIPT + capture.STOP_SCRIPT


# --- the overlay's side -------------------------------------------------------------------------------


def hold_draws(monkeypatch) -> list:
    """The frame draw's worker is held, not run, so a test runs it when it means to; other workers run."""
    held: list = []
    real = dc.jobs.thread

    def thread(name, target, stop=None):
        if name == "desk-frames":
            held.append(target)
            return None
        return real(name, target, stop)

    monkeypatch.setattr(dc.jobs, "thread", thread)
    return held


def look_data(sig="abc123", who="me", atlas=False, locked=False, look="masculine"):
    return {"locked": locked, "look": look, "who": who, "figure": {"atlas": atlas, "sig": sig}, "motion": {"mode": "full", "reason": ""}}


def test_atlas_and_an_empty_figure_have_no_key_and_the_default_persona_is_atlas() -> None:
    assert dc.figure_key(look_data(who="atlas")) is None
    assert dc.figure_key(look_data(who="persona", atlas=True)) is None  # the chat's default voice is drawn as Atlas
    assert dc.figure_key(look_data(sig="")) is None and dc.figure_key({"who": "me"}) is None
    assert dc.figure_key(look_data()) == capture.key_for("abc123")
    assert dc.figure_key(look_data(who="custom")) == dc.figure_key(look_data(who="me"))  # the same figure, the same frames


def test_a_figure_without_frames_shows_atlas_while_they_are_drawn_then_restarts_as_itself(over, tmp_path, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(capture, "cache_root", lambda: tmp_path)
    key = capture.key_for("abc123")
    pages = {"data": look_data(look="feminine"), "frames": FakePage()}
    started = hold_draws(monkeypatch)

    def run(script):
        if script == dc.LOOK_SCRIPT:
            return json.dumps(pages["data"])
        return pages["frames"](script)

    over.main_window.evaluate_js = run
    over.set_main_hidden(True)
    assert FakeRunner.started[0].look == "feminine"  # Atlas, in the look the app gave, until the frames land
    assert len(started) == 1 and key in over._rendering  # noqa: SLF001
    over.set_main_hidden(False)
    over.set_main_hidden(True)
    assert len(started) == 1  # one draw at a time for one figure


def test_a_finished_draw_restarts_the_figure_in_its_own_frames(over, tmp_path, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(capture, "cache_root", lambda: tmp_path)
    key = capture.key_for("abc123")
    jobs_run = hold_draws(monkeypatch)
    page = FakePage()
    over.main_window.evaluate_js = lambda script: json.dumps(look_data()) if script == dc.LOOK_SCRIPT else page(script)
    clock = Clock()
    real = capture.fetch_frames
    monkeypatch.setattr(capture, "fetch_frames", lambda ask: real(ask, sleep=clock.sleep, clock=clock))
    over.set_main_hidden(True)
    first = FakeRunner.started[0]
    assert first.look == "masculine" and not capture.complete(key)
    jobs_run.pop()()  # the worker runs
    assert capture.complete(key) and not over._rendering  # noqa: SLF001
    assert FakeRunner.started[-1].look == key and FakeRunner.started[-1] is not first and "stop" in first.calls


def test_a_failed_draw_is_logged_kept_atlas_and_not_retried_at_once(over, tmp_path, monkeypatch, caplog) -> None:  # noqa: F811
    monkeypatch.setattr(capture, "cache_root", lambda: tmp_path)
    jobs_run = hold_draws(monkeypatch)
    over.main_window.evaluate_js = lambda script: json.dumps(look_data()) if script == dc.LOOK_SCRIPT else None
    clock = Clock()
    real = capture.fetch_frames
    monkeypatch.setattr(capture, "fetch_frames", lambda ask: real(ask, sleep=clock.sleep, clock=clock))
    over.set_main_hidden(True)
    with caplog.at_level("WARNING"):
        jobs_run.pop()()
    assert "could not draw the companion's frames" in caplog.text
    assert len(FakeRunner.started) == 1 and FakeRunner.started[0].look == "masculine"
    over.set_main_hidden(False)
    over.set_main_hidden(True)
    assert jobs_run == []  # inside the retry gap


def test_a_locked_app_draws_nothing_and_keeps_the_last_frames(over, tmp_path, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(capture, "cache_root", lambda: tmp_path)
    key = capture.key_for("abc123")
    capture.write_set(key, fetch(FakePage()), root=tmp_path)
    jobs_run = hold_draws(monkeypatch)
    state = {"data": look_data()}
    over.main_window.evaluate_js = lambda script: json.dumps(state["data"])
    over.set_main_hidden(True)
    assert FakeRunner.started[0].look == key and jobs_run == []  # frames already there: used at once
    state["data"] = look_data(sig="other", locked=True, look="masculine")  # a locked window cannot say what it draws
    over.set_main_hidden(False)
    over.set_main_hidden(True)
    assert jobs_run == [] and FakeRunner.started[-1].look == key


def test_a_pruned_saved_set_does_not_start_a_runner_that_cannot_load(over, tmp_path, monkeypatch, prefs) -> None:  # noqa: F811
    monkeypatch.setattr(capture, "cache_root", lambda: tmp_path)
    prefs[dc.LOOK_PREF] = capture.key_for("gone")  # saved, and its folder was pruned
    over.main_window.evaluate_js = lambda script: json.dumps(look_data(locked=True)) if script == dc.LOOK_SCRIPT else None
    over.set_main_hidden(True)
    assert FakeRunner.started[0].look == "masculine"


@pytest.mark.parametrize("kind", ["me", "persona", "custom"])
def test_choosing_one_of_your_own_writes_its_pref_and_asks_for_its_frames(over, kind, tmp_path, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(capture, "cache_root", lambda: tmp_path)
    held = hold_draws(monkeypatch)
    seen: list[str] = []
    state = {"data": look_data(who="atlas", atlas=True)}

    def run(script):
        seen.append(script)
        if script == dc.LOOK_SCRIPT:
            return json.dumps(state["data"])
        if "prefs.set('avatar-buddy'," in script:
            state["data"] = look_data(who=kind, sig="sig-" + kind)  # the app now draws that figure
            return "ok"
        return None

    over.main_window.evaluate_js = run
    over.set_main_hidden(True)
    assert dc.DeskApi(over).choose_companion(kind) == "ok"
    write = next(s for s in seen if "prefs.set('avatar-buddy'," in s)
    assert f'prefs.set(\'avatar-buddy\',"{kind}")' in write and "syncNameMarkBuddy" in write and "'locked'" in write
    assert "atlas-look" not in write
    assert len(held) == 1 and capture.key_for("sig-" + kind) in over._rendering  # noqa: SLF001
    assert FakeRunner.started[-1].look == "masculine"  # Atlas stands in while it is drawn
