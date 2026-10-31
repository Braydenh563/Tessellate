"""Slot-first answers (audit 1029 C22, C23, C33; INBOX 1357).

A question has a slot, and the item that answers it must hold it: a ticked or
unticked task for "did I pay X", an open task for "what is left on X", a
dated line that says the thing for "how long since I called mum". When no item
holds the slot the answer says so; it never offers a near item (the first
list, the first to-do) as if it were the answer. No model, and the same with
one on. Every pattern here is anchored with one `.+` at the end and the rest
is read in code, so it stays linear (`tests/test_composer_regex_linear_1029.py`).
"""

from __future__ import annotations

import functools
import re
from collections.abc import Callable
from datetime import date
from typing import NamedTuple

from tessellate.ai import composer, composer_doings, composer_lists, factgraph, realise, recognise
from tessellate.ai import when as when_words

_DID = re.compile(r"^(?:did|have|has)\s+(?:i|we)\s+(?:already\s+|yet\s+|ever\s+)?(.+)$", re.I)
_LEFT = re.compile(r"^what(?:'s|\s+is|\s+else\s+is|\s+is\s+still)?\s+(?:still\s+)?(?:left|remaining|outstanding|open)\s*(.*)$", re.I)
#: "What's still on my grocery list", "what haven't I bought from it yet":
#: the open items, not the whole list (2026-10-30 probe).
_STILL_ON = re.compile(
    r"^what(?:'s|\s+is|\s+are)?\s+(?:still\s+(?:unchecked\s+|unticked\s+|open\s+|left\s+|to\s+(?:buy|do|get)\s+)?((?:on|in)\s+.+)|(?:have\s*n[o']t\s+i|haven't\s+i|have\s+i\s+not)\s+(?:bought|got|ticked(?:\s+off)?|packed|done)(?:\s+yet)?\s+((?:on|from|in)\s+.+?)(?:\s+yet)?)$",
    re.I,
)
#: "Is buying mint still on my list", "is comparing headphones still
#: outstanding": a yes or no about one open item (stress run 2026-10-30
#: quoted a journal line, or dumped the whole list).
_IS_STILL = re.compile(
    r"^is\s+(\S+(?:\s\S+)*?)\s+still\s+(?:on\s+(?:my|the)\b.*|outstanding|open|pending|to\s+do|unticked|unchecked|left)$",
    re.I,
)
_IS_DONE = re.compile(r"^(?:is|has)\s+(\S+(?:\s\S+)*?)\s+(?:been\s+)?(?:ticked(?:\s+off)?|done|finished|completed)(?:\s+yet)?$", re.I)
#: A line that says the doing did not happen ("Didn't buy replacement mint").
_UNDONE = re.compile(r"\b(?:did\s*n[o']t|didnt|not|never|forgot|failed|yet\s+to)\b", re.I)
_NEED = re.compile(r"^what\s+(?:else\s+)?(?:do|should)\s+i\s+(?:still\s+)?(?:need|have)\s+to\s+(.+)$", re.I)
_SINCE = re.compile(r"^how\s+long\s+(?:has\s+it\s+been\s+)?since\s+(?:i|we)\s+(?:last\s+)?(.+)$", re.I)
#: Words that carry no subject: the framing of the request itself.
_FILLER = frozenset({
    "the", "a", "an", "my", "our", "on", "for", "to", "of", "in", "at", "with", "list", "lists", "note", "notes", "item", "items",
    "task", "tasks", "checklist", "todo", "still", "do", "i", "we", "it", "that", "this", "yet", "already", "ever", "last",
})
_MARKERS = (" for ", " before ", " to ", " on ", " at ")


def _stems(text: str) -> list[str]:
    seen: list[str] = []
    for w in composer._words(text):  # noqa: SLF001  # the composer's own stemmer, so question and note read alike
        if w not in _FILLER and w not in seen:
            seen.append(w)
    return seen


def _holds(sentence, stems: list[str]) -> bool:  # noqa: ANN001
    have = set(composer._words(sentence.text))  # noqa: SLF001
    return bool(stems) and all(s in have for s in stems)


def _list_subject(rest: str) -> list[str]:
    """The stems of what a "left" question names: "on the Lisbon packing
    list" -> lisbon, pack; "to do for Atlas" -> atlas (the verb before the
    marker is the asking, not the subject)."""
    rest = " " + " ".join(rest.lower().split()) + " "
    cut = [rest.find(m) for m in _MARKERS if rest.find(m) >= 0]
    if cut and not rest.strip().startswith(("on ", "for ", "at ")):
        rest = rest[min(cut):]
    return _stems(rest) or [w for w in ("todo", "checklist") if w in rest.split()]


def _title_holds(view, stems: list[str]) -> bool:  # noqa: ANN001
    return bool(stems) and all(s in view.title_words for s in stems)


#: What is bought is on the shopping list: "what do I need to buy" names a
#: verb, and the list that verb is about (audit 1030 Z56).
_VERB_LISTS = {"buy": (["shop"], ["grocer"]), "bought": (["shop"], ["grocer"]), "get": (["shop"], ["grocer"])}


def _tasks(views: list, stems: list[str]) -> tuple[list, list]:
    """`(open, done)` task sentences of the best note the stems name: one
    whose title holds every stem first, then one filed or worded so
    (`composer._notes_named_by`, the reader "still open" questions share)."""
    for want in (stems, *_VERB_LISTS.get(stems[0], ())) if stems else ():
        named = composer._notes_named_by(views, set(want))  # noqa: SLF001
        for view in sorted(named, key=lambda v: (not _title_holds(v, want), v.rank)):
            tasks = [s for s in view.sentences if s.kind == "task"]
            if tasks:
                #: A box never ticked but done in a later note is done here
                #: too: one item, one state (fable-eye F3).
                later = [t for t in tasks if recorded_later(views, view, t)]
                return [(view, t) for t in tasks if not t.done and t not in later], [(view, t) for t in tasks if t.done or t in later]
    return [], []


#: A sentence that sets something to do: "Book the train to Leeds",
#: "Need to call the bank".
_TO_DO = re.compile(r"^\s*(?:[-*]\s*)?(?:(?:i\s+)?(?:need|have|want|plan) to\s+|remember to\s+|don't forget to\s+)?(?:go|buy|call|book|get|ask|pay|send|bring|check|email|text|draft|write|pack|order|fix|renew|sort|finish|print|post|return|clean)\b", re.I)


