"""The app does the note's AI actions itself when no model runs, and says so
(O7; INBOX 904 B33: "Can the composer do these ai actions well and just as
good?? And they arent ai actions if the composer does them when the ai isnt
available"; BACKLOG "The composer does Improve writing and Generate
title"). Measured 2026-10-17 on :8785 with no model: Generate title and
Improve answered 503 "The AI isn't available right now", and the Improve
button was disabled."""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.ai import proofread
from tessellate.entry import manager

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("typed", "read"),
    [
        ("teh meeting is on tuesday. we shoud prepare the slides wich are due tommorow",
         "The meeting is on Tuesday. We should prepare the slides which are due tomorrow"),
        ("I definately recieve the parcel becuase of Tom", "I definitely receive the parcel because of Tom"),
        ("i went to the shops.  then i saw Sarah,she was happy", "I went to the shops. Then I saw Sarah, she was happy"),
        ("they woudl like it", "They would like it"),
    ],
)
def test_proofreading_puts_spelling_and_capitals_right(typed, read):
    assert proofread.proofread(typed)[0] == read


@pytest.mark.parametrize(
    "kept",
    ["Perfectly fine sentence here.", "Check https://exmaple.com and #tagg it", "I want to shout at him", "Cristopher called", "u r gr8 lol"],
)
def test_proofreading_never_rewords_or_touches_links_names_and_style(kept):
    assert proofread.proofread(kept)[0] == kept[:1].upper() + kept[1:]


def test_improve_proofreads_with_no_model_and_says_who_did_it(client):
    body = client.post("/entries/improve", json={"text": "we shoud go on tuesday", "mode": "proofread"}).json()
    assert body["improved"] == "We should go on Tuesday" and body["by"] == "composer"
    assert body["said"].startswith("Atlas's assistant put right 1 spelling") and "no model" in body["said"], body["said"]
    refused = client.post("/entries/improve", json={"text": "we shoud go", "mode": "rewrite"})
    assert refused.status_code == 503 and "Proofread works without one" in refused.json()["detail"]


def test_generate_title_takes_one_from_the_notes_words_with_no_model(client, session):
    entry = manager.create_entry(session, "Remember to book the dentist before the end of October for a checkup.")
    session.commit()
    out = client.post(f"/entries/{entry.id}/generate-title")
    assert out.status_code == 200, out.text
    title = out.json()["title"]
    assert title and all(word.lower().strip(",.") in entry.content.lower() for word in title.split()), title


def test_the_menu_names_the_app_not_the_ai_when_no_model_runs():
    menus = (ROOT / "frontend" / "js" / "menus.js").read_text(encoding="utf-8")
    assert 'off ? "ph:text-aa Proofread" : "ph:sparkle Improve writing"' in menus
    assert 'off ? "ph:text-h Title from its words"' in menus
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    button = html[html.index('id="improve-btn"'):].split(">", 1)[0]
    assert "data-needs-model" not in button
    panel = (ROOT / "frontend" / "js" / "improve-panel.js").read_text(encoding="utf-8")
    assert 'body.by === "composer"' in panel
