"""Open questions are the person's own (INBOX 745 (b)).

The owner, of the Questions list (11 open): "these are just random questions
form my notes?? I didnt actually have any questions for myself, they are
unrelated and mostly from test notes". The ones quoted were a play's line,
conversation-starter prompts in quotes, a quote fragment, and joke setups
answered on the next line. Every sentence ending in "?" was a question.
"""

from __future__ import annotations

import json

from tessellate.ai import facts
from tessellate.core.database import DerivedFact, Entry, utcnow

NOT_OWN = {
    "script": "ACT I\nSCENE 2. A street at night.\nKNIGHT: What daring deed hath led thee to this street?\nSQUIRE: A dragon, sire.",
    "prompts": 'Conversation starters:\n- "If you were a spice, which one would you be and why?"\n- "What is the most adventurous thing you have done?"',
    "fragment": '" or "What\'s the most adventurous thing you have ever done so far?',
    "jokes": "Jokes for Sam\nWhat's an astronaut's favorite drink?\nGravi-tea.\nWhy did the student eat his homework?\nBecause the teacher said it was a piece of cake.",
    "example": 'Ask it things, for example "how do I sort my notes by date?" and it answers.',
    "guide": "# Getting started\n## Your first note\nHave you ever wondered where your ideas go?\n- Press New\n- Type\n- Save\n## Asking\nWhat would you like to find today?",
}

OWN = {
    "plain": "Plans for the shed. When does the timber arrive this month? Who is fixing the roof on the shed?",
    "bold": "**Should I renew the lease before June?** The landlord wants an answer soon.",
    "list": "To sort out:\n- Should I call the bank about the fee?\n- Book the dentist",
}


def _questions(text: str) -> list[str]:
    return [c.text for c in facts.candidates(text) if c.kind == "question"]


def test_not_the_persons_own_questions_are_not_candidates():
    for name, text in NOT_OWN.items():
        assert _questions(text) == [], name


def test_the_persons_own_questions_still_are():
    assert len(_questions(OWN["plain"])) == 2
    assert _questions(OWN["bold"]) == ["**Should I renew the lease before June?"]
    assert _questions(OWN["list"]) == ["- Should I call the bank about the fee?"]


def test_stored_questions_that_are_not_own_are_tombstoned_and_stay_gone(client, session):
    """Rows the old rule stored leave the list at the next pass, as
    tombstones, so a later read does not bring them back."""
    entry = Entry(content=NOT_OWN["jokes"], tags=json.dumps([]))
    session.add(entry)
    session.commit()
    start = NOT_OWN["jokes"].index("What's")
    end = NOT_OWN["jokes"].index("?", start) + 1
    session.add(DerivedFact(entry_id=entry.id, kind="question", text=NOT_OWN["jokes"][start:end],
                            span_start=start, span_end=end, model="local", confidence=0.9, computed_at=utcnow()))
    session.commit()
    facts.run(session, budget=5000, force=True)
    session.commit()
    rows = session.query(DerivedFact).filter_by(entry_id=entry.id, kind="question").all()
    assert rows and all(row.deleted_at is not None for row in rows)
    assert client.get("/questions?state=open").json()["total"] == 0


def test_the_list_shows_questions_and_titles_without_markdown(client, session):
    entry = Entry(content="**Lease** notes\n" + OWN["bold"], tags=json.dumps([]))
    session.add(entry)
    session.commit()
    facts.run(session, budget=5000)
    session.commit()
    item = client.get("/questions?state=open").json()["items"][0]
    assert item["display"] == "Should I renew the lease before June?"
    assert "**" not in item["note_title"]


def test_a_note_says_how_many_open_questions_it_asks(client, session):
    """INBOX 745 (c): "notes ask questions but there is no way to view the
    questions asked by notes if they have any from the notes themselves". The
    card reads `/questions/counts` (open questions per note, the reminders'
    shape) and opens the list filtered to that note (`entry_id`)."""
    asks = Entry(content=OWN["plain"], tags=json.dumps([]))
    quiet = Entry(content="Nothing to ask here, only a plain sentence or two.", tags=json.dumps([]))
    session.add_all([asks, quiet])
    session.commit()
    facts.run(session, budget=5000)
    session.commit()
    counts = client.get("/questions/counts", params={"ids": f"{asks.id},{quiet.id}"}).json()["counts"]
    assert counts == {str(asks.id): 2}
    only = client.get("/questions", params={"state": "open", "entry_id": asks.id}).json()
    assert only["total"] == 2 and {item["entry_id"] for item in only["items"]} == {asks.id}
    assert client.get("/questions", params={"state": "open", "entry_id": quiet.id}).json()["total"] == 0


ICE_BREAKERS = (
    "Before diving into deeper conversation, use light-hearted ice breakers like "
    '"If you were a spice, which one would you be and why?" or '
    '"What\'s the most adventurous thing you\'ve ever done?"'
)


