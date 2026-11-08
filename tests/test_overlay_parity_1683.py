"""INBOX 1683 asks M4 to M7 and B9 quality: the desk figure's props and prop acts, its face and micro-expressions,
its answers to the pointer (pat, rub, poke by mood, flip, flinch, hover) and to the screen (a window opening or
closing, the app changing, the hour, the battery, a download). The engine, its fakes and a fixed clock; nothing
here runs on Windows. Before and after numbers are in `tests/overlay_parity_sim.py`."""

from __future__ import annotations

import random

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import behaviour as bh  # noqa: E402
from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay import extras, faces, props, screenwatch  # noqa: E402
from tessellate.core.overlay.sprites import SpriteSet  # noqa: E402
from tests.overlay_parity_sim import picture  # noqa: E402
from tests.test_overlay_ride_1670 import make  # noqa: E402

LOOKS = ("masculine", "feminine")


def settle(e: eng.Engine, secs: float = 3.0, t: float = 0.0) -> float:
    for _ in range(int(secs / 0.05)):
        t += 0.05
        e.update(t)
    return t


def still(look: str = "masculine", seed: int = 2) -> tuple[eng.Engine, SpriteSet, float]:
    """A standing figure with no trip, climb or in-place act due: only what the test asks for happens."""
    e, s = make(look, "float", seed)
    e.presence = False  # Intent moved (INBOX 1692, 00:50Z): spells (presence) have their own tests; this one measures the plain acts
    e._enter("stand", 0.0)  # its first hold was drawn with presence on
    e.big_ready = e.trip_ready = e.climb_ready = e.ex.act_ready = float("inf")
    e.next_ambient = float("inf")
    e.ex.micro.next_at = float("inf")
    return e, s, settle(e, 1.0)


# --- the face ----------------------------------------------------------------------------------


