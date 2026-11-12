"""One suggestions inbox that learns (GRAPH_PLAN KG9 part two, INBOX 528).

The two new recognisers (`ai/inbox.merge_candidates`, `type_candidates`) are
tested on plain data; the routes (`/suggestions`) on a real notebook: a
merge moves every mention, a type lands on the link, and every accept and
dismissal is a correction the next pass reads.
"""

from __future__ import annotations

import random
import sqlite3
import time
from pathlib import Path

from tessellate.ai import learning
from tessellate.ai.inbox import EntityFacts, LinkFacts, merge_candidates, type_candidates
from tessellate.core import deps


def _ents(*rows):
    return [EntityFacts(id=i, name=n, notes=frozenset(notes)) for i, (n, notes) in enumerate(rows, 1)]


def _merge(found, a, b):
    return next((m for m in found if {m["keep_id"], m["merge_id"]} == {a, b}), None)


# --- the pure half -----------------------------------------------------------


def test_a_first_name_inside_a_full_name_is_a_merge_keeping_the_full_name():
    found = merge_candidates(_ents(("Sam", {1, 2}), ("Sam Lee", {2, 3}), ("Priya", {4})))
    row = _merge(found, 1, 2)
    assert row is not None and row["keep_id"] == 2
    assert {s["signal"] for s in row["signals"]} == {"part_name", "same_note"}
    assert "“Sam” is part of “Sam Lee”" in row["reason"]


def test_case_and_near_spellings_merge_and_different_people_do_not():
    found = merge_candidates(
        _ents(("priya shah", {1}), ("Priya Shah", {2}), ("Jonathan Smith", {3}), ("Jonathon Smith", {4}),
              ("Sam Lee", {5}), ("Sam Ng", {6}))
    )
    assert _merge(found, 1, 2)["signals"][0]["signal"] == "same_name"
    assert _merge(found, 3, 4)["signals"][0]["signal"] == "near_name"
    assert _merge(found, 5, 6) is None


def test_an_ambiguous_first_name_is_less_sure_and_a_dismissed_pair_never_returns():
    one = _merge(merge_candidates(_ents(("Sam", {1, 2}), ("Sam Lee", {1}))), 1, 2)
    two = merge_candidates(_ents(("Sam", {1, 2}), ("Sam Lee", {1}), ("Sam Ng", {2})))
    assert len(two) == 2 and all(m["confidence"] < one["confidence"] for m in two)
    assert merge_candidates(_ents(("Plan 2025", {1}), ("Plan 2026", {2}))) == []
    assert merge_candidates(_ents(("Sam", {1}), ("Sam Lee", {1})), exclude={frozenset((1, 2))}) == []


#: CPU seconds this machine's reference workload took when the 1.0 s budget
#: was set (a 4-core sandbox, 2026-10-05; merge_candidates took 0.20 s there).
REFERENCE_CPU_SECONDS = 0.11


def _reference_seconds() -> float:
    """A fixed pure-Python workload close to the pass's own (SequenceMatcher on
    short names), so the budget can be read in this machine's units."""
    from difflib import SequenceMatcher

    times = []
    for _ in range(3):
        started = time.process_time()
        for i in range(4000):
            SequenceMatcher(None, f"kalomira suteva {i}", f"kalomiro sutevo {i * 7}").ratio()
        times.append(time.process_time() - started)
    return min(times)