def _left_in_prose(out, stems: list[str], views: list) -> bool:  # noqa: ANN001
    """No checklist for it, but a note on it says what to do in sentences
    ("Book the train to Leeds and then draft the itinerary"): those, not "no
    checklist has anything left to tick" (2026-10-30 probe)."""
    for view in sorted(views, key=lambda v: v.rank):
        if not all(st in view.title_words or st in view.words for st in stems):
            continue
        todo = [s for s in view.sentences if s.kind == "prose" and _TO_DO.match(s.text)]
        if todo:
            out.lines.append(f"There is no checklist for it, but {composer_lists._title(view)} has this to do:")  # noqa: SLF001
            for s in todo[:6]:
                out.lines.append(f"- {s.text.strip()}")
                composer_lists._cite(out, view, s, s.text)  # noqa: SLF001
            return True
    return False


def _left(out, rest: str, views: list, today: date) -> bool:  # noqa: ANN001
    stems = _list_subject(rest)
    if not stems:
        return False
    open_, done = _tasks(views, stems)
    #: No list the subject names ("what do I need to buy" names a verb, not a
    #: list): the composer's own readers answer, as they did before the slots.
    if not open_ and not done:
        return _left_in_prose(out, stems, views)
    view = open_[0][0] if open_ else done[0][0]
    title = composer_lists._title(view)  # noqa: SLF001
    if not open_:
        out.lines.append(f"Nothing is left on {title}: all {len(done)} items are done.")
    else:
        out.lines.append(f"{len(open_)} still to do on {title}:")
        for v, task in open_[:12]:
            text = re.sub(r"^\s*[-*]\s*\[ \]\s*", "", task.text).strip()
            out.lines.append(f"- {text}")
            composer_lists._cite(out, v, task, text)  # noqa: SLF001
    _say_recorded(out, views, done, today)
    return True


def _say_recorded(out, views: list, done: list, today: date) -> None:  # noqa: ANN001
    """The items a later note records as done though their box is not ticked."""
    for v, task in done:
        if task.done or not (got := recorded_later(views, v, task)):
            continue
        out.lines.append(f"{_note_of(got[0], today).capitalize()} records “{_DOING_END.split(_task_name(task), 1)[0]}” as done, though its box is not ticked.")
        composer_lists._cite(out, got[0], got[1], out.lines[-1])  # noqa: SLF001


_TICKED_WORDS = frozenset({"checked", "ticked", "done", "bought", "got", "completed", "finished", "packed"})
_OPEN_WORDS = frozenset({"left", "open", "unchecked", "unticked", "remaining", "outstanding"})
_COUNT_VERBS = frozenset({"are", "is", "have", "has", "did", "do", "were", "was"})
_COUNT_FILLER = frozenset({"of", "the", "my", "items", "item", "things", "thing", "tasks", "boxes", "on", "in", "list"})


def _counted_ask(q: str) -> tuple[list[str], bool] | None:
    """"How many grocery items are checked off" -> (grocery stems, True);
    "how many things on the packing list are still open" -> (packing, False).
    Read word by word (CodeQL)."""
    tokens = re.sub(r"[^\w' ]", " ", q.lower()).split()
    if tokens[:2] != ["how", "many"]:
        return None
    at = next((i for i, t in enumerate(tokens) if i > 1 and t in _COUNT_VERBS), None)
    tail = set(tokens[at:]) if at else set()
    ticked, still = bool(tail & _TICKED_WORDS), bool(tail & _OPEN_WORDS) or "to do" in " ".join(tokens[at or 0:])
    if at is None or ticked == still:
        return None
    stems = _stems(" ".join(t for t in tokens[2:at] if t not in _COUNT_FILLER))
    return (stems, ticked) if stems else None


def _counted(out, q: str, views: list) -> bool:  # noqa: ANN001
    """How many of a checklist's items are ticked, or still open, named."""
    asked = _counted_ask(q)
    if not asked:
        return False
    open_, done = _tasks(views, asked[0])
    if not open_ and not done:
        return False
    picked = done if asked[1] else open_
    view = (open_ or done)[0][0]
    names = [re.sub(r"^\s*[-*]?\s*\[[ xX]\]\s*", "", t.text).strip().rstrip(".") for _v, t in picked]
    state = "ticked off" if asked[1] else "still open"
    total = len(open_) + len(done)
    line = f"{realise.count_word(len(picked)).capitalize()} of {realise.count_word(total)} {'is' if len(picked) == 1 else 'are'} {state} on {composer_lists._title(view)}"  # noqa: SLF001
    line += f": {realise.join_items(names)}." if names else "."
    out.lines.append(line)
    for v, task in picked:
        composer_lists._cite(out, v, task, line)  # noqa: SLF001
    return True


#: "Is the passport packed", "is everything bought yet", "what's unpacked",
#: "what have I ticked off": one checklist state, read the same by every
#: phrasing (audit 1030 Z56).
_STATE = r"packed|bought|ticked(?:\s+off)?|checked(?:\s+off)?|done|finished|completed|sorted|booked|crossed\s+off"
_IS_STATE = re.compile(rf"^(?:is|are|has|have)\s+(?:all\s+(?:of\s+)?)?(?P<obj>.+?)\s+(?:been\s+)?(?P<verb>{_STATE})(?:\s+(?:yet|already))?$", re.I)
_UN_STATE = re.compile(r"^what(?:'s|\s+is|\s+are)?\s+(?:still\s+)?(?:un(?P<un>packed|ticked|checked|bought|done)|not\s+(?P<not>packed|ticked|checked|bought|done)(?:\s+yet)?)$", re.I)
_TICKED_SO_FAR = re.compile(r"^what(?:'s|\s+have\s+i|\s+did\s+i|\s+i've)\s+(?:i\s+)?(?:ticked|checked|crossed)\s+off(?:\s+(?:so\s+far|already|yet))?$", re.I)
_EVERYTHING = frozenset({"everything", "all", "it all", "all of it", "everything on the list"})


def _task_name(task) -> str:  # noqa: ANN001
    return re.sub(r"^\s*[-*]?\s*\[[ xX]\]\s*", "", task.text).strip().rstrip(".")


def _all_of(out, open_: list, done: list) -> None:  # noqa: ANN001
    """Whether a whole list is done, said with what is open."""
    view = (open_ or done)[0][0]
    title = composer_lists._title(view)  # noqa: SLF001
    if open_:
        names = realise.join_items([_task_name(t).lower() for _v, t in open_])
        out.lines.append(f"Not yet: {realise.count_word(len(open_))} of {realise.count_word(len(open_) + len(done))} still open on {title}: {names}.")
    else:
        out.lines.append(f"Yes, all {realise.count_word(len(done))} items on {title} are ticked off.")
    for v, task in open_ or done:
        composer_lists._cite(out, v, task, out.lines[-1])  # noqa: SLF001


