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

_DONE_WORD = r"(?:done|complete|completed|finished|ticked|checked|ticked off|checked off|crossed off|sorted|packed|bought|booked|paid|sent|handled|got)"
_DONE_TAIL = re.compile(rf"(?<!\s)\s+(?:as |to be )?{_DONE_WORD}$", re.IGNORECASE)
_OFF_TAIL = re.compile(r"\s+off(?:\s+(?:of\s+)?(?:my |the |this |that )?(?:list|checklist|to-?do list|todo list|task list|tasks))?$", re.IGNORECASE)
_ON_LIST_TAIL = re.compile(r"\s+(?:on|from|in)\s+(?:my |the )?(?:list|checklist|to-?do list|todo list|task list)$", re.IGNORECASE)
_ARTICLE = re.compile(r"^(?:the |my |our |this |that |a |an |your )+", re.IGNORECASE)
_LEAD_KIND = re.compile(r"^(?:(?P<kind>reminder|task|to-?do|todo|check-?list item|list item|item)\s*(?:to |for |called |named |about |:)?\s*)", re.IGNORECASE)
_TAIL_KIND = re.compile(r"(?<!\s)\s+(?P<kind>reminder|task|to-?do|todo|check-?list item|check-?list|list item|item)s?$", re.IGNORECASE)

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
    if not found:
        return None
    #: "to my todo" names a list, so a task without a time is a line on it (R3-33).
    return {**found, "task": True, "asked": text, **({"on_list": words} if _ON_LIST.search(text) and not tail else {})}


#: "make a checklist note of milk, eggs and bread": the kind of list, then what it holds.
_CHECKLIST_NOTE = re.compile(
    r"^(?:make|create|start|write|build|set up|add)(?: me)? (?:a |an |the )?(?:new )?"
    r"(?P<kind>check-?list|to-?do list|todo list|shopping list|grocery list|packing list)(?: note)?"
    r"(?:\s+(?:called|named|titled)\s+(?P<name>.+?))?\s*(?P<join>of|for|with|containing|including|:)\s*(?P<items>.+)$",
    re.IGNORECASE,
)


def _checklist_items(said: str) -> list[str]:
    """The items of "milk, eggs and bread", capitalised and without repeats."""
    #: A quoted item ("Salt and pepper") keeps its own "and" and commas.
    parts = [re.sub(r"^(?:and|&)\s+", "", part.strip(), flags=re.IGNORECASE) for part in re.split(r'(?:,|;|\band\b|&)(?=(?:[^"]*"[^"]*")*[^"]*$)', said)]
    parts = [_unquote(p) for p in parts if p.strip()]
    return list(dict.fromkeys(p[:1].upper() + p[1:] for p in parts if p))


_CHECKLIST_TITLES = {"checklist": "Checklist", "todolist": "Todo list", "shoppinglist": "Shopping list", "grocerylist": "Grocery list", "packinglist": "Packing list"}
_FOR_PLACE = re.compile(r"^(?:the |my |our |a |an )?(?P<place>[^:]{1,40}?)\s*:\s*(?P<items>.+)$", re.IGNORECASE)


def _checklist_title_items(found: re.Match) -> tuple[str, str]:
    """(the title, the items said) of a checklist sentence: "a checklist for the kitchen: a, b" is
    "Kitchen checklist" with a and b (R9-12), else the name said or the kind's own."""
    kind = found.group("kind").lower().replace("-", "").replace(" ", "")
    title = (found.group("name") or _CHECKLIST_TITLES.get(kind) or kind.capitalize()).strip()
    said = found.group("items")
    place = _FOR_PLACE.match(said) if found.group("join").lower() == "for" and not found.group("name") else None
    if place:
        said, title = place.group("items"), f"{place.group('place').strip()} {_CHECKLIST_TITLES.get(kind, kind).lower()}"
    return title[:1].upper() + title[1:], said


_SUBJECT_ONLY = re.compile(r"^(?:the |my |our |a |an )?(?P<subject>[\w'’-]+(?: [\w'’-]+){0,3})$")


