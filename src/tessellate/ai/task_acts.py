"""Tasks as acts, with no model (audit 1028 E10).

The app has two kinds of task and this module reads both, adding nothing new
to store: a reminder (decision 75: the reminders are the task list) and an
unticked checklist line (`- [ ] item`) in a note. Adding a task sets a
reminder, so the time is asked once like any reminder's (decision 50);
completing one finds the reminder or checklist line the person's words name.
A name that fits more than one asks which, and a name that fits one only in
part asks as well: a guess here would tick off the wrong thing.

`commands.py` reads the sentences and plans the cards through this module;
the words are matched as stems (`meaning.stem`) so "reading" finds "read".
"""

from __future__ import annotations

import re
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import meaning

_BOX = re.compile(r"^(?P<lead>[ \t]*(?:[-*+]|\d+[.)])[ \t]+)\[ \][ \t]+(?P<item>\S.*?)[ \t]*$", re.MULTILINE)
_LISTS = r"(?:to-?do|todo|to do|tasks?)"
#: "to my to-do list", "on the task list", "onto my tasks"
_ON_LIST = re.compile(rf"\s(?:to|on|onto|in|into)\s+(?:my |the |our )?{_LISTS}(?: list)?\b[ :,]*", re.IGNORECASE)
_NEW_TASK = re.compile(
    rf"^(?:(?:add|create|make|set up|start|put down)\s+(?:a |an |another |one more |my )?(?:new )?|new\s+){_LISTS}(?: item)?\b[ :,\-]*(?P<body>.*)$",
    re.IGNORECASE,
)
_LABELLED = re.compile(rf"^{_LISTS}\s*:\s*(?P<body>.+)$", re.IGNORECASE)
_PLACE_VERBS = ("add ", "put ", "pop ", "stick ", "throw ", "write ", "pencil ")
_NOT_A_TASK_BODY = ("list", "lists", "manager", "app", "view", "page", "board", "feature", "tab", "widget")
#: Words that open the sentence, left out of the task's own words.
_LEAD_TO = ("to ", "that ", "for me to ")

_DONE_WORD = r"(?:done|complete|completed|finished|ticked|checked|ticked off|checked off|crossed off|sorted)"
_DONE_TAIL = re.compile(rf"\s+(?:as |to be )?{_DONE_WORD}$", re.IGNORECASE)
_OFF_TAIL = re.compile(r"\s+off(?:\s+(?:of\s+)?(?:my |the |this |that )?(?:list|checklist|to-?do list|todo list|task list|tasks))?$", re.IGNORECASE)
_ON_LIST_TAIL = re.compile(r"\s+(?:on|from|in)\s+(?:my |the )?(?:list|checklist|to-?do list|todo list|task list)$", re.IGNORECASE)
_ARTICLE = re.compile(r"^(?:the |my |our |this |that |a |an |your )+", re.IGNORECASE)
_LEAD_KIND = re.compile(r"^(?:(?P<kind>reminder|task|to-?do|todo|check-?list item|list item|item)\s*(?:to |for |called |named |about |:)?\s*)", re.IGNORECASE)
_TAIL_KIND = re.compile(r"\s+(?P<kind>reminder|task|to-?do|todo|check-?list item|check-?list|list item|item)s?$", re.IGNORECASE)

_STOP = frozenset("the a an my our of and or to in on for with about this that it please".split())
_KIND_WORDS = frozenset("task tasks reminder reminders todo item items checklist".split())
#: At most this many candidates are named when asking which.
_NAMED = 4


# --- reading --------------------------------------------------------------------------------


def _unquote(text: str) -> str:
    return text.strip(" \t\"'‘’“”`")


