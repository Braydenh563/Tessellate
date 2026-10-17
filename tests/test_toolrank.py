"""The ranked toolbox (O10 rest; BACKLOG "Composer ranks the tools the model
is offered").

`toolwords.focus_detail` scores a *group* of tools (sixteen board tools share
one score), so on a small window the cut inside a group was the table's order,
not the question's. `tools.rank_tools` scores every tool: the name's words, the
description's, the group the focus fired, the core, the web and plan asks, with
a question *about* a capability halving its write tools. `within_budget`
consumes that order, and the turn's log says what was offered and held back,
with the score."""

from __future__ import annotations

import pytest

from tessellate.ai import tools


def _order(question: str, recent: str = "") -> list[str]:
    return [name for name, _ in tools.rank_tools(question, recent)]


def _p(question: str) -> dict[str, float]:
    return dict(tools.rank_tools(question))


#: (what was asked, the tool that must come before the other, the other).
#: Chosen from the judgement of what is wanted, not from what the scorer
#: happened to answer; the owner's typos are fixtures too.
BEFORE = [
    ("add a node called Travel to my mind map", "add_map_node", "read_whiteboard"),
    ("add a node called Travel to my mind map", "add_map_node", "delete_board_item"),
    ("delete the tag gym", "delete_tag", "rename_tag"),
    ("delte the tag gym", "delete_tag", "rename_tag"),
    ("rename the tag gym to fitness", "rename_tag", "delete_tag"),
    ("rename the category Work to Jobs", "rename_category", "delete_category"),
    ("merge my two meeting categories", "merge_categories", "rename_category"),
    ("what is the path between golf and fitness", "path_between", "link_notes"),
    ("find notes similar to my golf note", "find_similar_notes", "unlink_notes"),
    ("pin my dentist note", "pin_note", "edit_note"),
    ("remind me to call mum tomorrow", "set_reminder", "list_reminders"),
    ("what reminders do i have", "list_reminders", "set_reminder"),
    ("compress this chat", "compress_chat", "search_chat_history"),
    ("serch teh web for rust news", "web_search", "read_url"),
    ("draw a diagram of my week", "generate_diagram", "add_board_shape"),
]


@pytest.mark.parametrize(("asked", "first", "second"), BEFORE)
def test_the_tool_the_words_name_ranks_above_its_neighbour(asked, first, second):
    order = _order(asked)
    assert order.index(first) < order.index(second), (asked, order[:14])


def test_every_tool_is_ranked_once_and_scores_are_probabilities():
    ranked = tools.rank_tools("delete the tag gym")
    names = [n for n, _ in ranked]
    assert len(names) == len(set(names)) == len(tools.TOOLS)
    assert all(0.0 <= p <= 1.0 for _, p in ranked)
    assert [p for _, p in ranked] == sorted((p for _, p in ranked), reverse=True)


def test_the_core_is_always_near_the_top():
    p = _p("delete the tag gym")
    for name in tools.CORE_TOOLS:
        if name in p:
            assert p[name] >= 0.9, (name, p[name])


def test_a_question_about_a_capability_holds_back_its_writes():
    asked_for = _p("tag my golf note as sport")
    asked_about = _p("how do I delete a tag")
    assert asked_about["delete_tag"] < 0.5 <= max(asked_for["tag_note"], 0.5)
    assert asked_about["delete_tag"] < _p("delete the tag gym")["delete_tag"]


def test_the_previous_turns_tools_count_for_a_follow_up():
    cold = dict(tools.rank_tools("do the same for the other one"))
    warm = dict(tools.rank_tools("do the same for the other one", recent_tools=("merge_categories",)))
    assert warm["merge_categories"] > cold["merge_categories"]


def test_an_unrelated_tool_is_low():
    p = _p("what did I write about my vintage camera")
    assert p["delete_tag"] < 0.2 and p["search_notes"] >= 0.9, (p["delete_tag"], p["search_notes"])


def test_within_budget_drops_the_least_likely_tool_first():
    specs = [s for s in tools.ollama_tools(None) if s["function"]["name"] in {"read_whiteboard", "add_map_node", "delete_board_item", "search_notes"}]
    ranking = dict(tools.rank_tools("add a node called Travel to my mind map"))
    budget = tools.schema_chars([s for s in specs if s["function"]["name"] in {"search_notes", "add_map_node"}]) + 40
    kept, dropped = tools.within_budget(specs, budget, ranking=ranking)
    names = [s["function"]["name"] for s in kept]
    assert "add_map_node" in names, (names, dropped)
    assert "delete_board_item" in dropped


def test_the_log_line_says_what_was_offered_and_held_back_with_scores():
    ranking = dict(tools.rank_tools("add a node called Travel to my mind map"))
    line = tools.ranking_line(["add_map_node", "search_notes"], ["delete_board_item"], ranking)
    assert line.startswith("tool ranking: offered add_map_node ") and "%" in line
    assert "held back delete_board_item " in line
