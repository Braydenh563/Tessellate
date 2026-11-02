"""Audit 1030 A15: one table of phrasings per act, each read through the typed reader.

A row is (sentence, intent, the arguments that must come out). A sentence that
must stay a question or a statement is in `NOT_ACTS`. Leads and tails are in
`test_audit_1030_ai_acts.py`; this file is about the verb forms."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import commands

NOW = datetime(2026, 10, 30, 10, 0)

TABLE = [
    # tag
    ("put the tag recipes on my sourdough notes", "tag", {"tags": ["recipes"]}),
    ("mark the passport note with #travel", "tag", {"tags": ["travel"]}),
    # untag
    ("untag the budget note finance", "untag", {"tags": ["finance"]}),
    ("take the urgent tag off this note", "untag", {"tags": ["urgent"], "these": True}),
    ("delete the tag recipes from the sourdough note", "untag", {"tags": ["recipes"]}),
    ("strip the tag money from the expenses note", "untag", {"tags": ["money"]}),
    ("remove the tag travel from the lisbon trip note", "untag", {"tags": ["travel"]}),
    # move
    ("shift the tokyo trip note to travel", "move", {"category": "travel"}),
    ("categorise the expenses note as finance", "move", {"category": "finance"}),
    ("change the category of the budget note to finance", "move", {"category": "finance"}),
    # pin
    ("keep the passport note pinned", "pin", {"about": "passport"}),
    ("put the budget note at the top", "pin", {"about": "budget"}),
    ("move the budget note to the top", "pin", {"about": "budget"}),
    # link
    ("link the lisbon trip note to the packing list", "link", {"about": "lisbon trip", "other": "packing list"}),
    ("relate the tokyo trip note to the lisbon trip note", "link", {"other": "lisbon trip"}),
    ("link project atlas with priya", "link", {"about": "project atlas", "other": "priya"}),
    ("join the todo note and the packing list", "link", {"other": "packing list"}),
    # rename
    ("call the budget note household budget", "rename", {"title": "household budget"}),
    ("title this note meeting notes", "rename", {"title": "meeting notes", "these": True}),
    # append
    ("put sunscreen on the lisbon packing list", "append", {"content": "Sunscreen"}),
    ("stick eggs on my shopping list", "append", {"content": "Eggs"}),
    ("add a line to the budget note saying rent went up to 1300", "append", {"content": "Rent went up to 1300"}),
    ("add to my gym log: ran 5k today", "append", {"content": "Ran 5k today"}),
    ("append to the todo note: call the bank", "append", {"content": "Call the bank"}),
    ("add a bullet to the lisbon trip note: book the tram", "append", {"content": "Book the tram"}),
    ("update the budget note with rent 1300", "append", {"content": "Rent 1300"}),
    ("tack a line on to my mood diary: felt great", "append", {"content": "Felt great"}),
    ("write down that the hotel is booked at the end of the lisbon trip note", "append", {"about": "lisbon trip"}),
    # new note
    ("start a new note about the kitchen renovation", "new_note", {"content": "The kitchen renovation"}),
    ("remember that sara's birthday is 3 december", "new_note", {"content": "Sara's birthday is 3 december"}),
    ("capture this: idea for a podcast", "new_note", {"content": "Idea for a podcast"}),
    # summarise
    ("tl;dr the project atlas note", "summarise", {"about": "project atlas"}),
    ("recap my mood diary", "summarise", {"about": "mood diary"}),
    ("short summary of my gym log", "summarise", {"about": "gym log"}),
    ("what is the gist of my reading list", "summarise", {"about": "reading list"}),
    ("can you summarise everything i wrote about money", "summarise", {"about": "money"}),
    # navigate
    ("show me the reminders tab", "navigate", {"surface": "reminders"}),
    ("show the graph view", "navigate", {"surface": "graph"}),
    ("open the calendar", "navigate", {"surface": "timeline"}),
    # meeting
    ("start recording a meeting called planning", "meeting", {"title": "Planning"}),
    ("take meeting notes", "meeting", {}),
]

#: Said the same way, but not an act: a question, a preference or a topic outside the notes.
NOT_ACTS = [
    "remember that i prefer short answers",
    "summarise the french revolution",
    "put this note in projects?",
    "mark the passport note with a smile",
    "what is the best way to put eggs on a list",
    "name the categories that are nearly empty and any that hold so much they are not really sorting anything",
    "add to today's note: call the bank",
]


@pytest.mark.parametrize(("text", "intent", "args"), TABLE)
def test_each_phrasing_reads_as_its_act(text, intent, args):
    found = commands.read_typed(text, NOW)
    assert found is not None and found["intent"] == intent, (text, found)
    for key, want in args.items():
        assert found.get(key) == want, (text, key, found)


@pytest.mark.parametrize("text", NOT_ACTS)
def test_what_is_not_an_act_stays_unread(text):
    found = commands.read_typed(text, NOW)
    assert found is None, (text, found)
