"""The desk reads the companion catalogue (atlascat-1108, Batch A): one loader, one table for both sides."""

from __future__ import annotations

import pytest

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import catalogue
from tests._cat_node import run


def test_the_loader_returns_every_entry() -> None:
    assert len(catalogue.entries()) == 323  # intent moved: E3 and E5 added entries, P7 added react.note_milestone, L-chat-7 react.writing_stretch
    assert catalogue.load()["moods"]


def test_a_missing_file_is_an_empty_table_not_a_crash(monkeypatch, tmp_path) -> None:
    catalogue.reset()
    monkeypatch.setattr(catalogue, "path", lambda: tmp_path / "none.json")
    try:
        assert catalogue.load() == {} and catalogue.entries() == [] and catalogue.by_desk_name() == {}
        (tmp_path / "bad.json").write_text("[1,", encoding="utf-8")
        catalogue.reset()
        monkeypatch.setattr(catalogue, "path", lambda: tmp_path / "bad.json")
        assert catalogue.load() == {}
    finally:
        catalogue.reset()


def _both_built_acts() -> list[dict]:
    return [e for e in catalogue.entries() if e["kind"] == "idle_act" and e["app"]["s"] == "built" and e["desk"]["s"] == "built"]


def _app_acts() -> dict:
    """The in-app act table once the catalogue block of avatars.js has applied the file to a stand-in table
    (a weight of 0 means an event starts it, and stays 0)."""
    acts = {}
    for e in _both_built_acts():
        for n in e["app"]["names"]:
            if n.startswith("acts:"):
                acts[n[5:]] = {"ms": 1, "w": 1, "cool": 1, "poses": ["stand"]}
    acts["yawn"]["w"] = 0
    acts["nap"]["w"] = 0
    return run("nmb.cat.load(); await new Promise((r) => setTimeout(r, 20)); console.log(JSON.stringify(NAME_MARK_BUDDY_ACTS));", acts)


def test_the_desk_takes_length_and_weight_from_the_table() -> None:
    seen = 0
    for e in _both_built_acts():
        names = [n[5:] for n in e["desk"]["names"] if n.startswith("acts:") and n[5:] in bh.CATALOGUED]
        for n in names:
            lo, hi = bh.ACTIVITIES[n].seconds
            # the table's range, with the built-in minimum kept (a shorter play breaks the redraw cap)
            assert hi == e["seconds"][1] and e["seconds"][0] <= lo <= hi, n
            assert bh.BASE_WEIGHT[n] == pytest.approx(e["w"] / len(names)), n
            seen += 1
    assert seen >= 20


def test_both_sides_agree_on_how_long_and_how_likely_an_act_is() -> None:
    """One table, so the two sides' durations agree: the desk draws from the range, the app runs its middle."""
    app = _app_acts()
    checked = 0
    for e in _both_built_acts():
        mid = (e["seconds"][0] + e["seconds"][1]) / 2
        app_names = [n[5:] for n in e["app"]["names"] if n.startswith("acts:")]
        desk_names = [n[5:] for n in e["desk"]["names"] if n.startswith("acts:") and n[5:] in bh.CATALOGUED]
        for n in app_names:
            assert app[n]["ms"] / 1000 == pytest.approx(mid, abs=0.0006), n
            for d in desk_names:
                lo, hi = bh.ACTIVITIES[d].seconds
                assert lo <= app[n]["ms"] / 1000 <= hi, (n, d)
            checked += 1
        live = [n for n in app_names if app[n]["w"] > 0]
        if live and desk_names:
            assert sum(app[n]["w"] for n in live) == pytest.approx(e["w"]), e["id"]
            assert sum(bh.BASE_WEIGHT[d] for d in desk_names) == pytest.approx(e["w"]), e["id"]
    assert checked >= 20