def _item_state(out, stems: list[str], views: list, today: date) -> bool:  # noqa: ANN001
    """Yes or no for one item: its own checklist line, or the later note that
    records it."""
    for view in sorted(views, key=lambda v: v.rank):
        for task in (s for s in view.sentences if s.kind == "task" and _holds(s, stems)):
            if not task.done and (got := recorded_later(views, view, task)):
                _later_line(out, got, view, today, asks_done=True)
            else:
                _verdict(out, view, task, "")
            return True
    return False


def _is_state(out, found, views: list, today: date) -> bool:  # noqa: ANN001
    obj, verb = " ".join(found.group("obj").lower().split()), found.group("verb").lower().split()[0]
    if obj in _EVERYTHING:
        open_, done = _tasks(views, _stems(verb))
        if open_ or done:
            _all_of(out, open_, done)
            return True
        return False
    return _item_state(out, _stems(obj), views, today)


def _ticked_so_far(out, views: list) -> bool:  # noqa: ANN001
    """Every ticked item, by the note it is in."""
    ticked = [(v, s) for v in sorted(views, key=lambda v: v.rank) for s in v.sentences if s.kind == "task" and s.done]
    if not ticked:
        return False
    notes = len({id(v) for v, _s in ticked})
    out.lines.append(f"You have ticked off {realise.count_word(len(ticked))} item{'s' if len(ticked) != 1 else ''} across {realise.count_word(notes)} note{'s' if notes != 1 else ''}:")
    for v, s in ticked[:12]:
        out.lines.append(f"- {_task_name(s)}, in {composer_lists._title(v)}")  # noqa: SLF001
        composer_lists._cite(out, v, s, _task_name(s))  # noqa: SLF001
    return True


def asks_state(question: str) -> bool:
    """Whether `question` asks a checklist's state by its verb ("what's
    unpacked", "what have I ticked off")."""
    q = " ".join(str(question or "").lower().split()).rstrip("?.!")
    return bool(_UN_STATE.match(q) or _TICKED_SO_FAR.match(q))


#: "Is the library membership renewed", "is the laptop backed up", "is the
#: invoice paid": the be-verb and a participle ask what "did I renew it" asks
#: (second eye F9).
_IS_PASSIVE = re.compile(
    r"^(?:is|are|was|were|has|have)\s+(?:the\s+|my\s+|our\s+)?(?P<thing>.+?)\s+(?:been\s+)?(?P<verb>\w{3,}ed|paid|sent|bought|made|done|written|taken)(?:\s+(?:up|off|out|in|away|down))?(?:\s+(?:yet|already))?$",
    re.I,
)


def _was_done(out, found, views: list, today: date) -> bool:  # noqa: ANN001
    """The did-I answer for a passive question; False with no line that says
    the doing, so the ordinary readers keep what is not a checklist matter."""
    verb, thing = found.group("verb").lower(), found.group("thing")
    obj = _stems(thing)
    if not obj or _first_did(views, _verb_forms(verb), obj) is None:
        return False
    return _did(out, f"{verb} {thing}", views, today)


def _state(out, q: str, views: list, today: date) -> bool:  # noqa: ANN001
    """A checklist's state asked by its verb; False when `q` is not one."""
    if m := _IS_STATE.match(q):
        return _is_state(out, m, views, today)
    if m := _IS_PASSIVE.match(q):
        return _was_done(out, m, views, today)
    if m := _UN_STATE.match(q):
        return _left(out, m.group("un") or m.group("not"), views, today)
    return bool(_TICKED_SO_FAR.match(q)) and _ticked_so_far(out, views)


def _verdict(out, view, task, verb_said: str) -> None:  # noqa: ANN001
    text = re.sub(r"^\s*[-*]\s*\[[ xX]\]\s*", "", task.text).strip()
    if task.done:
        line = f"Yes, “{text}” is ticked off in {composer_lists._title(view)}."  # noqa: SLF001
    else:
        line = f"Not yet: “{text}” is still open in {composer_lists._title(view)}."
    out.lines.append(line)
    composer_lists._cite(out, view, task, line)  # noqa: SLF001


@functools.lru_cache(maxsize=256)
def _verb_forms(word: str) -> frozenset[str]:
    """Every stem a verb is written as: "pay" is also "paid", "write" is
    "wrote" and "written", so "did I pay the phone bill" meets "Paid the
    phone bill" (audit 1030 Z18)."""
    forms = {word.lower()}
    for lemma, past, participle in factgraph._IRREGULAR:  # noqa: SLF001
        every = {lemma, participle, *past.split()}
        if word.lower() in every:
            forms |= every
    return frozenset(st for f in forms for st in _stems(f))


def _says_verb(sentence, forms: frozenset[str]) -> bool:  # noqa: ANN001
    return not forms or bool(forms & set(composer._words(sentence.text)))  # noqa: SLF001


def _first_did(views: list, verb: frozenset[str], obj):  # noqa: ANN001
    """The (view, sentence) that says the doing: a task that holds the object
    and the verb at once, else prose that does, else a task that holds the
    object alone ("[ ] Buy mint" does not answer "did I water the mint"
    while a line says the watering)."""
    said = task = None
    for view in sorted(views, key=lambda v: v.rank):
        for s in view.sentences:
            if not _holds(s, obj):
                continue
            if s.kind == "task":
                task = task or (view, s)
                if _says_verb(s, verb):
                    return view, s
            elif _says_verb(s, verb):
                said = said or (view, s)
    return said or task


def _done_later(views: list, verb: frozenset[str], obj, task_view):  # noqa: ANN001, ANN202
    """A line written no earlier than an open task that says the doing
    ("Renewed my library membership today" beside "[ ] Renew library
    membership"): the box was never ticked, the later note is the record."""
    since = task_view.written
    for view in sorted(views, key=lambda v: v.written or since, reverse=True):
        if since and view.written and view.written < since:
            continue
        for s in view.sentences:
            if s.kind != "task" and _holds(s, obj) and _says_verb(s, verb) and not (_INTENT.search(s.text) or _UNDONE.search(s.text)):
                return view, s
    return None


#: Where an open task's own words stop being the doing ("Renew library
#: membership - due 28 October" is renew + library membership).
_DOING_END = re.compile(r"\s+(?:-|due|by|on|before|at)\b|[,.;:(]", re.I)