def _subject_checklist(found: re.Match, said: str) -> dict | None:
    """"make a checklist for my trip": one subject and no items is a checklist note named for it ("Trip
    checklist") with one empty line to fill, not a search for the word (B25)."""
    if found.group("join").lower() != "for" or found.group("name") or "," in said or re.search(r"\band\b|&|:", said, re.I):
        return None
    subject = _SUBJECT_ONLY.match(said.strip())
    if not subject:
        return None
    kind = _CHECKLIST_TITLES.get(found.group("kind").lower().replace("-", "").replace(" ", ""), "Checklist")
    name = f"{subject.group('subject').strip()} {kind.lower()}"
    return {"intent": "new_note", "content": f"# {name[:1].upper() + name[1:]}\n\n- [ ] ", "checklist": True}


def read_checklist_note(text: str) -> dict | None:
    """A new note that is a checklist of the items named, as the `new_note` act
    (composer-r8): "make a checklist note of milk, eggs and bread". "for" counts
    only for two or more items, so "a checklist for my trip" is not a list of one."""
    found = _CHECKLIST_NOTE.match(" ".join(str(text or "").split()).rstrip(".!"))
    if not found:
        return None
    title, said = _checklist_title_items(found)
    subject = _subject_checklist(found, said)
    if subject:
        return subject
    items = _checklist_items(said)
    if not items or len(items) > 30 or any(len(i.split()) > 6 for i in items) or (found.group("join").lower() == "for" and len(items) < 2):
        return None
    return {"intent": "new_note", "content": f"# {title}\n\n" + "\n".join(f"- [ ] {i}" for i in items), "checklist": True}


def note_called(session: Session, name: str):  # noqa: ANN201
    """The newest note whose title line is `name` (any case), or None."""
    from tessellate.core.database import Entry

    rows = session.scalars(
        select(Entry).where(Entry.is_deleted.is_(False), Entry.deleted_at.is_(None), Entry.is_private.is_(False)).order_by(Entry.id.desc()).limit(500)
    ).all()
    return next((e for e in rows if (e.content or "").strip().split("\n", 1)[0].lstrip("# ").strip().lower() == name.strip().lower()), None)


def plan_into_list(session: Session, parsed: dict, card) -> dict | None:  # noqa: ANN001
    """A checklist asked for under the name of a note that exists ("make a shopping
    list with flour, yeast and salt") is those items added to that note, run at
    once with Undo, not a second note beside it. None when no note has the title."""
    from tessellate.ai import act_steps

    head, _, body = str(parsed["content"]).partition("\n")
    note = note_called(session, head.lstrip("# "))
    if note is None:
        return None
    wanted = [m.group("item") for m in _BOX.finditer(body)]
    new = [i for i in wanted if not act_steps.already_open(note.content or "", i)]
    name = head.lstrip("# ").strip()
    if not new:
        return {"line": f"Everything you named is already on your {name} note."}
    content = note.content or ""
    for item in new:
        content = act_steps.appended(content, item)
    label = f"Add {', '.join(f'“{i}”' for i in new)} to your {name} note"
    return {"line": f"{label}.", "card": card(label, [{"name": "edit_note", "arguments": {"note_id": note.id, "content": content}}], items=[name])}


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
    #: "tick the charger" (round 1 D3): ticking is not a question, so no trailing
    #: "off" is needed. "check X" asks ("check the weather"), and "cross" and
    #: "strike" are common verbs ("cross link two topics" is a help question),
    #: so those two still need the "off".
    if re.match(r"tick\s+(?!off\b)\S", text, re.IGNORECASE):
        return text.split(" ", 1)[1]
    if low.startswith("complete "):
        return text[len("complete ") :]
    return None


#: Looser ways to say a reminder or task is done; each needs the kind word said
#: ("finish the reminder to call mum"), or "I finished the report" would be an
#: act on a task that was never named (audit 1030 A15).
_DONE_LEADS = ("finish ", "i finished ", "i've finished ", "i have finished ", "done with ", "i'm done with ", "im done with ")


