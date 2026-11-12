"""W31: the app-to-overlay events feed (compalive-1109). The server notes nine things the in-app companion reacts to
(`graph_laid`, `long_note`, `note_binned`, `private_note`, `remark`, `reminder_bell`, `search_found`, `search_nothing`, `note_milestone`) in a
small ring of kind and time, never a title or a word of a note; the overlay reads what is new on its existing screen poll
(`ScreenWatch.poll`, every 2 s, never on the fall tick) and answers with acts that already have desk frames.
Fixed clock throughout. Real Windows is unverified: this is the ring, the routes and the engine's answer on a fake."""

from __future__ import annotations

import json

import pytest

from tessellate.core import companion_events as ce
from tessellate.core.overlay import extras, screenwatch

NOTE_KINDS = ("graph_laid", "long_note", "note_binned", "private_note", "remark", "reminder_bell", "search_found", "search_nothing", "note_milestone")


@pytest.fixture(autouse=True)
def _fresh_ring():
    ce.reset()
    yield
    ce.reset()


def test_the_ring_hands_out_monotonic_ids_and_only_kind_and_time() -> None:
    a = ce.record("note_binned", now=100.0)
    b = ce.record("long_note", now=101.0)
    assert 0 < a < b
    rows = ce.since(0, now=102.0)
    assert [(r["kind"]) for r in rows] == ["note_binned", "long_note"]
    assert all(set(r) == {"id", "kind", "at"} for r in rows)  # no title, no id of a note, no text
    assert ce.since(a, now=102.0)[0]["id"] == b


def test_an_unknown_kind_is_never_recorded() -> None:
    assert ce.record("a note title", now=1.0) == 0
    assert ce.since(0, now=2.0) == []


def test_the_ring_is_bounded_and_ids_keep_counting() -> None:
    last = 0
    for i in range(ce.RING * 3):
        last = ce.record("note_binned", now=1000.0 + i * 100)  # the gap is long past: none is thinned
    rows = ce.since(0, now=1000.0 + (ce.RING * 3 - 1) * 100 + 1)
    assert len(rows) <= ce.RING and rows[-1]["id"] == last >= ce.RING * 3
    assert len(ce._ring) == ce.RING  # the oldest fell off the end


def test_a_kind_repeated_inside_its_gap_is_thinned() -> None:
    first = ce.record("graph_laid", now=50.0)
    assert first
    assert ce.record("graph_laid", now=50.0 + ce.GAP["graph_laid"] - 1) == 0
    assert ce.record("graph_laid", now=50.0 + ce.GAP["graph_laid"] + 1)


def test_what_is_old_is_not_news() -> None:
    ce.record("note_binned", now=10.0)
    assert ce.since(0, now=10.0 + ce.STALE + 1) == []  # a sit or a sleep that read nothing does not replay it
    assert ce.latest() == 1


def test_a_miss_then_a_find_inside_thirty_seconds_is_found_and_a_lone_find_is_not() -> None:
    ce.searched(False, now=100.0)
    ce.searched(True, now=110.0)
    assert [r["kind"] for r in ce.since(0, now=111.0)] == ["search_nothing", "search_found"]
    ce.reset()
    ce.searched(True, now=500.0)
    assert ce.since(0, now=501.0) == []  # as in the app: a nod only after a miss
    ce.searched(False, now=600.0)
    before = ce.latest()
    ce.searched(True, now=600.0 + 31)
    assert ce.latest() == before  # a find thirty-one seconds after the miss is not a nod


# --- the server's places -------------------------------------------------------------------------------------------------


def kinds_after(last: int) -> list[str]:
    return [r["kind"] for r in ce.since(last, now=ce.clock())]


def test_binning_a_note_records_a_bare_kind(client) -> None:
    made = client.post("/entries", json={"content": "A quiet note about the garden fence."}).json()
    last = ce.latest()
    binned = client.delete(f"/entries/{made['id']}")
    assert binned.status_code == 200
    rows = ce.since(last, now=ce.clock())
    assert [r["kind"] for r in rows] == ["note_binned"]
    assert all(set(r) == {"id", "kind", "at"} for r in rows) and "garden" not in json.dumps(rows)


