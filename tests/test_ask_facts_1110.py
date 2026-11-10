"""Composer audit 2 (fable-composer2-1110.md) G1 and G3, no model, clock fixed at Tuesday 10 November 2026, 09:00.

- G1: a yes needs evidence that answers the question; the newest dated fact leads.
- G3: Ask reads reminders, and every surface counts them by one rule."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime

import pytest

from tessellate.api import chat_extra, chat_said, chat_turn, routes_chat
from tessellate.entry import manager
from tessellate.repo import reminders as reminder_repo

NOW = datetime(2026, 11, 10, 9, 0)

NOTES = [
    ("# Harbor launch plan\n\nShip the Harbor mobile app to the public on 14 December.\n\nThree gates before then: beta feedback closed, the pricing page signed off, and the app store review passed.", "Work", "2026-09-03T10:00:00"),
    ("# Harbor standup\n\nPricing page still not signed off. Legal says the launch slips to 11 January.", "Work", "2026-11-10T08:00:00"),
    ("Call mum on Sunday about christmas plans", "Personal", "2026-11-08T10:00:00"),
    ("# Running log\n\nGoal: run 10 km by December.\n\n3 October: 5 km in 28 minutes.\n17 October: 5 km in 27 minutes.", "Health", "2026-10-17T19:00:00"),
]

#: text, due
REMINDERS = [
    ("Pay phone bill", datetime(2026, 11, 9, 17, 0)),
    ("Email landlord", datetime(2026, 11, 8, 10, 0)),
    ("Take bins out", datetime(2026, 11, 10, 19, 0)),
    ("Book dentist", datetime(2026, 11, 14, 12, 0)),
    ("Renew passport", datetime(2026, 11, 20, 12, 0)),
]


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


@pytest.fixture
def seeded(session):
    for content, cat, when in NOTES:
        entry = manager.create_entry(session, content, category_name=cat)
        entry.created_at = entry.updated_at = datetime.fromisoformat(when)
    for text, due in REMINDERS:
        reminder_repo.create(session, text=text, due_at=due, done=False)
    session.commit()
    return session


def ask(client, question):
    body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
    text = ""
    with client.stream("POST", "/chat/stream", json=body) as response:
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event.get("type") == "answer":
                    text += event["delta"]
    return text


# --- G1 -----------------------------------------------------------------------


@pytest.mark.parametrize("question", ["is the pricing page signed off", "has the pricing page been signed off"])
def test_a_gate_still_to_pass_is_not_a_yes(client, seeded, question):
    said = ask(client, question)
    assert not said.startswith("Yes"), said


def test_have_i_called_mum_is_not_yes_when_the_note_is_a_to_do(client, seeded):
    said = ask(client, "have I called mum")
    assert not said.startswith("Yes"), said
    assert "Not yet" in said or "nothing" in said.lower(), said


@pytest.mark.parametrize("question", ["when is the launch", "when does harbor launch"])
def test_the_newest_dated_fact_leads_and_the_older_is_said_once(client, seeded, question):
    said = ask(client, question)
    assert "11 January" in said.split("14 December")[0], said
    assert said.count("14 December") <= 1, said


def test_the_when_answer_and_the_days_answer_agree(client, seeded):
    assert "11 January" in ask(client, "how many days until the launch")
    assert "11 January" in ask(client, "when is the launch")


# --- G3 -----------------------------------------------------------------------


def test_do_i_have_any_reminders_today_reads_the_reminders(client, seeded):
    said = ask(client, "do I have any reminders today")
    assert "Take bins out" in said and "nothing in your notes" not in said, said


def test_did_i_pay_the_phone_bill_reads_the_reminder(client, seeded):
    said = ask(client, "did I pay the phone bill")
    assert "Pay phone bill" in said, said
    assert not said.startswith("I found nothing") and not said.startswith("Yes"), said


def test_when_do_the_bins_go_out_reads_the_reminder(client, seeded):
    said = ask(client, "when do the bins go out")
    assert "Take bins out" in said and "19:00" in said, said


def test_a_reminder_question_is_not_answered_from_a_note_that_omits_it(client, seeded):
    said = ask(client, "what bills are due")
    assert "Pay phone bill" in said, said


# --- one count rule -----------------------------------------------------------


def test_one_due_summary_for_every_surface(seeded):
    from tessellate.ai import day_digest, due_summary

    got = due_summary.of(reminder_repo.every(seeded), NOW)
    assert (got.today, got.overdue, got.later) == (1, 2, 2)
    assert due_summary.say(got) == "One due today, two overdue"
    digest = day_digest._due(seeded, NOW)
    assert digest[0]["text"].lower().rstrip(".") == "one reminder due today and two overdue"
    welcome = chat_extra.welcome_line(seeded, NOW)
    assert "3 reminders" not in welcome, welcome
    assert "1 reminder" in welcome and "2 overdue" in welcome, welcome


def test_the_dashboard_counts_by_the_same_rule():
    code = (
        "const fs=require('fs');const vm=require('vm');"
        "const src=fs.readFileSync('frontend/js/dashboard.js','utf8');"
        "for (const n of ['dashContinueNote','dashMeetingWhen','dashGlanceFacts']) {"
        "vm.runInThisContext(src.match(new RegExp('function '+n+'\\\\([\\\\s\\\\S]*?\\\\n}\\\\n'))[0]);}"
        "const now=new Date(2026,10,10,9,0);"
        "const mk=(t,d)=>({text:t,due_at:new Date(...d).toISOString(),done:false});"
        "const r=[mk('a',[2026,10,9,17,0]),mk('b',[2026,10,8,10,0]),mk('c',[2026,10,10,19,0]),mk('d',[2026,10,14,12,0])];"
        "const t=dashGlanceFacts({reminders:r,now}).find((f)=>f.id==='due');"
        "console.log(JSON.stringify([t.today,t.overdue,t.later,t.say,t.label]));"
    )
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [1, 2, 1, "One due today, two overdue", "One due today, two overdue"]


# --- parity: the model-on path is handed the same facts ---------------------------


@pytest.mark.parametrize("question, fact", [
    ("do I have any reminders today", "Take bins out"),
    ("did I pay the phone bill", "Pay phone bill"),
    ("when do the bins go out", "Take bins out"),
])
def test_a_model_is_handed_the_reminders_as_facts(ai_client, fake_ollama, seeded, question, fact):
    fake_ollama.librarian_reply = "Taken from the facts."
    with ai_client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True}) as response:
        list(response.iter_lines())
    prompt = "\n".join(str(m.get("content") or "") for m in fake_ollama.chat_calls[-1])
    assert fact in prompt, prompt[-600:]