_OPEN_BOX = re.compile(r"^\s*[-*]\s*\[ \]\s*(.+)$", re.M)


def open_doings(content: str) -> list[str]:
    """What each unticked checkbox line asks ("Renew library membership"),
    so the route can fetch the notes that may record it done."""
    found = [_DOING_END.split(m.group(1).strip(), 1)[0].strip() for m in _OPEN_BOX.finditer(content or "")]
    return [d for d in found if len(d.split()) >= 2]


def asks_open(question: str) -> bool:
    """Whether `question` asks a checklist item's state (did, still, left, done)."""
    q = composer_lists._q(question)  # noqa: SLF001
    return any(p.match(q) for p in (_DID, _NEED, _LEFT, _STILL_ON, _IS_STILL, _IS_DONE))


def recorded_later(views: list, view, task):  # noqa: ANN001, ANN202
    """(note, sentence) of a later note that records the doing of an open
    checklist line, or None. One item has one state: the open list, the
    yes or no and the reminder offer all ask this (fable-eye F3, F15)."""
    if task.kind != "task" or task.done or not view.written:
        return None
    words = _DOING_END.split(re.sub(r"^\s*[-*]?\s*\[[ xX]\]\s*", "", task.text).strip(), 1)[0].split()
    if len(words) < 2 or not (obj := _stems(_asked_thing(words))):
        return None
    return _done_later([v for v in views if v is not view], _verb_forms(words[0]), obj, view)


#: A line that plans the doing is not a record of it: "did I pay rent"
#: beside "Remember to pay rent on the 1st" is "not yet" (audit 1030 Z19).
_INTENT = re.compile(
    r"^\s*(?:[-*]\s*)?(?:i\s+)?(?:remember to|need to|have to|must|should|plan to|going to|want to|don't forget to|todo:?|to do:?)\b",
    re.I,
)
#: "Did I write about the conference": a note that names the conference is
#: the writing, whatever verb it uses (audit 1030 Z18).
_WRITING = frozenset({"write", "written", "wrote", "mention", "mentioned", "note", "noted", "record", "recorded", "log", "logged", "jot", "jotted"})


def _note_of(view, today: date) -> str:  # noqa: ANN001
    day = view.written
    return f"your note of {composer_lists._day(day, today)}" if day else "one note"  # noqa: SLF001


def _say_line(out, view, s, lead: str) -> None:  # noqa: ANN001
    text = re.sub(r"^\s*[-*]\s*(?:\[[ xX]\]\s*)?", "", s.text).strip()
    out.lines.append(f"{lead}: {text}")
    composer_lists._cite(out, view, s, s.text)  # noqa: SLF001


def _say_did(out, view, s, verb_word: str, today: date) -> None:  # noqa: ANN001
    if s.kind == "task":
        _verdict(out, view, s, verb_word)
    elif _UNDONE.search(s.text):
        _say_line(out, view, s, f"No, {_note_of(view, today)} says")
    elif _INTENT.search(s.text):
        _say_line(out, view, s, f"Not yet, as far as your notes go. {_note_of(view, today).capitalize()} only plans it")
    else:
        _say_line(out, view, s, f"Yes, {_note_of(view, today)} says so")


def _asked_thing(words: list[str]) -> str:
    """"anything about meditation" is meditation."""
    return re.sub(r"^(?:(?:anything|something|much)\s+)?(?:about|on|of|regarding|to|for)\s+", "", " ".join(words[1:]), flags=re.I)


def _not_said(out, views: list, obj, words: list[str], today: date) -> None:  # noqa: ANN001
    """No note says the doing: the nearest note that names the thing, or a
    plain no, never the question echoed back ("says you written")."""
    thing = _yours(_asked_thing(words))
    seen = _first_did(views, frozenset(), obj)
    if seen:
        _say_line(out, seen[0], seen[1], f"I found nothing in your notes that says so. {_note_of(seen[0], today).capitalize()} mentions {thing}")
    elif empty := next((v for v in views if not v.sentences and _titled_for(v, obj)), None):
        line = f"Your {composer_lists._title(empty)} note has a title but nothing written under it, so it does not say."  # noqa: SLF001
        out.lines.append(line)
        out.rows.append({"sentence": line, "note_id": empty.note.get("source_id", empty.id), "source": empty.title,
                         "start": 0, "end": 0, "score": 1.0, "digest": True})
    elif near := _nearest(views, obj):
        _say_line(out, *near, f"I found nothing in your notes that says so. The closest is {_note_of(near[0], today)}")
    else:
        out.lines.append(f"I found nothing in your notes about {thing}.")


def _yours(thing: str) -> str:
    """"my Q1 running goal" said back is "your Q1 running goal"."""
    swap = {"my": "your", "mine": "yours", "me": "you", "i": "you", "myself": "yourself"}
    return re.sub(r"\b(?:my|mine|me|i|myself)\b", lambda m: swap[m.group(0).lower()], thing, flags=re.I)


def _titled_for(view, obj: list[str]) -> bool:  # noqa: ANN001
    return bool(obj) and all(composer._holds(st, view.title_words) for st in obj)  # noqa: SLF001


def _nearest(views: list, obj: list[str]):  # noqa: ANN202
    """The sentence that holds most of the thing, its note's title counted
    ("Q1: run a 10k" in Q1 goals for "my Q1 running goal"), when it holds
    at least two of its words; None otherwise."""
    best, score = None, 1
    for view in sorted(views, key=lambda v: v.rank):
        for s in view.sentences:
            have = set(composer._words(s.text)) | set(view.title_words)  # noqa: SLF001
            hits = sum(1 for st in obj if composer._holds(st, have))  # noqa: SLF001
            if hits > score:
                best, score = (view, s), hits
    return best


#: "Did I like the ramen place": the note rarely says "like"; it says "8/10,
#: the broth was great". A taste verb is answered by what the note says of
#: the thing, verdict left to the person (2026-10-30 sweep).
_TASTE = frozenset({"like", "enjoy", "love", "hate", "rate", "mind"})


_VERDICT = re.compile(
    r"\b(?:lov|lik|enjoy|hat|dislik|great|good|bad|boring|amazing|favou?rite|meh|okay|brilliant|terrible|awful|excellent|disappoint)\w*"
    r"|\b\d+(?:\.\d)?\s*/\s*(?:10|5)\b|\bstars?\b",
    re.I,
)