def _task_body(text: str) -> tuple[str, str] | None:
    """(what is to be done, any time said after the list) for a sentence that
    puts something on the task list, or None."""
    found = _NEW_TASK.match(text) or _LABELLED.match(text)
    if found:
        body = found.group("body").strip()
        low = body.lower()
        if not body or low.split(" ", 1)[0] in _NOT_A_TASK_BODY:
            return None
        for lead in _LEAD_TO:
            if low.startswith(lead):
                body = body[len(lead):]
                break
        return _unquote(body), ""
    low = text.lower()
    if not low.startswith(_PLACE_VERBS):
        return None
    ons = list(_ON_LIST.finditer(text))
    if not ons:
        return None
    found = ons[-1]
    head = text[text.index(" ") + 1 : found.start()].strip()
    head = _unquote(head)
    if not head or head.lower().startswith(("a reminder", "the reminder", "a note", "the tag", "a tag")):
        return None
    for lead in _LEAD_TO:
        if head.lower().startswith(lead):
            head = head[len(lead):]
    return head, text[found.end():].strip()


def read_add(text: str, reminder) -> dict | None:  # noqa: ANN001
    """The task a sentence adds, as the reminder it becomes (`reminder` is
    `commands._reminder` bound to the clock) with `task: True`, or None."""
    body = _task_body(text)
    if body is None:
        return None
    words, tail = body
    tail = re.sub(r"^for\s+", "", tail, flags=re.IGNORECASE)
    if not words:
        return None
    found = reminder(f"remind me to {words} {tail}".strip())
    return {**found, "task": True} if found else None


def read_complete(text: str) -> dict | None:
    """The task a sentence completes, as {"intent": "complete", "about",
    "kind"?}, or None. kind is "reminder" or "checklist" when the sentence
    says which, else both are looked in."""
    low = text.lower()
    rest = None
    if low.startswith(("mark ", "set ", "flag ")):
        rest = text[low.index(" ") + 1 :].strip()
        off = re.match(r"off\s+(.+)$", rest, re.IGNORECASE)
        if off:
            rest = off.group(1)
        elif _DONE_TAIL.search(rest):
            rest = _DONE_TAIL.sub("", rest, count=1)
        else:
            return None
    elif re.match(r"(?:tick|check|cross)\s+off\s+", text, re.IGNORECASE):
        rest = re.sub(r"^\w+\s+off\s+", "", text, count=1, flags=re.IGNORECASE)
    elif re.match(r"(?:tick|check|cross|strike)\s+(?!off\b)\S", text, re.IGNORECASE) and _OFF_TAIL.search(text):
        rest = _OFF_TAIL.sub("", text.split(" ", 1)[1], count=1)
    elif low.startswith("complete "):
        rest = text[len("complete ") :]
    if rest is None:
        return None
    rest = _ON_LIST_TAIL.sub("", _OFF_TAIL.sub("", rest.strip()), count=1).strip()
    kind = None
    lead = _LEAD_KIND.match(_ARTICLE.sub("", rest))
    rest = _ARTICLE.sub("", rest)
    if lead:
        kind = lead.group("kind").lower()
        rest = rest[lead.end() :]
    tail = _TAIL_KIND.search(rest)
    if tail:
        kind = tail.group("kind").lower()
        rest = rest[: tail.start()]
    about = _unquote(_ARTICLE.sub("", rest.strip()))
    if not about or not meaning.words_of(about):
        return None
    found: dict = {"intent": "complete", "about": about}
    if kind == "reminder":
        found["kind"] = "reminder"
    elif kind and kind.startswith(("check", "list")):
        found["kind"] = "checklist"
    return found


# --- matching ---------------------------------------------------------------------------------


def _stems(text: str) -> frozenset[str]:
    return frozenset(meaning.stem(w) for w in meaning.words_of(text) if w not in _STOP and w not in _KIND_WORDS)