def test_opening_a_long_note_records_long_note_and_a_short_one_nothing(client) -> None:
    long = client.post("/entries", json={"content": "word " * 300}).json()
    short = client.post("/entries", json={"content": "tiny"}).json()
    last = ce.latest()
    client.get(f"/entries/{short['id']}?open=1")
    assert kinds_after(last) == []
    client.get(f"/entries/{long['id']}")  # a read that is not an open (the graph's hover card, the agent) is not reading
    assert kinds_after(last) == []
    client.get(f"/entries/{long['id']}?open=1")
    assert kinds_after(last) == ["long_note"]


def test_a_private_note_is_only_ever_the_generic_kind(client, session) -> None:
    from tessellate.core.database import Entry  # noqa: PLC0415

    made = client.post("/entries", json={"content": "word " * 300}).json()
    session.get(Entry, made["id"]).is_private = True  # the vault is shut in a test: flag it as the privacy route would
    session.commit()
    last = ce.latest()
    client.get(f"/entries/{made['id']}?open=1")
    client.delete(f"/entries/{made['id']}")
    rows = ce.since(last, now=ce.clock())
    assert rows and {r["kind"] for r in rows} == {"private_note"}  # not long_note, not note_binned
    assert all(set(r) == {"id", "kind", "at"} for r in rows)


def test_a_search_records_found_or_nothing(client) -> None:
    client.post("/entries", json={"content": "Lemon tree pruning in March."})
    last = ce.latest()
    client.get("/search", params={"q": "zzqxjv"})
    assert kinds_after(last) == ["search_nothing"]


def test_the_graph_and_the_remarks_record_their_kinds(client) -> None:
    client.post("/entries", json={"content": "Something to map."})
    last = ce.latest()
    client.get("/graph")
    assert "graph_laid" in kinds_after(last)


def test_the_tenth_note_is_a_milestone_and_the_ninth_is_not(client) -> None:
    last = ce.latest()
    for n in range(1, 10):
        client.post("/entries", json={"content": f"Plain note number {n} about tomatoes."})
    assert "note_milestone" not in kinds_after(last)
    client.post("/entries", json={"content": "Plain note number 10 about tomatoes."})
    assert kinds_after(last).count("note_milestone") == 1


def test_there_is_no_route_that_serves_the_ring(client) -> None:
    paths = {getattr(r, "path", "") for r in client.app.routes}
    assert not [p for p in paths if "companion-event" in p or "companion_event" in p]
    assert not [p for p in paths if p.rstrip("/").endswith("/events") and "companion" in p]


# --- the overlay's side ---------------------------------------------------------------------------------------------------


def test_the_watch_reads_the_feed_on_its_own_poll_and_starts_at_the_head() -> None:
    ce.record("note_binned", now=ce.clock())
    watch = screenwatch.ScreenWatch(feed=ce.since)
    assert watch.poll(1.0, 12) == []  # what was already there at the first read is history
    ce.record("long_note", now=ce.clock())
    assert watch.poll(1.5, 12) == []  # not before its 2 s are up: no read of its own
    assert watch.poll(3.1, 12) == ["long_note"]
    assert watch.poll(5.2, 12) == []  # read once


def test_a_forgetful_watch_does_not_replay_what_it_missed() -> None:
    watch = screenwatch.ScreenWatch(feed=ce.since)
    watch.poll(1.0, 12)
    ce.record("remark", now=ce.clock())
    watch.forget()
    assert watch.poll(9.0, 12) == []


def test_a_broken_feed_is_no_event() -> None:
    def boom(*_a, **_k):
        raise RuntimeError("no")

    assert screenwatch.ScreenWatch(feed=boom).poll(1.0, 12) == []


@pytest.mark.parametrize("kind", NOTE_KINDS)
def test_every_fed_kind_has_a_desk_reaction_made_of_poses_the_desk_ships(kind: str) -> None:
    from tessellate.core.overlay import sprites  # noqa: PLC0415

    extras.register()
    r = extras.REACTIONS[kind]
    assert r.face and r.cooldown > 0
    if r.act:  # a reaction-only act, drawn on a pose the desk has frames for (a face alone needs none)
        pose = extras.REACT_ACTS[r.act].frame
        pose = pose if isinstance(pose, str) else pose[0][1]
        assert pose in sprites.FRAME_NAMES, (kind, r.act, pose)


