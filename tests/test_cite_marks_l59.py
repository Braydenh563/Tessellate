"""L-chat-59: the brief's chosen sentences carry `[Sn]` ids, the model writes
one back after a sentence that used it, and the turn's grounding names that
note; the person never sees an id."""

from __future__ import annotations

import json

from tessellate.ai import cite_marks, composer, librarian
from tessellate.entry import manager

BOILER = {
    "id": 41,
    "content": (
        "# Boiler\n\nThe boiler service is due on 12 November. The engineer is Sam from Hearth & Co. "
        "We moved into the flat in spring and the hallway still needs painting. The neighbours "
        "have a cat that sits on our windowsill. The parking permit costs more than it did "
        "and the bins are collected by the council."
    ),
}
RADIATOR = {
    "id": 42,
    "content": (
        "# Radiators\n\nThe boiler service should include bleeding the radiators. The spare room "
        "radiator rattles when the heating starts. Paint for the hallway is in the shed. The council "
        "tip opens at nine on Saturdays and the recycling goes out on Thursdays."
    ),
}
MARKS = {"S1": {"note_id": 41, "start": 0, "end": 10}, "S2": {"note_id": 42, "start": 0, "end": 10}}


def _scrub(deltas: list[str], marks=MARKS) -> tuple[str, cite_marks.MarkScrubber]:
    scrubber = cite_marks.MarkScrubber(marks)
    text = "".join(scrubber.feed(d) for d in deltas) + scrubber.flush()
    return text, scrubber


def test_a_mark_split_across_deltas_never_reaches_the_person():
    text, scrubber = _scrub(["The service is due on 12 November [", "S", "1]. Sam does it [S2", "]."])
    assert text == "The service is due on 12 November. Sam does it."
    assert [m for _t, m in scrubber.cites] == ["S1", "S2"]


def test_an_unknown_mark_is_taken_out_but_grounds_nothing():
    text, scrubber = _scrub(["It is due soon [S9]."])
    assert text == "It is due soon."
    assert scrubber.cites == [] and cite_marks.rows(text, scrubber) == []


def test_the_prompts_bare_mark_echoed_back_is_taken_out():
    text, scrubber = _scrub(["Sync is being rewritten. [S", "] It runs through a folder."])
    assert text == "Sync is being rewritten. It runs through a folder."
    assert scrubber.cites == []


def test_a_bracket_that_is_not_a_mark_is_kept():
    text, _ = _scrub(["Costs [about] ten [S", "pounds]."])
    assert text == "Costs [about] ten [Spounds]."


def test_a_round_bracket_mark_is_taken_only_for_an_id_the_brief_gave():
    text, scrubber = _scrub(["Read Ways of Seeing (S2). Size (S", "9) stays."])
    assert text == "Read Ways of Seeing. Size (S9) stays."
    assert [m for _t, m in scrubber.cites] == ["S2"]


def test_each_cite_names_its_answer_sentence_and_note():
    text, scrubber = _scrub(["The service is due on 12 November [S1]. ", "Bleed the radiators too [S2]."])
    assert cite_marks.rows(text, scrubber) == [
        {"sentence": "The service is due on 12 November.", "note_id": 41, "cited": "S1"},
        {"sentence": "Bleed the radiators too.", "note_id": 42, "cited": "S2"},
    ]


def test_with_no_marks_the_stream_is_untouched():
    text, scrubber = _scrub(["A [S1] stays when the brief had no ids."], marks={})
    assert text == "A [S1] stays when the brief had no ids."
    assert cite_marks.rows(text, scrubber) == []


def test_the_brief_marks_sentences_from_two_notes_and_the_prompt_asks_for_them():
    packed = composer.brief("When is the boiler service due?", [BOILER, RADIATOR])
    assert {m["note_id"] for m in packed["marks"].values()} == {41, 42}
    assert all(n.get("marked") for n in packed["notes"])
    assert "[S1] The boiler service is due on 12 November." in packed["notes"][0]["content"]
    content = librarian.build_messages("When is the boiler service due?", packed["notes"])[-1]["content"]
    assert content.count(librarian.CITE_HEADER) == 1


def test_one_note_needs_no_ids():
    packed = composer.brief("When is the boiler service due?", [BOILER])
    assert packed["marks"] == {}
    assert "[S" not in packed["notes"][0]["content"] and not packed["notes"][0].get("marked")
    content = librarian.build_messages("When is the boiler service due?", packed["notes"])[-1]["content"]
    assert librarian.CITE_HEADER not in content


def test_through_the_route_a_cited_sentence_is_grounded_and_the_id_is_gone(ai_client, fake_ollama, session):
    manager.create_entry(session, BOILER["content"])
    manager.create_entry(session, RADIATOR["content"])
    session.commit()
    fake_ollama.librarian_reply = "Bleed the radiators when the boiler is serviced [S2]."
    body = {"question": "What do my notes say about the boiler service?", "use_tools": False}
    with ai_client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    sent = fake_ollama.chat_calls[-1][-1]["content"]
    assert librarian.CITE_HEADER in sent and "[S2]" in sent
    answer = "".join(e["delta"] for e in events if e["type"] == "answer")
    assert "[S" not in answer
    rows = next(e for e in events if e["type"] == "grounding")["sentences"]
    cited = [r for r in rows if r.get("cited")]
    assert cited and cited[0]["sentence"] == "Bleed the radiators when the boiler is serviced."
