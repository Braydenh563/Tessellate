"""INBOX 1719 b and 1696 j (the owner: "it doesnt react to anything that happens on my screen"): the desk companion
answers the day and the desk as well as the windows. Dusk (the first evening hour) is a stretch, not the plain chime;
the morning's first input is a wave and a yawn (once a day, in place of the welcome back); a long run of typing come to
rest is a nod; back from behind a full-screen app it peeks out. Catalogue `react.night_falls`, `react.morning_hello`,
`react.typing_burst`, `react.fullscreen_app` were missing on both sides; the app's side is
`tests/test_atlas_daylife_1719.py`. A fixed clock and the fake win32; nothing here runs on Windows."""

from __future__ import annotations

import pytest

from tessellate.core.overlay import screenwatch as sw
from tests.test_companion_vitals_1719 import _still

pytest.importorskip("PIL")

from tessellate.core.overlay import win32 as k  # noqa: E402
from tests.test_overlay_runner import make, wait_for  # noqa: E402

NEW = ("night_falls", "morning_hello", "fullscreen_app", "typing_burst")


def watch() -> sw.ScreenWatch:
    return sw.ScreenWatch(downloads=lambda: None)


def test_dusk_is_a_stretch_and_the_other_hours_still_chime():
    w = watch()
    said = []
    for i, hour in enumerate(range(14, 20)):
        said += w.poll(i * 3600.0, hour, 0, day=100)
    assert said.count("night_falls") == 1 and said.count("hour_chime") == 4, said  # 15, 16, 18, 19 chime; 17 is dusk


def test_the_mornings_first_input_says_hello_once_a_day():
    w = watch()
    w.poll(0.0, 7, 30, day=100)
    assert w.input_seen(1.0, 60.0) == []  # nobody there yet
    assert w.input_seen(2.0, 0.5) == ["morning_hello"]  # the first key of the day
    assert w.input_seen(3.0, 0.5) == []
    assert w.input_seen(700.0, 650.0) == [] and w.input_seen(701.0, 0.5) == ["idle_return"]  # later the same morning
    w.poll(90_000.0, 7, 30, day=101)
    assert w.input_seen(90_001.0, 0.5) == ["morning_hello"]  # the next day
    w.poll(200_000.0, 14, 0, day=102)  # (the hour is taken at the top of the hour)
    assert w.input_seen(200_001.0, 0.5) == []  # an afternoon start: no morning hello


def test_a_long_run_of_typing_that_rests_is_a_burst():
    w = watch()
    t, said = 0.0, []
    for _ in range(20):  # 38 s of typing read at 0.5 Hz, one 3 s pause inside it
        said += w.typing_seen(t, True)
        t += 2.0
    said += w.typing_seen(t + 1.0, False)
    assert said == []  # resting under `BURST_GAP`: not over yet
    said += w.typing_seen(t + 4.5, False)
    assert said == ["typing_burst"]
    short = watch()
    for i in range(5):  # 8 s of typing
        short.typing_seen(i * 2.0, True)
    assert short.typing_seen(20.0, False) == []


@pytest.mark.parametrize("kind", NEW)
def test_each_is_played_by_the_figure(kind: str):
    e = _still(1)
    e.update(1.0)
    assert e.react(kind, 2.0)
    frames, faces = set(), set()
    t = 2.0
    while t < 6.0:
        t += 0.05
        out = e.update(t)
        frames.add(out.frame)
        faces.add(out.face[0] if out.face else None)
    assert faces - {None, "blink"}, kind  # it wears the reaction's face
    if kind == "morning_hello":
        assert "wave" in frames and "blink" in frames  # a wave, then the eyes shut a moment (the yawn)


def test_back_from_a_full_screen_app_it_peeks_out(caplog):
    caplog.set_level("INFO", logger="tessellate.core.overlay.runner")
    r, fake, clock, *_ = make(reduced=False)
    assert r.start()
    r.show()
    assert wait_for(lambda: r.host.visible)
    fake.notification = k.QUNS_D3D_FULL_SCREEN
    clock.t += 5
    fake.post(k.WM_TIMER)
    assert wait_for(lambda: r.busy)
    fake.notification = 5
    clock.t += 3
    fake.post(k.WM_TIMER)
    assert wait_for(lambda: not r.busy and r.host.visible)
    assert wait_for(lambda: any(rec.getMessage() == "overlay: screen event fullscreen_app" for rec in caplog.records))
    r.stop()
