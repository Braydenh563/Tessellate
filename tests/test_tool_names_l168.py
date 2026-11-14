"""L168: how the agent's tools are named and described (OPEN O10, the named defect set).

The model picks a tool from its name and the first sentence of its description,
so the names read as verb first snake_case, the first sentence is short and no
two tools open with the same words. The names below the first rule that are not
verb first are old (saved skills and prompts carry them) and stay named here.
"""

from __future__ import annotations

import re

from tessellate.ai import tools

#: Names that open with a noun or a bare word, kept because saved skills and
#: stored plans call them. A new tool is not added here: it takes a verb.
NOT_VERB_FIRST = {
    "related_notes": "read-only lookup, named in saved skills",
    "path_between": "read-only lookup, named in saved skills",
    "notebook_structure": "read-only lookup, named in saved skills",
    "notebook_overview": "read-only lookup, named in saved skills",
    "web_search": "outbound gate and the Settings switch name it",
}

#: First sentences over 12 words, 2026-11-14 (37 of 73). A tool leaves this set
#: when its lead is cut to 12 words; nothing joins it.
LONG_LEAD = {
    "add_board_shape", "add_map_node", "add_whiteboard_link", "ask_user", "audit_link_reasons", "calculate",
    "check_answer", "check_learned", "count_notes", "create_document", "create_mindmap", "edit_board_item",
    "find_contradictions", "find_similar_notes", "get_current_time", "link_map_nodes", "list_documents",
    "list_library", "list_notes", "list_tags", "map_from_note", "merge_categories", "move_board_item",
    "notebook_overview", "notebook_structure", "path_between", "place_library_item", "propose_act",
    "read_file", "read_mindmap", "read_text", "read_whiteboard", "related_notes", "restore_board_item",
    "search_files", "search_whiteboard", "summarize_notes"
}

LEAD_WORDS = 12
SNAKE = re.compile(r"[a-z]+(?:_[a-z0-9]+)*")


def _lead(spec) -> str:
    return re.split(r"(?<=[.!?])\s", spec.description.strip())[0]


VERBS = {
    "add", "ask", "audit", "calculate", "check", "complete", "compress", "count", "create", "delete", "edit",
    "find", "generate", "get", "link", "list", "make", "map", "merge", "move", "pin", "place", "propose",
    "read", "rename", "restore", "run", "save", "search", "set", "summarize", "tag", "unlink",
}


def test_every_tool_name_is_snake_case_and_verb_first():
    for name in tools.TOOLS:
        assert SNAKE.fullmatch(name), f"{name} is not snake_case"
        assert name.split("_")[0] in VERBS or name in NOT_VERB_FIRST, f"{name} does not start with a verb"
    for name in NOT_VERB_FIRST:
        assert name in tools.TOOLS, f"{name} is gone: drop it from NOT_VERB_FIRST"


def test_no_two_tools_open_with_the_same_sentence():
    seen: dict[str, str] = {}
    for name, spec in tools.TOOLS.items():
        lead = _lead(spec).lower()
        assert lead not in seen, f"{name} and {seen[lead]} open with the same sentence"
        seen[lead] = name


def test_a_tool_lead_is_twelve_words_or_the_tool_is_named_as_long():
    over = {n for n, s in tools.TOOLS.items() if len(_lead(s).split()) > LEAD_WORDS}
    assert over <= LONG_LEAD, f"cut the first sentence to {LEAD_WORDS} words: {sorted(over - LONG_LEAD)}"
    assert LONG_LEAD <= over, f"now short enough, drop from LONG_LEAD: {sorted(LONG_LEAD - over)}"


def test_the_lead_ends_without_a_stray_double_stop():
    for name, spec in tools.TOOLS.items():
        assert not _lead(spec).endswith(".."), name
