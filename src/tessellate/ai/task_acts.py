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
    return {**found, "task": True, "asked": text} if found else None


def _complete_rest(text: str) -> str | None:
    """What follows the completing verb ("mark X done", "tick off X", "tick X
    off", "complete X"), or None when the sentence is none of those."""
    low = text.lower()
    if low.startswith(("mark ", "set ", "flag ")):
        rest = text[low.index(" ") + 1 :].strip()
        off = re.match(r"off\s+(.+)$", rest, re.IGNORECASE)
        if off:
            return off.group(1)
        return _DONE_TAIL.sub("", rest, count=1) if _DONE_TAIL.search(rest) else None
    if re.match(r"(?:tick|check|cross)\s+off\s+", text, re.IGNORECASE):
        return re.sub(r"^\w+\s+off\s+", "", text, count=1, flags=re.IGNORECASE)
    if re.match(r"(?:tick|check|cross|strike)\s+(?!off\b)\S", text, re.IGNORECASE) and _OFF_TAIL.search(text):
        return _OFF_TAIL.sub("", text.split(" ", 1)[1], count=1)
    if low.startswith("complete "):
        return text[len("complete ") :]
    return None


#: Looser ways to say a reminder or task is done; each needs the kind word said
#: ("finish the reminder to call mum"), or "I finished the report" would be an
#: act on a task that was never named (audit 1030 A15).
_DONE_LEADS = ("finish ", "i finished ", "i've finished ", "i have finished ", "done with ", "i'm done with ", "im done with ")


def read_complete(text: str) -> dict | None:
    """The task a sentence completes, as {"intent": "complete", "about",
    "kind"?}, or None. kind is "reminder" or "checklist" when the sentence
    says which, else both are looked in."""
    rest = _complete_rest(text)
    loose = rest is None
    if loose:
        lead = next((w for w in _DONE_LEADS if text.lower().startswith(w)), None)
        if lead is None:
            return None
        rest = text[len(lead):]
    about, said = _split_kind(_ON_LIST_TAIL.sub("", _OFF_TAIL.sub("", rest.strip()), count=1))
    if loose and not said:
        return None
    return _task_found("complete", about, said)


def _split_kind(rest: str) -> tuple[str, str | None]:
    """(the task's own words, the kind word said with them) for what follows a
    verb: "the buy milk task" is ("buy milk", "task"), "reminder dentist" is
    ("dentist", "reminder")."""
    rest = _ARTICLE.sub("", rest.strip())
    said = None
    lead = _LEAD_KIND.match(rest)
    if lead:
        said = lead.group("kind").lower()
        rest = rest[lead.end() :]
    tail = _TAIL_KIND.search(rest)
    if tail:
        said = tail.group("kind").lower()
        rest = rest[: tail.start()]
    return _unquote(_ARTICLE.sub("", rest.strip())), said


def _kind_of(said: str | None) -> str | None:
    """"reminder" or "checklist" when the kind word says which, else None."""
    if said == "reminder":
        return "reminder"
    return "checklist" if said and said.startswith(("check", "list")) else None


def _task_found(intent: str, about: str, said: str | None) -> dict | None:
    if not about or not meaning.words_of(about) or about.lower().startswith(("all ", "every ")):
        return None
    found: dict = {"intent": intent, "about": about}
    if _kind_of(said):
        found["kind"] = _kind_of(said)
    return found


_CANCEL = re.compile(r"^(?:cancel|delete|remove|scrap|bin|trash|drop|take)\s+(?P<rest>.+)$", re.IGNORECASE)
#: "buy milk from my tasks", "buy milk off the to-do list"
_OFF_LIST = re.compile(
    r"\s+(?:off|from|out of|on)\s+(?:of\s+)?(?:my |the |our )?(?:task list|to-?do list|todo list|tasks|to-?dos|list|checklist)$", re.IGNORECASE
)
#: Words after the name that make it a note or something else, not a task.
_NOT_TASK_TAIL = re.compile(r"\s(?:notes?|tags?|categor(?:y|ies)|documents?|boards?|maps?|meetings?)$", re.IGNORECASE)


_CANCEL_LEADS = ("get rid of ", "never mind ", "clear ")
_NO_LONGER = (" any more", " anymore", " any longer")


def _cancel_form(text: str) -> str:
    """The plain "cancel ..." a looser way of saying it stands for."""
    low = text.lower().strip()
    for lead in _CANCEL_LEADS:
        if low.startswith(lead):
            return "cancel " + text.strip()[len(lead):]
    if low.startswith("stop reminding me about "):
        return "cancel the reminder about " + text.strip()[len("stop reminding me about "):]
    if low.startswith(("i don't need ", "i do not need ", "i dont need ")):
        rest = text.strip().split(" need ", 1)[1]
        for tail in _NO_LONGER:
            if rest.lower().endswith(tail):
                rest = rest[: -len(tail)]
        return "cancel " + rest
    return text


