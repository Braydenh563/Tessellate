"""Acts on the app's other surfaces, each with the inverse the model's own tool returns (L-chat-26,
decision 75): delete a document or a saved skill, put a note on the whiteboard, make a mind map.

The reader finds the sentence; the planner resolves the name against the notebook and draws the card
that waits for Confirm (or a typed yes, `ai/consent.py`), over tools the agent already has
(`delete_document`, `delete_skill`, `add_whiteboard_card`, `map_from_note`, `create_mindmap`). Nothing
here writes. `commands.py` lends its card and note helpers, read lazily (`commands` imports this module).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import composer_counter

INTENTS = frozenset({"delete_document", "delete_skill", "board_card", "make_map", "set_theme", "remember", "counter"})

#: The theme is a preference of the page, not of the server (`prefs`, settings.js `applyThemeChoice`): the step is
#: the card's Confirm, the page applies it, and patches the undo with the theme that was showing.
THEMES = ("light", "dark", "system")

_LEAD = r"^(?:(?:please|pls|can you|could you|would you)\s+)*"
_VERB = r"(?:delete|remove|bin|trash|get rid of)"
_DOCUMENT = (
    re.compile(rf"{_LEAD}{_VERB}\s+(?:the |my )?(?:document|doc)\s+(?:called |named |titled )?(?P<name>.+)$", re.I),
    re.compile(rf"{_LEAD}{_VERB}\s+(?:the |my )?(?P<name>.+?)\s+(?:document|doc)$", re.I),
)
_SKILL = (
    re.compile(rf"{_LEAD}{_VERB}\s+(?:the |my )?(?:saved )?skill\s+(?:called |named )?(?P<name>.+)$", re.I),
    re.compile(rf"{_LEAD}{_VERB}\s+(?:the |my )?(?P<name>.+?)\s+skill$", re.I),
)
_BOARD = re.compile(
    rf"{_LEAD}(?:put|add|place|drop|pin)\s+(?:the |my )?(?P<t>.+?\b(?:note|entry)(?:\s+(?:number\s+)?#?\d+)?|(?:note|entry)\s+(?:number\s+)?#?\d+)\s+(?:on|onto|to|in|into)\s+(?:the |my |a )?(?:white)?board$", re.I)
_MAP_OF = re.compile(
    rf"{_LEAD}(?:make|create|build|draw|start)\s+(?:me\s+)?(?:a |the )?mind ?map\s+(?:of|from|for|about|on)\s+(?:the |my )?(?P<t>.+)$", re.I)
_MAP_INTO = re.compile(rf"{_LEAD}(?:turn|make|convert)\s+(?:the |my )?(?P<t>.+?)\s+(?:in)?to\s+(?:a |the )?mind ?map$", re.I)
_NEW_BOARD = re.compile(
    rf"{_LEAD}(?:make|create|start|build|add)\s+(?:me\s+)?(?:a |the )?(?:new |blank |empty )?(?:white)?board\s+(?:called|named|titled|for|about)\s+(?P<t>.+)$", re.I)
#: The sentence the tool cue `save_user_preference` names (act_registry `TOOL_CUES`): a preference of the person's, never a note.
_REMEMBER = re.compile(rf"{_LEAD}remember that\s+(?P<t>i(?:['’]m)?\s+(?:prefer|like|want)\b.+)$", re.I)
_THEME = (
    re.compile(rf"{_LEAD}(?:switch|change|go|turn|set|use|put|enable|activate|swap)(?: (?:it|the app|this|everything|me|over))*(?: (?:to|on|into))?\s+(?:the |my )?(?P<t>dark|light|system)\s+(?:mode|theme)(?:\s+(?:on|please))?$", re.I),
    re.compile(rf"{_LEAD}(?:switch|go|change|swap)\s+(?:over\s+)?to\s+(?:the )?(?P<t>dark|light)$", re.I),
)
_THEME_OFF = re.compile(rf"{_LEAD}(?:turn off|disable|switch off)\s+(?:the |my )?dark\s+(?:mode|theme)$", re.I)
_NOTE_WORD = re.compile(r"\b(?:note|entry)\b|#\d|\bnumber \d", re.I)
_NO_NAME = frozenset({"a", "an", "the", "my", "any", "one", "this", "that", "it", "a saved", "saved", "all", "every"})


def _name(text: str) -> str:
    return " ".join(text.split()).strip(" .!?\"'“”‘’")


def _named(patterns, text: str) -> str:  # noqa: ANN001
    for pattern in patterns:
        if (found := pattern.match(text)) and (name := _name(found.group("name"))) and name.lower() not in _NO_NAME and not name.lower().startswith(("all ", "every ")):
            return name
    return ""


def _theme_of(text: str) -> str:
    if _THEME_OFF.match(text):
        return "light"
    found = next((m for pattern in _THEME if (m := pattern.match(text))), None)
    return found.group("t").lower() if found else ""


def read(text: str, one_target) -> dict | None:  # noqa: ANN001
    """The act `text` is, or None. `one_target` names a note from words."""
    if counted := composer_counter.read(text):
        return counted
    if theme := _theme_of(text):
        return {"intent": "set_theme", "name": theme}
    if name := _named(_DOCUMENT, text):
        return {"intent": "delete_document", "name": name}
    if name := _named(_SKILL, text):
        return {"intent": "delete_skill", "name": name}
    if found := _REMEMBER.match(text):
        said = _name(found.group("t"))
        return {"intent": "remember", "preference": said[:1].upper() + said[1:]} if said and len(said) <= 200 else None
    if found := _NEW_BOARD.match(text):
        name = _name(found.group("t"))
        return {"intent": "make_map", "title": name, "kind": "board"} if name and name.lower() not in _NO_NAME else None
    if found := _BOARD.match(text):
        target = one_target(_name(found.group("t")), bare=False)
        return {"intent": "board_card", **target, "single": True} if target and target.get("single", True) else None
    return _map(text, one_target)


def _map(text: str, one_target) -> dict | None:  # noqa: ANN001
    """"make a mind map from the boiler note", "start a mind map of Trips"."""
    found = _MAP_OF.match(text) or _MAP_INTO.match(text)
    if not found:
        return None
    said = _name(found.group("t"))
    if re.search(r"\bnotes\b", said, re.I):
        #: "a mind map of my garden notes" draws the notes on a subject (mermaid 1466), never an empty map named so.
        return None
    if _NOTE_WORD.search(said) and (target := one_target(said, bare=False)) and target.get("single", True):
        return {"intent": "make_map", **target, "single": True}
    return {"intent": "make_map", "title": said} if said and found.re is _MAP_OF and said.lower() not in _NO_NAME else None


# --- plan -------------------------------------------------------------------------------


def _one(rows: list[str], wanted: str) -> tuple[str | None, str]:
    """The one name in `rows` that `wanted` means (exact, then contained, case folded), else (None, why)."""
    low = wanted.casefold()
    exact = [r for r in rows if r.casefold() == low]
    near = exact or [r for r in rows if low in r.casefold()]
    if len(near) == 1:
        return near[0], ""
    if not near:
        return None, "none"
    return None, "Which one: " + " or ".join(f"“{r}”" for r in near[:3]) + "?"


def _counter(session: Session, parsed: dict, c: dict) -> dict:
    """One dated line on "Counter: <name>", or the note made with it; Undo is the edit's or the note's own."""
    from tessellate.core.database import LIKE_ESCAPE, Entry, like_escape

    pattern = f"%{like_escape(composer_counter.PREFIX)}%"
    notes = [{"id": e.id, "content": e.content} for e in session.scalars(select(Entry).where(Entry.content.like(pattern, escape=LIKE_ESCAPE), Entry.is_private.is_(False))).all()]
    today = c["today"]()
    found = composer_counter.find(notes, parsed["name"])
    line = composer_counter.line_for(parsed["n"], today)
    if found is None:
        label = f"Start a counter for {parsed['name']} with {parsed['n']} today"
        steps = [{"name": "create_note", "arguments": {"content": composer_counter.new_content(parsed["name"], parsed["n"], today)}}]
        return {"line": c["confirm"](label), "card": c["card"](label, steps)}
    entry = session.get(Entry, found["id"])
    from tessellate.ai import act_steps

    steps = [act_steps.locked_edit(entry.id, entry.content, f"{entry.content.rstrip()}\n{line}")]
    label = f"Add {parsed['n']} to your {parsed['name']} counter ({composer_counter.total(found, None, None) + parsed['n']} in all)"
    return {"line": c["confirm"](label), "card": c["card"](label, steps, [], [c["item"](entry)])}


def _delete_document(session: Session, parsed: dict, c: dict) -> dict:
    from tessellate.core.database import Document

    #: A private document is never matched by a sentence: with the vault locked its title reads the same as every other.
    rows = list(session.execute(select(Document.id, Document.title).where(Document.is_private.is_(False))).all())
    titles = {t: i for i, t in rows}
    name, why = _one(list(titles), parsed["name"])
    if name is None:
        return {"line": f"I found no document called “{parsed['name']}”." if why == "none" else why}
    label = f"Move the document “{name}” to the bin"
    return {"line": c["confirm"](label), "card": c["card"](label, [{"name": "delete_document", "arguments": {"document_id": titles[name]}}])}


def _delete_skill(parsed: dict, c: dict) -> dict:
    from tessellate.ai import skills
    from tessellate.core import deps

    config = deps.get_config()
    mine = [str(s.get("name") or "") for s in skills.stored(config)]
    name, why = _one([m for m in mine if m], parsed["name"])
    if name is None:
        if any(parsed["name"].casefold() == b["name"].casefold() for b in skills.builtins()):
            return {"line": f"“{parsed['name']}” is a built-in skill, so it cannot be deleted."}
        return {"line": f"I found no saved skill called “{parsed['name']}”." if why == "none" else why}
    label = f"Delete the saved skill “{name}”"
    return {"line": c["confirm"](label), "card": c["card"](label, [{"name": "delete_skill", "arguments": {"name": name}}])}


def _note(session: Session, parsed: dict, note_ids: list[int] | None, c: dict):  # noqa: ANN202
    entry, question = c["resolve_one"](session, parsed.get("about"), note_ids, bool(parsed.get("these")), parsed.get("note_id"))
    if entry is None:
        return None, {"line": question}
    ok, skipped = c["split_allowed"]([entry])
    return (entry, None) if ok else (None, {"line": c["summarise_done"]([], skipped)})


def plan(session: Session, parsed: dict, note_ids: list[int] | None, c: dict) -> dict:
    """The line and card for one of `INTENTS`. `c` is `commands`' lending (`commands._parity_helpers`)."""
    intent = parsed["intent"]
    if intent == "counter":
        return _counter(session, parsed, c)
    if intent == "set_theme":
        label = "Follow the system theme" if parsed["name"] == "system" else f"Switch to the {parsed['name']} theme"
        return {"line": c["confirm"](label), "card": c["card"](label, [{"name": "set_theme", "arguments": {"theme": parsed["name"]}}])}
    if intent == "delete_document":
        return _delete_document(session, parsed, c)
    if intent == "delete_skill":
        return _delete_skill(parsed, c)
    if intent == "remember":
        label = f"Suggest remembering that {parsed['preference'][:1].lower()}{parsed['preference'][1:]}"
        return {"line": c["confirm"](label), "card": c["card"](label, [{"name": "save_user_preference", "arguments": {"preference": parsed["preference"]}}])}
    if intent == "make_map" and parsed.get("kind") == "board":
        label = f"Make a board called “{parsed['title']}”"
        return {"line": c["confirm"](label), "card": c["card"](label, [{"name": "create_mindmap", "arguments": {"title": parsed["title"], "kind": "board"}}])}
    if intent == "make_map" and parsed.get("title"):
        label = f"Start a mind map called “{parsed['title']}”"
        return {"line": c["confirm"](label), "card": c["card"](label, [{"name": "create_mindmap", "arguments": {"title": parsed["title"]}}])}
    entry, refusal = _note(session, parsed, note_ids, c)
    if entry is None:
        return refusal
    title = c["note_title"](entry.content, size=48)
    if intent == "board_card":
        label = f"Put “{title}” on the whiteboard"
        steps = [{"name": "add_whiteboard_card", "arguments": {"note_id": entry.id}}]
    else:
        label = f"Make a mind map from “{title}”"
        steps = [{"name": "map_from_note", "arguments": {"note_id": entry.id}}]
    return {"line": c["confirm"](label), "card": c["card"](label, steps, [], [c["item"](entry)])}


