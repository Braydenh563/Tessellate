"""The Guide finds the right help topic for the way people actually ask.

INBOX 406, the owner: "improve the answers and accuracy of responses when no
ai model is available". With no model the Guide answers from `HELP_TOPICS`
alone, so which topic a question reaches *is* the answer. Measured on
`fixtures/help_questions.json` (122 questions with typos, synonyms and plain
phrasing): the keyword-count rule it replaced reached the right topic first
for 49% and nothing at all for 20%; the ranked rule reaches it first for 99%
and within the top three for all of them. INBOX 410 added 55 questions about
each surface's keys, controls and hidden features (177 in all): 99.4% first,
100% within three. The bar below is lower than the
number so a new topic can shift one question without a false alarm, and high
enough that a regression in the rule cannot hide.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tessellate.ai import help_chat

BANK = json.loads((Path(__file__).parent / "fixtures" / "help_questions.json").read_text())


def _ranked(question: str) -> list[str]:
    return [topic["id"] for topic in help_chat._matching_topics(question)]


def test_every_expected_topic_exists():
    ids = {topic["id"] for topic in help_chat.HELP_TOPICS}
    assert not [expected for _, expected in BANK if expected not in ids]


def test_the_right_topic_comes_first_for_nearly_every_question():
    wrong = [(q, e, _ranked(q)) for q, e in BANK if _ranked(q)[:1] != [e]]
    assert len(wrong) <= len(BANK) * 0.05, wrong


def test_the_right_topic_is_always_in_the_top_three():
    missing = [(q, e, _ranked(q)) for q, e in BANK if e not in _ranked(q)]
    assert not missing, missing


def test_a_typo_still_finds_its_topic():
    assert _ranked("hwo do i set a remnder")[:1] == ["reminders"]
    assert _ranked("how do I chnage the theme")[:1] == ["appearance"]


def test_the_offline_answer_leads_with_one_topic_and_names_the_rest():
    reply = help_chat.offline_answer("how do I scan a document")
    #: The layout is the answer's "From the help" view since INBOX 787.
    body = reply["system"]["content"]
    first = help_chat._matching_topics("how do I scan a document")[0]
    # Laid out (INBOX 430): the entry's title as a heading, then its text.
    assert body.startswith(f"### {help_chat.topic_title(first)}")
    assert first["body"][:60] in body


#: **The questions the Guide could not answer before round 7** (INBOX 430:
#: "expand the help content massively, covering every tab, setting and
#: feature"). Twenty-two questions about the companion, Atlas's look, the
#: faces and the Settings sections that had no entry: before the expansion
#: none of them had an entry about its subject to reach (the companion was
#: answered as "a feature within the Ask tab"). Now every one reaches its
#: entry first.
R7 = json.loads((Path(__file__).parent / "fixtures" / "help_questions_r7.json").read_text())


def test_the_new_entries_answer_the_questions_they_were_written_for():
    assert len(R7) >= 20
    wrong = [(q, e, _ranked(q)) for q, e in R7 if _ranked(q)[:1] != [e]]
    assert not wrong, wrong


def test_every_settings_section_has_an_entry_that_opens_it():
    # Each section in the Settings list is the badge (the link) of at least
    # one entry, so a question about any of them can end in a button that
    # opens it.
    html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text()
    nav = html[html.index('id="settings-search"') : html.index('<div class="modal-content"')]
    sections = set(re.findall(r'data-section="([a-z-]+)"', nav))
    opened = {topic["badge"].get("section") for topic in help_chat.HELP_TOPICS}
    assert sections and not sections - opened, sections - opened


def test_the_system_answer_is_laid_out_with_its_path_steps_and_link():
    topics = help_chat.topics_for("the companion went off screen, how do I call it back")
    system = help_chat.system_answer(topics)
    text = system["content"]
    assert text.startswith("### The corner companion")
    assert "**Where:** Settings, Appearance, Atlas and faces, Corner companion" in text
    assert "\n1. Open Settings, Appearance" in text
    assert system["open"] == {"label": "Corner companion", "section": "appearance", "target": "avatar-buddy-row"}
    # Never "a feature within the Ask tab": the companion lives on the page. Since 1673 it keeps a
    # place of its own (a page and a spot), so the body says that instead of "not in any tab".
    assert "Ask tab" not in topics[0]["body"] and "a place of its own" in topics[0]["body"]
