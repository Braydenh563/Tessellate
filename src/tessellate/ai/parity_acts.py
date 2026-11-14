"""Acts the model had a tool for and the composer had no sentence for (CHAT_PLAN decision 75,
parity agent 2026-11-10): delete or merge a category, delete a tag, replace a note's text,
turn a note's open checklist lines into reminders.

The reader finds the sentence; the planner resolves it against the notebook and draws the
card that waits for Confirm (or a typed yes, `ai/consent.py`), over tools the agent already
has (`delete_category`, `merge_categories`, `delete_tag`, `edit_note`, `set_reminder`), each
with an Undo. Nothing here writes. `commands.py` lends its card and note helpers, read lazily
(`commands` imports this module).
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from tessellate.ai import object_acts

INTENTS = frozenset({"delete_category", "merge_categories", "delete_tag", "edit_text", "to_reminders", "run_skill"})

_VERB = r"(?:delete|remove|drop|get rid of)"
_LEAD = r"^(?:(?:please|pls|can you|could you|would you)\s+)*"
_CATEGORY = r"categor(?:y|ies)|folders?"
_DELETE_CATEGORY = (
    re.compile(rf"{_LEAD}{_VERB}\s+(?:the |my )?(?:{_CATEGORY})\s+(?:called |named )?(?P<name>.+)$", re.I),
    re.compile(rf"{_LEAD}{_VERB}\s+(?:the |my )?(?P<name>.+?)\s+(?:{_CATEGORY})$", re.I),
)
_MERGE = re.compile(
    rf"{_LEAD}merge\s+(?:the |my )?(?:(?:{_CATEGORY})\s+)?(?P<a>.+?)\s+(?:into|with|and|to)\s+(?:the |my )?(?:(?:{_CATEGORY})\s+)?(?P<b>.+?)(?:\s+(?:{_CATEGORY}))?$", re.I)
_DELETE_TAG = re.compile(rf"{_LEAD}{_VERB}\s+(?:the |my )?(?:tag|label)\s+(?:called |named )?(?P<name>.+)$", re.I)
_EDIT = re.compile(
    rf"{_LEAD}(?:edit|change|update|rewrite|replace)\s+(?:the )?(?P<target>[^:]+?)\s*(?::|\bto say\b|\bto read\b|\bso (?:that )?it (?:says|reads)\b)\s*(?P<text>.+)$", re.I | re.S)
_SWAP = r"(?:change|replace|swap|update|switch)\s+(?P<old>.+?)\s+(?:to|with|for|by)\s+(?P<new>.+?)"
_NOTE_NAMED = r"(?:the |my )?(?P<target>.+?\b(?:note|entry))"
_FIND = (
    re.compile(rf"{_LEAD}{_SWAP}\s+in\s+{_NOTE_NAMED}$", re.I | re.S),
    re.compile(rf"{_LEAD}in\s+{_NOTE_NAMED}\s*,?\s+{_SWAP}$", re.I | re.S),
)
_REMINDERS = re.compile(
    rf"{_LEAD}(?:turn|make|convert|change|set)\s+(?:the |my )?(?P<src>.+?)\s+(?:in)?to\s+reminders?(?:\s+(?P<when>(?:for|on|at|by|tomorrow|today|tonight|next|this|in)\b.*))?$", re.I)
_REMINDERS_FROM = re.compile(
    rf"{_LEAD}(?:make|set|create|add)\s+reminders?\s+(?:from|for|out of)\s+(?:the |my )?(?P<src>.+?)(?:\s+(?P<when>(?:for|on|at|by|tomorrow|today|tonight|next|this|in)\b.*))?$", re.I)
#: "the action items in the Harbor note" names the note after the list word.
_IN_NOTE = re.compile(r"^(?P<what>.+?)\s+(?:in|from|on|of)\s+(?:the |my )?(?P<note>.+?)(?:\s+note)?$", re.I)
_LISTISH = frozenset({"items", "tasks", "todos", "to-dos", "checklist", "list", "lines", "bullets", "steps", "action items", "open items", "open tasks"})
_SKILL = re.compile(rf"{_LEAD}(?:run|start|launch|use)\s+(?:the |my )?(?:skill\s+(?:called |named )?(?P<a>.+)|(?P<b>.+?)\s+skill)$", re.I)
_NO_SKILL = frozenset({"a", "an", "the", "my", "any", "one", "this", "that", "it", "a saved", "saved"})
_OPEN_ITEM = re.compile(r"^\s*[-*+]\s+\[ \]\s+(.+?)\s*$", re.M)
_MAX_REMINDERS = 12


def words() -> frozenset[str]:
    """The words of these acts' own phrases ("reminders", "skill"): a real word one slip from one is read as it."""
    from tessellate.ai import act_registry

    return frozenset(w for a in act_registry.ACTS.values() if a.intent in INTENTS for w in re.findall(r"[a-z]{4,}", f"{a.verb} {a.label} {a.example}".lower()))