#: "I've booked the car service" (R9-12): a deed that names an open task is that task ticked.
#: Only verbs a task starts with, so "I've seen the film" is no act.
_DEED = re.compile(r"^i(?:'ve|’ve| have)\s+(?P<verb>[a-z]+)\s+(?P<rest>.+)$", re.IGNORECASE)
_DEED_VERBS = {
    "booked": "book", "called": "call", "paid": "pay", "emailed": "email", "sent": "send", "bought": "buy", "renewed": "renew",
    "cleaned": "clean", "fixed": "fix", "ordered": "order", "posted": "post", "returned": "return", "submitted": "submit",
    "phoned": "phone", "texted": "text", "tidied": "tidy", "washed": "wash", "cancelled": "cancel", "replied": "reply",
}


def _deed_rest(text: str) -> str | None:
    """"book the car service" for "I've booked the car service", or None."""
    found = _DEED.match(text.strip().rstrip(".!"))
    verb = _DEED_VERBS.get(found.group("verb").lower()) if found else None
    return f"{verb} {found.group('rest')}" if verb else None


def read_complete(text: str) -> dict | None:
    """The task a sentence completes, as {"intent": "complete", "about",
    "kind"?}, or None. kind is "reminder" or "checklist" when the sentence
    says which, else both are looked in."""
    rest = _complete_rest(text)
    deed = _deed_rest(text) if rest is None else None
    if deed:
        about, said = _split_kind(deed)
        return _task_found("complete", about, said)
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


_UNTICK = re.compile(r"^(?:please )?(?:un-?tick|un-?check|un-?cross|un-?strike|un-?complete|re-?open)\s+(?P<rest>.+)$", re.IGNORECASE)
_NOT_DONE = r"(?:not (?:done|finished|complete|completed|ticked|checked|crossed off)|undone|incomplete|unfinished|unticked|unchecked|open|still open|outstanding|to-?do)"
_MARK_UNDONE = re.compile(rf"^(?:mark|set|flag)\s+(?P<rest>.+?)\s+(?:as |to be |back to |back as )?{_NOT_DONE}$", re.IGNORECASE)


def read_uncomplete(text: str) -> dict | None:
    """The done task a sentence reopens ("untick bread", "mark the passport as
    not done"), as {"intent": "uncomplete", "about", "kind"?}, or None. Read
    before `read_complete`, whose "mark X ... done" would take "not done" as
    the end of the name."""
    found = _UNTICK.match(text.strip()) or _MARK_UNDONE.match(text.strip())
    if not found:
        return None
    rest = _ON_LIST_TAIL.sub("", _OFF_TAIL.sub("", found.group("rest").strip(), count=1), count=1)
    about, said = _split_kind(rest)
    return _task_found("uncomplete", about, said)


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


def _candidates(session: Session, kind: str | None, title, done: bool = False) -> list[dict]:  # noqa: ANN001
    """The open tasks and reminders, or with `done` the ticked ones (what an untick reads)."""
    out: list[dict] = []
    if kind in (None, "reminder"):
        out.extend(_reminders(session, done))
    if kind in (None, "checklist"):
        out.extend(_checklist_lines(session, title, done))
    for item in out:
        item["stems"] = _stems(item["text"])
    return out


def _reminders(session: Session, done: bool) -> list[dict]:
    from tessellate.core.database import Entry, Reminder

    wanted = select(Reminder).where(Reminder.done.is_(done), Reminder.deleted_at.is_(None)).order_by(Reminder.due_at.desc() if done else Reminder.due_at).limit(500)
    rows = session.scalars(wanted).all()
    linked = {r.entry_id for r in rows if r.entry_id is not None}
    private = set(session.scalars(select(Entry.id).where(Entry.id.in_(linked), Entry.is_private.is_(True)))) if linked else set()
    return [
        {"kind": "reminder", "id": row.id, "text": row.text, "due": row.due_at,
         "where": f"reminder due {row.due_at.strftime('%a')} {row.due_at.day} {row.due_at.strftime('%b')}"}
        for row in rows if row.entry_id not in private
    ]