def test_merge_candidates_at_five_thousand_entities_is_quick():
    """Under a second for 5,000 names on a machine as fast as the one the
    budget was set on, and proportionally more on a slower one. A fixed 1.0 s
    failed on CI runners several times slower than a laptop (1.71 s of CPU
    time, 2026-10-05), which said nothing about the pass. CPU time, best of
    three, so other processes do not count; the reference workload scales the
    budget, never the other way round (a faster machine keeps 1.0 s)."""
    rng = random.Random(4)
    syll = ["ka", "lo", "mi", "ra", "su", "te", "vo", "ne", "pa", "di", "ro", "ya"]
    word = lambda: "".join(rng.choice(syll) for _ in range(rng.randint(2, 3))).title()  # noqa: E731
    surnames = [word() for _ in range(60)]
    rows = [(f"{word()} {rng.choice(surnames)}", {i}) for i in range(5000)]
    ents = _ents(*rows)
    times = []
    for _ in range(3):
        started = time.process_time()
        merge_candidates(ents)
        times.append(time.process_time() - started)
    took = min(times)
    budget = 1.0 * max(1.0, _reference_seconds() / REFERENCE_CPU_SECONDS)
    assert took < budget, (took, budget)


def test_a_cue_in_the_sentence_or_the_reason_suggests_a_type():
    links = [
        LinkFacts(id=1, source_id=1, target_id=2, context="Cone 6 reduction, for example [[Glaze A]]."),
        LinkFacts(id=2, source_id=1, target_id=3, reason="this continues the October plan"),
        LinkFacts(id=3, source_id=1, target_id=4, context="See [[Kiln]] when you can."),
        LinkFacts(id=4, source_id=2, target_id=3, reason="supports the claim", deduced=True),
    ]
    found = {row["link_id"]: row for row in type_candidates(links)}
    assert found[1]["link_type"] == "example_of"
    assert found[1]["context"][found[1]["hit_start"]:found[1]["hit_end"]].lower() == "for example"
    assert found[2]["link_type"] == "continues"
    assert 3 not in found and 4 not in found


def test_two_types_at_once_is_no_suggestion_and_a_dismissal_holds():
    both = LinkFacts(id=1, source_id=1, target_id=2, context="It contradicts, for example, the plan.")
    assert type_candidates([both]) == []
    one = LinkFacts(id=2, source_id=1, target_id=2, context="Background for the trip.")
    assert type_candidates([one], exclude={(2, "context")}) == []
    assert type_candidates([one])[0]["link_type"] == "context"


# --- the routes ----------------------------------------------------------------


def _note(client, text):
    return client.post("/entries", json={"content": text}).json()


def _entity(session, name, *entry_ids):
    from tessellate.core.database import Entity, EntityMention

    entity = Entity(name=name)
    session.add(entity)
    session.flush()
    for entry_id in entry_ids:
        session.add(EntityMention(entity_id=entity.id, entry_id=entry_id))
    session.commit()
    return entity.id


def test_the_inbox_offers_a_merge_and_accepting_it_moves_every_mention(client, session):
    from tessellate.core.database import Entity, EntityMention

    a, b, c = (_note(client, f"Note {i} about the studio") for i in range(3))
    sam = _entity(session, "Sam", a["id"], b["id"])
    sam_lee = _entity(session, "Sam Lee", b["id"], c["id"])
    body = client.get("/suggestions").json()
    row = next(m for m in body["merges"] if {m["keep_id"], m["merge_id"]} == {sam, sam_lee})
    assert row["keep_id"] == sam_lee and row["keep_name"] == "Sam Lee"

    made = client.post("/suggestions/merges/accept", json={"keep_id": sam_lee, "merge_id": sam, "signals": ["part_name"]})
    assert made.status_code == 200, made.text
    session.expire_all()
    notes = sorted(m.entry_id for m in session.query(EntityMention).filter_by(entity_id=sam_lee))
    assert notes == sorted({a["id"], b["id"], c["id"]})
    assert session.query(EntityMention).filter_by(entity_id=sam).count() == 0
    gone = session.get(Entity, sam)
    assert gone.merged_into == sam_lee and "Sam" in (session.get(Entity, sam_lee).aliases or [])
    assert client.get("/suggestions").json()["merges"] == []
    kinds = [c["kind"] for c in client.get("/learned/corrections").json()]
    assert "accept_merge" in kinds
    # Undo removes the correction the accept taught (INBOX 898): the answer names it.
    cid = made.json()["correction_id"]
    removed = client.delete(f"/learned/corrections/{cid}")
    assert removed.status_code in (200, 204)
    assert "accept_merge" not in [c["kind"] for c in client.get("/learned/corrections").json()]