def restore_document(session: Session, args: dict) -> dict:
    """Out of the bin, the same row and id: the Undo of `delete_document` (a step of this module, not a tool the model is offered)."""
    from tessellate.core.database import Document
    from tessellate.entry.bin import including_binned

    with including_binned(session):
        document = session.get(Document, int(args.get("document_id") or 0))
    if document is None or document.is_private:
        return {"error": f"No document with id {args.get('document_id')}"}
    if document.deleted_at is not None:
        document.deleted_at = None
        session.commit()
    return {"label": f"Restored the document “{document.title[:60]}” from the bin", "undo": {"tool": "delete_document", "arguments": {"document_id": document.id}}}


def drop_preference(session: Session, args: dict) -> dict:
    """The Undo of a suggested preference: the row goes while it still waits for an answer (an accepted one is the person's, left to Settings)."""
    from tessellate.core.database import UserPreference

    row = session.get(UserPreference, int(args.get("id") or 0))
    if row is None or not row.proposed:
        return {"label": "That suggestion has been answered already, so it stays as you left it"}
    session.delete(row)
    session.commit()
    return {"label": "Dropped the suggestion"}


def run_step(session: Session, name: str, args: dict) -> dict:
    """The theme step (the page applies it; the undo carries "system" until the page patches in the theme it replaced), or `restore_document`."""
    if name == "restore_document":
        return restore_document(session, args)
    if name == "drop_preference":
        return drop_preference(session, args)
    theme = str(args.get("theme") or "")
    if theme not in THEMES:
        return {"error": "That theme is not one I know: light, dark or system."}
    label = "Set the theme to follow the system" if theme == "system" else f"Switched to the {theme} theme"
    return {"label": label, "undo": {"tool": "set_theme", "arguments": {"theme": "system"}}}