def test_without_the_file_the_desk_keeps_its_built_in_numbers(monkeypatch, tmp_path) -> None:
    """The fallback: a missing catalogue changes nothing (the apply runs on copies of the tables)."""
    acts, weight = dict(bh.ACTIVITIES), dict(bh.BASE_WEIGHT)
    monkeypatch.setattr(bh, "ACTIVITIES", dict(acts))
    monkeypatch.setattr(bh, "BASE_WEIGHT", dict(weight))
    monkeypatch.setattr(catalogue, "path", lambda: tmp_path / "none.json")
    catalogue.reset()
    try:
        bh._from_catalogue()
        assert bh.ACTIVITIES == acts and bh.BASE_WEIGHT == weight
    finally:
        monkeypatch.undo()
        catalogue.reset()


@pytest.mark.parametrize("drop", ["seconds", "w", "energy", "id"])
def test_an_entry_missing_a_key_is_skipped_not_a_crash(monkeypatch, tmp_path, drop: str) -> None:
    """Review of atlascat-1108: a JSON object whose entry lacks `seconds`, `w` or `energy` must leave the built-ins, not raise at import."""
    import json

    raw = json.loads(catalogue.path().read_text(encoding="utf-8"))
    for e in raw["entries"]:
        if e.get("kind") == "idle_act" and e.get("desk", {}).get("s") == "built":
            e.pop(drop, None)
    raw["entries"].append("not an entry")
    (tmp_path / "bad.json").write_text(json.dumps(raw), encoding="utf-8")
    acts, weight = dict(bh.ACTIVITIES), dict(bh.BASE_WEIGHT)
    monkeypatch.setattr(bh, "ACTIVITIES", dict(acts))
    monkeypatch.setattr(bh, "BASE_WEIGHT", dict(weight))
    monkeypatch.setattr(bh, "CATALOGUED", set())
    monkeypatch.setattr(catalogue, "path", lambda: tmp_path / "bad.json")
    catalogue.reset()
    try:
        bh._from_catalogue()
        assert bh.ACTIVITIES == acts and bh.BASE_WEIGHT == weight and not bh.CATALOGUED
        assert bh.catalogue_factor("doze", "content", 12) == 1.0
    finally:
        monkeypatch.undo()
        catalogue.reset()


# --- A4: beats ---------------------------------------------------------------------------------------------------

MAX_HOLD = 90.0


def _longest_hold(seed: int, gait: str, secs: float = 600.0, force: str = "") -> tuple[float, tuple]:
    """A fixed-clock sim: the longest stretch (seconds) the figure keeps one pose, which is the same state, act, facing, shift count and
    spot (a walk or a glide is moving, so it holds none)."""
    from tests.test_overlay_ride_1670 import make

    e, _ = make("masculine", gait, seed)
    t = 100.0
    e.update(t)
    for _ in range(200):
        if e.state == "stand":
            break
        t += 0.25
        e.update(t, None)
    if force:
        e._start_act(force, t)
    sig, since, longest, who = None, t, 0.0, ()
    end = t + secs
    while t < end:
        t += 0.25
        e.update(t, None)
        cur = (e.state, e.act, e.facing, e.mind.shifts, round(e.x / 4), round(e.y / 4))
        if cur != sig:
            if sig is not None and t - since > longest:
                longest, who = t - since, sig
            sig, since = cur, t
    return max(longest, t - since), who


@pytest.mark.parametrize("gait", ["walk", "float"])
@pytest.mark.parametrize("seed", [1, 2, 3, 5])
def test_the_desk_holds_no_pose_over_90_seconds_in_600(seed: int, gait: str) -> None:
    longest, who = _longest_hold(seed, gait)
    assert longest <= MAX_HOLD, (longest, who)


@pytest.mark.parametrize("name", ["doze", "curl_up", "lie_down"])
def test_a_long_forced_act_turns_over_inside_its_budget(name: str) -> None:
    longest, who = _longest_hold(2, "walk", 300.0, force=name)
    assert longest <= MAX_HOLD, (longest, who)


def test_a_shift_beat_falls_inside_the_budget_of_every_desk_act_that_has_one() -> None:
    seen = 0
    for name, e in catalogue.by_desk_name().items():
        every = bh.shift_every(name)
        if every:
            assert every == tuple(next(b["every"] for b in e["beats"] if b.get("shifts"))) and every[1] <= MAX_HOLD, name
            seen += 1
    assert seen >= 4