def test_a_dismissed_merge_stays_dismissed(client, session):
    a = _note(client, "one")
    x = _entity(session, "Sam", a["id"])
    y = _entity(session, "Sam Lee", a["id"])
    assert client.get("/suggestions").json()["merges"]
    client.post("/suggestions/merges/dismiss", json={"a": x, "b": y, "signals": ["part_name"]})
    assert client.get("/suggestions").json()["merges"] == []


def test_extraction_after_a_merge_lands_on_the_survivor(session):
    from tessellate.ai.entities import _find_or_create_entity, merge_entities
    from tessellate.core.database import Entity

    keep = Entity(name="Sam Lee")
    gone = Entity(name="Sam")
    session.add_all([keep, gone])
    session.flush()
    merge_entities(session, keep, gone)
    assert _find_or_create_entity(session, "sam", {}).id == keep.id


def test_a_type_suggestion_lands_on_the_link_and_teaches(client, session):
    from tessellate.core.database import EntryLink

    target = _note(client, "# Glaze A\n\nshino over tenmoku")
    holder = _note(client, "# Firing log\n\nCone 6 went well, for example [[Glaze A]] crawled less.")
    rows = client.get("/suggestions").json()["types"]
    row = next(r for r in rows if r["source_id"] == holder["id"] and r["target_id"] == target["id"])
    assert row["link_type"] == "example_of" and row["type_label"] == "Example of"
    made = client.post(
        "/suggestions/types/accept", json={"link_id": row["link_id"], "link_type": "example_of", "signals": ["cue"]}
    )
    assert made.status_code == 200, made.text
    session.expire_all()
    assert session.get(EntryLink, row["link_id"]).link_type == "example_of"
    assert client.get("/suggestions").json()["types"] == []
    kinds = [c["kind"] for c in client.get("/learned/corrections").json()]
    assert "accept_link_type" in kinds
    cid = made.json()["correction_id"]
    removed = client.delete(f"/learned/corrections/{cid}")
    assert removed.status_code in (200, 204)
    assert "accept_link_type" not in [c["kind"] for c in client.get("/learned/corrections").json()]


def test_a_dismissed_type_stays_dismissed_and_a_private_end_is_never_offered(client, session):
    from tessellate.core.database import Entry

    target = _note(client, "# Kiln two\n\nbody")
    holder = _note(client, "# Plan\n\nBackground: [[Kiln two]] is the gas one.")
    row = client.get("/suggestions").json()["types"][0]
    client.post("/suggestions/types/dismiss", json={"link_id": row["link_id"], "link_type": row["link_type"]})
    assert client.get("/suggestions").json()["types"] == []

    other = _note(client, "# Kiln three\n\nbody")
    _note(client, "# Plan two\n\nBackground: [[Kiln three]] is electric.")
    assert client.get("/suggestions").json()["types"]
    session.get(Entry, other["id"]).is_private = True
    session.commit()
    assert client.get("/suggestions").json()["types"] == []
    assert target and holder


def test_a_link_type_can_be_changed_and_a_bad_one_is_refused(client, session):
    from tessellate.core.database import EntryLink

    a, b = _note(client, "first"), _note(client, "second")
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]})
    link = session.query(EntryLink).one()
    ok = client.patch(f"/entries/{b['id']}/links/{link.id}", json={"link_type": "supports"})
    assert ok.status_code == 200, ok.text
    session.expire_all()
    assert session.get(EntryLink, link.id).link_type == "supports"
    assert client.patch(f"/entries/{a['id']}/links/{link.id}", json={"link_type": "nonsense"}).status_code == 422


