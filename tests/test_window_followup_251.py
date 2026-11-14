"""L-chat-251: "what about last month" after "what did I write about running" is the question asked
for that month, so a month with no running note says none, like the question typed in full."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd


@pytest.mark.parametrize("notes_only", [True, False], ids=["ask", "chat"])
def test_a_window_follow_up_with_no_note_in_the_window_says_none(client, session, monkeypatch, notes_only):
    sd.seed(session)
    sd.fix_clock(monkeypatch)
    first = sd.ask(client, "what did I write about running", notes_only=notes_only)["text"]
    history = [{"question": "what did I write about running", "answer": first}]
    then = sd.ask(client, "what about last month", history=history, notes_only=notes_only)["text"]
    alone = sd.ask(client, "what did I write about running last month", notes_only=notes_only)["text"]
    assert "5 September" not in then, then
    #: The same reader answered both: the latest running note is named, as when the question is typed in full.
    assert "Sun 8 Nov" in then and "Sun 8 Nov" in alone, (then, alone)