def _clean(text: str) -> str:
    return object_acts._name(" ".join(text.split()).rstrip(" .!"))  # noqa: SLF001


def _read_category_and_tag(text: str) -> dict | None:
    for pattern in _DELETE_CATEGORY:
        if (found := pattern.match(text)) and (name := _clean(found.group("name"))) and not name.lower().startswith(("a ", "all ", "every ")):
            return {"intent": "delete_category", "name": name}
    if (found := _DELETE_TAG.match(text)) and not re.search(r" (?:from|form)\b|\bnotes?$", found.group("name"), re.I) and (name := _clean(found.group("name"))):
        return {"intent": "delete_tag", "name": name}
    if re.search(_CATEGORY, text, re.I) and (found := _MERGE.match(text)):
        first, second = _clean(found.group("a")), _clean(found.group("b"))
        if first and second:
            return {"intent": "merge_categories", "from": first, "into": second}
    return None


def _read_edit(text: str, one_target) -> dict | None:  # noqa: ANN001
    """"edit the wifi note: the network is Bluegum-6G": the note named before the colon (or "to say") gets the
    words after it as its text. The target must say a note ("the wifi note"), so "change the heading: x" is no edit."""
    for pattern in _FIND:
        if found := pattern.match(text):
            return _read_find(found, one_target)
    found = _EDIT.match(text)
    if not found:
        return None
    target = " ".join(found.group("target").split())
    words = found.group("text").strip()
    if not words or not re.search(r"\b(?:note|entry)$", target, re.I) or target.lower().startswith(("the name of", "the title of", "my name")):
        return None
    named = one_target(target, bare=False)
    if not named or not named.get("single", True):
        return None
    return {"intent": "edit_text", **named, "single": True, "content": words}


def _read_find(found: re.Match, one_target) -> dict | None:  # noqa: ANN001
    """"change Bluegum-5G to 6G in the wifi note": only that text changes, the rest of the note stays."""
    old, new = (found.group(k).strip().strip("\"'“”‘’") for k in ("old", "new"))
    named = one_target(" ".join(found.group("target").split()), bare=False)
    if not old or not named or not named.get("single", True) or old.lower().startswith(("the name of", "the title of", "my name")):
        return None
    return {"intent": "edit_text", **named, "single": True, "find": old, "replace_with": new}


def _read_reminders(text: str, resolve) -> dict | None:  # noqa: ANN001
    found = _REMINDERS.match(text) or _REMINDERS_FROM.match(text)
    if not found:
        return None
    src = " ".join(found.group("src").split())
    if not src or src.lower().split(" ")[0] in ("it", "this", "that"):
        return None
    said = (found.group("when") or "").strip()
    due = resolve(re.sub(r"^(?:for|on|by)\s+", "", said, flags=re.I)) if said else None
    return {"intent": "to_reminders", "source": src, "due_at": due, "when_said": said}


def _read_skill(text: str) -> dict | None:
    """"run the daily review skill", "start the skill called Fix my links": a skill by its name."""
    found = _SKILL.match(text)
    name = _clean(found.group("a") or found.group("b") or "") if found else ""
    return {"intent": "run_skill", "name": name} if name and name.lower() not in _NO_SKILL else None


def read(text: str, one_target, resolve) -> dict | None:  # noqa: ANN001
    """The act `text` is, or None. `one_target` names a note from words; `resolve` reads a time from words."""
    return _read_category_and_tag(text) or _read_edit(text, one_target) or _read_reminders(text, resolve) or _read_skill(text)


# --- plan -------------------------------------------------------------------------------


def _delete_category(session: Session, parsed: dict, c) -> dict:  # noqa: ANN001
    from tessellate.entry import manager
    from tessellate.entry import manager_categories

    rows = manager_categories.all_categories(session)
    names = [row["name"] for row in rows]
    name = object_acts._find(parsed["name"], names)  # noqa: SLF001
    if name is None:
        return {"line": object_acts._unknown("category", parsed["name"], names, "delete")}  # noqa: SLF001
    if name == manager.UNCATEGORISED:
        return {"line": f"“{name}” is where notes with no category sit, so it cannot be deleted."}
    count = next(row["count"] for row in rows if row["name"] == name)
    kept = "no notes in it" if not count else f"{count} note{'' if count == 1 else 's'} in it, kept as Uncategorised"
    label = f"Delete the category “{name}” ({kept})"
    return {"line": c.confirm(label), "card": c.card(label, [{"name": "delete_category", "arguments": {"name": name}}])}