def _checklist_lines(session: Session, title, done: bool) -> list[dict]:  # noqa: ANN001
    from tessellate.core.database import Entry

    marked = (Entry.content.like("%[x]%") | Entry.content.like("%[X]%")) if done else Entry.content.like("%[ ]%")
    notes = session.scalars(
        select(Entry).where(marked, Entry.is_deleted.is_(False), Entry.deleted_at.is_(None), Entry.is_private.is_(False)).limit(500)
    ).all()
    return [
        {"kind": "checklist", "id": note.id, "text": line.group("item"), "line": line.group(0), "where": f"in {title(note)}", "content": note.content}
        for note in notes
        for line in (_TICKED if done else _BOX).finditer(note.content or "")
    ]


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
    note, split before the lookup (audit 1029 C43). A name only a ticked line
    carries is said to be ticked, not missing (audit 1031 C41)."""
    about = str(parsed.get("about") or "")
    reopening = parsed.get("intent") == "uncomplete"
    items = _candidates(session, parsed.get("kind"), title, done=reopening)
    split = _ON_NOTE.match(" ".join(about.split()))
    item, note = (split.group("item"), split.group("note")) if split else (about, "")
    found, say = _on_note(items, about, item, note) if split else (None, "")
    if not (found or say):
        found, say = _match(items, about, parsed.get("kind"), "ticked task or reminder" if reopening else "")
    if found is None and say.startswith("I found no") and reopening:
        say = _not_ticked(session, parsed, title) or say
    elif found is None and say.startswith("I found no") and parsed.get("kind") != "reminder":
        say = _already_ticked(session, item, note, title) or say
    return found, say


def _on_note(items: list[dict], about: str, item: str, note: str) -> tuple[dict | None, str]:
    """The item on the note named, when the whole phrase is no task's name."""
    wanted = _stems(note)
    if not wanted or _match(items, about)[0]:
        return None, ""
    on_note = [i for i in items if i["kind"] == "checklist" and wanted <= _stems(i["where"])]
    return _match(on_note, item) if on_note else (None, "")


_TICKED = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+\[[xX]\][ \t]+(?P<item>\S.*?)[ \t]*$", re.MULTILINE)


def _already_ticked(session: Session, about: str, on_note: str, title) -> str:  # noqa: ANN001
    """"“Charger” is already ticked off (in Lisbon packing list).", or "" when
    no ticked line carries the name: a ticked item is not "not found"
    (audit 1031 C41)."""
    from tessellate.core.database import Entry

    wanted, note = _stems(about), _stems(on_note)
    if not wanted:
        return ""
    notes = session.scalars(
        select(Entry).where(
            Entry.content.like("%[x]%") | Entry.content.like("%[X]%"), Entry.is_deleted.is_(False), Entry.deleted_at.is_(None),
            Entry.is_private.is_(False),
        ).limit(500)
    ).all()
    for entry in notes:
        where = title(entry)
        if note and not note <= _stems(where):
            continue
        for line in _TICKED.finditer(entry.content or ""):
            if wanted <= _stems(line.group("item")):
                return f"“{line.group('item')}” is already ticked off (in {where})."
    return ""


def _not_ticked(session: Session, parsed: dict, title) -> str:  # noqa: ANN001
    """"“Charger” is not ticked off (in Lisbon packing list)." for an untick of an open item."""
    found, _ = _match(_candidates(session, parsed.get("kind"), title), str(parsed.get("about") or ""))
    return f"{_name(found)} is not ticked off." if found else ""


def _match(items: list[dict], about: str, kind: str | None = None, what: str = "") -> tuple[dict | None, str]:
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
    where = what or ("reminder" if kind == "reminder" else "open task or reminder")
    return None, f"I found no {where} named “{about}”."


# --- planning -----------------------------------------------------------------------------------


