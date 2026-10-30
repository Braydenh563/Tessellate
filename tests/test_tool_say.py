"""Every agent tool's result said in words, a structure and links, with no
model (`ai/tool_say.py`; the owner, 2026-10-11: "make sure needle tool calls
are properly outputted in human readable ways and well structured and
written ways by the composer when the ai isnt available").

The gold is `fixtures/composer/tool_results_1011.json`: each of the
registry's tools run once on a seeded notebook, plus results in the tools'
own shapes for what this sandbox cannot produce (marked `fake`: no model,
no upload, no network). Each is said through `tool_say.say`, and a failure
of each tool is said too. needle itself runs through the fake transport
here (the real engine is not installed in this sandbox); the route test at
the end drives a whole turn with one of the owner's own typed requests."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tessellate.ai import tool_say, tools

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "tests" / "fixtures" / "composer" / "tool_results_1011.json").read_text(encoding="utf-8"))["tools"]
CASES = [(name, n, case) for name, cases in sorted(GOLD.items()) for n, case in enumerate(cases)]
#: Ids of the things a result names: a note, a document, a board, a chat.
_ITEM_KEYS = ("id", "note_id", "document_id", "board_id", "card_id")
_LINK = re.compile(r"\]\((#/[a-z/0-9-]+|https?://[^)\s]+)\)")


def _prose(text: str) -> str:
    """The words a person reads: link targets and quotes taken out."""
    text = re.sub(r"\]\([^)]*\)", "]", text)
    return "\n".join(line for line in text.splitlines() if not line.startswith(">"))


def _names_an_item(result: dict) -> bool:
    def walk(value) -> bool:  # noqa: ANN001
        if isinstance(value, dict):
            return any(isinstance(value.get(k), int) and not isinstance(value.get(k), bool) for k in _ITEM_KEYS) or any(walk(v) for v in value.values())
        if isinstance(value, list):
            return any(walk(v) for v in value)
        return False

    return walk(result) or any(isinstance(result.get(k), list) and result.get(k) for k in ("results", "files", "conversations"))


def _house_style(text: str, where: str) -> None:
    prose = _prose(text)
    assert text.strip(), where
    assert not re.search(r"[{}]", prose), (where, text)
    assert not re.search(r'"\w+"\s*:', prose), (where, text)
    assert not re.search(r"\b[a-z]+_[a-z_]+\b", prose), (where, text)
    assert not re.search(r"\bph:[\w-]+", text), (where, text)
    assert chr(0x2014) not in text and "!" not in prose, (where, text)
    first = re.sub(r"^\[", "", text.strip())
    assert first[:1].isupper() or first[:1].isdigit(), (where, text)
    for name in tools.TOOLS:
        assert name not in prose, (where, name)


def test_every_tool_in_the_registry_has_a_result_in_the_gold():
    assert set(GOLD) == set(tools.TOOLS), set(tools.TOOLS) ^ set(GOLD)
    assert set(tool_say.SAYERS) == set(tools.TOOLS)


@pytest.mark.parametrize(("name", "n", "case"), CASES, ids=[f"{name}-{n}" for name, n, _ in CASES])
def test_each_result_is_said_in_words_a_shape_and_links(name, n, case):
    said = tool_say.say(name, case["result"], case["args"])
    text = said["text"]
    _house_style(text, name)
    if _names_an_item(case["result"]) and "error" not in case["result"]:
        assert _LINK.search(text), (name, text)
    assert said["links"] == _LINK.findall(text)


@pytest.mark.parametrize("name", sorted(tools.TOOLS))
def test_a_failure_is_a_plain_sentence_with_the_next_step(name):
    for error in (
        f"{name}: No note with id 4242",
        f"{name}: note_id must be a whole number, like 12",
        f"{name}: {{'board_id': 3}} is not a board",
        f"The '{name}' tool is turned off in Settings, Tools it can use",
    ):
        text = tool_say.say(name, {"error": error}, {})["text"]
        _house_style(text, f"{name}: {error}")
        assert len([p for p in text.split("\n\n") if p.strip()]) >= 2, (name, error, text)


def test_the_shapes_are_the_ones_promised():
    """A list is a list, counts are a table, the next step is a link."""
    by = {name: tool_say.say(name, GOLD[name][0]["result"], GOLD[name][0]["args"])["text"] for name in GOLD}
    assert by["search_notes"].startswith("I found two notes about “harbor launch”.")
    assert "\n- [Harbor launch moved" in by["search_notes"] and "](#/notes/5)" in by["search_notes"]
    assert "| Tag | Notes |" in by["list_tags"] and "| #harbor | 2 |" in by["list_tags"]
    assert "| Reminder | When |" in by["list_reminders"]
    assert by["create_note"].endswith("[Open it](#/notes/7)")
    assert by["set_reminder"].startswith("I'll remind you to call the dentist on ")
    assert "[Show all notes](#/notes)" in by["list_notes"]
    assert by["get_note"].count("](#/notes/1)") == 1 and "> Dentist check-up" in by["get_note"]
    missing = tool_say.say("get_note", {"error": "get_note: No note with id 99999"}, {"note_id": 99999})["text"]
    assert missing.startswith("I could not find note 99999.") and "[Open Notes](#/notes)" in missing


def test_needle_says_the_tools_results_through_it(app_state):
    """`needle_provider._said_by_tools`: each tool message said by
    `tool_say`, with the arguments its call was made with."""
    from tessellate.ai import needle_provider

    case = GOLD["search_notes"][0]
    messages = [
        {"role": "user", "content": "wat notes do i hav abt the harbor launch"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "search_notes", "arguments": case["args"]}}]},
        {"role": "tool", "tool_name": "search_notes", "content": json.dumps(case["result"])},
    ]
    said = needle_provider._said_by_tools(messages)
    assert said == tool_say.say("search_notes", case["result"], case["args"])["text"]
    assert "](#/notes/5)" in said


def test_a_scoped_count_is_not_said_as_no_notes():
    """Found writing this: `realise` read only `total`, so "how many notes
    are tagged harbor" with needle answered "You have no notes."."""
    from datetime import date

    from tessellate.ai import realise

    result = GOLD["count_notes"][0]["result"]
    assert realise.tool_answer("count_notes", result, date(2026, 10, 11))["text"] == "You have two notes."


