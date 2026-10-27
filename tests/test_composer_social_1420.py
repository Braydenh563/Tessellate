"""INBOX 1420 (the owner, 2026-10-27): with no model, "what about social
connections" named untitled notes by a cut phrase ("here are some
refined"), doubled an article ("the the The Complete Social Skills
Guide"), kept a title's colon ("the Ice Breakers:"), let markdown through
("the Follow-Up**"), said a heading as a sentence ("After making an initial
connection."), clipped a diary sentence into a wrong meaning ("I had work
today and a friend") and put the citation before an emoticon ("bit9 :(")."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests import _social_1420 as social

NOW = datetime(2026, 10, 27, 12, 0)
QUESTIONS = [
    "what about social connections",
    "what have I written about social skills",
    "tell me about my conversation notes",
    "what do my notes say about friends",
]
#: The ten graded in the round's scratch file (`composer1420-grades.md`).
GRADED = [*QUESTIONS, "what about conversation starters", "summarise my social notes",
          "what did I write about my friends", "anything about ice breakers", "what do I know about dating",
          "what have I saved about talking to people"]


@pytest.fixture
def notebook(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    made = []
    for content, category, tags, when, _links in social.NOTES:
        entry = manager.create_entry(session, content, category, tags)
        entry.created_at = datetime.fromisoformat(when)
        made.append(entry)
    session.commit()
    for (_c, _cat, _t, _w, links), entry in zip(social.NOTES, made, strict=True):
        for i in links:
            manager.create_link(session, entry, made[i], reason="Both offer conversation starters")
    session.commit()
    return made


def _ask(client, question: str) -> dict:
    events: dict[str, list] = {}
    body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
    with client.stream("POST", "/chat/stream", json=body) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                events.setdefault(event["type"], []).append(event)
    events["text"] = "".join(e["delta"] for e in events.get("answer", []))
    return events


#: A citation as the chat streams it: a run of digits glued to a word.
_CITE = re.compile(r"(?<=[a-z.!?)])\d{1,2}\b")


def defects(text: str) -> list[str]:
    """Each defect class the owner's answer had, found in an answer's text."""
    #: The composer's own bold label opening a line ("**23 July:** ...") is
    #: its formatting, which the chat renders; any other mark is the note's.
    own = re.sub(r"(?m)^\*\*[^*\n]{1,40}\*\* ", "", text)
    plain = _CITE.sub("", own.replace("**", ""))
    found = []
    if re.search(r"\b(?:the|a|an) (?:the|The|A|An)\b", plain):
        found.append("doubled article")
    if "**" in own or "__" in own:
        found.append("markdown")
    if re.search(r"\w:(?=[,.;]|\s+and\b|\s+each\b|$)", plain, re.M):
        found.append("name keeps its colon")
    if re.search(r"\bhere are some refined\b(?!,)", plain, re.I):
        found.append("cut opening as a name")
    if re.search(r"\bAfter making an initial connection\.|, The Complete Social Skills Guide\.|\b[Yy]our It's\b", plain):
        found.append("heading said as a sentence")
    if re.search(r"\?[.,]|\? And\b|happened to you the week of", plain):
        found.append("question list punctuation")
    if re.search(r"work today and a friend(?! was sad)", plain):
        found.append("clipped diary sentence")
    if re.search(r"\d\s*:\(", text):
        found.append("citation before the emoticon")
    if re.search(r"\bFollow- Up\b", plain):
        found.append("broken hyphen kept")
    return found


@pytest.mark.parametrize("question", QUESTIONS)
def test_an_overview_of_the_owners_social_notes_reads_as_english(client, notebook, question):
    text = _ask(client, question)["text"]
    assert text.strip()
    assert defects(text) == [], text


@pytest.mark.parametrize("question", QUESTIONS)
def test_the_owners_search_results_are_said_as_english(question):
    """The five notes the owner's search found by meaning (the route's
    keyword search in tests finds fewer), straight into the digest."""
    from tessellate.ai import composer_digest

    text = composer_digest.answer(question, social.notes(), today=social.TODAY)["text"]
    assert defects(text) == [], text


def test_what_about_a_category_is_an_overview_of_it():
    from tessellate.ai import composer_digest

    assert composer_digest.kind_of("what about social connections") == "overview"
    text = composer_digest.answer("what about social connections", social.notes(), today=social.TODAY)["text"]
    assert "The Complete Social Skills Guide" in text and "stayed with her" in text


def test_the_link_reasons_carry_no_markdown_and_no_doubled_article():
    from tessellate.ai import composer_frame

    notes = social.notes()
    notes[2]["match_info"] = {"type": "connected", "reason": "Both offer conversation starters"}
    said = composer_frame.reasons("what about social connections", notes)
    assert said["3"] == "Linked to The Complete Social Skills Guide (Both offer conversation starters)"
    assert not any("**" in r or "the The" in r for r in said.values()), said


def test_a_bare_title_is_named_without_its_colon_or_a_second_article():
    from tessellate.ai import composer_frame

    assert composer_frame.short_name({"content": social.ICE}) == "the Ice Breakers"
    assert composer_frame.short_name({"content": social.GUIDE}) == "The Complete Social Skills Guide"
    assert composer_frame.short_name({"content": social.FOLLOW}) == "the Follow-Up Questions"


def test_an_untitled_note_is_named_by_a_whole_description_not_a_cut_phrase():
    from tessellate.ai import composer_frame

    name = composer_frame.short_name({"content": social.PICKUP})
    assert name == "your non-corny pickup and conversation starters", name
    #: A diary line is named by a whole clause, never cut mid-thought.
    assert composer_frame.short_name({"content": social.FRIEND}) == "“I had work today and a friend was sad”"


def test_the_citation_goes_after_an_emoticon_not_before_it():
    from tests._app_js import app_js_text

    app_js = app_js_text()
    #: `citationInsertionPoint` steps over ":(" as it steps over a stop.
    face = re.search(r"end \+= \(/(.+?)/\.exec\(node\.data\.slice\(end\)\)", app_js)
    assert face, "citationInsertionPoint steps over an emoticon"
    for tail in [" :(", ":)", " ;-)", " :D"]:
        assert re.match(face.group(1), tail), tail
    assert not re.match(face.group(1), " and more")


@pytest.mark.skipif(not os.environ.get("COMPOSER_1420_DUMP"), reason="grading dump, run by hand")
def test_dump_the_graded_answers(client, notebook):
    for question in GRADED:
        text = _ask(client, question)["text"]
        print(f"\n## {question}\n\n{text}\n\ndefects: {defects(text)}")


# --- second pass (the owner, 2026-10-27, after the first) -------------------


def test_a_bold_line_heading_is_a_name_and_its_marks_never_show():
    """"**Phase 1: the Opener**" was said with its marks, a cite inside the bold."""
    from tessellate.ai import composer_digest

    notes = social.notes()
    notes[0]["content"] = social.GUIDE.replace("## Phase 2: the Connection", "**Phase 1: the Opener**\nSay hello first and smile.\n\n**Phase 2: the Connection**")
    text = composer_digest.answer("what about social connections", notes, today=social.TODAY)["text"]
    assert "Phase 1" not in text and defects(text) == [], text


def test_the_also_line_joins_sentences_as_sentences():
    """"That's fascinating; What drew you to it?; you've always ...": a run of
    sentences joined by semicolons, a capital after each."""
    from tessellate.ai import composer_digest

    assert composer_digest._join(["That's fascinating", "What drew you to it?", "you've always liked it"]) == (
        "That's fascinating. What drew you to it? You've always liked it"
    )
    assert composer_digest._join(["rows", "pull-ups"]) == "rows; pull-ups"


@pytest.mark.parametrize("question", ["what have I written about uni", "tell me about my university notes"])
def test_untitled_uni_notes_are_named_by_what_they_are_about(question):
    from tessellate.ai import composer_digest

    text = composer_digest.answer(question, social.uni_notes(), today=social.TODAY)["text"]
    assert "the note on cloud computing" in text, text
    #: Never an opening cut mid-phrase, never "you noted that you had noted".
    assert "uni days this week are Tuesday," not in text and "your uni days this week are Tuesday" not in text.split("\n\n")[1], text
    assert not re.search(r"you (?:noted|wrote|said|mentioned) that you had (?:noted|jotted|written)", text), text
    assert "however" not in text
    #: The 20 July note is said with its verb: what the person wrote.
    assert re.search(r"20 July, you \w+(?: down)? that cloud computing is the delivery", text), text
    assert defects(text) == [], text


def test_what_do_i_know_about_x_leads_with_the_note_that_defines_it():
    """The owner: "it missed my main note about what cloud computing is"."""
    from tessellate.ai import composer_digest

    text = composer_digest.answer("what do I know about cloud computing", social.uni_notes(), today=social.TODAY)["text"]
    body = text.split("\n\n")
    lead = next(p for p in body if "cloud computing" in p and not p.startswith("You have"))
    assert "cloud computing is the delivery" in lead, text
    assert text.index("is the delivery") < text.index("three lectures"), text


def test_the_open_note_is_offered_only_when_the_question_is_about_it():
    """Every answer ended "You have “test draft” open. Ask me what is left on it"."""
    from tessellate.ai import composer_aware as aware

    seen = aware.build(tab="chat", open_title="test draft")
    for seed in ("a", "b", "c", "d"):
        assert "test draft" not in aware.closing(seen, seed, asked="what do I know about cloud computing")
    assert "test draft" in aware.closing(seen, "a", asked="what is left on the test draft")
    assert "test draft" in aware.closing(seen, "a", asked="summarise this")


def test_note_names_stay_linear_on_unclosed_marks_and_tabs():
    #: CodeQL alerts 1846 and 1847: a pasted line of unclosed marks or tabs.
    import time

    from tessellate.ai import composer

    started = time.perf_counter()
    composer.plain_words("__" + "**a" * 20000)
    composer._title("\t" * 20000 + "x:\nbody")
    assert time.perf_counter() - started < 1.0
    assert composer.plain_words("**Phase 1:** the __Opener__") == "Phase 1: the Opener"