_ON_NOTE_TAIL = re.compile(r" on the .+$")
_NAME_SPLIT = re.compile(r"\s*(?:,|;|&|\band\b|\bthen\b|\bplus\b|\balso\b)\s*", re.IGNORECASE)


def _names_in(about: str) -> list[str]:
    """The task names a sentence lists ("email landlord and call plumber"), each on
    the note the whole list names ("... on the packing list")."""
    whole = " ".join(about.split())
    split = _ON_NOTE.match(whole)
    item, note = (split.group("item"), split.group("note")) if split else (whole, "")
    return [f"{p}{f' on the {note}' if note else ''}" for p in (q.strip() for q in _NAME_SPLIT.split(item)) if p]


def pick_each(session: Session, parsed: dict, title) -> tuple[list[dict], list[dict], str]:  # noqa: ANN001
    """(the tasks named, the names left out as card `skipped` rows, what to say
    when none was found). A name that is one
    task's whole name ("salt and pepper") is that one task; otherwise a list
    ("email landlord and call plumber") is each of them (D10)."""
    item, say = pick(session, parsed, title)
    if item is not None:
        return [item], [], ""
    names = _names_in(str(parsed.get("about") or ""))
    if len(names) < 2:
        return [], [], say
    found: list[dict] = []
    unsaid: list[str] = []
    left: list[dict] = []
    for name in names:
        one, why = pick(session, {**parsed, "about": name}, title)
        if one is None:
            unsaid.append(why)
            left.append({"reason": "unfound" if why.startswith("I found no") else "unclear", "name": _ON_NOTE_TAIL.sub("", name)})
        elif not any(one["kind"] == f["kind"] and one["id"] == f["id"] and one.get("line") == f.get("line") for f in found):
            found.append(one)
    return found, left, " ".join(unsaid)


def _the_names(items: list[dict]) -> str:
    named = [f"“{i['text']}”" for i in items]
    return named[0] if len(named) == 1 else ", ".join(named[:-1]) + " and " + named[-1]


def _each_label(head: str, tail: str, items: list[dict]) -> str:
    where = "" if len(items) > 1 or items[0]["kind"] == "reminder" else f" ({items[0]['where']})"
    return f"{head} {_the_names(items)}{f' {tail}' if tail else ''}{where}"


def _each_steps(items: list[dict], reminder_step, rewrite) -> list[dict]:  # noqa: ANN001
    """One step per reminder, and one edit per note that holds checklist lines: two
    lines on one note are changed in one edit, or the second would undo the first."""
    steps: list[dict] = []
    edits: dict[int, dict] = {}
    for item in items:
        if item["kind"] == "reminder":
            steps.append(reminder_step(item))
            continue
        step = edits.get(item["id"])
        if step is None:
            step = edits[item["id"]] = {"name": "edit_note", "arguments": {"note_id": item["id"], "content": item["content"]}}
            steps.append(step)
        step["arguments"]["content"] = rewrite(step["arguments"]["content"], item["line"])
    return steps


def _plan_each(session: Session, parsed: dict, card, title, head: str, tail: str, reminder_step, rewrite) -> dict:  # noqa: ANN001
    items, left, said = pick_each(session, parsed, title)
    if not items:
        #: "the first one" is still an ordinal when no list was shown to count from.
        return {"line": NO_LIST if ordinal_of(parsed.get("about")) else said}
    label = _each_label(head, tail, items)
    return {"line": f"{label}.", "card": card(label, _each_steps(items, reminder_step, rewrite), left)}


def plan_complete(session: Session, parsed: dict, card, title) -> dict:  # noqa: ANN001
    """The card that completes the task or tasks named, run at once with Undo, or
    the question that asks which. `card` is `commands._card` and `title` the one
    reader's (`composer_frame.note_title`), passed in because this module sits
    below commands."""
    return _plan_each(session, parsed, card, title, "Mark", "done",
                      lambda i: {"name": "complete_reminder", "arguments": {"reminder_id": i["id"], "done": True}},
                      lambda content, line: content.replace(line, line.replace("[ ]", "[x]", 1), 1))


