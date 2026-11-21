"""Citations survive a heading followed by a list, live and reopened
(coordinator report: an Ask answer reopened from history was missing
in-text markers for two bullets under a "## Schedule and Frequency"
heading, though the Sources panel listed the note and earlier sections
kept their own markers).

**Reproduction attempted, not found.** Driven through the real pipeline
(fake_ollama's answer stream through `/chat/stream`, the real
`ground_answer_sentences`, a real saved `AskTurn`, a real
`GET /ask-history/{id}`) with a heading immediately followed by a two-item
list, one note grounding a paragraph earlier and a different sentence in
the list (the "same note cited twice, non-adjacently" shape), and bold
markdown ending a list item right before its period: the live SSE
`grounding` event and the reopened turn's `grounding` were identical in
every variation tried, and `addInlineCitations` (capture-ask.js, run
directly against the rendered markdown in a real DOM, `scratchpad/`
`ui-sweeps/citationheading.js`) placed every marker correctly in each case.

This holds what was verified as a regression test, on the theory that
"list items after a heading" was simply undertested before, not that a
fix landed here: if either the live/reopened grounding equality or the
frontend's own marker placement for this shape ever regresses, this is
what catches it. The report's own root cause is LEDGER L-chat-11; the most
likely next step is the actual saved turn's stored `grounding`/
`raw_result_ids` from the owner's own notebook, which nothing here has
access to.
"""

from __future__ import annotations

import json

from tessellate.entry import manager

HEADING_AND_LIST_ANSWER = (
    "## Overview\n"
    "The overview mentions a key fact from note two.\n\n"
    "## Details\n"
    "A second section names a detail from note five, cited here first.\n\n"
    "## Schedule and Frequency\n"
    "- Your university days this week are noted as **Tuesday and Thursday**.\n"
    "- You have attended multiple lectures for your cloud computing class, "
    "including three lectures last week.\n"
)


def _ask(client, question, **body):
    events = []
    with client.stream(
        "POST", "/chat/stream", json={"question": question, "notes_only": True, **body}
    ) as r:
        for line in r.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events


def test_live_and_reopened_grounding_agree_for_a_heading_then_list(ai_client, fake_ollama, session):
    """The same shape the report describes: two sections that ground
    normally (giving the "earlier markers [2] and [5]" the report saw),
    then a heading immediately followed by a two-item list, one note
    (note 1) grounding a bullet, a second note (the same one already cited
    once earlier, non-adjacently) grounding the other bullet."""
    manager.create_entry(session, "my uni days this week are tuesday and thursday")
    manager.create_entry(session, "gym schedule: monday wednesday friday mornings")
    manager.create_entry(session, "cloud computing lecture notes: covered docker and kubernetes")
    manager.create_entry(session, "I attended three cloud computing lectures last week, all recorded")
    manager.create_entry(session, "car service booked for next tuesday afternoon")
    session.commit()

    fake_ollama.librarian_reply = HEADING_AND_LIST_ANSWER
    events = _ask(
        ai_client,
        "what are my uni days and how many cloud computing lectures have I been to",
    )
    live_grounding = next(e["sentences"] for e in events if e.get("type") == "grounding")
    #: The two list-item sentences from the report's own shape are grounded
    #: live, not dropped: this is the assertion that would have caught the
    #: report if the cause were server-side.
    live_texts = {row["sentence"] for row in live_grounding}
    #: The raw markdown, `**` and all: grounding matches the answer as the
    #: model wrote it, not the plain text a renderer would show.
    assert any("university days" in t and "Tuesday" in t for t in live_texts)
    assert any("cloud computing class" in t for t in live_texts)

    turn_id = ai_client.get("/ask-history").json()["turns"][0]["id"]
    reopened = ai_client.get(f"/ask-history/{turn_id}").json()

    #: The exact comparison the coordinator asked for: live vs reopened.
    assert reopened["grounding"] == live_grounding