def _merge(session: Session, parsed: dict, c) -> dict:  # noqa: ANN001
    from tessellate.entry import manager
    from tessellate.entry import manager_categories

    rows = manager_categories.all_categories(session)
    names = [row["name"] for row in rows]
    found = {key: object_acts._find(parsed[key], names) for key in ("from", "into")}  # noqa: SLF001
    for key in ("from", "into"):
        if found[key] is None:
            return {"line": object_acts._unknown("category", parsed[key], names, "merge")}  # noqa: SLF001
    source, target = found["from"], found["into"]
    if source == target:
        return {"line": f"“{source}” and “{target}” are the same category."}
    if manager.UNCATEGORISED in (source, target):
        return {"line": "Uncategorised is where notes with no category sit, so it is not merged. Move the notes instead."}
    count = next(row["count"] for row in rows if row["name"] == source)
    label = f"Merge the category “{source}” into “{target}” ({count} note{'' if count == 1 else 's'} move)"
    return {"line": c.confirm(label), "card": c.card(label, [{"name": "merge_categories", "arguments": {"from": source, "into": target}}])}


def _delete_tag(session: Session, parsed: dict, c) -> dict:  # noqa: ANN001
    from tessellate.repo import tags as tags_repo

    counts = tags_repo.counts(session)
    name = object_acts._find(parsed["name"], list(counts))  # noqa: SLF001
    if name is None:
        return {"line": object_acts._unknown("tag", parsed["name"], list(counts), "delete")}  # noqa: SLF001
    if refusal := object_acts.guard(session, "delete_tag", {"name": name}):
        return {"line": refusal}
    notes = counts[name]
    label = f"Remove the tag “{name}” from {notes} note{'' if notes == 1 else 's'}"
    return {"line": c.confirm(label), "card": c.card(label, [{"name": "delete_tag", "arguments": {"name": name}}])}


def replaced(old: str, text: str) -> str:
    """`old` with its text replaced by `text`, its heading kept unless the new words bring their own."""
    first = (old or "").split("\n", 1)[0]
    new = text.strip()
    if new.startswith("#") or not first.startswith("#"):
        return new
    return f"{first}\n\n{new}"


def _edit_text(session: Session, parsed: dict, note_ids: list[int] | None, helpers: dict) -> dict:
    from tessellate.api.edit_conflicts import content_hash  # lazy: `ai` sits below `api`

    entry, question = helpers["resolve_one"](session, parsed.get("about"), note_ids, bool(parsed.get("these")), parsed.get("note_id"))
    if entry is None:
        return {"line": question}
    ok, skipped = helpers["split_allowed"]([entry])
    if not ok:
        return {"line": helpers["summarise_done"]([], skipped)}
    title = helpers["item"](entry)
    if "find" in parsed:
        return _find_replace(entry, parsed, helpers, skipped, title)
    new = replaced(entry.content or "", parsed["content"])
    if new.strip() == (entry.content or "").strip():
        return {"line": f"“{title}” already says that."}
    clip = helpers["clip"]
    body = (entry.content or "").split("\n", 1)[0] if (entry.content or "").startswith("#") else ""
    old_text = (entry.content or "").removeprefix(body).strip() or (entry.content or "").strip()
    label = f"Replace the text of “{title}” with “{clip(parsed['content'].strip(), 80)}”"
    steps = [{"name": "edit_note", "arguments": {"note_id": entry.id, "content": new, "base_hash": content_hash(entry.content)}}]
    card = helpers["card"](label, steps, skipped, [title, f"Was: {clip(' '.join(old_text.split()), 120)}", f"Now: {clip(' '.join(parsed['content'].split()), 120)}"])
    return {"line": helpers["confirm"](label), "card": card}


def _find_replace(entry, parsed: dict, helpers: dict, skipped: list, title: str) -> dict:  # noqa: ANN001
    """One find-and-replace over the note's text: every place the words stand, the rest untouched (Undo restores the whole)."""
    from tessellate.api.edit_conflicts import content_hash

    old, now, content, clip = parsed["find"], parsed["replace_with"], entry.content or "", helpers["clip"]
    pattern = re.compile(re.escape(old), 0 if old in content else re.I)
    hits = list(pattern.finditer(content))
    if not hits:
        return {"line": f"I could not find “{clip(old, 60)}” in “{title}”, so nothing changes."}
    new = pattern.sub(lambda _m: now, content)
    if new == content:
        return {"line": f"“{title}” already says that."}
    start = content.rfind("\n", 0, hits[0].start()) + 1
    end = content.find("\n", hits[0].end())
    was = content[start : end if end != -1 else len(content)]
    after = pattern.sub(lambda _m: now, was)
    more = f" ({len(hits)} places)" if len(hits) > 1 else ""
    label = f"Change “{clip(old, 40)}” to “{clip(now, 40)}” in “{title}”{more}"
    steps = [{"name": "edit_note", "arguments": {"note_id": entry.id, "content": new, "base_hash": content_hash(entry.content)}}]
    card = helpers["card"](label, steps, skipped, [title, f"Was: {clip(' '.join(was.split()), 120)}", f"Now: {clip(' '.join(after.split()), 120)}"])
    return {"line": helpers["confirm"](label), "card": card}