def plan_uncomplete(session: Session, parsed: dict, card, title) -> dict:  # noqa: ANN001
    """The card that reopens the ticked task or tasks named (a done reminder, or a
    `[x]` line made `[ ]` again), run at once with Undo, or the question that asks which."""
    return _plan_each(session, parsed, card, title, "Mark", "not done",
                      lambda i: {"name": "complete_reminder", "arguments": {"reminder_id": i["id"], "done": False}},
                      lambda content, line: content.replace(line, re.sub(r"\[[xX]\]", "[ ]", line, count=1), 1))


def plan_cancel(session: Session, parsed: dict, card, title) -> dict:  # noqa: ANN001
    """The card that bins the reminders named or removes the checklist lines
    named, run at once with Undo (a binned reminder is restored, an edited note
    put back), or the question that asks which."""
    return _plan_each(session, parsed, card, title, "Cancel", "", lambda i: {"name": "bin_reminder", "arguments": {"reminder_id": i["id"]}}, _without_line)


def _without_line(content: str, line: str) -> str:
    """`content` with the checklist `line` and its line break taken out."""
    if line + "\n" in content:
        return content.replace(line + "\n", "", 1)
    return content.replace("\n" + line, "", 1) if "\n" + line in content else content.replace(line, "", 1)


def plan_snooze(session: Session, parsed: dict, card, title, said_when, now=None) -> dict:  # noqa: ANN001
    """The card that moves a reminder's time, with Undo once confirmed. Only a
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
    #: Read on the person's clock (aware), compared and stored as wall time like `now` (naive).
    due = due.replace(tzinfo=None)
    #: The run stores with `restore=True`, which skips the route's past check.
    if now is not None and due <= now:
        return {"line": f"That time has passed. Say a later one, like: snooze {parsed['about']} until tomorrow."}
    when = said_when(due)
    #: "for 2 hours, at 2pm", never "to in 2 hours" (audit 1029 C47).
    label = f"Snooze “{item['text']}” " + (f"for {when[3:]}" if when.startswith("in ") else f"to {when}")
    arguments = {"reminder_id": item["id"], "due_at": due.isoformat(), "was": item["due"].isoformat()}
    return {"line": f"{label}.", "card": card(label, [{"name": "snooze_reminder", "arguments": arguments}])}


#: The steps this module runs itself (`commands.run` hands them over).
OWN_STEPS = frozenset({"restore_reminder", "snooze_reminder"})


def _named(session: Session, reminder_id: int) -> str:
    """A reminder by its words, never its number (audit 1028 E64)."""
    from tessellate.core.database import Reminder

    held = session.get(Reminder, reminder_id)
    return f"“{held.text[:60]}”" if held is not None and held.text else "that reminder"


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
            return {"label": f"Restored reminder {_named(session, reminder_id)}", "undo": {"tool": "bin_reminder", "arguments": {"reminder_id": reminder_id}}}
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
    return {"label": f"Snoozed reminder {_named(session, reminder_id)}", "undo": {"tool": "snooze_reminder", "arguments": back} if back else None}


def undo_step(name: str, args: dict) -> dict | None:
    """What Undo runs after a completed (or reopened) reminder: the other way."""
    if name == "complete_reminder":
        return {"tool": "complete_reminder", "arguments": {"reminder_id": args["reminder_id"], "done": not args.get("done", True)}}
    return None




#: A note a "todo" is added to: its title, as a person names the list.
_TODO_TITLE = re.compile(r"^(?:my |the )?(?:to-?do|to do|tasks?|check-?list)(?: list)?s?$", re.IGNORECASE)


def todo_note(session: Session):  # noqa: ANN201
    """The newest note called todo, to-do, tasks or checklist, or None."""
    from tessellate.core.database import Entry

    rows = session.scalars(
        select(Entry).where(Entry.is_deleted.is_(False), Entry.deleted_at.is_(None), Entry.is_private.is_(False)).order_by(Entry.id.desc()).limit(500)
    ).all()
    return next((e for e in rows if _TODO_TITLE.match(_ARTICLE.sub("", (e.content or "").strip().split("\n", 1)[0].lstrip("# ").strip()).strip())), None)


def plan_task_line(session: Session, parsed: dict, card, title, confirm) -> dict:  # noqa: ANN001
    """"add buy stamps to my todo": a checklist line on the note called todo,
    run at once with Undo; no such note is offered, never a reminder time asked
    (R3-33). `card` is `commands._card`, `confirm` its Confirm line."""
    from tessellate.ai import act_steps

    item = _unquote(str(parsed["on_list"]))
    item = item[:1].upper() + item[1:]
    note = todo_note(session)
    if note is None:
        label = f"Make a note “Todo” with “{item}” on it"
        return {"line": f"You have no todo note yet. {confirm(label)} Or say when, and I will set a reminder instead.",
                "card": card(label, [{"name": "create_note", "arguments": {"content": f"# Todo\n\n- [ ] {item}"}}])}
    name = title(note)
    if any(_stems(m.group("item")) == _stems(item) for m in _BOX.finditer(note.content or "")):
        return {"line": f"“{item}” is already open on your {name} note."}
    body = (note.content or "").rstrip()
    last = next((x for x in reversed(body.split("\n")) if x.strip()), "")
    content = act_steps.appended(body, item) if re.match(r"\s*[-*+]\s+\[[ xX]\]", last) else f"{body}\n\n- [ ] {item}"
    label = f"Add “{item}” to your {name} note"
    return {"line": f"{label}.", "card": card(label, [{"name": "edit_note", "arguments": {"note_id": note.id, "content": content}}], items=[name])}


_ORDINAL_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "last": -1}
_ORDINAL_NAME = re.compile(
    rf"^(?:the |number |no\.? |#)*(?P<nth>{'|'.join(_ORDINAL_WORDS)}|\d{{1,2}}(?:st|nd|rd|th)?)(?: (?:one|item|task|thing|line))?$", re.IGNORECASE
)
_LIST_LINE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(?P<item>\S.*?)\s*$", re.MULTILINE)


NO_LIST = "I do not have a list in front of me to count from. Name the task, like: tick buy stamps."


def ordinal_of(about: str) -> int | None:
    """1-based position ("the first one", "number 2"), -1 for the last, or None
    when the name is a task's own words."""
    found = _ORDINAL_NAME.match(" ".join(str(about or "").split()))
    if not found:
        return None
    word = found.group("nth").lower()
    return _ORDINAL_WORDS.get(word) or int(re.sub(r"\D", "", word))