def read_cancel(text: str) -> dict | None:
    """The task a sentence cancels ("cancel the dentist task", "remove buy
    milk from my tasks"), as {"intent": "cancel", "about", "kind"?}. A task
    must be said as one (a kind word or the list), or "delete the dentist
    note" and "cancel my subscription" would be read as tasks."""
    text = _cancel_form(text)
    found = _CANCEL.match(text)
    if not found:
        return None
    rest, listed = _OFF_LIST.subn("", found.group("rest").strip(), count=1)
    if _NOT_TASK_TAIL.search(rest):
        return None
    about, said = _split_kind(rest)
    if not (said or listed) or (text.lower().startswith("take ") and not listed):
        return None
    return _task_found("cancel", about, said)


_SNOOZE = re.compile(r"^(?P<verb>snooze|postpone|delay|defer|reschedule|push(?: back)?|move)\s+(?P<rest>.+)$", re.IGNORECASE)
_UNTIL = re.compile(r"\s(?:until|till|til|to|for|by)\s", re.IGNORECASE)


def _snooze_split(rest: str, resolve) -> tuple[str, str, object]:  # noqa: ANN001
    """(the task's words, the time words, the time): the time is read from
    the last " until / to / for " that reads as one; None, with the words
    after the last separator kept, when none does."""
    marks = list(_UNTIL.finditer(rest))
    for mark in reversed(marks):
        said = rest[mark.end() :].strip(" .,")
        due = resolve(said)
        if due is not None:
            return rest[: mark.start()].strip(), said, due
    if marks:
        return rest[: marks[-1].start()].strip(), rest[marks[-1].end() :].strip(" .,"), None
    return rest.strip(), "", None


def read_snooze(text: str, resolve) -> dict | None:  # noqa: ANN001
    """The reminder a sentence snoozes, as {"intent": "snooze", "about",
    "kind"?, "due_at", "said"}; due_at is None when no time reads (asked
    once). `resolve` reads a time phrase through `ai/recognise.py` (this
    module reads no dates). "move" needs a kind word, so "move the sourdough
    note to Cooking" stays a filing; the others need a kind word or a time."""
    found = _SNOOZE.match(text)
    if not found:
        return None
    words, said_when, due = _snooze_split(found.group("rest"), resolve)
    if _NOT_TASK_TAIL.search(words):
        return None
    about, said = _split_kind(words)
    verb = found.group("verb").lower()
    if (verb == "move" and not said) or not (verb == "snooze" or said or due is not None):
        return None
    read = _task_found("snooze", about, said)
    return {**read, "due_at": due, "said": said_when} if read else None


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
                "kind": "reminder", "id": row.id, "text": row.text, "due": row.due_at,
                "where": f"reminder due {row.due_at.strftime('%a')} {row.due_at.day} {row.due_at.strftime('%b')}",
            })
    if kind in (None, "checklist"):
        notes = session.scalars(
            select(Entry).where(
                Entry.content.like("%[ ]%"), Entry.is_deleted.is_(False), Entry.deleted_at.is_(None),
                Entry.is_private.is_(False),
            ).limit(500)
        ).all()
        out.extend(
            {"kind": "checklist", "id": note.id, "text": line.group("item"), "line": line.group(0), "where": f"in {title(note)}", "content": note.content}
            for note in notes
            for line in _BOX.finditer(note.content or "")
        )
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


#: "<item> on|in|from the <note> (note|list)": the item and the note it is on.
#: Read on whitespace squashed to single spaces: words joined by one space
#: leave no two ways to split a run of blanks, so the match stays linear.
_ON_NOTE = re.compile(r"^(?P<item>\S+(?: \S+)*?) (?:on|in|from|off) (?:my|the) (?P<note>\S+(?: \S+)*?)(?: (?:note|list|checklist))?$", re.IGNORECASE)


def pick(session: Session, parsed: dict, title) -> tuple[dict | None, str]:  # noqa: ANN001
    """(the one task named, ""), or (None, what to say instead). A name with a
    note after it ("charger on the Lisbon packing list") is the item on that
    note, split before the lookup (audit 1029 C43)."""
    about = str(parsed.get("about") or "")
    items = _candidates(session, parsed.get("kind"), title)
    split = _ON_NOTE.match(" ".join(about.split()))
    if split and not _match(items, about)[0]:
        note = _stems(split.group("note"))
        if note:
            on_note = [i for i in items if i["kind"] == "checklist" and note <= _stems(i["where"])]
            if on_note:
                found, say = _match(on_note, split.group("item"))
                if found or say:
                    return found, say
    found, say = _match(items, about, parsed.get("kind"))
    return found, say