def _titled(view, stems: list[str]) -> bool:  # noqa: ANN001
    have = set(composer._words(getattr(view, "title", "") or ""))  # noqa: SLF001
    return bool(stems) and getattr(view, "titled", False) and all(s in have for s in stems)


def _taste_said(views: list, stems: list[str]):  # noqa: ANN001
    """The (view, sentences) that give a verdict on the thing: the note named
    for it first, whose lines are about it without naming it ("# Piranesi /
    Loved it. 9/10"), then any line that names it and judges (audit 1030 Z11:
    "did I like Piranesi" quoted the reading list)."""
    for view in sorted(views, key=lambda v: (not _titled(v, stems), v.rank)):
        own = _titled(view, stems)
        said = [s for s in view.sentences if _VERDICT.search(s.text) and (own or _holds(s, stems))]
        if said:
            return view, said[:2]
    return None


def _say_taste(out, view, said: list, today: date) -> None:  # noqa: ANN001
    day = view.written
    where = f"Your {view.title} note" if getattr(view, "titled", False) and view.title else "Your note"
    when = f" of {composer_lists._day(day, today)}" if day else ""  # noqa: SLF001
    text = " ".join(re.sub(r"^\s*[-*]\s*(?:\[[ xX]\]\s*)?", "", s.text).strip() for s in said)
    out.lines.append(f"{where}{when} says: {text}")
    for s in said:
        composer_lists._cite(out, view, s, s.text)  # noqa: SLF001


def _did(out, rest: str, views: list, today: date) -> bool:  # noqa: ANN001
    words = rest.split()
    if len(words) < 2:
        return False
    verb = _verb_forms(words[0])
    obj = _stems(_asked_thing(words))
    if not obj:
        return False
    if words[0] in _TASTE and (best := _taste_said(views, obj) or _one_line(_first_did(views, frozenset(), obj))):
        _say_taste(out, *best, today)
        return True
    if words[0].lower() in _WRITING and (seen := _first_did(views, frozenset(), obj)):
        _say_line(out, *seen, f"Yes, {_note_of(seen[0], today)} mentions {_asked_thing(words)}")
        return True
    best = _first_did(views, verb, obj)
    if best is not None and best[1].kind == "task" and not best[1].done:
        best = _done_later(views, verb, obj, best[0]) or best
    if best is None:
        _not_said(out, views, obj, words, today)
        return True
    _say_did(out, *best, words[0], today)
    return True


def _later_line(out, got, view, today: date, *, asks_done: bool) -> None:  # noqa: ANN001
    """An item done in a later note, its box never ticked: that note is the
    record, said as the note (second eye F3), never as a tick."""
    later, said = got
    line = f"{'Yes' if asks_done else 'No'}, {_note_of(later, today)} ({composer_lists._title(later)}) says it is done; the box in {composer_lists._title(view)} is still unticked."  # noqa: SLF001
    out.lines.append(line)
    composer_lists._cite(out, later, said, line)  # noqa: SLF001


def _is_still(out, rest: str, views: list, today: date, *, asks_done: bool = False) -> bool:  # noqa: ANN001
    """Only a checklist line answers; with none, the question goes on to the
    readers that know prose ("Is the empty-title bug done?")."""
    words = rest.split()
    if len(words) < 2:
        return False
    verb, obj = _verb_forms(words[0]), _stems(_asked_thing(words))
    best = _first_did(views, verb, obj) if obj else None
    if best is None or best[1].kind != "task":
        return False
    view, task = best
    text = re.sub(r"^\s*[-*]?\s*\[[ xX]\]\s*", "", task.text).strip()
    title = composer_lists._title(view)  # noqa: SLF001
    if not task.done and (got := recorded_later(views, view, task)):
        _later_line(out, got, view, today, asks_done=asks_done)
        return True
    if asks_done:
        line = f"Yes, “{text}” is ticked off in {title}." if task.done else f"Not yet: “{text}” is still open in {title}."
    else:
        line = f"No, “{text}” is ticked off in {title}." if task.done else f"Yes, “{text}” is still open in {title}."
    out.lines.append(line)
    composer_lists._cite(out, view, task, line)  # noqa: SLF001
    return True


def _is_done(out, rest: str, views: list, today: date) -> bool:  # noqa: ANN001
    return _is_still(out, rest, views, today, asks_done=True)


def _one_line(found):  # noqa: ANN001, ANN202
    return (found[0], [found[1]]) if found else None


def _when_said(view, sentence, today: date) -> date | None:  # noqa: ANN001
    for day, at in composer._days_named(view, today, "past"):  # noqa: SLF001
        if sentence.start <= at < sentence.end:
            return day
    return view.written


def _since_found(views: list, verb: list[str], obj: list[str], today: date) -> list:
    """The dated sentences that say the verb with the object, the object
    being in the sentence or in its note's title or filing ("I called her"
    in the Sara note); audit 1030 Z22."""
    found = []
    for view in views:
        head = set(view.title_words) | set(view.filed_words)
        for s in view.sentences:
            if s.kind == "task" and not s.done:
                continue
            have = set(composer._words(s.text))  # noqa: SLF001
            if all(v in have for v in verb) and all(o in have or o in head for o in obj):
                day = _when_said(view, s, today)
                if day and day <= today:
                    found.append((day, view, s))
    return found


def _since(out, rest: str, views: list, today: date) -> bool:  # noqa: ANN001
    words = rest.split()
    verb, obj = _stems(words[0]) if words else [], _stems(" ".join(words[1:]))
    if not verb:
        return False
    found = _since_found(views, verb, obj, today)
    if not found:
        out.lines.append(f"Your notes do not say when you {rest}, so I cannot work out how long it has been.")
        return True
    day, view, s = max(found, key=lambda f: f[0])
    n = (today - day).days
    ago = "today" if n == 0 else "yesterday" if n == 1 else f"{n} days ago"
    line = f"It was {composer_lists._day(day, today)}, {ago}."  # noqa: SLF001
    out.lines.append(line)
    composer_lists._cite(out, view, s, line)  # noqa: SLF001
    return True


#: "compare the two X notes", "what changed between the two X notes",
#: "the difference between my two X notes" (2026-10-30 sweep).
_PAIR_LEAD = re.compile(
    r"^(?:compare|what(?:'s| is| are)? (?:changed|different|the differences?) between|(?:the )?differences? between) (?:the |my )?two "
)