def counted_from(parsed: dict, history: list[dict] | None) -> dict:
    """`parsed` with an ordinal task ("the first one") named by the task at that
    place in the list the last answer showed; left as it is when there is none."""
    place = ordinal_of(parsed.get("about")) if parsed.get("intent") in ("complete", "uncomplete", "cancel") else None
    shown = item_in(place, str((history or [{}])[-1].get("answer") or "")) if place else None
    return {**parsed, "about": shown} if shown else parsed


def items_in(answer: str) -> list[str]:
    """Every list item the answer showed, in order, parsed once."""
    items = []
    for line in _LIST_LINE.finditer(answer or ""):
        text = re.sub(r"\[([^\]]{1,300})\]\([^)]{0,1000}\)", r"\1", line.group("item"))
        text = re.sub(r"[*_`]+|\s*\[[^\]]{0,300}\]\s*$", "", text)
        text = re.split(r"\s+\(|:\s", text, maxsplit=1)[0].strip(" .;")
        if text:
            items.append(text)
    return items


def item_in(position: int, answer: str) -> str | None:
    """The task at `position` in the list the last answer showed, or None when
    that answer showed no list that long (R3-33: "tick the first one")."""
    items = items_in(answer)
    if not items or abs(position) > len(items) or position == 0:
        return None
    return items[position - 1] if position > 0 else items[-1]