#: The families of the registry and the shape each promises (the owner,
#: 2026-10-11: "a lead sentence, then a list or table with counts and a link
#: per item"). Every tool is in one family; each family is checked below.
FAMILIES = {
    "find": {"search_notes", "list_notes", "find_similar_notes", "related_notes", "search_whiteboard", "search_files", "search_chat_history", "web_search", "path_between"},
    "counts": {"count_notes", "list_tags", "list_categories", "list_documents", "list_skills", "list_reminders", "list_library", "notebook_overview", "notebook_structure", "summarize_notes"},
    "read": {"get_note", "get_document", "read_file", "read_url", "read_text", "read_whiteboard", "read_mindmap", "search_help", "get_current_time", "calculate", "check_answer", "find_contradictions"},
    "notes": {"create_note", "edit_note", "delete_note", "restore_note", "pin_note", "tag_note", "link_notes", "unlink_notes", "audit_link_reasons", "move_notes"},
    "filing": {"create_category", "rename_category", "delete_category", "merge_categories", "rename_tag", "delete_tag"},
    "documents": {"create_document", "delete_document"},
    "boards": {"add_board_shape", "add_whiteboard_card", "add_whiteboard_link", "delete_board_item", "edit_board_item", "move_board_item", "restore_board_item", "place_library_item", "generate_diagram", "create_mindmap", "map_from_note", "add_map_node", "link_map_nodes"},
    "reminders": {"set_reminder", "complete_reminder"},
    "skills": {"save_skill", "delete_skill", "run_skill", "save_user_preference"},
    "turn": {"ask_user", "make_plan", "propose_act", "compress_chat"},
}
_COUNT_WORD = re.compile(r"\b(\d+|no|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|every|nothing)\b", re.I)


def _items(result: dict) -> list[int]:
    """The ids of a result's own list of two or more things, if it has one."""
    for value in result.values():
        if isinstance(value, list) and len(value) >= 2 and all(isinstance(x, dict) for x in value):
            ids = [x.get(k) for x in value for k in ("id", "note_id", "document_id", "board_id") if isinstance(x.get(k), int)]
            if ids:
                return list(dict.fromkeys(ids))
    return []


def test_every_tool_is_in_one_family():
    named = [t for tools_of in FAMILIES.values() for t in tools_of]
    assert sorted(named) == sorted(tools.TOOLS), set(named) ^ set(tools.TOOLS)


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_each_family_leads_with_a_sentence_then_its_shape(family):
    for name in sorted(FAMILIES[family]):
        for case in GOLD[name]:
            if "error" in case["result"]:
                continue
            text = tool_say.say(name, case["result"], case["args"])["text"]
            lead = text.split("\n\n")[0].splitlines()[0].strip()
            assert re.search(r"[.:?]$", lead), (name, lead)
            ids = _items(case["result"])
            if ids:
                #: Two or more things: a list or a table, a count in the lead
                #: and a link to each one shown (eight at most).
                assert re.search(r"^(- |\| |\d+\. )", text, re.M), (name, text)
                assert _COUNT_WORD.search(lead), (name, lead)
                linked = [i for i in ids if re.search(rf"\]\(#/[a-z/]+/{i}\)", text)]
                assert len(linked) >= min(len(ids), 8), (name, ids, text)
            if family == "counts":
                assert _COUNT_WORD.search(lead), (name, lead)
            if family in ("notes", "filing", "documents", "boards", "reminders", "skills"):
                #: An act says what changed and where to see it.
                assert _LINK.search(text), (name, text)


def test_two_calls_in_one_turn_are_two_answers_each_with_its_lead(app_state):
    """needle often calls twice (find, then act): each result is said in
    its own paragraph block, never one run-on or a JSON list."""
    from tessellate.ai import needle_provider

    find, made = GOLD["search_notes"][0], GOLD["create_note"][0]
    messages = [
        {"role": "user", "content": "find harbor notes and make a note to buy oat milk"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "search_notes", "arguments": find["args"]}},
            {"function": {"name": "create_note", "arguments": made["args"]}},
        ]},
        {"role": "tool", "tool_name": "search_notes", "content": json.dumps(find["result"])},
        {"role": "tool", "tool_name": "create_note", "content": json.dumps(made["result"])},
    ]
    said = needle_provider._said_by_tools(messages)
    assert said.startswith("I found two notes about “harbor launch”.")
    assert "\n\nSaved a new note in Shopping" in said and said.endswith("[Open it](#/notes/7)")
    _house_style(said, "two calls")