def _pair_subject(q: str) -> str | None:
    """What the two notes are about in "compare the two X notes", else None."""
    lead = _PAIR_LEAD.match(" ".join(q.lower().split()))
    if not lead:
        return None
    low = lead.string[lead.end():]
    for tail in (" notes", " note", " ones"):
        if low.endswith(tail):
            return low[: -len(tail)]
    return low


def _say_side_by_side(out, named: list, low: str) -> None:  # noqa: ANN001
    out.lines.append(f"Your two {low} notes, side by side:")
    for view in named[:2]:
        first = next((x for x in view.sentences if x.kind in ("prose", "item", "task")), None)
        line = f"- {composer_lists._title(view)}: {first.text.strip() if first else 'empty'}"  # noqa: SLF001
        out.lines.append(line)
        if first is not None:
            composer_lists._cite(out, view, first, line)  # noqa: SLF001
    sizes = [len(str(v.note.get("content") or "").split()) for v in named[:2]]
    if sizes[0] != sizes[1]:
        longer = named[0] if sizes[0] > sizes[1] else named[1]
        out.lines.append(f"{composer_lists._title(longer)} is the longer, {max(sizes)} words to {min(sizes)}.")  # noqa: SLF001


def _pair(out, q: str, views: list, today: date) -> bool:  # noqa: ANN001
    """"Compare the two lentil soup notes": both sides, side by side, or which
    side is missing (audit 1029 C36). Read in code, not by a pattern, so a long
    question costs nothing."""
    low = _pair_subject(q)
    if low is None:
        return False
    stems = _stems(low)
    if not stems:
        return False
    named = composer._notes_named_by(views, set(stems))  # noqa: SLF001
    named = sorted(named, key=lambda v: (not _title_holds(v, stems), v.rank))
    if not named:
        return False
    if len(named) == 1:
        view = named[0]
        out.lines.append(f"You have only one {low} note, {composer_lists._title(view)}, so there is nothing to compare it with.")  # noqa: SLF001
        return True
    _say_side_by_side(out, named, low)
    return True


# --- value slots (audit 1029 C21): one table, one reader -----------------------------------
#
# "What temperature do I bake at", "when is the race", "how many km did I run
# on Sunday" each ask for a VALUE: a number with a unit, a date. The sentence
# that answers must hold it; a sentence that only names the subject ("I bake
# sourdough on Sundays") is not the answer. A slot kind is one row: how its
# question is read (`ask`) and how its value is read out of a sentence
# (`read`). Adding a kind adds a row, never a branch in `_value`.


class Ask(NamedTuple):
    """What a value question names: the subject words, a unit, a weekday."""

    subject: list[str]
    unit: str | None = None
    day: str | None = None


class Slot(NamedTuple):
    kind: str
    ask: Callable[[list[str]], Ask | None]
    read: Callable[[str, str | None], str | None]
    #: What is missing when no sentence holds it ("a temperature"); `{unit}`
    #: is the question's own unit word.
    noun: str
    #: The ordinary readers already word a value they find (a day is worked
    #: out against the note's own date, "tomorrow" in a July note is not
    #: tomorrow): the slot only speaks to say that no sentence holds one.
    plain: bool = False


_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_AUX = frozenset({"do", "did", "does", "should", "shall", "must", "can", "could", "will", "would", "have", "has"})
_SELF = frozenset({"i", "we"})
_DONE = frozenset({"did", "have", "has"})
#: Words that frame the question and are not the thing it is about.
_CUES = frozenset({"temperature", "temp", "degrees", "date", "day", "many", "much", "time", "when", "what", "which", "at", "to", "of"})
#: A superlative asks which note is first or next, the ranker's question.
_RANKED = frozenset({"next", "first", "last", "latest", "newest", "upcoming", "previous", "earliest"})
#: Regular pasts the unit and slot readers match by their lemma too; the
#: irregular ones are the stemmer's own (`composer.IRREGULAR_PAST`).
_IRREGULAR = {**composer.IRREGULAR_PAST, "baked": "bake", "cycled": "cycle", "walked": "walk"}
#: Unit aliases by the unit a question names; the first is how the note's own
#: figure is read back to the person.
_UNITS = {
    "km": ("km", "kms", "kilometre", "kilometres", "kilometer", "kilometers"),
    "miles": ("miles", "mile", "mi"),
    "minutes": ("minutes", "minute", "mins", "min"),
    "hours": ("hours", "hour", "hrs", "hr"),
    "pages": ("pages", "page", "pp"),
    "kg": ("kg", "kgs", "kilo", "kilos", "kilogram", "kilograms"),
    "steps": ("steps", "step"),
    "calories": ("calories", "calorie", "kcal", "cal"),
    "litres": ("litres", "litre", "liters", "liter", "l"),
    "cups": ("cups", "cup"),
    "reps": ("reps", "rep"),
    "words": ("words", "word"),
    "glasses": ("glasses", "glass"),
}
_UNIT_OF = {alias: unit for unit, aliases in _UNITS.items() for alias in aliases}


def _flat(words: list[str], drop=()) -> list[str]:  # noqa: ANN001
    return [w for w in words if w not in drop]


#: How a temperature is asked: "how hot is the oven", "what temp for the loaf",
#: "what oven setting", "how warm should the starter be" (audit 1030 Z25).
_HEAT = frozenset({"hot", "warm", "cold", "cool", "chilled", "temperature", "temp", "temps", "degrees", "setting", "heat"})
_COPULA = frozenset({"is", "are", "be", "was", "were", "need", "needs", "set", "for", "at", "oven", "ovens"})


def _ask_temperature(t: list[str]) -> Ask | None:
    """"what temperature do I bake at", "how hot is the oven": a temperature
    asked of something I do or keep."""
    if t[:2] == ["at", "what"]:
        t = t[1:]
    if t[:1] == ["how"] and len(t) > 2 and t[1] in _HEAT:
        rest = t[2:]
    elif t[:1] == ["what"] and len(t) > 2 and any(w in _HEAT for w in t[1:4]):
        rest = [w for w in t[1:] if w not in _HEAT]
    else:
        return None
    subject = _flat(rest, _AUX | _SELF | _COPULA | _FILLER)
    #: A bare "the oven" is what is baked in it: the notes say "bake at 230C".
    return Ask(subject or ["bake"]) if rest else None


