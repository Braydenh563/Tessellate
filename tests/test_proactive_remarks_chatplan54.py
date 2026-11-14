"""CHAT_PLAN "Proactive" (L-chat-54, 55, 57): the companion's remarks on real
signals only, from the notebook and no model, on a fixed clock.

Measured before (scratch probe on this fixture): a reminder due at 18:00 was
said at 09:00 (the window was three days); `_back` was never fed so no
resurfaced note was ever spoken; a 40-day-old unticked item, a tension, a dated
flight with no reminder and a new sentence answering a question said nothing."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from tessellate.ai import composer_voice
from tessellate.api import routes_insights
from tessellate.ai import tensions
from tessellate.core.database import DerivedFact, Reminder
from tessellate.entry import manager

NOW = datetime(2026, 11, 10, 9, 0)


def _clock(monkeypatch) -> None:
    monkeypatch.setattr(routes_insights, "user_now", lambda _config: NOW)


def _note(session, text: str, when: datetime):
    note = manager.create_entry(session, text)
    note.created_at = when
    session.commit()
    return note


def _remarks(client) -> list[dict]:
    return client.get("/insights/remarks").json()["remarks"]


def test_p1_a_reminder_is_said_within_the_hour_or_when_overdue_not_hours_ahead(client, session, monkeypatch):
    _clock(monkeypatch)
    session.add_all([
        Reminder(text="Collect the parcel", due_at=NOW + timedelta(minutes=30)),
        Reminder(text="Book the dentist", due_at=NOW - timedelta(hours=3)),
        Reminder(text="Evening class", due_at=NOW + timedelta(hours=9)),
    ])
    session.commit()
    said = " ".join(r["text"] for r in _remarks(client) if r["kind"] == "due")
    assert "Collect the parcel" in said and "Book the dentist" in said
    assert "Evening class" not in said


def test_p2_one_back_remark_is_said_for_the_resurfaced_note(client, session, monkeypatch):
    from tessellate.ai import resurface

    _clock(monkeypatch)
    old = _note(session, "# Kiln\n\nFired the first test tiles at a thousand and two hundred degrees.", datetime(2026, 5, 2, 9, 0))
    monkeypatch.setattr(resurface, "for_day", lambda _s, _d, limit=3: [old])
    back = [r for r in _remarks(client) if r["kind"] == "resurfaced"]
    assert len(back) == 1 and "Kiln" in back[0]["text"] and back[0]["fact"] == f"resurfaced:{old.id}"


def test_p5_a_plan_open_over_thirty_days_is_said_as_unticked(client, session, monkeypatch):
    _clock(monkeypatch)
    _note(session, "# Flat\n\n- [ ] Renew the passport\n- [x] Pay the deposit", datetime(2026, 9, 20, 9, 0))
    fresh = _note(session, "# Garage\n\n- [ ] Sort the shelves", datetime(2026, 11, 1, 9, 0))
    drift = [r for r in _remarks(client) if r["kind"] == "drift"]
    assert len(drift) == 1 and "Renew the passport" in drift[0]["text"] and "20 September" in drift[0]["text"]
    assert fresh.id not in drift[0]["sources"]


def test_p9_a_tension_is_said_once_with_both_sentences_and_the_newer_named(client, session, monkeypatch):
    _clock(monkeypatch)
    a = _note(session, "# Launch plan\n\nWe will launch in May with the full team.", datetime(2026, 3, 1, 9, 0))
    b = _note(session, "# Launch slipped\n\nThe launch moved to August after the delay.", datetime(2026, 10, 1, 9, 0))
    tensions.record_event(session, tensions.FOUND, a.id, b.id, reason="launch month", model="local", confidence=0.9)
    session.commit()
    tension = [r for r in _remarks(client) if r["kind"] == "tension"]
    assert len(tension) == 1
    text = tension[0]["text"]
    assert "launch in May" in text and "moved to August" in text and "Launch slipped" in text
    assert text.index("May") < text.index("August") and tension[0]["ttl_days"] >= 3650


def test_p10_a_dated_plan_in_a_week_with_no_reminder_gets_an_act_chip(client, session, monkeypatch):
    _clock(monkeypatch)
    trip = _note(session, "# Trip\n\nFlight to Lisbon on 14 November at 9am.", datetime(2026, 10, 20, 9, 0))
    said = [r for r in _remarks(client) if r["kind"] == "upcoming"]
    assert len(said) == 1 and "No reminder is set." in said[0]["text"] and "Flight to Lisbon" in said[0]["text"]
    assert said[0]["act"]["due_at"].startswith("2026-11-14T09:00") and said[0]["act"]["entry_id"] == trip.id
    session.add(Reminder(text="Flight", due_at=datetime(2026, 11, 14, 9, 0), entry_id=trip.id))
    session.commit()
    assert not [r for r in _remarks(client) if r["kind"] == "upcoming"]


def test_p8_a_new_sentence_that_answers_an_open_question_is_said_with_both_quoted(client, session, monkeypatch):
    _clock(monkeypatch)
    asker = _note(session, "Is the API subscription worth the monthly cost for the side project?", datetime(2026, 11, 1, 9, 0))
    session.add(DerivedFact(entry_id=asker.id, kind="question", text="Is the API subscription worth the monthly cost?", confidence=0.9))
    session.commit()
    _note(session, "# Costs\n\nThe API subscription is worth the monthly cost: it saved me ten hours.", datetime(2026, 11, 10, 8, 0))
    said = [r for r in _remarks(client) if r["kind"] == "answered"]
    assert len(said) == 1
    assert "API subscription worth the monthly cost" in said[0]["text"] and "saved you ten hours" in said[0]["text"]


def test_private_notes_are_never_read_for_a_remark(client, session, monkeypatch):
    _clock(monkeypatch)
    secret = _note(session, "# Vault\n\n- [ ] Move the safe code 4417", datetime(2026, 9, 1, 9, 0))
    secret.is_private = True
    session.commit()
    assert "4417" not in client.get("/insights/remarks").text


def _spread(days: list[int]) -> list[dict]:
    today = date(2026, 11, 10)
    return [
        {"id": i + 1, "content": f"Golf round number {i}\nPlayed golf at the club.", "created_at": (today - timedelta(days=d)).isoformat(), "category": "", "tags": []}
        for i, d in enumerate(days)
    ]


def test_p4_a_pattern_needs_three_mentions_across_three_weeks():
    today = date(2026, 11, 10)
    same_week = [r for r in composer_voice.remarks(_spread([1, 2, 3]), today=today) if r["kind"] == "pattern"]
    spread = [r for r in composer_voice.remarks(_spread([1, 9, 17]), today=today) if r["kind"] == "pattern"]
    assert same_week == []
    assert spread and "last four weeks" in spread[0]["text"] and "golf" in spread[0]["text"].lower()


def test_p3_the_dashboard_line_says_this_day_in_an_earlier_year_on_an_odd_draw(client, session, monkeypatch):
    _clock(monkeypatch)
    _note(session, "# Lisbon\n\nBooked the hotel in Alfama for the first week.", datetime(2025, 11, 10, 9, 0))
    _note(session, "Bought bread and milk this morning.", datetime(2026, 11, 9, 9, 0))
    odd = client.get("/insights/today-line?seed=1").json()
    even = client.get("/insights/today-line?seed=2").json()
    assert odd["kind"] == "on_this_day" and "2025" in odd["text"] and "Lisbon" in odd["text"]
    assert even["kind"] == "today"


def test_p7_the_no_model_digest_is_labelled_your_notes_no_ai(client, session, monkeypatch):
    note = manager.create_entry(session, "Bought milk and eggs")
    session.commit()
    assert note.id
    one_shot = client.post("/insights/digest").json()
    assert one_shot["source"] == "Your notes, no AI"
    events = [json.loads(line) for line in client.post("/insights/digest/stream").text.splitlines() if line.strip()]
    assert {"type": "source", "label": "Your notes, no AI"} in events


# --- P11: rate rules, run in node against the real file ------------------------------

_ROOT = Path(__file__).resolve().parents[1]
_RUNNER = r"""
const fs = require("fs");
const store = {};
global.window = global;
global.prefs = { json: (k, d) => (k in store ? JSON.parse(store[k]) : d), setJSON: (k, v) => { store[k] = JSON.stringify(v); } };
const spec = JSON.parse(process.argv[2]);
global.nmb = { keyAt: 0, afterClean: (f) => f() };
global.apiJson = async () => ({ remarks: spec.remarks });
global.nameMarkBuddyStill = () => false;
global.nameMarkBuddyExpress = () => {};
const said = [];
global.nameMarkSay = (_b, text) => said.push(text);
global.reminderMadeUndo = () => {};
global.toast = () => {};
const classes = new Set();
global.document = { hidden: false, getElementById: () => ({ isConnected: true, classList: { contains: (c) => classes.has(c) }, querySelector: () => null }), createElement: () => ({}) };
new Function(fs.readFileSync(process.argv[1], "utf8")).call(global);
(async () => {
  const log = [];
  for (const step of spec.steps) {
    const real = Date.now;
    Date.now = () => step.at;
    nmb.keyAt = step.key || 0;
    const before = said.length;
    await window.nameMarkBuddyRemark();
    log.push(said.length - before);
    Date.now = real;
  }
  console.log(JSON.stringify({ log, said, store }));
})();
"""
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _run(remarks: list[dict], steps: list[dict]) -> dict:
    got = subprocess.run(
        ["node", "-e", _RUNNER, str(_ROOT / "frontend/js/companion-remark.js"), json.dumps({"remarks": remarks, "steps": steps})],
        capture_output=True, text=True, check=True, timeout=30,
    )
    return json.loads(got.stdout)


DAY = 86_400_000
T0 = 1_800_000_000_000


@node
def test_p11_three_a_day_none_after_a_key_press_and_one_fact_once_a_week():
    four = [{"text": f"Remark {i}", "key": f"k{i}", "fact": f"f{i}"} for i in range(4)]
    out = _run(four, [{"at": T0 + i * 1000, "key": 0} for i in range(4)])
    assert out["log"] == [1, 1, 1, 0], "the fourth in a day is not said"
    out = _run(four, [{"at": T0, "key": T0 - 5_000}, {"at": T0 + 60_000, "key": T0 + 55_000}])
    assert out["log"] == [0, 0] and out["said"] == [], "typed within 20 s of the key press"
    out = _run(four[:1], [{"at": T0}, {"at": T0 + 6 * DAY}, {"at": T0 + 8 * DAY}])
    assert out["log"] == [1, 0, 1], "the same fact is not said again for 7 days"
    once = [{"text": "Tension", "key": "t", "fact": "tension:1:2", "ttl_days": 3650}]
    assert _run(once, [{"at": T0}, {"at": T0 + 100 * DAY}])["log"] == [1, 0]


def test_p11_the_companion_has_one_switch_for_remarks_and_the_act_chip_makes_a_reminder():
    boot = (_ROOT / "frontend/js/avatars.js").read_text(encoding="utf-8")
    assert '["remark", "Say something from your notes now and then", ["remark"]]' in boot
    lazy = (_ROOT / "frontend/js/companion-remark.js").read_text(encoding="utf-8")
    assert 'apiJson("/reminders", { method: "POST"' in lazy and "entry_id: act.entry_id" in lazy


def test_the_help_topic_says_what_the_companion_now_says_and_its_limits():
    from tessellate.ai.help_topics_more import MORE_TOPICS

    body = next(t["body"] for t in MORE_TOPICS if t["id"] == "companion-remarks")
    for phrase in ("three times a day", "within the hour", "unticked", "disagree", "Set a reminder", "20 seconds", "only once"):
        assert phrase in body