def _match(items: list[dict], about: str, kind: str | None = None) -> tuple[dict | None, str]:
    wanted = _stems(about)
    if not wanted:
        return None, "Which task do you mean? Say its name, like: tick off buy milk."
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
    where = "reminder" if kind == "reminder" else "open task or reminder"
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


def _label(verb: str, item: dict) -> str:
    return f"{verb} “{item['text']}”" + ("" if item["kind"] == "reminder" else f" ({item['where']})")


def _without_line(content: str, line: str) -> str:
    """`content` with the checklist `line` and its line break taken out."""
    if line + "\n" in content:
        return content.replace(line + "\n", "", 1)
    return content.replace("\n" + line, "", 1) if "\n" + line in content else content.replace(line, "", 1)


def plan_cancel(session: Session, parsed: dict, card, title) -> dict:  # noqa: ANN001
    """The card that bins the reminder named or removes the checklist line
    named, run at once with Undo (a binned reminder is restored, an edited
    note put back), or the question that asks which."""
    item, say = pick(session, parsed, title)
    if item is None:
        return {"line": say}
    label = _label("Cancel", item)
    if item["kind"] == "reminder":
        steps = [{"name": "bin_reminder", "arguments": {"reminder_id": item["id"]}}]
    else:
        steps = [{"name": "edit_note", "arguments": {"note_id": item["id"], "content": _without_line(item["content"], item["line"])}}]
    return {"line": f"{label}.", "card": card(label, steps), "run": True}


def plan_snooze(session: Session, parsed: dict, card, title, said_when, now=None) -> dict:  # noqa: ANN001
    """The card that moves a reminder's time, run at once with Undo. Only a
    reminder has a time, so a checklist line is told so; `said_when` says a
    time against today (`commands.reminder_when`)."""
    item, say = pick(session, parsed, title)
    if item is None:
        return {"line": say}
    if item["kind"] != "reminder":
        return {"line": f"Only reminders can be snoozed, and “{item['text']}” is a checklist line ({item['where']}). Set a reminder for it to give it a time."}
    due = parsed.get("due_at")
    if due is None:
        return {"line": f"Until when? Say it like: snooze {parsed['about']} until Friday."}
    #: The run stores with `restore=True`, which skips the route's past check.
    if now is not None and due <= now:
        return {"line": f"That time has passed. Say a later one, like: snooze {parsed['about']} until tomorrow."}
    when = said_when(due)
    #: "for 2 hours, at 2pm", never "to in 2 hours" (audit 1029 C47).
    label = f"Snooze “{item['text']}” " + (f"for {when[3:]}" if when.startswith("in ") else f"to {when}")
    arguments = {"reminder_id": item["id"], "due_at": due.isoformat(), "was": item["due"].isoformat()}
    return {"line": f"{label}.", "card": card(label, [{"name": "snooze_reminder", "arguments": arguments}]), "run": True}


#: The steps this module runs itself (`commands.run` hands them over).
OWN_STEPS = frozenset({"restore_reminder", "snooze_reminder"})


def run_step(session: Session, name: str, args: dict) -> dict:
    """Run `restore_reminder` (Undo of a cancel) or `snooze_reminder` through
    the reminders' own routes: {"label", "undo"}, or {"error"}."""
    from datetime import datetime

    from fastapi import HTTPException

    from tessellate.api import routes_reminders as rr

    reminder_id = int(args["reminder_id"])
    try:
        if name == "restore_reminder":
            rr.restore_reminder(reminder_id, session)
            return {"label": f"Restored reminder #{reminder_id}", "undo": {"tool": "bin_reminder", "arguments": {"reminder_id": reminder_id}}}
        #: restore=True: the time was checked against the person's clock when
        #: planned, and Undo's old time is usually past (see ReminderUpdate).
        try:
            due = datetime.fromisoformat(str(args["due_at"]))
        except ValueError:
            return {"error": "That time is not a date I can read, such as 31 February."}
        rr.update_reminder(reminder_id, rr.ReminderUpdate(due_at=due, restore=True), session)
    except HTTPException as exc:
        return {"error": str(exc.detail)}
    back = {"reminder_id": reminder_id, "due_at": args["was"], "was": args["due_at"]} if args.get("was") else None
    return {"label": f"Snoozed reminder #{reminder_id}", "undo": {"tool": "snooze_reminder", "arguments": back} if back else None}


def undo_step(name: str, args: dict) -> dict | None:
    """What Undo runs after a completed reminder."""
    if name == "complete_reminder" and args.get("done", True):
        return {"tool": "complete_reminder", "arguments": {"reminder_id": args["reminder_id"], "done": False}}
    return None