def test_an_accepted_suggestion_keeps_the_signals_confidence(client, session):
    from tessellate.core.database import EntryLink

    a, b = _note(client, "first"), _note(client, "second")
    client.post(
        f"/entries/{a['id']}/links",
        json={"target_id": b["id"], "reason": "both mention Priya", "reason_confidence": 0.72},
    )
    assert session.query(EntryLink).one().reason_confidence == 0.72


def test_tension_decisions_are_corrections(client):
    a, b = _note(client, "The kiln fires at 1200"), _note(client, "The kiln never passes 1100")
    client.post("/entries/tensions/dismiss", json={"earlier_id": a["id"], "later_id": b["id"]})
    client.post("/entries/tensions/accept", json={"earlier_id": a["id"], "later_id": b["id"]})
    kinds = [c["kind"] for c in client.get("/learned/corrections").json()]
    assert "dismiss_tension" in kinds and "accept_tension" in kinds


def test_type_decisions_reweight_that_type(session):

    for i in range(6):
        learning.record(session, kind="dismiss_link_type", subject={"link_id": i, "signals": ["context"]})
    session.commit()
    weights = learning.signal_weights(session, accept="accept_link_type", dismiss="dismiss_link_type", prior=3.0)
    assert 0.5 <= weights["context"] < 1.0
    one = LinkFacts(id=1, source_id=1, target_id=2, context="Background for the trip.")
    assert type_candidates([one], weights=weights) == []