def test_the_ring_kinds_and_the_reactions_are_the_same_nine() -> None:  # intent unchanged; P7 added the round-count cheer
    assert set(ce.KINDS) == set(NOTE_KINDS)
    assert set(NOTE_KINDS) <= set(extras.REACTIONS)


def test_only_a_round_note_count_is_a_cheer_and_it_matches_the_apps_list() -> None:
    import re  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    js = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    app = [int(n) for n in re.search(r"NMB_MILESTONES = \[([\d, ]+)\]", js).group(1).split(",")]
    assert list(ce.MILESTONES) == app
    # counted in order, as a growing notebook calls it: only the round numbers rise past the highest one cheered
    cheered = [n for n in range(1, 2001) if ce.counted(n, now=1e6 + n * 5000.0)]
    assert cheered == [10, 25, 50, 100, 250, 500, 1000, 2000]


def test_a_milestone_is_cheered_once_even_when_the_count_dips_and_returns() -> None:
    assert ce.counted(100, now=0.0)
    assert ce.counted(100, now=4000.0) == 0  # a second look at 100, an hour later: not news
    assert ce.counted(99, now=8000.0) == 0 and ce.counted(100, now=12000.0) == 0  # deleted one, added one
    assert ce.counted(250, now=16000.0)


def test_a_jump_over_a_round_number_still_cheers_it_once() -> None:
    ce.seed(98)
    assert ce.counted(103, now=0.0)  # an import took the count past 100
    assert ce.counted(104, now=9000.0) == 0


def test_a_milestone_refused_by_the_gap_is_tried_again_not_lost() -> None:
    assert ce.counted(10, now=0.0)
    assert ce.counted(25, now=10.0) == 0  # inside the hour's gap
    assert ce.counted(26, now=4000.0)  # the next look after the gap cheers the 25 it missed


def test_a_seeded_count_is_not_cheered_and_a_reset_forgets_it() -> None:
    ce.seed(100)
    assert ce.counted(101, now=0.0) == 0
    assert ce.counted(250, now=9000.0)
    ce.reset()
    assert ce.counted(10, now=0.0)


def test_a_draft_is_not_counted(client, monkeypatch) -> None:
    seen: list[int] = []
    monkeypatch.setattr(ce, "counted", lambda total, now=None: seen.append(total) or 0)
    client.post("/entries", json={"content": "A draft about tomatoes.", "is_draft": True})
    assert seen == []
    client.post("/entries", json={"content": "A plain note about tomatoes."})
    assert seen == [1]


def test_the_notebook_total_at_start_is_the_baseline(client) -> None:
    from tessellate.api import app as app_module  # noqa: PLC0415

    for n in range(10):
        client.post("/entries", json={"content": f"Plain note number {n} about tomatoes."})
    ce.reset()
    app_module._seed_companion_milestone()
    last = ce.latest()
    client.post("/entries", json={"content": "Plain note number 11 about tomatoes."})
    assert "note_milestone" not in kinds_after(last)  # a restart at 10 notes does not cheer the 10 again


@pytest.mark.parametrize("kind", NOTE_KINDS)
def test_the_running_overlay_answers_each_fed_kind_on_its_screen_poll(kind: str) -> None:
    from tests.test_overlay_react_1700 import _up, _until_answered  # noqa: PLC0415

    r, fake, clock = _up()
    e = r.engine
    e.ex.cool.clear()
    e.facing = 1
    assert ce.record(kind)
    _until_answered(r, clock, e, kind, n=16)
    assert kind in e.ex.last, (kind, e.ex.last)
    r.stop()


def test_the_feed_adds_no_timer_of_its_own() -> None:
    import inspect  # noqa: PLC0415

    from tessellate.core.overlay import runner  # noqa: PLC0415

    src = inspect.getsource(runner)
    assert "companion_events.since" in src and src.count("companion_events") == 2  # the import and the one handed to the watch
    for banned in ("threading.Timer", "set_timer(", "SetTimer"):
        assert banned not in inspect.getsource(screenwatch)
