"""I21 (life-1109 kk, `int.catch_midair`): pressed while it falls, the companion clutches, goes wide-eyed, then is relieved.
Both sides: the app marks a press that lands on a flight and answers the next landing (`caught`, a habit row); the desk's
`Extras.view` sees the press arrive from a fall or a fly and fires `caught` once it stands again. A fixed clock throughout;
real Windows and a real browser drive are unverified (see the ledger)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tests._js_scope import unwrapped

from tessellate.core.overlay import extras

ROOT = Path(__file__).resolve().parents[1]
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))
MENU = unwrapped((ROOT / "frontend" / "js" / "companion-menu.js").read_text(encoding="utf-8"))


def test_the_app_marks_a_press_on_a_flight_and_answers_the_next_landing_once() -> None:
    at = AV.index("nmb.caughtMid = nmb.flight ? performance.now() : 0;")
    down = AV[at - 300 : at + 120]
    assert "drag = { box: null" in down and "nmb.grabbed = true;" in down  # in the face's pointerdown, before the capture
    assert "nmb.caughtMid = nmb.flight ? performance.now() : 0;" in down  # a press on a flight; any other press clears an old mark
    land = AV[AV.index('if (act === "land" && nmb.carriedMs >= 2500)') :]
    land = land[: land.index("if (act === \"land\") nmb.carriedMs = 0;")]
    assert "nmb.caughtMid" in land and 'nameMarkBuddyReact("caught")' in land
    assert "performance.now() - nmb.caughtMid < 15000" in land  # a stale mark never answers a later landing
    assert "nmb.caughtMid = 0" in land


def test_caught_is_a_habit_row_and_plays_a_clutch_then_relief() -> None:
    row = [ln for ln in AV.splitlines() if ln.strip().startswith("caught:")]
    assert row and "habit: true" in row[0] and "cool:" in row[0]  # off with Little habits, off under reduced motion
    branch = MENU[MENU.index('} else if (kind === "caught") {') :]
    branch = branch[: branch.index('} else if (kind === "binned")')]
    assert 'nameMarkBuddyExpress("surprised"' in branch and 'nameMarkBuddyExpress("happy"' in branch
    assert branch.index('"surprised"') < branch.index('"happy"')  # wide eyes first, relief after


def _extras(state: str, pre: str):
    fired: list[str] = []
    e = SimpleNamespace(reduced=False, state=state, pre_press=pre, fired=fired)
    ex = extras.Extras.__new__(extras.Extras)
    ex.e = e
    ex.caught_at = None
    ex.fire = lambda kind, now, **_k: fired.append(kind) or True
    return e, ex, fired


def test_the_desk_fires_caught_when_it_stands_after_a_press_on_a_fall() -> None:
    e, ex, fired = _extras("pressed", "fall")
    ex.watch_catch(100.0)
    assert ex.caught_at == 100.0 and fired == []  # held: nothing yet, it is in a hand
    e.state = "fall"
    ex.watch_catch(100.5)
    assert fired == []  # let go and still coming down
    e.state = "stand"
    ex.watch_catch(101.2)
    assert fired == ["caught"] and ex.caught_at is None
    ex.watch_catch(102.0)
    assert fired == ["caught"]  # once


def test_a_press_on_a_stand_or_a_late_landing_is_no_catch() -> None:
    e, ex, fired = _extras("pressed", "stand")
    ex.watch_catch(100.0)
    e.state = "stand"
    ex.watch_catch(101.0)
    assert ex.caught_at is None and fired == []
    e, ex, fired = _extras("pressed", "fly")
    ex.watch_catch(100.0)
    e.state = "stand"
    ex.watch_catch(100.0 + extras.CATCH_WAIT + 1.0)  # a carry that went on for a minute: the clutch is long over
    assert fired == [] and ex.caught_at is None


def test_the_desk_row_is_made_of_an_act_the_desk_ships() -> None:
    extras.register()
    r = extras.REACTIONS["caught"]
    assert r.act in extras.REACT_ACTS and r.face == "surprised" and r.cooldown > 0
    assert extras.REACT_ACTS[r.act].where == "react"
