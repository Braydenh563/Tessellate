"""Settings, Data: the suppressed-suggestions list (wc3-1110 "Left" item 2).

Counts and Clear all existed; this is one row per thing said no to, each with
its own Restore, taken back by the same `/dismissed/restore` Undo. The page
half is driven by scratchpad/ui-sweeps (1440 and 390); the markup, the help
and the copy are pinned here.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.ai import learning
from tessellate.core import deps
from tests.test_suggestions_inbox_kg9 import _entity, _note

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
DATA = (ROOT / "frontend" / "js" / "settings-data.js").read_text(encoding="utf-8")


def _items(client) -> list[dict]:
    return client.get("/suggestions/dismissed/items").json()["items"]


def test_every_kind_of_no_is_listed_once_with_words_not_ids(client, session):
    a = _note(client, "Garden plan for the spring")
    b = _note(client, "Boiler service history")
    sam = _entity(session, "Sam", a["id"])
    lee = _entity(session, "Sam Lee", a["id"])
    client.post("/suggestions/merges/dismiss", json={"a": sam, "b": lee, "signals": ["part_name"]})
    client.post("/entries/tensions/dismiss", json={"earlier_id": a["id"], "later_id": b["id"]})
    client.post(f"/entries/{a['id']}/suggested-tags", json={"discard": ["Study", "uni"]})
    learning.record(session, kind="dismiss_resurface", subject={"entry_id": b["id"]})
    session.commit()

    found = _items(client)
    by_key = {item["key"].split(":")[0]: [] for item in found}
    for item in found:
        by_key[item["key"].split(":")[0]].append(item)
    # The tension is one row (its pair key and its correction are one thing).
    assert len(by_key["t"]) == 1 and "Garden plan" in by_key["t"][0]["label"] and "Boiler" in by_key["t"][0]["label"]
    assert sorted(i["label"] for i in by_key["n"]) == ["Study", "uni"]
    assert all("Garden plan for the spring" in i["kind_label"] for i in by_key["n"]), "the tag's note is named under it"
    merge = next(i for i in by_key["c"] if i["kind"] == "dismiss_merge")
    assert merge["label"] == "Sam and Sam Lee" and merge["kind_label"] == "Name merge"
    old = next(i for i in by_key["c"] if i["kind"] == "dismiss_resurface")
    assert "Boiler service history" in old["label"]
    assert all(not re.fullmatch(r"[\d: ]+", i["label"]) for i in found), "no row is only numbers"
    assert not any("\u2014" in i["label"] + i["kind_label"] for i in found)


def test_restoring_one_row_offers_that_suggestion_again_and_leaves_the_rest(client, session):
    a = _note(client, "one")
    sam = _entity(session, "Sam", a["id"])
    lee = _entity(session, "Sam Lee", a["id"])
    client.post("/suggestions/merges/dismiss", json={"a": sam, "b": lee, "signals": ["part_name"]})
    learning.record(session, kind="dismiss_resurface", subject={"entry_id": a["id"]})
    session.commit()
    assert client.get("/suggestions").json()["merges"] == []
    merge = next(i for i in _items(client) if i["kind"] == "dismiss_merge")

    done = client.post("/suggestions/dismissed/item/restore", json={"key": merge["key"]}).json()
    assert done["restored"] == 1 and len(done["ids"]) == 1
    assert client.get("/suggestions").json()["merges"], "the merge is offered again"
    assert [i["kind"] for i in _items(client)] == ["dismiss_resurface"]
    assert client.get("/suggestions/dismissed").json()["total"] == 1

    # Undo is the route the Clear all toast already uses.
    back = client.post("/suggestions/dismissed/restore", json={"ids": done["ids"], "tensions": done["tensions"], "note_tags": done["note_tags"]}).json()
    assert back["restored"] == 1
    assert client.get("/suggestions").json()["merges"] == []
    assert len(_items(client)) == 2


def test_restoring_one_tension_pair_or_one_note_tag_and_undoing_each(client, session):
    a = _note(client, "Alpha note")
    b = _note(client, "Beta note")
    client.post("/entries/tensions/dismiss", json={"earlier_id": a["id"], "later_id": b["id"]})
    client.post(f"/entries/{a['id']}/suggested-tags", json={"discard": ["Study", "uni"]})
    pair = next(i for i in _items(client) if i["key"].startswith("t:"))
    tag = next(i for i in _items(client) if i["key"].startswith("n:") and i["label"] == "Study")

    done = client.post("/suggestions/dismissed/item/restore", json={"key": pair["key"]}).json()
    assert done["tensions"] == [pair["key"][2:]] and done["restored"] == 1
    assert deps.get_config().get_preference("tensions_dismissed") == []
    assert not any(i["key"].startswith("t:") for i in _items(client)), "the pair's correction is revived with its key"
    client.post("/suggestions/dismissed/restore", json={"ids": done["ids"], "tensions": done["tensions"]})
    assert any(i["key"] == pair["key"] for i in _items(client))

    one = client.post("/suggestions/dismissed/item/restore", json={"key": tag["key"]}).json()
    assert one["restored"] == 1 and one["note_tags"] == {str(a["id"]): ["Study"]}
    assert client.get(f"/entries/{a['id']}").json()["discarded_tags"] == ["uni"]
    # Undo adds the tag back beside the one still turned down.
    client.post("/suggestions/dismissed/restore", json={"note_tags": one["note_tags"]})
    assert sorted(client.get(f"/entries/{a['id']}").json()["discarded_tags"]) == ["Study", "uni"]


def test_a_key_that_is_gone_or_made_up_restores_nothing(client):
    for key in ("c:99999", "t:1:2", "n:99999:x", "z:1", "", "c:abc"):
        done = client.post("/suggestions/dismissed/item/restore", json={"key": key})
        assert done.status_code == 200 and done.json()["restored"] == 0, key


def test_the_list_is_capped_and_says_how_many_are_not_shown(client, session):
    for n in range(205):
        learning.record(session, kind="dismiss_resurface", subject={"entry_id": n + 1}, from_value=f"Old note {n}")
    session.commit()
    body = client.get("/suggestions/dismissed/items").json()
    assert len(body["items"]) == 200 and body["more"] == 5


def test_a_long_note_name_is_cut_with_an_ellipsis_not_mid_word(client):
    a = _note(client, "Tomato seedlings need six hours of sun and a warm windowsill all spring long")
    client.post(f"/entries/{a['id']}/suggested-tags", json={"discard": ["garden"]})
    kind = next(i for i in _items(client) if i["label"] == "garden")["kind_label"]
    name = kind.removeprefix("Tag turned down on ")
    assert name.endswith("…") and len(name) <= 36


def test_the_page_has_the_list_its_help_and_wires_restore():
    assert 'id="dismissed-list"' in INDEX and 'id="dismissed-toggle"' in INDEX
    assert 'class="ghost small disclosure-row hidden"' in INDEX, "a disclosure is the row recipe"
    assert "Review them one by one" in INDEX[INDEX.index('id="clear-help"') : INDEX.index('id="clear-help"') + 1800], "the help names the list"
    assert "/suggestions/dismissed/items" in DATA and "/suggestions/dismissed/item/restore" in DATA
    assert "rowActions(" in DATA[DATA.index("function dismissedRow") :], "Restore is the row-actions recipe, not a bordered button"
    assert 'label: "Restore"' in DATA and "settingsClearDone(" in DATA[DATA.index("async function dismissedRestore") :]
    assert 'kept.kind === "dismissed-one"' in DATA, "Undo and Redo know the one-row change"
    assert "\u2014" not in INDEX[INDEX.index('id="clear-help"') : INDEX.index('id="dismissed-list"') + 300]