def _source_note(session: Session, parsed: dict, note_ids: list[int] | None, helpers: dict):  # noqa: ANN202
    """(the note whose open lines become reminders, a question when there is none to take)."""
    src = parsed["source"]
    low = src.lower()
    named = _IN_NOTE.match(src)
    if named and named.group("what").lower() in _LISTISH:
        return helpers["resolve_one"](session, named.group("note"), note_ids, False, None)
    if low in _LISTISH and note_ids:
        return helpers["resolve_one"](session, None, note_ids, True, None)
    about = re.sub(r"\s+note$", "", src, flags=re.I)
    found = helpers["resolve_one"](session, about, note_ids, False, None)
    #: The speller reads the one-word spelling as "to do" before this sees it; a note with the one-word or hyphenated title is looked up as typed.
    for spelling in ("todo", "to-do"):
        if found[0] is None and re.search(r"\bto do\b", about, re.I):
            found = helpers["resolve_one"](session, re.sub(r"\bto do\b", spelling, about, flags=re.I), note_ids, False, None)
    return found


def _to_reminders(session: Session, parsed: dict, note_ids: list[int] | None, helpers: dict, now: datetime) -> dict:
    entry, question = _source_note(session, parsed, note_ids, helpers)
    if entry is None:
        return {"line": question}
    ok, skipped = helpers["split_allowed"]([entry])
    if not ok:
        return {"line": helpers["summarise_done"]([], skipped)}
    items = [m.group(1) for m in _OPEN_ITEM.finditer(entry.content or "")][:_MAX_REMINDERS]
    title = helpers["item"](entry)
    if not items:
        return {"line": f"“{title}” has no open checklist lines to turn into reminders."}
    due = parsed.get("due_at")
    if due is None:
        return {"line": f"When should the {len(items)} reminder{'' if len(items) == 1 else 's'} from “{title}” go off? Say it again with a time, like: turn the {parsed['source']} into reminders for Friday at 9."}
    when = helpers["when_words"](due, now)
    label = f"Set {len(items)} reminder{'' if len(items) == 1 else 's'} {when} from “{title}”"
    steps = [{"name": "set_reminder", "arguments": {"text": item, "due_at": due.isoformat(), "note_id": entry.id}} for item in items]
    return {"line": helpers["confirm"](label), "card": helpers["card"](label, steps, skipped, items)}


def _run_skill(parsed: dict) -> dict:
    """The model's own hand-over (`run_skill`), said as a sentence: the page asks before it starts the run."""
    from tessellate.ai.tools import tool_handoff
    from tessellate.ai.tools._common import ToolError

    try:
        event = tool_handoff.validate_run_skill({"name": parsed["name"]})
    except ToolError as exc:
        said = str(exc)
        if "needs" in said and "inputs" in said:
            return {"line": "That skill needs some details first, so start it from the Skill menu in Chat."}
        return {"line": said.split(" Call list_skills")[0]}
    return {"line": f"I can run the skill “{event['skill']}”. It starts when you press Run the skill.", "tool": event}


def plan(session: Session, parsed: dict, note_ids: list[int] | None, helpers: dict, now: datetime) -> dict:
    """The line and card for one of `INTENTS`. `helpers` is `commands`' lending (`commands._parity_helpers`)."""
    helper = object_acts.Helpers(helpers["card"], helpers["confirm"], helpers["item"], helpers["note_title"], helpers["summarise_done"])
    intent = parsed["intent"]
    if intent == "delete_category":
        return _delete_category(session, parsed, helper)
    if intent == "merge_categories":
        return _merge(session, parsed, helper)
    if intent == "delete_tag":
        return _delete_tag(session, parsed, helper)
    if intent == "edit_text":
        return _edit_text(session, parsed, note_ids, helpers)
    if intent == "run_skill":
        return _run_skill(parsed)
    return _to_reminders(session, parsed, note_ids, helpers, now)