def test_the_migration_adds_the_entity_columns_over_the_auto_migrator(tmp_path):
    from tessellate.core.database_manager import DatabaseManager, _ensure_alembic_baseline

    db_path = tmp_path / "entities.db"
    DatabaseManager(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        assert {"kind", "aliases", "merged_into"} <= {r[1] for r in conn.execute('PRAGMA table_info("entities")')}
        conn.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("DELETE FROM alembic_version")
        conn.execute("INSERT INTO alembic_version VALUES ('a7d3e9c1f5b4')")
        conn.commit()
    finally:
        conn.close()
    _ensure_alembic_baseline(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [(_alembic_head(),)]
    finally:
        conn.close()


def _alembic_head() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return ScriptDirectory.from_config(config).get_current_head()


# Settings, Data: forgetting every dismissed suggestion, and taking the forgetting back


def test_a_dismissed_merge_comes_back_when_dismissals_are_cleared_and_goes_again_on_undo(client, session):
    a = _note(client, "one")
    x = _entity(session, "Sam", a["id"])
    y = _entity(session, "Sam Lee", a["id"])
    client.post("/suggestions/merges/dismiss", json={"a": x, "b": y, "signals": ["part_name"]})
    body1 = client.get("/suggestions").json()
    assert body1["merges"] == []
    body2 = client.get("/suggestions/dismissed").json()
    assert body2["by_kind"] == {"dismiss_merge": 1}

    cleared = client.post("/suggestions/dismissed/clear").json()
    assert cleared["cleared"] == 1 and len(cleared["ids"]) == 1
    body3 = client.get("/suggestions").json()
    assert body3["merges"], "the suggestion is offered again"
    body4 = client.get("/suggestions/dismissed").json()
    assert body4["total"] == 0
    kinds = [c["kind"] for c in client.get("/learned/corrections").json()]
    assert "dismiss_merge" not in kinds, "a forgotten dismissal is no longer a verdict"

    restored = client.post("/suggestions/dismissed/restore", json={"ids": cleared["ids"], "tensions": cleared["tensions"]}).json()
    assert restored["restored"] == 1
    body5 = client.get("/suggestions").json()
    assert body5["merges"] == []
    body6 = client.get("/suggestions/dismissed").json()
    assert body6["total"] == 1


def test_dismissed_tension_pairs_are_cleared_and_restored_with_the_corrections(client, session):
    deps.get_config().set_preference("tensions_dismissed", ["1:2", "3:4"])
    learning.record(session, kind="dismiss_resurface", subject={"entry_id": 1})
    session.commit()
    body = client.get("/suggestions/dismissed").json()
    assert body["total"] == 3 and body["tension_pairs"] == 2 and body["by_kind"] == {"dismiss_resurface": 1}

    cleared = client.post("/suggestions/dismissed/clear").json()
    assert cleared["cleared"] == 3 and cleared["tensions"] == ["1:2", "3:4"]
    assert deps.get_config().get_preference("tensions_dismissed", None) == []

    client.post("/suggestions/dismissed/restore", json={"ids": cleared["ids"], "tensions": cleared["tensions"]})
    assert deps.get_config().get_preference("tensions_dismissed") == ["1:2", "3:4"]
    body7 = client.get("/suggestions/dismissed").json()
    assert body7["total"] == 3


def test_clearing_leaves_other_corrections_alone_and_restore_ignores_strangers(client, session):
    learning.record(session, kind="refile", subject={"entry_id": 1}, from_value="A", to_value="B")
    learning.record(session, kind="accept_merge", subject={"a": 1, "b": 2})
    session.commit()
    body8 = client.post("/suggestions/dismissed/clear").json()
    assert body8["cleared"] == 0
    kinds = [c["kind"] for c in client.get("/learned/corrections").json()]
    assert "accept_merge" in kinds
    # An id that is not a revived dismissal is not touched.
    live_id = learning.corrections(session, "accept_merge")[0].id
    body9 = client.post("/suggestions/dismissed/restore", json={"ids": [live_id], "tensions": []}).json()
    assert body9["restored"] == 0


def test_tags_turned_down_on_notes_are_counted_cleared_and_restored(client):
    """INBOX 1271: "Clear dismissed suggestions" now reaches the per-note
    "Not suggested" tags, and Undo puts each back on its own note."""
    a = _note(client, "gym session")
    b = _note(client, "boiler service")
    client.post(f"/entries/{a['id']}/suggested-tags", json={"discard": ["Study", "uni"]})
    client.post(f"/entries/{b['id']}/suggested-tags", json={"discard": ["Study"]})
    body = client.get("/suggestions/dismissed").json()
    assert body["note_tags"] == 3 and body["total"] == 3

    cleared = client.post("/suggestions/dismissed/clear").json()
    assert cleared["cleared"] == 3
    assert client.get("/suggestions/dismissed").json()["total"] == 0
    assert client.get(f"/entries/{a['id']}").json()["discarded_tags"] == []

    client.post(
        "/suggestions/dismissed/restore",
        json={"ids": cleared["ids"], "tensions": cleared["tensions"], "note_tags": cleared["note_tags"]},
    )
    assert client.get(f"/entries/{a['id']}").json()["discarded_tags"] == ["Study", "uni"]
    assert client.get(f"/entries/{b['id']}").json()["discarded_tags"] == ["Study"]
    assert client.get("/suggestions/dismissed").json()["note_tags"] == 3


# L590: clearing dismissed suggestions clears per-note "Not suggested" tags (server, above) and the
# client carries them through Undo; an Undo of a look change reaches the top-bar theme button at once.
def test_the_clear_button_carries_note_tags_and_a_look_undo_repaints_the_theme_button():
    from pathlib import Path

    js = Path(__file__).resolve().parents[1] / "frontend" / "js"
    data = (js / "settings-data.js").read_text(encoding="utf-8")
    assert "note_tags: done.note_tags" in data.split('$("clear-dismissed")', 1)[1][:600]
    look = data.split('kept.kind === "look") {', 1)[1].split("} else if", 1)[0]
    assert "applyThemeChoice(" in look and "await" not in look.split("applyThemeChoice(", 1)[0].split("\n")[-1]
    settings = (js / "settings.js").read_text(encoding="utf-8")
    choice = settings.split("function applyThemeChoice(", 1)[1].split("\n}\n", 1)[0]
    assert "applyResolvedMode()" in choice
    assert "renderThemeToggle();" in settings.split("function applyResolvedMode()", 1)[1].split("\n}\n", 1)[0]
