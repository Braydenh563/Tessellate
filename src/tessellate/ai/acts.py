"""The act registry (CHAT_PLAN "The deterministic foundation", module 3,
decision 53): every act the app does from a sentence, each with `parse`,
`preview`, `run`, its `inverse` and a help line, over `ai/commands.py`, which
keeps the grammar, the cards and the tool door.

Every surface that names what an act does reads it from here: the capability
line said with no model, the palette's act rows, the Guide's act topics
(`help_topics_more.py`), and the line Ask says when a sentence is an act. A
model's proposed act (`propose`) is checked against the registry and goes
through the same preview, Confirm and Undo as a typed one: the model
proposes, the engine decides.

`inverse` names the step Undo runs; the run returns it (`run(...)["undo"]`)
and the page puts it on the app-wide undo stack (`pushUndo`, WORLD_CLASS
decision 53), so Ctrl+Z after an act takes it back.
`tests/test_acts.py` runs every write act and then its inverse on a real
notebook and checks the notebook is as it was.
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from tessellate.ai import act_registry, commands, consent_store, recognise, task_acts, validate
from tessellate.ai.act_registry import (
    ACTS,
    CONFIRM_INTENTS,
    Act,
    _ACTS,
    ask_line,
    capability_line,
    guide_topic,
    palette_rows,
)

#: The table and its text are read through this module too (routes_chat,
#: the tests), so the re-exports are named rather than incidental.
__all__ = [
    "ACTS", "CONFIRM_INTENTS", "Act", "_ACTS", "ask_line", "capability_line", "guide_topic", "palette_rows",
    "parse", "missing", "preview", "run", "inverse", "propose",
    "BOARD_ACTS", "BOARD", "board_parse", "board_label",
]


# --- the four stages ------------------------------------------------------------------


def parse(text: str, now: datetime, history: list[dict] | None = None) -> dict | None:
    """The act `text` says, as `commands.read` gives it, or None. With the chat's
    `history`, "tick the first one" names the task the last answer listed first."""
    parsed = commands.read_typed(text, now)
    parsed = parsed if parsed and parsed.get("intent") in ACTS else None
    return task_acts.counted_from(parsed, history) if parsed else None


def missing(parsed: dict) -> list[str]:
    """The slots the act needs that the sentence did not fill (decision 50:
    asked once, never guessed)."""
    return validate.slots_missing(parsed, ACTS[parsed["intent"]].slots)


def preview(session: Session, parsed: dict, note_ids: list[int] | None = None) -> dict:
    """What the act would do, written nowhere: the line and, for a write, the
    card with the exact steps (`commands.plan`)."""
    return commands.plan(session, parsed, note_ids)


def run(session: Session, steps: list[dict], skipped: list[dict] | None = None, say=None) -> dict:  # noqa: ANN001
    """Run a card's steps through the agent's tools; the result carries the
    inverse steps Undo runs. `say` words the "Done" line (the composer's)."""
    return commands.run(session, steps, skipped, say)


def ticked_line(card: dict, frame) -> str:  # noqa: ANN001
    """What a confirmed tick says ("ticked off “a” and “b”"), then the names
    left out (`commands.not_done`'s line). `frame` words the done part."""
    if " not done" in card["label"]:
        #: An untick is said as itself (R9-12), not as the edit it is under the card.
        return re.sub(r"^Mark (“.*?”) not done( \(in )?", lambda m: f"Unticked {m.group(1)}" + (" (" if m.group(2) else ""), card["label"]) + "." + (f" {commands.not_done(card.get('skipped') or [])}" if card.get("skipped") else "")
    what = re.sub(r"^Mark (“.*”) done", r"ticked off \1", card["label"])
    return f"{frame(what)} {commands.not_done(card.get('skipped') or [])}".strip()


def plain_say(label: str) -> dict:
    """The wording of a card nobody worded when it was drawn (a starter's, a model's proposal):
    the neutral voice, seeded by the card, so Confirm answers in the confirmations' own frames."""
    from tessellate.ai import composer_compose

    return {"mood": composer_compose.mood_of(seed=label, intent="act"), "intent": "act"}


def done_line(what: str, label: str = "") -> str:
    """"Done: ..." as the composer's confirmations say it, for a run that has only its words
    (a parked tool call)."""
    from tessellate.ai import composer_compose

    what = what.rstrip(".")
    return composer_compose.frame("act_done", plain_say(label or what)["mood"], what=f"{what[:1].lower()}{what[1:]}")


def run_said(session: Session, label: str, steps: list[dict], skipped: list[dict] | None, say: dict | None) -> dict:
    """`run` for a confirmed card, in the composer's own words (the ones the card was
    drawn with): "Done: I saved that to Shopping.", "I will remind you on Friday at 9:
    call the dentist.", "ticked off “Sunscreen”". `say` is `{mood, intent}`, None for plain."""
    from tessellate.ai import composer_checklist, composer_compose

    say = say or plain_say(label)
    mood = say["mood"]
    done = run(session, steps, skipped, lambda what: composer_compose.frame("act_done", mood, what=f"{what[:1].lower()}{what[1:]}"))
    if done["ok"] and say["intent"] == "reminder":
        done["summary"] = composer_compose.frame("act_card", mood, what=f"{label[:1].lower()}{label[1:]}")
    elif done["ok"] and say["intent"] in ("complete", "uncomplete"):
        done["summary"] = ticked_line({"label": label, "skipped": skipped or []}, lambda what: composer_compose.frame("act_done", mood, what=what))
        #: The tick that finishes a list is remarked on (CHAT_PLAN C9).
        finished = [composer_checklist.remark(str(s.get("arguments", {}).get("content") or "")) for s in steps if s.get("name") == "edit_note"] if say["intent"] == "complete" else []
        done["summary"] = " ".join([done["summary"], *(r for r in finished if r)])
    return done


def run_confirmed(session: Session, steps: list[dict], skipped: list[dict], consent_id: str | None) -> dict:
    """Confirm on a card: its own id runs what the server parked for it, in its own words;
    Undo posts no id and runs the steps it sends."""
    parked = consent_store.take(consent_id)
    if parked and parked.get("steps"):
        done = run_said(session, parked["label"], parked["steps"], parked["skipped"], parked.get("say"))
        if done["ok"]:
            consent_store.note_latest(parked["label"], done.get("undo"))
            consent_store.log_undo(done.get("undo"), parked["label"])
        return consent_store.remember(consent_id, done) if done["ok"] else done
    return run(session, steps, skipped)


def inverse(intent: str) -> str:
    """The tool Undo runs after this act, "" for one that changes nothing."""
    act = ACTS.get(intent)
    return act.inverse if act else ""


# --- a model's act (decision 53) ---------------------------------------------------------


def propose(session: Session, text: str, now: datetime, note_ids: list[int] | None = None) -> dict | None:
    """A model's proposed act, said as a sentence ("remind me to call Sam on
    Friday"), read by the same grammar and previewed as a card that waits for
    Confirm whatever the act: a model never runs a write on its own word.
    None when the sentence is not an act the registry has."""
    parsed = parse(text, now)
    if parsed is None:
        return None
    planned = preview(session, parsed, note_ids)
    planned.pop("run", None)
    if planned.get("card"):
        planned["card"] = {**planned["card"], "proposed": True, "label_said": False}
    return planned


# --- the board's acts (CHAT_PLAN section 2, the whiteboard and mind map row) ----------
#
# What a sentence typed in the command palette over a board does to it: the
# same registry shape, run by the board's own arrange commands
# (whiteboard-commands.js `wbPaletteActRow`), so "arrange as a grid of 3" is
# an act with a preview line and the board's Undo, not a search. The number is
# the recogniser's (`recognise.count_of`); `tests/fixtures/composer/
# board_acts_1010.json` is the set, at 1.0.

BOARD_ACTS = (
    Act("grid", "arrange", "arrange as a grid", "Lays the selection (or the whole board) out in rows of that many.",
        "arrange as a grid of 3", ("columns",), "undo"),
    Act("row", "arrange", "arrange in a row", "Lays the selection out left to right.", "put them in a row", (), "undo"),
    Act("column", "arrange", "arrange in a column", "Stacks the selection top to bottom.", "stack them in a column", (), "undo"),
    Act("align", "align", "align edges", "Lines the selection up on one edge or centre.", "align left", ("edge",), "undo"),
    Act("distribute", "space", "space evenly", "Spaces three or more items evenly.", "space them evenly left to right",
        ("axis",), "undo"),
    Act("same-size", "size", "make the same size", "Gives the selection the largest one's width or height.",
        "same width", ("dimension",), "undo"),
)
BOARD: dict[str, Act] = {a.intent: a for a in BOARD_ACTS}

_COUNT = r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|twelve)"
_BOARD_GRAMMAR = (
    ("grid", re.compile(rf"\b(?:grid|rows?)\s+of\s+{_COUNT}\b|\b{_COUNT}\s+(?:columns?|cols?|across|wide|per row|in a row each)\b")),
    ("grid", re.compile(r"\b(?:arrange|lay|put|make|tidy|sort|turn)\b.*\b(?:grid|tiles?)\b|\b(?:as|into|in) a grid\b|^(?:grid|tile them)$")),
    ("row", re.compile(r"\b(?:in|into|on)\s+(?:a|one)\s+(?:row|line)\b|\bline (?:them|it|these|everything) up\b|\bside by side\b")),
    ("column", re.compile(r"\b(?:in|into)\s+(?:a|one)\s+column\b|\bstack (?:them|these|it|everything)\b|\bone (?:above|under) (?:the )?(?:other|another)\b")),
    ("align", re.compile(r"\balign\b|\bline up (?:the )?(?:left|right|top|bottom)\b")),
    ("distribute", re.compile(r"\b(?:distribute|space (?:them |these |it )?(?:out )?evenly|even(?:ly)? spac|equal gaps?)")),
    ("same-size", re.compile(r"\bsame (?:width|height|size)\b|\b(?:as )?wide as the widest\b|\b(?:as )?tall as the tallest\b")),
)
_EDGES = (("hcenter", r"\bcent(?:re|er)s?\b.*\bhoriz|\bhoriz\w*\b.*\bcent"), ("vcenter", r"\bcent(?:re|er)s?\b.*\bvert|\bvert\w*\b.*\bcent|\bmiddle"),
          ("left", r"\bleft"), ("right", r"\bright"), ("top", r"\btop"), ("bottom", r"\bbottom"), ("hcenter", r"\bcent(?:re|er)"))


