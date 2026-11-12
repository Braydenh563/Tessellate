"""The calls that put back what a delete took (L-chat-26), kept apart so the tools that delete stay small.

Each is an `undo` the run summary offers beside the change, the same contract `_undo_edit` follows: a tool
call the page hands back to `POST /chat/command/run`."""

from __future__ import annotations


def skill_restore(skill: dict) -> dict:
    """`save_skill` with a deleted skill's fields: its `verify` block back in the flat `verify_*` arguments the tool takes."""
    arguments = {key: skill.get(key) for key in ("name", "prompt", "steps", "tools", "when_to_use") if skill.get(key)}
    verify = skill.get("verify") or {}
    if verify.get("tool"):
        expect = verify.get("expect") or {}
        predicate = next(iter(expect), "unchanged")
        arguments.update(verify_tool=verify["tool"], verify_expect=predicate, verify_untagged=bool((verify.get("args") or {}).get("untagged")))
        if predicate != "unchanged":
            arguments["verify_value"] = expect[predicate]
    return {"tool": "save_skill", "arguments": arguments}


def board_card_removed(card_id: int) -> dict:
    """`delete_board_item` for a card just placed (the note stays in the notebook)."""
    return {"tool": "delete_board_item", "arguments": {"kind": "card", "item_id": card_id}}


def board_note_binned(note_id: int) -> dict:
    """`delete_note` for a map just made: a map is a board, which is a note, and the bin keeps it."""
    return {"tool": "delete_note", "arguments": {"note_id": note_id}}