@pytest.mark.parametrize("look", LOOKS)
def test_every_expression_changes_the_face_and_nothing_else(look: str) -> None:
    s = SpriteSet(look)
    base = s.frame("stand", 96, False)
    for kind in faces.EXPRESSIONS:
        drawn = faces.draw(s, "stand", base, False, None, (kind, 3), base)
        assert drawn.bgra != base.bgra, kind
        changed = [i for i in range(0, len(base.bgra), 4) if drawn.bgra[i:i + 4] != base.bgra[i:i + 4]]
        rows = {i // 4 // base.width for i in changed}
        # all of it is on the head: inside the band from the brows to the chin
        assert min(rows) >= 40 and max(rows) <= 90, (kind, min(rows), max(rows))


@pytest.mark.parametrize("look", LOOKS)
def test_a_face_is_left_off_where_there_is_none_to_draw_on(look: str) -> None:
    s = SpriteSet(look)
    for name in ("walk3", "hang", "tumble", "sleep"):
        base = s.frame(name, 96, False)
        assert faces.draw(s, name, base, False, None, ("joy", 3)) is base
    stand = s.frame("stand", 96, False)
    assert faces.draw(s, "stand", stand, False, None, ("joy", 0), stand) is stand
    assert faces.draw(s, "stand", stand, False, None, ("no such", 3), stand) is stand


def test_the_levels_ease_a_look_in_and_out() -> None:
    steps = [faces.level_at(u / 20) for u in range(20)]
    assert steps[0] == 1 and max(steps) == 3 and steps[-1] == 1
    assert faces.level_at(1.0) == 0 and faces.level_at(-0.1) == 0
    assert [extras.ease(t, 2.0) for t in (0.0, 0.13, 0.5, 1.8, 1.95)] == [1, 2, 3, 2, 1]


@pytest.mark.parametrize("look", LOOKS)
def test_the_face_follows_the_head_through_a_pose_and_a_mirror(look: str) -> None:
    s = SpriteSet(look)
    base = s.frame("stand", 96, False)
    flat = faces.head_point(s, "stand", base, False, None)
    leaned = faces.head_point(s, "stand", base, False, (1.0, 1.0, 0.06, 0.0))
    squashed = faces.head_point(s, "stand", base, False, (1.0, 0.9, 0.0, 0.0))
    mirrored = faces.head_point(s, "stand", s.frame("stand", 96, True), True, None)
    assert flat and leaned and squashed and mirrored
    assert leaned[0] > flat[0] + 2  # a lean moves the head the way the warp does
    assert squashed[1] > flat[1] + 3  # a squash about the feet lowers it
    assert abs((mirrored[0] + flat[0]) - base.width) < 1.0  # mirrored about the frame's middle


def test_the_idle_cycle_and_a_sit_and_a_wave_have_a_found_face() -> None:
    s = SpriteSet("masculine")
    for name in ("idle0", "idle12", "sit", "wave", "look"):
        assert faces.eye_anchor(s, name) is not None, name
    assert faces.eye_anchor(s, "walk0") is None


def test_micro_expressions_are_seeded_rare_and_fit_the_mood() -> None:
    def run(seed: int) -> list[tuple[float, str]]:
        m = faces.Micro(random.Random(seed))
        seen, last = [], None
        for i in range(0, 6000):
            now = i * 0.1
            m.tick(now, "curious", True)
            if m.kind and m.kind != last:
                seen.append((round(now, 1), m.kind))
            last = m.kind
        return seen

    a = run(5)
    assert a == run(5) and a != run(6)
    assert 30 <= len(a) <= 90  # one every 6 to 16 s of a ten minute stretch
    assert {k for _t, k in a} <= {k for k, _s in faces.MICRO["curious"]}
    quiet = faces.Micro(random.Random(5))
    for i in range(1000):
        quiet.tick(i * 0.1, "curious", False)  # typing: none
    assert quiet.view(99.0) is None and not quiet.kind


# --- props and prop acts -----------------------------------------------------------------------


@pytest.mark.parametrize("look", LOOKS)
def test_every_prop_is_drawn_on_the_frame_its_act_uses(look: str) -> None:
    s = SpriteSet(look)
    for name, (spec, act, _w) in props.PROP_ACTS.items():
        frame = act.frame if isinstance(act.frame, str) else act.frame[0][1]
        base = s.frame(frame, 96, False)
        for phase in range(spec.steps):
            drawn = props.draw(base, (spec.prop, phase, 3), False)
            assert drawn.bgra != base.bgra, (name, phase)
        a = props.draw(base, (spec.prop, 0, 3), False)
        b = props.draw(base, (spec.prop, 1, 3), False)
        assert a.bgra != b.bgra, name  # it moves: a page, a bobber, a flame, steam
        assert props.draw(base, (spec.prop, 0, 1), False).bgra != a.bgra  # fetched in steps, not at once
        if spec.at[0]:
            assert props.draw(base, (spec.prop, 0, 3), True).bgra != a.bgra  # on the other side when it faces left


def test_the_acts_the_owner_named_exist_and_are_in_the_minds_table() -> None:
    eng.extras.register()
    named = {"read_book", "lounge_beanbag", "go_fishing", "push_ups", "read_map"}
    assert named <= set(bh.ACTIVITIES) and named <= set(props.PROP_ACTS)
    assert len(bh.ACTIVITIES) >= 26 + 9 + 5 + len(extras.REACT_ACTS)
    mind = bh.Mind(0.0)
    mind.needs["curiosity"] = 0.9
    mind.needs["rest"] = 0.9
    table = dict(mind.weights(100.0, "float", 14))
    assert "read_book" in table and "lounge_beanbag" in table
    assert not set(extras.REACT_ACTS) & set(table), "a reaction's act is never chosen on its own"
    assert "push_ups" not in dict(mind.weights(100.0, "float", 14)), "a floater does not do push ups"


def test_the_prop_is_fetched_used_and_put_away() -> None:
    sizes = [(props.view("read_book", u / 50, u / 50 * 40) or (0, 0, 0))[2] for u in range(50)]
    assert sizes[0] == 0 and sizes[-1] <= 1 and max(sizes) == 3
    assert sizes[:6] == sorted(sizes[:6]) and sizes[-6:] == sorted(sizes[-6:], reverse=True)
    assert props.view("breathe", 0.5, 5.0) is None and props.view("read_book", 1.0, 40.0) is None
    assert props.next_step("read_book", 0.5, 40.0, 20.0) > 0.0


def test_a_prop_act_shows_its_prop_and_face_and_leaves_the_stand_unpushed() -> None:
    e, _s, t = still()
    due = e.state_until
    e._start_act("read_book", t)
    e.ex.hold = due
    seen_prop, seen_face = set(), set()
    t0 = t
    while e.state == "act" and t < t0 + 90:
        t += 0.05
        out = e.update(t)
        if out.prop:
            seen_prop.add(out.prop[0])
        if out.face:
            seen_face.add(out.face[0])
    assert seen_prop == {"book"} and seen_face == {"focus"}
    assert e.state == "stand" and e.state_until <= due, "the stand's own end (a trip, a climb) is not pushed back by an act"


def test_a_figure_that_stands_does_things_in_place_now_and_then(monkeypatch) -> None:
    monkeypatch.setattr(eng, "IDLE_SIT", float("inf"))  # the person is about: the long-idle sit is off
    monkeypatch.setattr(eng, "IDLE_SLEEP", float("inf"))
    e, _s = make("masculine", "float", 3)
    e.presence = False  # Intent moved (INBOX 1692, 00:50Z): a spell holds one act for minutes; this counts the plain acts
    e.big_ready = e.trip_ready = e.climb_ready = float("inf")
    names, t, last = [], 0.0, None
    while t < 1800.0:
        t += 0.1
        e.update(t)
        if e.state == "act" and e.act_started != last:
            last = e.act_started
            names.append(e.act)
    assert 15 <= len(names) <= 60, len(names)
    assert len(set(names)) >= 10, set(names)
    assert not set(names) & set(extras.REACT_ACTS)


def test_nothing_in_place_starts_while_the_person_types_or_a_card_waits() -> None:
    e, _s, t = still()
    e.ex.act_ready = 0.0
    e.quiet = True
    settle(e, 3.0, t)
    assert e.state == "stand"


# --- the pointer -------------------------------------------------------------------------------


def feed(e: eng.Engine, t: float, path: list[tuple[int, int]], dt: float = 0.05) -> float:
    out = None
    for p in path:
        t += dt
        out = e.update(t, p)
    return t if out is not None else t


def centre(e: eng.Engine) -> tuple[int, int]:
    x, y, _c = e._display(e._frame(e.now))
    lx, top, r, b = e._box(e._frame(e.now))
    return int(x + (lx + r) / 2), int(y + (top + b) / 2)


def box(e: eng.Engine) -> tuple[int, int, int, int]:
    x, y, _c = e._display(e._frame(e.now))
    lx, top, r, b = e._box(e._frame(e.now))
    return int(x + lx), int(y + top), int(x + r), int(y + b)


def run_gesture(kind: str, seed: int = 2) -> str | None:
    e, _s, t = still(seed=seed)
    lx, top, r, b = box(e)
    cx, cy = (lx + r) // 2, (top + b) // 2
    w = r - lx
    if kind == "pat":
        path = [(cx, top + 8), (cx, top + 26), (cx, top + 8), (cx, top + 26), (cx, top + 8), (cx, top + 26)]
    elif kind == "rub":
        path = [(cx - 25, cy), (cx + 25, cy), (cx - 25, cy), (cx + 25, cy), (cx - 25, cy), (cx + 25, cy), (cx - 25, cy)]
    elif kind == "poke":
        # Intent moved (INBOX 1692, the owner 2026-11-08: "it gets instantly mad every time i hover"): a poke is a
        # jab that goes back out the way it came; an arrival that stays is a hover.
        path = [(cx + 400, cy), (cx + 330, cy), (cx + 200, cy), (cx + 60, cy), (cx + 10, cy), (cx + 120, cy), (cx + 300, cy)]
    elif kind == "flip":
        path = [(lx - 160, cy), (lx - 80, cy), (lx, cy), (cx, cy), (r, cy), (r + 80, cy), (r + 160, cy)]
    elif kind == "flinch":
        # Intent moved (INBOX 1692): a flinch is a swipe that whizzes past, not an approach that stops beside it.
        path = [(cx + w * 2 + 100, top - 50), (cx + w, top - 50), (cx, top - 50), (cx - w, top - 50), (cx - w * 2 - 100, top - 50)]
        path += [path[-1]] * 4
    elif kind == "hover":
        path = [(cx + 3 * (i % 2), cy) for i in range(30)]
    else:
        raise AssertionError(kind)
    t0 = t
    t = feed(e, t, path, 0.05 if kind in ("pat", "rub", "hover") else 0.04)
    got = e.ex.last[-1] if e.ex.last else None
    assert t >= t0
    return got


@pytest.mark.parametrize("kind,answer", [
    ("pat", "pat"), ("rub", "rub"), ("flip", "flip"), ("flinch", "flinch"), ("hover", "hover"),
])
def test_each_gesture_is_known_and_answered(kind: str, answer: str) -> None:
    assert run_gesture(kind) == answer


def test_a_poke_is_answered_by_mood() -> None:
    answers = set()
    for mood in ("happy", "sleepy", "bored"):
        e, _s, t = still()
        e.mind.feel(mood, t)
        lx, top, r, b = box(e)
        cy = (top + b) // 2
        # Intent moved (INBOX 1692): the jab goes back out; the answer by mood is unchanged.
        feed(e, t, [(r + 400, cy), (r + 330, cy), (r + 200, cy), (r + 60, cy), (r - 12, cy), (r + 100, cy), (r + 300, cy)], 0.04)
        answers.add((mood, e.ex.last[-1] if e.ex.last else None))
    assert answers == {("happy", "poke_giggle"), ("sleepy", "poke_miffed"), ("bored", "poke_curious")}


@pytest.mark.parametrize("mood", ["happy", "sleepy", "startled", "bored"])
@pytest.mark.parametrize("speed", [1, 3])
def test_an_ordinary_hover_arrival_is_never_a_poke_or_a_flinch(mood: str, speed: int) -> None:
    """INBOX 1692, the owner 2026-11-08: "it gets instantly mad every time i hover my mouse over it". Moving the
    mouse onto it, fast or slow, and resting there is a hover (a smile); stopping beside it is nothing."""
    for stop in ("on", "beside"):
        e, _s, t = still()
        e.mind.feel(mood, t)
        lx, top, r, b = box(e)
        cx, cy = (lx + r) // 2, (top + b) // 2
        end = (cx, cy) if stop == "on" else (r + 40, cy)
        far = (end[0] + 900, end[1] - 300)
        steps = 6
        arrive = [(far[0] + (end[0] - far[0]) * i // steps, far[1] + (end[1] - far[1]) * i // steps) for i in range(steps + 1)]
        feed(e, t, arrive + [end] * 40, 0.05 / speed)
        t2 = feed(e, t + 1, [(end[0] + (i % 2), end[1]) for i in range(30)], 0.05)
        assert t2 > t
        said = set(e.ex.last)
        assert not said & {"poke_giggle", "poke_miffed", "poke_curious", "flinch"}, (mood, speed, stop, said)
        if stop == "on":
            assert "hover" in said, (mood, speed, said)


def test_a_pointer_that_only_passes_or_rests_far_away_is_not_a_gesture() -> None:
    e, _s, t = still()
    lx, top, r, b = box(e)
    cy = (top + b) // 2
    t = feed(e, t, [(lx - 400 + i * 12, cy - 300) for i in range(60)], 0.05)  # a slow drift well above it
    t = feed(e, t, [(lx - 500, cy)] * 40, 0.05)
    feed(e, t, [(lx + (i * 7), cy + 200) for i in range(40)], 0.05)  # under it, slowly
    assert e.ex.last == []


def test_a_gesture_is_not_answered_while_typing_or_in_a_card_or_when_still() -> None:
    for quiet in ("quiet", "reduced"):
        e, _s, t = still()
        setattr(e, quiet, True)
        lx, top, r, b = box(e)
        cx = (lx + r) // 2
        feed(e, t, [(cx, top + 8), (cx, top + 26)] * 4, 0.05)
        assert e.ex.last == [], quiet


def test_a_gesture_turns_it_to_the_pointer_and_wakes_a_sleeper() -> None:
    e, _s, t = still()
    e._enter("sleep", t)
    lx, top, r, b = box(e)
    cx, cy = (lx + r) // 2, (top + b) // 2
    feed(e, t, [(cx - 25, cy), (cx + 25, cy)] * 4, 0.05)
    assert e.ex.last and e.state != "sleep"


def test_the_reaction_shows_in_the_very_next_picture() -> None:
    """The latency from the pointer's gesture to the first visible change is the draw itself, not a wait."""
    e, _s, t = still()
    before = picture(e.update(t + 0.05))
    assert e.react("window_opened", t + 0.1)
    after = picture(e.update(t + 0.1))
    assert after != before and after[-1] is not None and e.state == "act"


def test_the_pointer_is_watched_close_up_and_not_far_off() -> None:
    e, _s, t = still()
    lx, top, r, b = box(e)
    assert e.update(t + 0.1, (lx - 30, top + 20)).wake_ms <= extras.WATCH_MS
    assert e.update(t + 0.3, (lx - 3000, top)).wake_ms > extras.WATCH_MS


# --- the screen --------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(k for k, r in extras.REACTIONS.items() if not r.touch))
def test_each_screen_event_has_its_own_answer(kind: str) -> None:
    e, _s, t = still()
    assert e.react(kind, t + 0.1)
    r = extras.REACTIONS[kind]
    assert e.state == "act" and e.act == r.act
    out = e.update(t + 0.2)
    assert out.face and out.face[0] == r.face
    assert e.react(kind, t + 0.5) is False, "a cooldown: the same event does not fire twice in a row"


def test_a_screen_event_waits_for_a_free_moment() -> None:
    e, _s, t = still()
    e.quiet = True
    assert e.react("window_opened", t) is False
    e.quiet = False
    e.busy_flag = True
    e.card = object()
    assert e.react("window_opened", t) is False
    e.card = None
    e._enter("held", t)
    assert e.react("window_opened", t) is False
    e._enter("hang", t)
    assert e.react("window_opened", t) is False


def test_a_screen_event_never_breaks_a_reaction_that_is_running() -> None:
    e, _s, t = still()
    assert e.react("download_done", t)
    assert e.react("window_closed", t + 0.2) is False


def test_the_screen_watch_says_what_changed() -> None:
    fg = [10]
    bat = [(80, False)]
    files = [3]
    w = screenwatch.ScreenWatch(lambda: fg[0], lambda: bat[0], lambda: files[0])
    assert w.windows_seen([1, 2]) == []  # the first list is only remembered
    assert w.windows_seen([1, 2, 3]) == ["window_opened"]
    assert w.windows_seen([1, 3]) == ["window_closed"]
    assert w.windows_seen([5]) == ["window_opened", "window_closed"]
    assert w.poll(0.0, 9, 30) == []
    assert w.poll(1.0, 9, 31) == [], "polled at most every two seconds"
    fg[0] = 11
    assert w.poll(2.0, 9, 31) == ["app_switched"]
    assert w.poll(4.0, 10, 0) == ["hour_chime"]
    assert w.poll(6.0, 10, 0) == [], "the hour is said once"
    bat[0] = (15, False)
    assert w.poll(8.0, 10, 0) == ["battery_low"]
    assert w.poll(10.0, 10, 0) == [], "low is said once until it has been charged"
    bat[0] = (40, False)
    w.poll(12.0, 10, 1)
    bat[0] = (12, False)
    assert w.poll(14.0, 10, 1) == ["battery_low"]
    bat[0] = (5, True)  # on mains: never
    w.poll(16.0, 10, 1)
    files[0] = 4
    assert w.poll(18.0, 10, 1) == [], "the folder is read every ten seconds, not every poll (a huge folder costs a bounded read)"
    assert w.poll(20.0, 10, 1) == ["download_done"]
    files[0] = None
    assert w.poll(30.0, 10, 1) == []


def test_downloads_count_skips_files_still_being_written(tmp_path) -> None:
    for name in ("a.pdf", "b.zip", "c.crdownload", "d.part"):
        (tmp_path / name).write_text("x")
    (tmp_path / "sub").mkdir()
    assert screenwatch.downloads_count(tmp_path) == 2
    assert screenwatch.downloads_count(tmp_path / "missing") is None


# --- the hour ----------------------------------------------------------------------------------


@pytest.mark.parametrize("look", LOOKS)
def test_an_hour_awake_shows_many_more_acts_and_pictures_and_still_barely_moves(look: str) -> None:
    from tests.overlay_parity_sim import hour

    r = hour("float", look, 2, 1800.0)
    assert r["acts"] >= 14, r  # was 3 or 4 in the same hour: stands lasted three to nine minutes
    assert r["longest_repeat"] <= 2, r
    assert r["pictures"] >= 700, r  # was 331 to 800 an hour
    assert r["moving_share"] <= 0.012, r  # travel is still rare: 0.3 to 1 percent of the hour by seed, 0.55 on average (was 0.5)
    # Intent moved (atlascat-1108 C1): the tail layer wakes a stand or a sit every `TAIL_LAYER_MS` (30 a second): 1745 a minute
    # measured; the ceiling is that pace.
    assert 70 <= r["wakes_per_min"] <= 60_000 // eng.TAIL_LAYER_MS, r


@pytest.mark.parametrize("seed", [1, 3, 4])
def test_a_tremor_on_a_pointer_resting_on_the_figure_is_not_a_pat_or_a_rub(seed: int) -> None:
    """Review of the first build: 2 px of jitter a frame, resting on the figure, fired pat and rub."""
    e, _s, t = still(seed=seed)
    lx, top, r, b = box(e)
    rng = random.Random(seed)
    x, y = (lx + r) / 2, top + (b - top) * 0.3
    for _ in range(int(60 / 0.016)):
        t += 0.016
        x += rng.uniform(-2, 2)
        y += rng.uniform(-2, 2)
        e.update(t, (int(x), int(y)))
    assert not {"pat", "rub"} & set(e.ex.last), e.ex.last


def test_an_act_never_starts_the_instant_the_figure_is_free_or_after_a_stall() -> None:
    e, _s, t = still()
    e.ex.act_ready = 0.0
    e.ex.life(t + 500.0)  # the clock jumped (a suspend): the next act is re-timed, not fired
    assert e.state == "stand" and e.ex.act_ready > t + 500.0
    e.quiet = True
    e.ex.life(t + 501.0)
    assert e.ex.act_ready >= t + 501.0 + extras.LIFE_SETTLE, "typing holds the next act back for a while"


def test_the_screen_events_read_nothing_while_it_sleeps_sits_or_stays() -> None:
    from tests.test_overlay_roam_runner import started, tick

    for how in ("sleep", "sit", "stay"):
        r, fake, clock, _ = started()
        if how == "stay":
            r.engine.command("stay", clock.t)
        else:
            r.engine.last_active = clock.t - 700  # long untouched, as the climb guard's own test does
            r.engine._enter(how, clock.t)
        before = len(fake.calls)
        tick(r, clock, 3.0, 5)
        asked = [fn for _d, fn, _a in fake.calls[before:] if fn in ("GetSystemPowerStatus", "EnumWindows")]  # (the foreground window is also read for fullscreen)
        assert asked == [], (how, asked)
        r.stop()