def _ask_date(t: list[str]) -> Ask | None:
    """"when is the race", "when do I fly", "what is the beta date": a day.
    "When did I buy the kindle" is not one: a done thing is dated by the
    note that tells it, which the when-answer says (the gold's day lead)."""
    if len(t) >= 3 and t[0] == "when" and t[1] not in _DONE and (t[1] in _AUX or t[1] in ("is", "are", "am")):
        subject = _flat(t[2:], _SELF)
    elif len(t) >= 3 and t[0] == "what" and ("date" in t[1:6] or "day" in t[1:6]):
        if any(w in t for w in ("today", "tomorrow", "yesterday", "week", "month", "year")):
            return None
        subject = _flat(t[1:], ("is", "are", "the", "my", "date", "day", "of", "on", "for"))
    else:
        return None
    return Ask(subject) if subject and not _RANKED & set(subject) else None


def _ask_quantity(t: list[str]) -> Ask | None:
    """"how many km did I run on Sunday": a count of a unit I did."""
    if len(t) < 6 or t[0] != "how" or t[1] not in ("many", "much") or t[2] not in _UNIT_OF or t[3] not in _AUX or t[4] not in _SELF:
        return None
    day = next((w for w in t[5:] if w in _WEEKDAYS), None)
    rest = _flat(t[5:], (*_WEEKDAYS, "on", "in", "during", "last", "this", "today", "yesterday", "week", "weekend"))
    return Ask(rest, _UNIT_OF[t[2]], day) if rest else None


@functools.cache
def _temperature_pattern() -> re.Pattern[str]:
    return re.compile(r"(?<![\w.])\d{2,3}(?:[.,]\d)?\s?(?:[°º]\s?[CFcf]?|(?i:degrees?|deg)\b|[CF]\b)|(?i:gas\s+mark\s+\d)")


@functools.cache
def _quantity_pattern(unit: str) -> re.Pattern[str]:
    aliases = "|".join(sorted(_UNITS.get(unit, (unit,)), key=len, reverse=True))
    return re.compile(rf"(?<![\w.,])\d+(?:[.,]\d+)?\s?(?i:{aliases})\b")


def _read_temperature(text: str, unit: str | None) -> str | None:
    found = _temperature_pattern().search(text)
    return found.group(0).strip() if found else None


def _read_quantity(text: str, unit: str | None) -> str | None:
    found = _quantity_pattern(_UNIT_OF.get(unit or "", unit or "")).search(text) if unit else None
    return found.group(0).strip() if found else None


def _read_date(text: str, unit: str | None) -> str | None:
    """The first time phrase that names a day: a date, not a bare "May"."""
    for _start, _end, phrase in when_words.find(text):
        if recognise.names_a_day(phrase):
            return phrase
    return None


#: The table. A new kind is a row here.
SLOTS = (
    Slot("temperature", _ask_temperature, _read_temperature, "temperature"),
    Slot("date", _ask_date, _read_date, "date", plain=True),
    Slot("quantity", _ask_quantity, _read_quantity, "number of {unit}"),
)


def read_value(kind: str, text: str, unit: str | None = None) -> str | None:
    """The value of slot `kind` in `text` ("230C", "12 km", "14 November"), or None."""
    slot = next((s for s in SLOTS if s.kind == kind), None)
    return slot.read(text, unit) if slot else None


def _norm(text: str) -> list[str]:
    return [_IRREGULAR.get(w, w) for w in composer._words(text)]  # noqa: SLF001


def _subject_stems(subject: list[str]) -> list[str]:
    seen: list[str] = []
    for w in _norm(" ".join(subject)):
        if w not in _FILLER and w not in _CUES and w not in _AUX and w not in seen:
            seen.append(w)
    return seen


def _score(view, sentence, stems: list[str]) -> int:  # noqa: ANN001
    """How much of the subject a sentence and its note's title and filing hold:
    twice for the sentence's own words, once for the heading's."""
    have = set(_norm(sentence.text))
    head = set(view.title_words) | set(view.filed_words)
    return sum(2 * composer._holds(s, have) + composer._holds(s, head) for s in stems)  # noqa: SLF001


def _weekday_fits(ask: Ask, view, sentence) -> int:  # noqa: ANN001
    """1 when the sentence names the weekday asked, -1 when it names another
    (so "On Saturday I ran 5 km" is not Sunday's answer), else 0."""
    if not ask.day:
        return 0
    named = {w for w in re.split(r"\W+", sentence.text.lower()) if w in _WEEKDAYS}
    if named:
        return 1 if ask.day in named else -1
    return 1 if view.written and _WEEKDAYS[view.written.weekday()] == ask.day else 0


def _value(out, slot: Slot, ask: Ask, views: list, today: date) -> bool:  # noqa: ANN001
    """The sentence of the notes that names the subject AND holds the slot's
    value; else the plain statement that none does, with the nearest note."""
    stems = _subject_stems(ask.subject)
    if not stems:
        return False
    held, near = [], []
    for view in views:
        for s in view.sentences:
            if s.kind in ("picture", "picture_text"):
                continue
            score = _score(view, s, stems)
            if not score:
                continue
            near.append((score, -view.rank, view, s))
            value = slot.read(s.text, ask.unit)
            fit = _weekday_fits(ask, view, s)
            if value and fit >= 0:
                held.append((score, fit, -view.rank, view, s, value))
    if held and slot.plain:
        return False
    if held:
        _score_, _fit, _rank, view, s, value = max(held, key=lambda h: h[:3])
        line = f"Your notes say {value}, in {composer_lists._title(view)}: {s.text.strip()}"  # noqa: SLF001
        out.lines.append(line)
        composer_lists._cite(out, view, s, line)  # noqa: SLF001
        return True
    subject = " ".join(_flat(ask.subject, _AUX | _SELF)) or stems[0]
    missing = slot.noun.format(unit=ask.unit or "")
    if not near:
        out.lines.append(f"I found no note about {subject}, so I have no {missing} to give.")
        return True
    _score_, _rank, view, s = max(near, key=lambda n: n[:2])
    line = f"Your notes do not say a {missing} for {subject}. The nearest is {composer_lists._title(view)}: {s.text.strip()}"  # noqa: SLF001
    out.lines.append(line)
    composer_lists._cite(out, view, s, line)  # noqa: SLF001
    return True


# --- how often, how old (audit 1029 C23) ----------------------------------------------------

#: What a note says when it gives a thing's start ("started on", "since",
#: "bought", "born"); the date in that sentence is the start date.
_START = frozenset({"start", "begin", "begun", "since", "born", "buy", "make", "create", "plant", "adopt", "found", "open", "join", "install", "build", "brew", "from"})
_ABOUT = frozenset({"write", "wrote", "written", "note", "post", "journal", "log", "about", "on", "mention", "talk", "think"})


