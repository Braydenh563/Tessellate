"""The review of the chat acts merged on 2026-11-08 (X17 cancel, X5 rename a
tag, category or note, X8 restore, X10 add to today): each finding is a test
that failed before its fix. Every provider runs against a fake transport
(CLAUDE.md section 4); the clock is fixed."""

from __future__ import annotations

import json
import re
from datetime import datetime

import pytest

from tessellate.ai import commands, composer_cancel, starter_acts
from tessellate.core.database import Entry

NOW = datetime(2026, 11, 8, 10, 0)
HEADING = "# 2026-11-08"


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    from tessellate.api import routes_chat

    monkeypatch.setattr("tessellate.core.config.user_now", lambda _config: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _config: NOW)


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True, **body}) as r:
        assert r.status_code == 200
        return [json.loads(line) for line in r.iter_lines() if line.strip()]


def _text(events) -> str:
    return " ".join(e.get("delta", "") for e in events if e.get("type") == "answer")


def _card(client, said, **body):
    events = _events(client, said, **body)
    return next((e for e in events if e.get("type") == "act"), None), events


def _run(client, steps):
    return client.post("/chat/command/run", json={"steps": steps}).json()


def _note(client, content, **body):
    return client.post("/entries", json={"content": content, **body}).json()["id"]


def _seal(session, note_id):
    session.get(Entry, note_id).is_private = True
    session.commit()


def _tags(session, note_id):
    session.expire_all()
    return session.get(Entry, note_id).tags


# --- 1, 2, 11: a rename never merges, whatever hides the other holder ------------------------------


def test_a_locked_private_note_holding_the_new_tag_blocks_the_merge(client, session):
    public = [_note(client, f"# S{i}\n\nx", tags=["gym"]) for i in range(2)]
    secret = _note(client, "# Secret\n\nbody", tags=["fitness"])
    _seal(session, secret)
    card, events = _card(client, "rename the tag gym to fitness")
    assert card is None and "There is already a tag called “fitness”" in _text(events)
    assert [json.loads(_tags(session, i)) for i in public] == [["gym"]] * 2


def test_a_binned_note_holding_the_new_tag_blocks_the_merge(client, session):
    _note(client, "# S\n\nx", tags=["gym"])
    old = _note(client, "# Old\n\nx", tags=["fitness"])
    client.delete(f"/entries/{old}")
    card, events = _card(client, "rename the tag gym to fitness")
    assert card is None and "There is already a tag called “fitness”" in _text(events)


def test_a_binned_private_note_holding_the_old_tag_blocks_the_rename(client, session):
    _note(client, "# S\n\nx", tags=["gym"])
    secret = _note(client, "# Secret\n\nx", tags=["gym"])
    _seal(session, secret)
    client.delete(f"/entries/{secret}")
    card, events = _card(client, "rename the tag gym to fitness")
    assert card is None and "also on private notes" in _text(events)


def test_a_rename_touching_a_binned_note_undoes_exactly(client, session):
    live = _note(client, "# S\n\nx", tags=["gym", "legs"])
    binned = _note(client, "# Old\n\nx", tags=["legs", "gym"])
    client.delete(f"/entries/{binned}")
    before = (_tags(session, live), _tags(session, binned))
    card, _ = _card(client, "rename the tag gym to fitness")
    outcome = _run(client, card["steps"])
    assert outcome["ok"] and "fitness" in _tags(session, live) and "fitness" in _tags(session, binned)
    _run(client, outcome["undo"])
    assert sorted(json.loads(_tags(session, live))) == sorted(json.loads(before[0]))
    assert sorted(json.loads(_tags(session, binned))) == sorted(json.loads(before[1]))


def test_a_category_cannot_be_renamed_onto_one_that_only_a_binned_note_holds(client):
    _note(client, "# S\n\nx", category="Work")
    old = _note(client, "# Old\n\nx", category="Job")
    client.delete(f"/entries/{old}")
    card, events = _card(client, "rename the category Work to Job")
    assert card is None and "There is already a category called “Job”" in _text(events)


def test_the_confirm_route_runs_the_same_checks_as_the_planner(client, session):
    _note(client, "# S\n\nx", tags=["gym"])
    secret = _note(client, "# Secret\n\nx", tags=["fitness"])
    _seal(session, secret)
    outcome = _run(client, [{"name": "rename_tag", "arguments": {"old": "gym", "new": "fitness"}}])
    assert not outcome["ok"]
    assert json.loads(_tags(session, secret)) == ["fitness"]
    a = _note(client, "# A\n\nx", category="Work")
    _note(client, "# B\n\nx", category="Job")
    outcome = _run(client, [{"name": "rename_category", "arguments": {"old": "Work", "new": "Job"}}])
    assert not outcome["ok"] and client.get(f"/entries/{a}").json()["category"] == "Work"


