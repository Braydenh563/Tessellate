"""Every write tool has a verifier (AGENT_SKILLS_REFORM Phase E, decision 4).

The harness reads back what a write tool claims before the model sees the
result: `contracts.py` for the note, tag, category and reminder tools,
`tools/verify.py` for the rest. A write tool with neither fails here, and
each verifier is shown to refuse a claim the notebook does not hold, so a
verifier that always passes is caught too.
"""

from __future__ import annotations

import pytest

from tessellate.ai import tools
from tessellate.ai.tools import contracts, verify


def test_every_write_tool_has_a_verifier():
    unchecked = sorted(name for name in tools.WRITE_TOOLS if not verify.has_verifier(name))
    assert unchecked == [], (
        "these write tools reach the model unchecked; add a verifier in "
        f"ai/tools/verify.py: {unchecked}"
    )


def test_the_two_tables_name_real_tools_and_do_not_overlap():
    assert set(verify.VERIFIERS) <= set(tools.TOOLS)
    assert set(verify.VERIFIERS) <= tools.WRITE_TOOLS, "a verifier on a read tool checks nothing"
    covered = {name for name, (_pre, post) in contracts.CONTRACTS.items() if post}
    assert not covered & set(verify.VERIFIERS), "a tool checked twice"


#: A claim no empty notebook can hold, per verifier: each must refuse it.
FALSE_CLAIMS = {
    "create_document": ({"title": "Plan"}, {"id": 999_999}),
    "delete_document": ({"document_id": 0}, {}),
    "add_whiteboard_card": ({}, {"card_id": 999_999, "note_id": 1}),
    "add_whiteboard_link": ({}, {"link_id": 999_999}),
    "link_map_nodes": ({}, {"link_id": 999_999}),
    "generate_diagram": ({}, {"cards": [{"card_id": 999_999}]}),
    "create_mindmap": ({}, {"board_id": 999_999, "root_id": 1}),
    "map_from_note": ({}, {"board_id": 999_999, "nodes": 3}),
    "add_map_node": ({}, {"node_id": 999_999, "board_id": 1}),
    "move_board_item": ({"x": 0, "y": 0}, {"kind": "card", "item_id": 999_999}),
    "edit_board_item": ({}, {"kind": "object", "item_id": 999_999}),
    "add_board_shape": ({}, {"kind": "shape", "item_id": 999_999}),
    "restore_board_item": ({}, {"kind": "card", "item_id": 999_999}),
    "place_library_item": ({}, {"sketch_ids": [999_999], "object_ids": []}),
    "audit_link_reasons": ({}, {"updated": 5}),
    "check_learned": ({}, {"retired": 3, "run": "2026-11-01T09:00:00"}),
    "save_skill": ({}, {"name": "never saved"}),
}


def test_every_verifier_has_a_false_claim_case():
    #: `delete_board_item` and `delete_skill` are shown the other way round
    #: below: their false claim needs a row that exists.
    assert set(FALSE_CLAIMS) | {"delete_board_item", "delete_skill"} == set(verify.VERIFIERS)


@pytest.mark.parametrize("name", sorted(FALSE_CLAIMS))
def test_a_verifier_refuses_what_the_notebook_does_not_show(app_state, name):
    from tessellate.core import deps

    args, result = dict(FALSE_CLAIMS[name][0]), dict(FALSE_CLAIMS[name][1])
    if name == "delete_document":
        from tessellate.core.database import Document

        with deps.get_db().session() as session:
            document = Document(title="Kept", content="x")
            session.add(document)
            session.commit()
            args["document_id"] = document.id
    with deps.get_db().session() as session:
        problem = verify.check(session, name, args, result)
    assert problem and problem.startswith(f"{name} did not take effect")


def test_a_deleted_item_still_there_is_refused(app_state):
    from tessellate.core import deps
    from tessellate.entry import manager

    with deps.get_db().session() as session:
        entry = manager.create_entry(session, "on a board", "Work", [])
        card_id = tools.execute_tool(session, "add_whiteboard_card", {"note_id": entry.id})["card_id"]
        problem = verify.check(session, "delete_board_item", {}, {"kind": "card", "item_id": card_id})
    assert problem and "still on the board" in problem


def test_a_deleted_skill_still_saved_is_refused(app_state):
    from tessellate.core import deps

    deps.get_config().set_preference("skills", [{"name": "Mine", "prompt": "x"}])
    with deps.get_db().session() as session:
        problem = verify.check(session, "delete_skill", {}, {"name": "Mine"})
    assert problem and "still saved" in problem


def test_a_true_claim_passes_through_execute_tool(app_state):
    """The happy path is untouched: a real write comes back as written."""
    from tessellate.core import deps

    with deps.get_db().session() as session:
        made = tools.execute_tool(session, "create_document", {"title": "Plan", "content": "Steps."})
        assert "error" not in made, made
        gone = tools.execute_tool(session, "delete_document", {"document_id": made["id"]})
    assert "error" not in gone, gone


def test_a_verifier_fault_never_costs_the_write(app_state, monkeypatch):
    from tessellate.core import deps

    def broken(*_args):
        raise RuntimeError("checker bug")

    monkeypatch.setitem(verify.VERIFIERS, "create_document", broken)
    with deps.get_db().session() as session:
        assert verify.check(session, "create_document", {}, {"id": 1}) is None