def _filed_under(views: list, stems: list[str]) -> list:
    """The notes TITLED or TAGGED with every stem (the filing says what a note
    is about; a passing mention does not)."""
    return sorted((v for v in views if all(s in v.title_words or s in v.filed_words for s in stems)), key=lambda v: v.rank)


def _often(out, rest: list[str], views: list, today: date) -> bool:  # noqa: ANN001
    """"How often do I write about baking": the notes titled or tagged baking,
    counted, with the gap between them; a mention in another note is not one."""
    if rest[0] in ("mention", "mentioned"):
        return False  # a count of mentions: `composer_lists` counts them
    stems = _stems(" ".join(w for w in rest if w not in _ABOUT))
    if not stems:
        return False
    subject = " ".join(w for w in rest if w not in _ABOUT and w not in _FILLER)
    filed = _filed_under(views, stems)
    if not filed:
        if rest[0] not in _ABOUT:
            #: "how often do I water the garden" with no log filed under it:
            #: a sentence says how often ("Water every second day"), the
            #: ordinary answer's to find (2026-10-30 sweep).
            return False
        return _only_mentioned(out, views, stems, subject)
    out.lines.append(_often_line(filed, subject, today) + ":")
    for v in filed[:6]:
        first = next((x for x in v.sentences if x.kind in ("prose", "item", "task")), None)
        entry = f"- {composer_lists._title(v)}"  # noqa: SLF001
        out.lines.append(entry)
        if first is not None:
            composer_lists._cite(out, v, first, entry)  # noqa: SLF001
    return True


def _only_mentioned(out, views: list, stems: list[str], subject: str) -> bool:  # noqa: ANN001
    """No note is filed under the subject: say how many mention it, or False."""
    said = [v for v in views if all(composer._holds(s, set(v.words)) for s in stems)]  # noqa: SLF001
    if not said:
        return False
    out.lines.append(f"No note is titled or tagged {subject}; {composer_lists._plural(len(said), 'note')} only {'mentions' if len(said) == 1 else 'mention'} it in passing.")  # noqa: SLF001
    return True


def _often_line(filed: list, subject: str, today: date) -> str:
    """How many notes are filed under the subject, from when to when and how far apart."""
    days = sorted(v.written for v in filed if v.written)
    line = f"You have {composer_lists._plural(len(filed), 'note')} titled or tagged {subject}"  # noqa: SLF001
    if len(days) >= 2 and days[-1] > days[0]:
        gap = round((days[-1] - days[0]).days / (len(days) - 1))
        line += f", from {composer_lists._day(days[0], today)} to {composer_lists._day(days[-1], today)}"  # noqa: SLF001
        line += f", about one every {composer_lists._plural(max(gap, 1), 'day')}"  # noqa: SLF001
    return line


def _start_day(view, today: date) -> tuple[date, object] | None:  # noqa: ANN001
    """`(day, sentence)` of the earliest past day a sentence of the note gives
    as a start ("Started on 1 September")."""
    found = []
    for s in view.sentences:
        if not _START & set(_norm(s.text)):
            continue
        for day, at in composer._days_named(view, today, "past"):  # noqa: SLF001
            if s.start <= at < s.end:
                found.append((day, s))
    return min(found, key=lambda f: f[0]) if found else None


def _old(out, rest: list[str], views: list, today: date) -> bool:  # noqa: ANN001
    """"How old is my sourdough starter": today less the start date the note
    gives; when it gives none, that is said."""
    stems = _stems(" ".join(rest))
    if not stems:
        return False
    named = composer._notes_named_by(views, set(stems))  # noqa: SLF001
    named = sorted(named, key=lambda v: (not _title_holds(v, stems), v.rank))
    if not named:
        return False
    subject = " ".join(w for w in rest if w not in _FILLER)
    for view in named:
        if got := _start_day(view, today):
            day, s = got
            n = (today - day).days
            line = f"Your {subject} is {composer_lists._plural(n, 'day')} old, started on {composer_lists._day(day, today)}"  # noqa: SLF001
            line += f", about {n // 30} months." if n >= 60 else "."
            out.lines.append(line)
            composer_lists._cite(out, view, s, line)  # noqa: SLF001
            return True
    view = named[0]
    first = next((x for x in view.sentences if x.kind in ("prose", "item", "task")), None)
    line = f"Your notes do not say when your {subject} was started, so I cannot work out its age. The nearest is {composer_lists._title(view)}."  # noqa: SLF001
    out.lines.append(line)
    if first is not None:
        composer_lists._cite(out, view, first, line)  # noqa: SLF001
    return True


def answer(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    """Say the slot's answer, or that no note holds it; False when `asked` is
    not a slot question this module reads."""
    q = composer_lists._q(asked)  # noqa: SLF001
    if _PAIR_LEAD.match(" ".join(q.lower().split())) and _pair(out, q, views, today):
        return True
    if _counted(out, q, views) or _state(out, " ".join(q.lower().split()).rstrip("?.!"), views, today):
        return True
    tokens = q.lower().replace("'s ", " is ").split()
    shaped = _by_words(out, tokens, views, today)
    if shaped is not None:
        return shaped
    for pattern, say in ((_SINCE, _since), (_DID, _did), (_NEED, _left), (_LEFT, _left), (_STILL_ON, _left), (_IS_STILL, _is_still), (_IS_DONE, _is_done)):
        if m := pattern.match(q):
            return say(out, next((g for g in m.groups() if g), ""), views, today)
    return False


def _by_words(out, tokens: list[str], views: list, today: date) -> bool | None:  # noqa: ANN001
    """A value slot's answer (True, or False when the slot cannot say), how
    often or how old; None when the words ask none of these."""
    if tokens and tokens[0] in ("what", "when", "how", "at"):
        for slot in SLOTS:
            if (ask := slot.ask(tokens)) is not None:
                return _value(out, slot, ask, views, today)
    return True if tokens[:1] == ["how"] and _how(out, tokens, views, today) else None


def _how(out, tokens: list[str], views: list, today: date) -> bool:  # noqa: ANN001
    """A doing counted from the lines that say it was done (audit 1030 Z23),
    how often the notes are filed under a subject, or how old a thing is."""
    if composer_doings.answer(out, " ".join(tokens), views, today):
        return True
    if len(tokens) > 4 and tokens[1] == "often" and tokens[2] in _AUX and tokens[3] in _SELF and _often(out, tokens[4:], views, today):
        return True
    return len(tokens) > 3 and tokens[1] == "old" and tokens[2] in ("is", "are", "was") and _old(out, tokens[3:], views, today)