def test_the_command_route_is_behind_the_apps_origin_check(client):
    """No route of its own: the app-wide Origin check refuses a page on another site."""
    step = [{"name": "rename_tag", "arguments": {"old": "gym", "new": "fitness"}}]
    refused = client.post("/chat/command/run", json={"steps": step}, headers={"Origin": "https://evil.example"})
    assert refused.status_code == 403


# --- 3, 7, 8: reading a rename or a restore ----------------------------------------------------


def _read(said):
    return commands.read_typed(said, NOW)


@pytest.mark.parametrize("said", ["rename note 12 to Travel", "rename the note 12 to Travel", "rename note #12 to Travel", "rename #12 to Travel"])
def test_a_note_named_by_its_number_keeps_its_id(said):
    found = _read(said)
    assert found and found["intent"] == "rename" and found["note_id"] == 12 and found["title"] == "Travel", said


def test_a_rename_by_number_reaches_that_note_not_a_title_with_the_number(client):
    for i in range(12):
        _note(client, f"# Filler {i}\n\nx")
    lease = _note(client, "# Flat 12 lease\n\nRoom 12.")
    target = _note(client, "# Passport\n\nRenew.")
    card, _ = _card(client, f"rename note {target} to Travel")
    assert card and card["steps"][0]["arguments"]["note_id"] == target and lease != target


def test_a_rename_stops_before_a_second_request(client):
    _note(client, "# S\n\nx", tags=["gym"])
    found = _read("rename the tag gym to fitness and delete the boiler note")
    assert found["intent"] == "rename_tag" and found["new"] == "fitness"
    card, events = _card(client, "rename the tag gym to fitness and delete the boiler note")
    assert card["label"] == "Rename the tag “gym” to “fitness” on 1 note"
    assert "delete the boiler note" in _text(events), "the part left over is said, not dropped"


def test_a_name_holding_and_without_a_verb_is_kept_whole():
    assert _read("rename the tag R and D to research")["old"] == "R and D"
    assert _read("rename the tag gym to arts and crafts")["new"] == "arts and crafts"


def test_a_note_title_holding_to_is_found_by_the_longer_name(client):
    cook = _note(client, "# How to cook\n\nBoil water.")
    _note(client, "# How to park\n\nSlowly.")
    card, _ = _card(client, "rename the note how to cook to Recipes")
    assert card and card["steps"][0]["arguments"]["note_id"] == cook
    assert card["steps"][0]["arguments"]["content"].startswith("# Recipes")


def test_the_first_to_still_splits_when_the_old_name_is_the_short_one(client):
    atlas = _note(client, "# Atlas\n\nMaps.")
    card, _ = _card(client, "rename the note Atlas to Trip to Lisbon")
    assert card and card["steps"][0]["arguments"]["note_id"] == atlas
    assert card["steps"][0]["arguments"]["content"].startswith("# Trip to Lisbon")


@pytest.mark.parametrize("said", [
    "rename the tag “back to school” to school",
    "rename the tag \"back to school\" to school",
    "rename the tag back to school to school",
    "rename the tag back-to-school to “school”",
])
def test_a_tag_name_holding_to_is_renamed(client, said):
    _note(client, "# A\n\nx", tags=["back-to-school"])
    card, events = _card(client, said)
    assert card and card["steps"] == [{"name": "rename_tag", "arguments": {"old": "back-to-school", "new": "school"}}], _text(events)


def test_a_quoted_new_name_may_hold_to(client):
    _note(client, "# A\n\nx", tags=["school"])
    card, _ = _card(client, "rename the tag school to “back to school”")
    assert card and card["steps"][0]["arguments"]["new"] == "back to school"


@pytest.mark.parametrize("said", ["get back to John about the boiler note", "get back to me about the passport note", "recover from the flu note", "recover from the flu"])
def test_get_back_and_recover_need_the_bin_named(said):
    found = _read(said)
    assert found is None or found["intent"] != "restore", said


@pytest.mark.parametrize("said", ["recover the passport note from the bin", "get back the passport note from the trash", "restore the passport note"])
def test_get_back_and_recover_read_with_the_bin_named(said):
    found = _read(said)
    assert found and found["intent"] == "restore" and found["about"] == "passport", said


def test_restore_all_says_how_many_and_asks(client):
    for name in ("Passport", "Boiler"):
        client.delete("/entries/" + str(_note(client, "# " + name + "\n\nx")))
    card, events = _card(client, "restore all my notes from the bin")
    assert card is None and "2 notes in the bin" in _text(events) and "“restore the Boiler note”" in _text(events)