def _candidates(session: Session, kind: str | None, title) -> list[dict]:  # noqa: ANN001
    from tessellate.core.database import Entry, Reminder

    out: list[dict] = []
    if kind in (None, "reminder"):
        rows = session.scalars(select(Reminder).where(Reminder.done.is_(False)).order_by(Reminder.due_at).limit(500)).all()
        linked = {r.entry_id for r in rows if r.entry_id is not None}
        private = set(session.scalars(select(Entry.id).where(Entry.id.in_(linked), Entry.is_private.is_(True)))) if linked else set()
        for row in rows:
            if row.entry_id in private:
                continue
            out.append({
                "kind": "reminder", "id": row.id, "text": row.text,
                "where": f"reminder due {row.due_at.strftime('%a')} {row.due_at.day} {row.due_at.strftime('%b')}",
            })
    if kind in (None, "checklist"):
        notes = session.scalars(
            select(Entry).where(
                Entry.content.like("%[ ]%"), Entry.is_deleted.is_(False), Entry.deleted_at.is_(None),
                Entry.is_private.is_(False),
            ).limit(500)
        ).all()
        for note in notes:
            for line in _BOX.finditer(note.content or ""):
                out.append({"kind": "checklist", "id": note.id, "text": line.group("item"), "line": line.group(0), "where": f"in {title(note)}", "content": note.content})
    for item in out:
        item["stems"] = _stems(item["text"])
    return out


def _name(item: dict) -> str:
    return f"“{item['text']}” ({item['where']})"


def _ask(items: list[dict], about: str, partial: bool) -> str:
    named = [_name(i) for i in items[:_NAMED]]
    more = f", and {len(items) - _NAMED} more" if len(items) > _NAMED else ""
    listed = (", ".join(named[:-1]) + " or " + named[-1]) if len(named) > 1 else named[0]
    lead = f"I found nothing named exactly “{about}”. Did you mean" if partial else "Which one do you mean"
    return f"{lead}: {listed}{more}? Say it again with more of its name."


def pick(session: Session, parsed: dict, title) -> tuple[dict | None, str]:
    """(the one task named, ""), or (None, what to say instead)."""
    about = str(parsed.get("about") or "")
    wanted = _stems(about)
    if not wanted:
        return None, "Which task do you mean? Say its name, like: tick off buy milk."
    items = _candidates(session, parsed.get("kind"), title)
    scored = [(len(wanted & i["stems"]) / len(wanted), i) for i in items]
    full = [i for score, i in scored if score == 1.0]
    if full:
        exact = [i for i in full if i["stems"] == wanted]
        if len(exact) == 1:
            return exact[0], ""
        if len(full) == 1:
            return full[0], ""
        return None, _ask(full, about, partial=False)
    near = [i for score, i in scored if score >= 0.5]
    if near:
        return None, _ask(near, about, partial=True)
    where = "reminder" if parsed.get("kind") == "reminder" else "open task or reminder"
    return None, f"I found no {where} named “{about}”."


# --- planning -----------------------------------------------------------------------------------


def plan_complete(session: Session, parsed: dict, card, title) -> dict:  # noqa: ANN001
    """The card that completes the task named, run at once with Undo, or the
    question that asks which. `card` is `commands._card` and `title` `commands._title`, passed in
    because this module sits below commands."""
    item, say = pick(session, parsed, title)
    if item is None:
        return {"line": say}
    label = f"Mark “{item['text']}” done" + ("" if item["kind"] == "reminder" else f" ({item['where']})")
    if item["kind"] == "reminder":
        steps = [{"name": "complete_reminder", "arguments": {"reminder_id": item["id"], "done": True}}]
    else:
        ticked = item["content"].replace(item["line"], item["line"].replace("[ ]", "[x]", 1), 1)
        steps = [{"name": "edit_note", "arguments": {"note_id": item["id"], "content": ticked}}]
    return {"line": f"{label}.", "card": card(label, steps), "run": True}


def undo_step(name: str, args: dict) -> dict | None:
    """What Undo runs after a completed reminder."""
    if name == "complete_reminder" and args.get("done", True):
        return {"tool": "complete_reminder", "arguments": {"reminder_id": args["reminder_id"], "done": False}}
    return None


