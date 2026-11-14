"""The recount rows L-chat-144 to L-chat-176 (CHAT_PLAN B1 to B41 gates), each
gate the plan names proved on a fixed clock, no model. One test per gate."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from tests._app_js import app_js_text

from tessellate.ai import composer_digest, composer_voice

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 7, 17)


def _note(i: int, content: str, day: str) -> dict:
    return {"id": i, "content": content, "created_at": f"{day}T10:00:00", "category": "Life", "tags": []}


GYM = [_note(1, "Gym three times this week", "2026-07-14"), _note(2, "Gym again on Tuesday, legs", "2026-07-07"),
       _note(3, "Gym on Friday, back day", "2026-07-03"), _note(4, "Dentist is booked with Dr Lee", "2026-05-02")]


def test_b2_ten_kinds_each_have_a_gold_answer():
    """B2: a shape per question kind, ten kinds, each a gold answer."""
    gold = json.loads((ROOT / "tests" / "fixtures" / "gold_answers.json").read_text(encoding="utf-8"))
    kinds = {a["type"] for a in gold["answers"]}
    assert len(kinds) >= 10, kinds


def test_b4_each_fact_carries_a_count_or_an_age():
    """B4: "three notes", "the newest written a few days ago", "just the one note"."""
    many = composer_digest.answer("how is the gym going?", GYM, today=TODAY)["text"]
    assert "three notes" in many and "a few days ago" in many
    one = composer_digest.answer("what do I know about the dentist?", GYM, today=TODAY)["text"]
    assert "just the one note" in one


def test_b5_hovering_a_citation_previews_its_sentence():
    """B5: the mark opens the peek on hover and the peek holds the cited sentence, marked."""
    code = app_js_text()
    assert 'link.addEventListener("mouseenter", () => scheduleCitationPeek(link, describe));' in code
    peek = code[code.index("function openCitationPeek") : code.index("function openCitationPeek") + 3600]
    assert 'mark.textContent = passage;' in peek and "citationPeekText(content, source.start, source.end" in peek


@pytest.mark.parametrize("notes", [GYM[:1], GYM[3:], [_note(i, f"# Note {i}\n\nBody", "2026-07-17") for i in range(1, 4)]])
def test_b41_the_greeting_line_never_repeats_in_twenty_draws(notes):
    """B41: the sub line rotates; two draws in a row never say the same words."""
    lines = [composer_voice.today_line(notes, today=TODAY, seed=1000 + s)["text"] for s in range(21)]
    assert all(a != b for a, b in zip(lines, lines[1:])), lines
    assert len(set(lines)) >= 4


def test_b41_the_dashboard_draws_the_composed_line_with_a_moving_seed():
    dash = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert "dashTodayLine(dashLine.bucket)" in dash and "Math.floor(Date.now() / DASH_LINE_MS)" in dash


def test_b23_every_number_in_the_day_digest_links_to_its_list(session):
    """B23: each count line names the phrases that hold its numbers (`links`), and no number is left outside one."""
    from tests.test_day_digest import NOW, _notebook, _numbers

    from tessellate.ai import day_digest

    _notebook(session)
    counted = [line for line in day_digest.compose(session, NOW)["lines"] if line["kind"] in ("count", "more")]
    assert {line["part"] for line in counted} >= {"due", "questions", "changed", "quiet"}
    for line in counted:
        rest = line["text"].lower()
        assert line["links"], line
        for phrase in line["links"]:
            assert phrase.lower() in rest, (phrase, line)
            rest = rest.replace(phrase.lower(), "")
        assert not _numbers(rest), (rest, line)


def test_b23_the_dashboard_wraps_each_link_phrase_in_an_opener():
    js = (ROOT / "frontend" / "js" / "dash-day.js").read_text(encoding="utf-8")
    body = js[js.index("function digestSaidLine") : js.index("function dashPatternBit")]
    assert "line.links" in body and "opens[line.part](line)" in body and 'link.className = "digest-day-open"' in body


def test_413_the_empty_chat_fit_cannot_chase_its_own_resize_observer():
    """INBOX 413 (L-chat-167): the observer only records the size, the fit runs a
    frame later for a change of 2px or more, and flips at most once in 500ms."""
    chat = (ROOT / "frontend" / "js" / "chat.js").read_text(encoding="utf-8")
    observer = chat[chat.index("new ResizeObserver((entries) => {") :]
    observer = observer[: observer.index(".observe(box)")]
    assert "fitChatEmpty()" in observer and observer.index("requestAnimationFrame") < observer.index("fitChatEmpty()")
    assert "Math.abs(rect.width - last.w) < 2 && Math.abs(rect.height - last.h) < 2" in observer
    assert "if (queued) return;" in observer
    panes = (ROOT / "frontend" / "js" / "settings-panes.js").read_text(encoding="utf-8")
    fit = panes[panes.index("function fitChatEmpty()") :]
    fit = fit[: fit.index("\n}\n")]
    assert "performance.now() - (fitChatEmpty.lastFlip" not in fit  # read once into a local, below
    assert "now2 - (fitChatEmpty.lastFlip || 0) < 500" in fit and "room + 4 < full" in fit and "room >= full + 4" in fit
    #: The benign browser notice is swallowed, never counted as a fault.
    assert "ResizeObserver loop " in (ROOT / "frontend" / "js" / "boot-guard.js").read_text(encoding="utf-8")


def test_composer_row1_a_remark_names_its_note_and_the_bubble_opens_it(client, session, monkeypatch):
    """Composer row 1: composed from the notes, rate-limited, never twice, quiet while typing, source one tap away."""
    from datetime import datetime

    from tessellate.api import routes_insights
    from tessellate.entry import manager

    monkeypatch.setattr(routes_insights, "user_now", lambda _config: datetime(2026, 11, 1, 9, 0))
    old = manager.create_entry(session, "# Lisbon\n\nBooked the hotel in Alfama for the first week.")
    old.created_at = datetime(2025, 11, 1, 10, 0)
    session.commit()
    remarks = client.get("/insights/remarks").json()["remarks"]
    named = [r for r in remarks if "Lisbon" in r["text"] or "hotel" in r["text"]]
    assert named and old.id in named[0]["sources"]
    remark = (ROOT / "frontend" / "js" / "companion-remark.js").read_text(encoding="utf-8")
    assert "Date.now() - (nmb.keyAt || 0) < 4000" in remark and remark.index("nmb.keyAt") < remark.index("prefs.setJSON(NMB_REMARK_SEEN")
    assert "flashEntry(source)" in remark and "event.stopPropagation()" in remark
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    assert re.search(r"\.nm-say\.nm-say-source \{\s*pointer-events: auto;", css)
    boot = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    assert "remark: { cool: 3 * 60 * 60 * 1000" in boot


def test_b24_a_typed_sentence_shows_the_act_it_would_do_and_writes_nothing(client, session):
    """B24: "remind me Tuesday 9am lecture" previews its card in the palette; the route runs nothing."""
    from tessellate.core.database import Reminder

    got = client.get("/read/act", params={"q": "remind me Tuesday 9am lecture"}).json()["act"]
    assert got["intent"] == "reminder" and "ecture" in (got["label"] or got["line"]) and got["steps"] >= 1
    assert session.query(Reminder).count() == 0
    assert client.get("/read/act", params={"q": "what is the weather like"}).json() == {"act": None}
    #: No time given: Chat asks once, so the palette shows no card for it.
    assert client.get("/read/act", params={"q": "remind me to ring the plumber"}).json() == {"act": None}


def test_b24_the_palette_asks_for_three_words_and_sends_the_sentence_to_chat():
    palette = (ROOT / "frontend" / "js" / "app-palette.js").read_text(encoding="utf-8")
    body = palette[palette.index("function paletteTypedActRows") : palette.index("async function paletteStartAct")]
    assert "/read/act?q=" in body and "split(/\\s+/).length < 3" in body and "}, 250)" in body
    assert "sendChatMessage(text)" in body and "...paletteTypedActRows(lowered)" in palette