# --- 4, 6: restore never says what a sealed note holds, and brings back notes only ------------


def test_restore_treats_a_private_note_as_missing(client, session):
    secret = _note(client, "# Divorce lawyer\n\nsecret")
    client.delete(f"/entries/{secret}")
    _seal(session, secret)
    _, private = _card(client, "restore the divorce note")
    _, absent = _card(client, "restore the zebra note")
    assert "private" not in _text(private).lower()
    assert _text(private).replace("divorce", "X") == _text(absent).replace("zebra", "X")
    _, numbered = _card(client, f"restore note {secret}")
    assert "private" not in _text(numbered).lower() and "nothing in the bin" in _text(numbered)


def test_restore_offers_a_public_note_beside_a_private_one(client, session):
    public = _note(client, "# Passport\n\nRenew.")
    secret = _note(client, "# Passport secret\n\nx")
    client.delete(f"/entries/{public}")
    client.delete(f"/entries/{secret}")
    _seal(session, secret)
    card, _ = _card(client, "restore the passport note")
    assert card and card["steps"][0]["arguments"]["note_id"] == public


def test_restore_leaves_a_binned_board_to_the_bin_view(client, session):
    board = _note(client, "# Kitchen plan\n\nboard")
    session.get(Entry, board).is_board = True
    session.commit()
    client.delete(f"/entries/{board}")
    card, events = _card(client, "restore the kitchen plan from the bin")
    assert card is None and "nothing in the bin" in _text(events)
    outcome = _run(client, [{"name": "restore_note", "arguments": {"note_id": board}}])
    assert not outcome["ok"]
    session.expire_all()
    assert session.get(Entry, board).is_deleted


def test_restore_matches_whole_words(client):
    client.delete("/entries/" + str(_note(client, "# Cardiology appointment\n\nx")))
    card, events = _card(client, "restore the car note")
    assert card is None and "nothing in the bin" in _text(events)
    card, _ = _card(client, "restore the cardiology note")
    assert card


# --- 5, 9: add to today's note -----------------------------------------------------------------


def _today(client, body="- call the bank"):
    return _note(client, f"{HEADING}\n\n{body}")


def test_undo_of_add_to_today_refuses_when_the_note_changed_since(client):
    note = _today(client)
    card, _ = _card(client, "add buy milk to today's note")
    outcome = _run(client, card["steps"])
    typed = client.get(f"/entries/{note}").json()["content"] + "\n- typed later by hand"
    client.put(f"/entries/{note}", json={"content": typed})
    undone = _run(client, outcome["undo"])
    assert not undone["ok"] and "changed" in undone["summary"].lower()
    assert client.get(f"/entries/{note}").json()["content"] == typed, "the text typed after the act is kept"


def test_undo_of_add_to_today_still_works_when_nothing_changed(client):
    note = _today(client)
    card, _ = _card(client, "add buy milk to today's note")
    outcome = _run(client, card["steps"])
    assert _run(client, outcome["undo"])["ok"]
    assert client.get(f"/entries/{note}").json()["content"] == f"{HEADING}\n\n- call the bank"


def test_two_cards_for_a_note_not_made_yet_make_one_note(client, session):
    first, _ = _card(client, "add buy milk to today's note")
    second, _ = _card(client, "add pay rent to today's note")
    assert first["steps"][0]["name"] == second["steps"][0]["name"] == "create_note"
    assert _run(client, first["steps"])["ok"] and _run(client, second["steps"])["ok"]
    session.expire_all()
    daily = [e.content for e in session.query(Entry).all() if (e.content or "").startswith(HEADING)]
    assert len(daily) == 1 and "Buy milk" in daily[0] and "Pay rent" in daily[0], daily


def test_the_words_keep_their_case_where_a_fold_changes_the_length():
    kind, slots = starter_acts.read("add İİ x to today's note")
    assert kind == "append_today" and slots["words"] == "İİ x"
    kind, slots = starter_acts.read("add buy milk to today’s note")
    assert slots["words"] == "buy milk"


@pytest.mark.parametrize("said", ["add that to today's note", "add it to today's note"])
def test_a_pointer_is_asked_about_not_written(client, said):
    card, events = _card(client, said)
    #: Moved 2026-11-09: a pointer is the note it means (owner decision), so with none to mean it asks which.
    assert card is None and "Which note should go in today's note?" in _text(events)


def test_a_pointer_read_by_the_starter_is_asked_about_too(session):
    line, card = starter_acts._append_today(session, slots={"words": "it"}, now=NOW)
    assert card is None and "Which note should go in today's note?" in line