def _grid_slots(found: re.Match, low: str) -> tuple[str, dict] | None:
    said = next((g for g in found.groups() if g), None) if found.groups() else None
    columns = recognise.count_of(said) if said else None
    if columns is not None and not 1 <= columns <= 12:
        return None
    if columns == 1:
        return "column", {}
    return "grid", ({"columns": columns} if columns is not None else {})


def _align_slots(found: re.Match, low: str) -> tuple[str, dict] | None:
    edge = next((name for name, rx in _EDGES if re.search(rx, low)), None)
    return None if edge is None else ("align", {"edge": edge})


def _distribute_slots(found: re.Match, low: str) -> tuple[str, dict] | None:
    vertical = re.search(r"\b(?:top to bottom|vertical\w*|down|rows)\b", low)
    return "distribute", {"axis": "vertical" if vertical else "horizontal"}


def _same_size_slots(found: re.Match, low: str) -> tuple[str, dict] | None:
    return "same-size", {"dimension": "height" if re.search(r"height|tall", low) else "width"}


#: One reader per intent that has slots; an intent without one (row, column) has none to read.
_BOARD_SLOTS = {"grid": _grid_slots, "align": _align_slots, "distribute": _distribute_slots, "same-size": _same_size_slots}


def board_parse(text: str) -> dict | None:
    """The board act `text` says, `{intent, slots, label, help, inverse}`,
    or None when it is not one (the palette then searches as before)."""
    low = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if not low or len(low) > 120:
        return None
    for intent, pattern in _BOARD_GRAMMAR:
        found = pattern.search(low)
        if not found:
            continue
        read = _BOARD_SLOTS.get(intent, lambda _found, _low, _intent=intent: (_intent, {}))(found, low)
        if read is None:
            return None
        intent, slots = read
        act = BOARD[intent]
        return {"intent": intent, "slots": slots, "label": board_label(intent, slots), "help": act.help, "inverse": act.inverse}
    return None


def board_label(intent: str, slots: dict) -> str:
    """The act's preview line, as the palette row says it."""
    if intent == "grid":
        n = slots.get("columns")
        return f"Arrange as a grid, {n} across" if n else "Arrange as a grid"
    if intent == "align":
        words = {"left": "left edges", "right": "right edges", "top": "top edges", "bottom": "bottom edges",
                 "hcenter": "centres horizontally", "vcenter": "centres vertically"}
        return f"Align {words[slots['edge']]}"
    if intent == "distribute":
        return "Space evenly, " + ("top to bottom" if slots["axis"] == "vertical" else "left to right")
    if intent == "same-size":
        return f"Same {slots['dimension']} as the {'tallest' if slots['dimension'] == 'height' else 'widest'}"
    return BOARD[intent].label[:1].upper() + BOARD[intent].label[1:]


#: The agent's propose_act tool reaches `propose` through the leaf (act_registry.py says why).
act_registry.proposer = propose