def test_a_quoted_prompt_pair_gives_no_fragment_and_no_question():
    """INBOX 785: the owner's note, two quoted prompts in one sentence. The
    splitter cuts it at each `?`, leaving a piece that opens on `" or "`; the
    prompts are quoted, so neither is the person's own question (745 (b)), and
    no piece of the sentence is kept as one."""
    assert _questions(ICE_BREAKERS) == []
    assert _questions("Ice breakers\n\n" + ICE_BREAKERS + "\n\nShould I renew the lease before June?") == [
        "Should I renew the lease before June?"
    ]


def _store_old_fragments(session, content: str) -> int:
    """The rows the splitter used to store for `content`: every sentence ending
    in a question mark, quoted or not, as the old rule did."""
    entry = Entry(content=content, tags=json.dumps([]))
    session.add(entry)
    session.commit()
    for text, start, end in facts.sentences(content):
        if text.endswith("?"):
            session.add(DerivedFact(entry_id=entry.id, kind="question", text=text, span_start=start, span_end=end,
                                    model="local", confidence=0.9, computed_at=utcnow()))
    session.commit()
    return entry.id


def test_stored_fragments_do_not_reach_the_list_before_a_pass_runs(client, session):
    """The rows were stored on 2026-10-07 and the night pass that tombstones
    them (`_retire_not_own_questions`) runs only with background tasks on, so
    the owner still saw `" or "What's the most ...` hours after the rule was
    fixed (INBOX 785). Reading the list retires them."""
    entry_id = _store_old_fragments(session, ICE_BREAKERS + "\n\nShould I renew the lease before June?")
    assert session.query(DerivedFact).filter_by(entry_id=entry_id, kind="question", deleted_at=None).count() == 3
    body = client.get("/questions?state=open").json()
    assert [item["display"] for item in body["items"]] == ["Should I renew the lease before June?"]
    assert body["counts"]["open"] == 1
    assert not any(item["text"].lstrip().startswith(('"', "”")) for item in body["items"])
    session.expire_all()
    assert session.query(DerivedFact).filter_by(entry_id=entry_id, kind="question", deleted_at=None).count() == 1


def test_a_note_card_does_not_count_the_retired_fragments(client, session):
    entry_id = _store_old_fragments(session, ICE_BREAKERS)
    assert client.get("/questions/counts", params={"ids": str(entry_id)}).json()["counts"] == {}


# --- review finding 3: "pasted" needs the address beside the question ---------------

#: A note that holds a URL and a question with "you" in it is not a paste.
OWN_WITH_URL = {
    "inline": "Grant details at https://example.org/grants then link below.\n\nCan you check with Sam whether the grant covers travel?",
    "other_paragraph": "See https://example.org/grants for the rules.\n\nCan you check with Sam whether the grant covers travel?",
    "other_line_break": "Grant call notes https://example.org/grants\n\nDo you think the grant covers travel?",
    "far": "https://example.org/a\n\nSome unrelated text about the shed roof.\n\nCan you check with Sam whether the grant covers travel?",
}
#: Pasted: the address on its own line or paragraph beside the question, or a quote.
PASTED = {
    "own_line": "Page I copied:\nhttps://example.org/quiz\nHave you ever wondered where your ideas go?",
    "paragraph_before": "https://example.org/quiz\n\nWhat would you like to find today?",
    "paragraph_after": "What would you like to find today?\n\n<https://example.org/quiz>",
    "link_only": "[Quiz](https://example.org/quiz)\n\nWhat would you like to find today?",
    "quote_block": "> Have you ever wondered where your ideas go?\n> More below.",
}


def _kept(text: str) -> bool:
    start = text.index("?") + 1
    sentence_start = max(text.rfind(". ", 0, start), text.rfind("\n", 0, start)) + 1
    return facts.kept_question(text, sentence_start, start)


def test_a_url_in_the_note_does_not_make_the_persons_question_pasted():
    for name, text in OWN_WITH_URL.items():
        assert _questions(text), name
        assert _kept(text), name


def test_a_question_beside_a_pasted_address_or_in_a_quote_is_not_the_persons():
    for name, text in PASTED.items():
        assert _questions(text) == [], name


def test_a_stored_row_a_model_decided_on_is_not_retired_by_the_rule(client, session):
    text = "> Have you ever wondered where your ideas go?\n> More below."
    entry = Entry(content=text, tags=json.dumps([]))
    session.add(entry)
    session.commit()
    end = text.index("?") + 1
    for who in ("local", "qwen3:8b"):
        session.add(DerivedFact(entry_id=entry.id, kind="question", text=text[2:end], span_start=2, span_end=end,
                                model=who, confidence=0.9, computed_at=utcnow()))
    session.commit()
    assert facts._retire_not_own_questions(session) == 1
    session.expire_all()
    left = session.query(DerivedFact).filter_by(entry_id=entry.id, deleted_at=None).all()
    assert [row.model for row in left] == ["qwen3:8b"]