# --- 10: cancel ----------------------------------------------------------------------------------

LABEL = "Move the note “Boiler service” to the bin"
WAITING = [{"question": "delete the boiler note", "answer": "Confirm to do it.", "pending_act": LABEL}]


@pytest.mark.parametrize("said", ["no, cancel that", "wait cancel", "no cancel it", "no. cancel", "wait, cancel that", "Cancel!"])
def test_cancel_in_other_words_closes_the_open_card(said):
    events = composer_cancel.reply(said, WAITING)
    assert events and events[1] == {"type": "act", "cancel": True, "label": LABEL}


@pytest.mark.parametrize("said", ["cancel the boiler note", "no, cancel my gym membership note", "wait for me"])
def test_a_sentence_with_cancel_in_it_is_not_the_drop(said):
    assert composer_cancel.reply(said, WAITING) is None


@pytest.mark.parametrize("said", ["no, cancel that", "wait cancel", "no cancel it", "cancel that"])
def test_cancel_reaches_the_open_card_through_the_chat_route(client, said):
    _note(client, "# Boiler service\n\nDue.")
    sent = _events(client, "delete the boiler note")
    card = next(e for e in sent if e.get("type") == "act")
    history = [{"question": "delete the boiler note", "answer": _text(sent), "pending_act": card["label"]}]
    events = _events(client, said, history=history)
    assert {"type": "act", "cancel": True, "label": card["label"]} in events
    assert "Nothing was changed" in _text(events)


def _js(name):
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "frontend" / "js" / name).read_text(encoding="utf-8")
    return text, lambda fn: re.search(rf"^function {fn}\(.*?^}}", text, re.S | re.M).group(0)


def _node(script):
    import subprocess

    outcome = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30)
    return json.loads(outcome.stdout)


def test_the_page_closes_only_the_card_the_reply_names():
    """renderActCard's cancel branch on a page with two open cards: found by the id the reply
    names (`waitingCard`), which a send leaves on the card after it marks it not pending."""
    ask, _ = _js("ask-compose.js")
    finder = re.search(r"  const waitingCard = .*?;\n", ask).group(0)
    branch = re.search(r"if \(event\.cancel\) \{\n(.*?)\n  \}", ask, re.S).group(1)
    out = _node(
        finder
        + "const close = (event) => {" + branch + "};"
        + r"""
const mk = (label) => ({ dataset: { askedAct: label }, consentId: "id-" + label, replaced: false, replaceWith() { this.replaced = true; } });
const cards = [mk("Move A to the bin"), mk("Move B to the bin")];
var document = { querySelectorAll: () => cards };
var toolChip = (t) => t;
close({ label: "Move A to the bin", consent_id: "id-Move A to the bin" });
const one = cards.map((c) => c.replaced);
close({ label: "Move C to the bin", consent_id: "id-none" });
const none = cards.map((c) => c.replaced);
close({});
console.log(JSON.stringify({ one, none, last: cards.map((c) => c.replaced) }));
"""
    )
    assert out["one"] == [True, False], "the named card closes, the other stays open"
    assert out["none"] == [True, False], "an id no card has closes nothing"
    assert out["last"] == [True, True], "no id or label (an older server) closes the last open card"


def test_the_page_sends_the_last_open_cards_label_and_the_mark_is_set():
    ask, _ = _js("ask-compose.js")
    kit, pick = _js("answer-kit.js")
    assert "card.dataset.pendingAct = card.dataset.askedAct = event.label" in ask and "delete card.dataset.pendingAct" in ask
    assert "chatHistoryWithOpenCard" not in ask, "the comment names the function that exists"
    out = _node(
        pick("chatHistoryToSend")
        + r"""
const cards = [{ dataset: { pendingAct: "Move A to the bin", askedAct: "Move A to the bin" }, consentId: "a1" }, { dataset: { pendingAct: "Move B to the bin", askedAct: "Move B to the bin" }, consentId: "b2" }];
var $ = () => ({ querySelectorAll: () => cards.filter((c) => c.dataset.pendingAct) });
var chatConv = { turns: [{ question: "a" }, { question: "b" }] };
var chatSummary = null;
var MAX_CLIENT_HISTORY = 10;
const first = chatHistoryToSend();
const second = chatHistoryToSend();
console.log(JSON.stringify([first, second]));
"""
    )
    first, second = out
    assert first[-1]["pending_act"] == "Move B to the bin" and first[-1]["pending_id"] == "b2" and "pending_act" not in first[0]
    assert "pending_act" not in second[-1], "a send marks every card not pending: a card ignored turns ago is never run by a later yes"
