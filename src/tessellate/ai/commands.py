"""Acts: a Chat message read as a command, with no model (CHAT_PLAN Phase 6,
decision 38; Phase 5 (f): the owner, "or the composer can somehow call tools
and act like an agent").

The grammar is `verb object [qualifier] [when]`, read by rules the way
`ai/when.py` reads a time. The verbs (`VERBS`): remind, tag, untag, file
(into a category), rename, pin, unpin, link, unlink, delete (always
confirmed), create (a note, a meeting, a document, a mind map), add (to a
note), summarise, find, open. No archive (decision 42: archiving stays a
UI action). Three stages, each testable alone:

- `parse(text, now)`: the `Command` (verb, object, when, confirm) from the
  words alone, or None. No database, no model. `read` gives the same as the
  arguments' dict; `tests/test_composer_commands.py` holds the table of
  phrasings it is measured on.
- `plan(session, parsed, note_ids)`: the exact change it would make, as the
  card the person sees (the notes it names, the category, the tags), or one
  clarifying question when its object is not one note. Nothing is written.
- `run(session, steps)`: what Confirm does. Every step goes through
  `tools.execute_tool`, the agent's own door, so the audit log, the private
  note refusal and each step's undo are the agent's; the result is one line
  and the steps that undo it.

A sentence this does not read is not a guess: `parse` returns None and the
turn goes on to the composer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import address, anchor_acts, find_topic, note_recency, object_acts, parity_acts, reminder_parser, surface_acts, task_acts, when
from tessellate.ai import act_registry, act_steps
from tessellate.ai import composer_calendar
from tessellate.ai.composer_frame import note_title
from tessellate.ai.act_registry import CONFIRM_INTENTS
from tessellate.ai import filed_name
from tessellate.ai.filed_name import filed_listing

#: The verbs of the grammar (decision 38), as said in `Command.verb`.
VERBS = ("remind", "complete", "cancel", "snooze", "tag", "untag", "file", "rename", "restore", "pin", "unpin", "link", "unlink", "delete", "create", "add", "summarise", "find", "open")
#: The intents `read` gives, each with its verb.
_VERB_OF = {
    "reminder": "remind", "tag": "tag", "untag": "untag", "move": "file", "rename": "rename", "rename_tag": "rename", "rename_category": "rename", "create_category": "create", "delete_category": "delete", "merge_categories": "rename", "delete_tag": "delete", "edit_text": "rename", "to_reminders": "remind", "run_skill": "open", "delete_document": "delete", "delete_skill": "delete", "board_card": "add", "make_map": "create", "remember": "add", "restore": "restore", "pin": "pin",
    "unpin": "unpin", "link": "link", "unlink": "unlink", "delete": "delete", "new_note": "create",
    "meeting": "create", "append": "add", "complete": "complete", "uncomplete": "complete", "cancel": "cancel", "snooze": "snooze", "set_name": "rename", "set_theme": "change", "summarise": "summarise", "find": "find", "similar": "find", "open": "open", "navigate": "open",
}
#: The intents that write: each is shown as a card.
WRITE_INTENTS = frozenset({"reminder", "tag", "untag", "move", "rename", "rename_tag", "rename_category", "create_category", "delete_category", "merge_categories", "delete_tag", "edit_text", "to_reminders", "restore", "pin", "unpin", "link", "unlink", "delete", "new_note", "meeting", "append", "complete", "uncomplete", "cancel", "snooze", "set_name"}) | surface_acts.INTENTS
#: Read only: answered at once, nothing to confirm.
READ_INTENTS = frozenset({"find", "similar", "open", "navigate", "summarise"})
#: The writes that wait for Confirm: anything that removes, renames, moves or
#: rewrites. The rest (a reminder, a new note, a pin) run at once with Undo
#: beside the line that says what was done.

#: Agent mode with no model, for anything `parse` does not read: generated
#: from the act registry (`act_registry.capability_line`), kept here by name
#: for the callers that read it as a constant.
def __getattr__(name: str) -> str:
    if name == "CAPABILITY_LINE":
        from tessellate.ai import act_registry

        return act_registry.capability_line()
    raise AttributeError(name)


#: Steps a command card may run. The registry tools are the agent's; the two
#: others are this module's own, for what no registry tool does.
RUNNABLE = frozenset(
    {"set_reminder", "tag_note", "edit_note", "create_note", "delete_note", "restore_note", "rename_tag", "rename_category", "create_category", "delete_category", "merge_categories", "delete_tag", "move_notes",
     "pin_note", "link_notes", "unlink_notes", "start_meeting", "bin_reminder", "complete_reminder", "restore_reminder", "snooze_reminder", "set_display_name",
     "delete_document", "restore_document", "create_document", "delete_skill", "save_skill", "add_whiteboard_card", "delete_board_item", "restore_board_item", "map_from_note", "create_mindmap", "set_theme", "save_user_preference", "drop_preference"}
)

_MAX_TEXT = 300
_MAX_NOTES = 50

# --- parse ---------------------------------------------------------------------
#
# Every pattern runs on text already folded to single spaces and capped at
# `_MAX_TEXT`, and splits are done with `str` methods where a lazy `.+?` would
# otherwise sit before a separator (CodeQL, polynomial regular expression).

#: Longest first inside a family, so "i'd like you to " goes before "i'd like to ".
_POLITE = ("please ", "pls ", "plz ", "kindly ", "can you ", "could you ", "would you ", "will you ", "can u ", "could u ",
           "i want you to ", "i need you to ", "i'd like you to ", "i would like you to ", "i want to ",
           "i'd like to ", "i would like to ", "go ahead and ", "if you could ", "if you can ", "when you can, ", "when you can ",
           "let's ", "lets ", "ok so ", "okay so ", "ok ", "okay ", "just ", "also ", "so ", "and ", "then ")
#: A wish said casually is the same request (INBOX 1507: "i wanna make a note"
#: was searched for, not made). Tried only when the whole sentence reads as no
#: act: "I need to call the bank, remind me" is a reminder whose task keeps its
#: lead (INBOX 1459). "let me know" stays a question.
_CASUAL = ("i wanna ", "i wana ", "wanna ", "i'd love to ", "i would love to ", "can i ", "could i ", "may i ",
           "lemme ", "let me ", "i need to ", "help me ", "i gotta ", "i have to ", "i'm gonna ", "im gonna ",
           "i'm going to ", "im going to ", "gonna ")
_TRAILING = (" please", " pls", " plz", " for me", " thanks", " thank you so much", " thank you", " ty", " thx", " now", " if you can",
             " when you can", " if you could")
#: Said of when: it is a due hint, never part of the words an act writes ("call
#: mum as soon as possible" is a reminder soon, not a title).
_URGENT_TAIL = (" asap", " as soon as possible", " right now")
_ASKING = re.compile(r"^(?:what|who|where|when|how|why|which|whether|if|of|out)\b", re.IGNORECASE)


def _fold(text: str) -> tuple[str, bool, bool]:
    """(the command text, said as a question, said politely)."""
    return _fold_urgent(text)[:3]


def _fold_urgent(text: str) -> tuple[str, bool, bool, bool]:
    """`_fold`, and whether the person asked for it at once (asap)."""
    urgent = False
    text = " ".join(str(text or "").split())[:_MAX_TEXT].strip(" .!")
    question = text.endswith("?")
    text = text.rstrip("?").strip(" ,")
    polite = False
    changed = True
    while changed:
        changed = False
        low = text.lower()
        for word in _POLITE:
            if low.startswith(word):
                text, polite, changed = text[len(word):].lstrip(" ,"), True, True
                break
        low = text.lower()
        for word in _TRAILING:
            if low.endswith(word):
                text, changed = text[: -len(word)].rstrip(" ,"), True
                break
        for word in _URGENT_TAIL:
            if low.endswith(word):
                text, changed, urgent = text[: -len(word)].rstrip(" ,"), True, True
                break
    return text, question, polite, urgent


def _cap(text: str) -> str:
    text = text.strip(" ,.;:-")
    return text[:1].upper() + text[1:]


def _drop_article(text: str) -> str:
    low = text.lower()
    for word in ("the ", "my ", "a ", "an ", "our "):
        if low.startswith(word):
            return text[len(word):]
    return text


def _split_last(text: str, separators: tuple[str, ...]) -> tuple[str, str] | None:
    """`text` split at the rightmost of `separators`, or None."""
    low = text.lower()
    best = max(((low.rfind(sep), sep) for sep in separators), key=lambda pair: pair[0])
    at, sep = best
    if at <= 0:
        return None
    return text[:at].strip(), text[at + len(sep):].strip()


_THESE = {
    "these notes": False, "these": False, "those notes": False, "those": False,
    "them": False, "these ones": False, "the notes": False,
    "this note": True, "this": True, "it": True, "that note": True,
}
_ABOUT_WORDS = ("about ", "on ", "for ", "mentioning ", "that mention ", "called ", "named ", "titled ")
_NOTE_HEADS = re.compile(
    r"^(?:all )?(?:of )?(?:my |the |all |any |every )?(notes?|everything|anything|entries|entry) ",
    re.IGNORECASE,
)


#: A note by its number (OPEN 1522: "pin note 12", as "open note 12" already
#: was); `about` keeps the words so a line that quotes it still reads.
_NOTE_NUMBER = re.compile(r"(?:(?:the|this|my) )?(?:(?:note|entry)(?: (?:number|no\.?))? ?#?|#)(\d{1,9})", re.IGNORECASE)


#: "the interesting bean one", "that gym one", "the one about the gym": a note
#: pointed at by its name and the word "one" (INBOX 1570).
_ONE_ABOUT = re.compile(r"(?:(?:the|that|this|my) )?one (?:about|on|for|called|named|titled|with|that mentions?|mentioning) (?:the |my )?(?P<name>.+)", re.IGNORECASE)
_NAME_ONE = re.compile(r"(?:(?:the|that|this|my) )?(?P<name>.+?\S) one", re.IGNORECASE)


def _one_named(text: str) -> str:
    """The title inside "the X one" or "the one about X", else ""."""
    said = text.strip(" .,!?")
    found = _ONE_ABOUT.fullmatch(said) or _NAME_ONE.fullmatch(said)
    name = found.group("name").strip() if found else ""
    #: "the other one", "the second one", "the last one" point back at an answer
    #: (`reading.follow`), not at a title.
    words = set(re.findall(r"[a-z']+", name.lower()))
    return "" if not name or words <= _POINTERS else name


_POINTERS = frozenset(
    "the that this my which every each any no a an other another last first second third fourth fifth next previous same old older "
    "new newer newest oldest latest earlier later final top bottom left right one ones".split()
)


def _target(text: str) -> dict | None:
    """Which notes a phrase names: the attached ones ("these notes") or the
    ones a search finds ("my notes about Z", "my Z notes"), one by its number
    ("note 12"), or None."""
    low = text.lower().strip()
    number = _NOTE_NUMBER.fullmatch(text.strip(" ."))
    if number:
        return {"about": f"note {number.group(1)}", "note_id": int(number.group(1)), "single": True}
    if low in _THESE:
        return {"these": True, "single": _THESE[low]}
    if named := _one_named(text):
        return {"about": _drop_article(named), "single": True}
    head = _NOTE_HEADS.match(text)
    if head:
        rest = text[head.end():]
        rest_low = rest.lower()
        for word in _ABOUT_WORDS:
            if rest_low.startswith(word):
                about = _drop_article(rest[len(word):].strip())
                if not about:
                    return None
                single = head.group(1).lower() in ("note", "entry") and not low.startswith(("my notes", "every "))
                return {"about": about, "single": single}
        return None
    words = text.split(" ")
    if len(words) >= 2 and words[-1].lower() in ("note", "notes"):
        #: "all my uni notes" names the uni notes (audit 1028 E9).
        about = _drop_article(re.sub(r"^(?:all|every|any)\s+(?:of\s+)?", "", " ".join(words[:-1]), flags=re.I))
        if about and about.lower() not in ("all", "the", "my", "these", "those", "some"):
            return {"about": about, "single": words[-1].lower() == "note"}
    return None


#: Other kinds of thing a verb here may name; a phrase holding one is not a note's title.
_OTHER_KINDS = frozenset("reminder reminders tag tags label labels category categories folder folders board boards map maps document documents meeting meetings timer task tasks event events".split())
#: What the app itself holds: "delete all my data" is the Guide's, never a note's title.
_APP_NOUNS = frozenset(
    "data account accounts everything anything history chat chats conversation conversations messages message settings app "
    "notebook notebooks model models vault backup backups cache index search session sessions workspace workspaces theme "
    "password passwords it this that them these those one ones all".split()
)


#: A title is a noun phrase; a clause ("bin day is on thursday") is a sentence.
_CLAUSE_WORDS = frozenset("is are was were be been do does did has have had will would should can could that which who what when where why how if whether because".split())


#: Words that point at no note in particular ("the old stuff", "everything
#: from last year"): a title never reads as one, so it is not an act.
_VAGUE = frozenset({"stuff", "things", "thing", "junk", "bits", "everything", "anything", "something", "rubbish", "clutter", "others", "rest", "ones", "whatever"})


def _bare_target(text: str) -> dict | None:
    """A note named by its title alone ("the gym log", "my history essay"),
    for the verbs only a note can take: tag, rename, pin, delete (audit 1028
    E7: every one of them needed the literal word "note"). The notes are
    found later by the words, and no match or several is asked, never run."""
    phrase = _drop_article(re.sub(r"\s+(?:please|pls|thanks|thank you|now|for me)\W*$", "", text.strip(), flags=re.I).strip(" .,'\"“”"))
    phrase = _drop_article(_one_named(phrase) or phrase)
    words = re.findall(r"[\w'’-]+", phrase.lower())
    if _VAGUE & set(words):
        return None
    if not 1 <= len(words) <= 6 or words[0].isdigit() or words[-1] in _APP_NOUNS or all(w in _APP_NOUNS for w in words):
        return None
    if _OTHER_KINDS & set(words) or _CLAUSE_WORDS & set(words):
        return None
    return {"about": phrase, "single": True, "bare": True}


def _tags(text: str) -> list[str]:
    text = text.strip(" .,'\"")
    if "#" in text:
        found = re.findall(r"#([\w][\w/-]{0,39})", text)
    else:
        found = []
        for piece in re.split(r",| and ", text):
            piece = piece.strip(" '\"")
            if piece:
                found.append("-".join(piece.split()))
    found = [t for t in found if t and len(t) <= 40]
    return found if 0 < len(found) <= 5 else []


#: Words a time said first may open with ("on Friday at 9 remind me to ...").
# The reminder phrase reader lives with the parser (`reminder_parser.reminder_head`)
# so `reminder_suggest` can share it without importing this module.
_reminder_head = reminder_parser.reminder_head


def _without_lead(text: str, leads: tuple[str, ...], *, once: bool = True) -> str:
    for lead in leads:
        if text.lower().startswith(lead):
            text = text[len(lead):]
            if once:
                break
    return text


_DANGLING = frozenset({"before", "by", "on", "until", "at", "after"})


def _without_dangling(words: str) -> str:
    """"renew rego before 3 december": the date came off, its joining word stays behind."""
    tail = words.rstrip().rsplit(" ", 1)
    return tail[0] if len(tail) == 2 and tail[1].lower() in _DANGLING else words


def _as_typed_case(said: str, rest: str) -> str:
    """As typed: the time parser raises the first letter for the stored
    reminder; the object is said back in the person's own case."""
    return said[:1].lower() + said[1:] if rest[:1].islower() else said


def _bare_reminder(head: str) -> dict | None:
    """"set a reminder" alone is asked what and when (INBOX 1507); "ping me"
    alone is not yet a request, and the bare word lists them (INBOX 1357 B)."""
    if "remind" not in head or head.strip(" .").lower() in ("reminder", "reminders", "a reminder"):
        return None
    return {"intent": "reminder", "text": "", "said": "", "due_at": None, "time_given": False, "no_subject": ""}


def _repeat_of(parsed: dict | None) -> dict:
    """The stored repeat a reminder sentence said ("every day at 8"), as the key it travels under."""
    return {"recurring": parsed["recurring"]} if parsed and parsed.get("recurring") else {}


_CLOCK = r"\d{1,2}(?::\d\d)?\s?(?:am|pm|a\.m\.|p\.m\.)?"
_WINDOW = re.compile(rf"\s*\b(?:between|from)\s+(?P<a>{_CLOCK})\s+(?:and|to|until|till|-)\s+(?P<b>{_CLOCK})(?![\d:])", re.I)


def _clock_window(rest: str) -> tuple[str, str]:
    """"call mum tomorrow between 8 and 10": the reminder is for the start of the window, so the sentence is read
    as "at 8" and the window stays in the words (L207: it was read as 9 with the numbers dropped from the text)."""
    found = _WINDOW.search(rest)
    if not found or re.search(r"\bat \d", rest, re.I):
        return rest, ""
    sign = found[0].lower().lstrip().startswith("from")
    if sign and not re.search(r"[ap]m|[ap]\.m|:", found["a"] + found["b"], re.I):
        return rest, ""  # "pages from 3 to 5" is not a time
    start, end = found["a"].strip(), found["b"].strip()
    if not re.search(r"[ap]", start, re.I) and (meridiem := re.search(r"([ap])\.?m", end, re.I)):
        start += f"{meridiem.group(1).lower()}m"  # "between 2 and 4pm" is 2pm
    return re.sub(r"\s+", " ", f"{rest[: found.start()]} at {start} {rest[found.end():]}").strip(), f" between {found['a'].strip()} and {end}"


#: "... the day before", "... an hour before" with no thing it is before: a reminder whose time is still to ask.
_BEFORE_TAIL = re.compile(r"\s+(?:the (?:day|night|week|morning|evening) before|(?:an?|one|1) (?:hour|hr) before)\s*$", re.I)


def _read_when(rest: str, now: datetime, locale: str | None) -> tuple[str, dict | None]:
    """`rest` with a "between 8 and 10" window read as its start, and the time and words it says (or None)."""
    rest, window = _clock_window(rest)
    parsed = reminder_parser.parse_relative(rest, now) or when.parse_reminder_text(rest, now, locale=locale)
    if parsed is not None:
        parsed = {**parsed, "text": (reminder_parser.without_conditions(parsed["text"]) or parsed["text"]) + window}
    return rest, parsed


def _before_without_a_time(rest: str, about: bool) -> dict | None:
    """"about the dentist the day before" says what, not which day: asked for the day, never guessed (L49)."""
    before = _BEFORE_TAIL.search(rest)
    if not before or not rest[: before.start()].strip(" ,.;:-"):
        return None
    what = _without_lead(rest[: before.start()].strip(" ,.;:-"), ("to ", "about ", "that ", "for "), once=False)
    return {"intent": "reminder", "text": _cap(what)[:500], "said": what[:500], "due_at": None, "time_given": False, **({"thing": True} if about else {})}


def _reminder(text: str, now: datetime, locale: str | None = None) -> dict | None:
    text, head = _reminder_head(text)
    if head is None:
        return None
    rest = text[len(head):].strip(" :,-")
    if head == "remind me" and _ASKING.match(rest):
        return None
    about = rest.lower().startswith("about ")
    rest = _without_lead(rest, ("to ", "2 ", "about ", "that ", "for "))
    if not rest:
        return _bare_reminder(head)
    rest = reminder_parser.unhedged(rest)
    if (unanchored := _before_without_a_time(rest, about)) is not None:
        return unanchored
    rest, parsed = _read_when(rest, now, locale)
    gap = _reminder_gap(rest, parsed, now)
    if gap is not None:
        return gap
    if parsed is None:
        if about:
            # "Remind me about my trip" with no time is a question as often
            # as a request; a reminder needs the time said.
            return None
        #: No time said: asked once ("Remind you when?"), never guessed as tomorrow
        #: at 9 (decisions 48 and 50, the owner's pick 2026-11-12).
        due, said, words = None, False, rest
    else:
        due, said, words = parsed["due_at"], True, parsed["text"]
    words = _without_lead(words, ("to ", "about ", "that ", "for "), once=False)
    words = _without_dangling(words)
    said_words = _as_typed_case(words.strip(" ,.;:-"), rest)
    words = _cap(words)
    if not words:
        return None
    return {
        "intent": "reminder", "text": words[:500], "said": said_words[:500], "due_at": due, "time_given": said and _ahead(due, now),
        "clock_unsaid": bool(parsed and parsed.get("clock_unsaid")),
        **_repeat_of(parsed),
    }


_MONTH_NAMES = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
_MONTH_DAYS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
_DAY_MONTH = re.compile(
    r"\b(?:(?P<d1>\d{1,2})(?:st|nd|rd|th)?(?: of)? (?P<m1>%s)|(?P<m2>%s) (?P<d2>\d{1,2})(?:st|nd|rd|th)?)\b"
    % ("|".join(_MONTH_NAMES), "|".join(_MONTH_NAMES)),
    re.I,
)


def _impossible_day(text: str) -> str:
    """"31 February" when `text` names a day its month does not have, else ""."""
    for m in _DAY_MONTH.finditer(text):
        day, month = int(m["d1"] or m["d2"]), (m["m1"] or m["m2"]).lower()
        if not 1 <= day <= _MONTH_DAYS[_MONTH_NAMES.index(month)]:
            return f"{day} {month.capitalize()}"
    return ""


def _reminder_gap(rest: str, parsed: dict | None, now: datetime) -> dict | None:
    """A reminder that cannot be set as said, asked rather than guessed
    (audit 1028 E26): only a time ("set a reminder for 5pm" stored "5pm" as
    its words), or a day its month does not have ("31 February")."""
    if parsed is not None and parsed["text"].strip(" .,").lower() == rest.strip(" .,").lower():
        return {"intent": "reminder", "text": "", "said": "", "due_at": parsed["due_at"], "time_given": True, "no_subject": rest.strip(" .,")}
    impossible = _impossible_day(rest) if parsed is None else ""
    if impossible:
        return {"intent": "reminder", "text": rest[:500], "said": rest[:500], "due_at": None, "time_given": False, "impossible": impossible}
    return None


def _tag(text: str) -> dict | None:
    low = text.lower()
    if low.startswith(("tag ", "label ")):
        body = text.split(" ", 1)[1]
        return _tag_with(body) or _note_then_tags(body) or _tag_hashed(body) or _tag_these(body)
    added = _tag_added(text)
    if added:
        return added
    placed = _tag_placed(text)
    if placed:
        return placed
    if low.startswith("give "):
        #: "give my gym log the tag fitness"
        split = _split_last(text[len("give "):], (" the tag ", " the tags ", " the label ", " a tag ", " a label "))
        if split:
            target, tags = split
            found = _target(target) or _bare_target(target)
            if found and _tags(tags):
                return {"intent": "tag", **found, "tags": _tags(tags)}
    return None


def _tag_added(text: str) -> dict | None:
    """"add the tag finance to the expenses note"."""
    low = text.lower()
    for lead in ("add the tags ", "add the tag ", "add tags ", "add tag ", "add the label ", "add label ", "add a tag ", "add a label "):
        if low.startswith(lead):
            split = _split_last(text[len(lead):], (" to ",))
            if split:
                tags, target = split
                found = _target(target) or _bare_target(target)
                if found and _tags(tags):
                    return {"intent": "tag", **found, "tags": _tags(tags)}
    return None


#: Ways to put a tag on a note that do not start with the word "tag":
#: (lead, the words that split the tag from the note).
_TAG_PLACING = (("put the tag ", " on "), ("put tag ", " on "), ("put the label ", " on "), ("stick the tag ", " on "), ("mark ", " with "))


def _tag_placed(text: str) -> dict | None:
    """"put the tag recipes on my sourdough notes", "mark the passport note with #travel"."""
    low = text.lower()
    for lead, sep in _TAG_PLACING:
        if not low.startswith(lead):
            continue
        split = _split_last(text[len(lead):], (sep,))
        if not split:
            return None
        first, second = split
        tags, target = (second, first) if lead == "mark " else (first, second)
        if lead == "mark " and "#" not in tags:
            return None
        found = _target(target) or _bare_target(target)
        return {"intent": "tag", **found, "tags": _tags(tags)} if found and _tags(tags) else None
    return None


def _tag_with(body: str) -> dict | None:
    """"tag my trip notes with travel": the notes, then "with", the tags."""
    split = _split_last(body, (" with ", " as "))
    if not split:
        return None
    target, tags = split
    for lead in ("the tags ", "the tag ", "tags ", "tag "):
        if tags.lower().startswith(lead):
            tags = tags[len(lead):]
    found = _target(target) or _bare_target(target)
    return {"intent": "tag", **found, "tags": _tags(tags)} if found and _tags(tags) else None


def _tag_hashed(body: str) -> dict | None:
    """"tag my gym notes #fitness": the notes, then tags written with a hash and no "with" (CHAT_PLAN X2)."""
    tail = re.search(r"((?:\s#[\w-]+)+)\s*$", " " + body)
    if not tail or not body[: len(body) - len(tail.group(1).strip())].strip():
        return None
    found = _target(body[: len(body) - len(tail.group(1).strip())].strip())
    tags = _tags(tail.group(1))
    return {"intent": "tag", **found, "tags": tags} if found and tags else None


def _tag_these(body: str) -> dict | None:
    """"tag these travel": the attached notes."""
    for these in sorted(_THESE, key=len, reverse=True):
        if body.lower().startswith(these + " "):
            tags = _tags(body[len(these):])
            if tags:
                return {"intent": "tag", "these": True, "single": _THESE[these], "tags": tags}
    return None


def _note_then_tags(body: str) -> dict | None:
    """"tag the dentist note health": the note, then the tags, no "with"."""
    numbered = re.match(r"((?:the |this |my )?(?:note|entry)(?: (?:number|no\.?))? ?#?\d{1,9}|#\d{1,9}) (.+)$", body, re.I)
    if numbered and (found := _target(numbered.group(1))) and (tags := _tags(numbered.group(2))):
        return {"intent": "tag", **found, "tags": tags}  # "tag note 12 gym" (L71)
    cut = body.lower().rfind(" note ")
    if cut <= 0:
        return None
    found = _one_target(body[: cut + len(" note")].strip())
    tags = _tags(body[cut + len(" note "):])
    return {"intent": "tag", **found, "tags": tags} if found and tags else None


#: Every way to start a filing; the flag says a note's title alone names it
#: ("shift the tokyo trip note to travel"), which "put" and "send" do not.
_MOVE_VERBS = {
    "move ": True, "file ": True, "shift ": True, "categorise ": True, "categorize ": True, "recategorise ": True,
    "recategorize ": True, "change the category of ": True, "set the category of ": True, "change the folder of ": True,
    "put ": False, "send ": False,
}
_BIN_WORDS = {"bin", "the bin", "trash", "the trash", "recycle bin", "the recycle bin"}


#: The daily note said as a place: the starter acts' append, never a category named so.
_DAILY_NOTE = re.compile(r"^(?:(?:today'?s|the|my|the day'?s) daily|today'?s|the day'?s) (?:note|journal)$|^my (?:journal|diary)$")


def _move_category(category: str) -> str:
    """The category a move names, cleaned, or "" when it names none (the bin,
    the daily note, a sentence)."""
    said = category.strip().lower()
    category = _drop_article(category.strip())
    low_cat = category.lower()
    if _DAILY_NOTE.match(low_cat) or _DAILY_NOTE.match(said):
        return ""  # "put it in today's note" appends to the daily note (starter acts), it is no category
    for tail in (" category", " folder"):
        if low_cat.endswith(tail):
            category = category[: -len(tail)]
    if category.lower().startswith("category "):
        category = category[len("category "):]
    category = category.strip(" '\"")
    return "" if not category or category.lower() in _BIN_WORDS or len(category) > 120 else category


def _move(text: str) -> dict | None:
    low = text.lower()
    verb = next((v for v in _MOVE_VERBS if low.startswith(v)), None)
    if verb is None:
        return None
    split = _split_last(text[len(verb):], (" to ", " into ", " in ", " under ", " as "))
    if not split:
        return None
    target, category = split
    found = _target(target) or (_bare_target(target) if _MOVE_VERBS[verb] else None)
    if not found or category.lower() in ("top", "the top"):
        return None
    category = _move_category(category)
    if not category:
        return None
    return {"intent": "move", **found, "category": category}


_NOTE_HEADS_NEW = (
    ("note to self", False), ("note that", False), ("new note", True), ("quick note", True), ("make a note", False),
    ("take a note", False), ("save a note", False), ("add a note", False), ("create a note", False),
    ("write a note", False), ("jot down", False), ("write down", False), ("note down", False),
    ("save this", True), ("creat a note", False), ("make note", False), ("note", True),
    ("start a new note", False), ("start a note", False), ("begin a note", False), ("make a new note", False),
    ("create a new note", False), ("write a new note", False), ("remember that", False), ("capture this", True),
)


_NAMED = ("called ", "titled ", "named ")
#: The words that join a note's name to what it says: "called X with Y",
#: "titled X saying Y", "named X that says Y", "called X: Y" (audit 1028 E25).
_JOIN = r"(?:with|saying|containing|including|that says|which says|that reads|reading|having|and (?:say|says|put|write|writes))"
_QUOTED_NAME = re.compile(r"^[\"“‘'](?P<name>.{1,120}?)[\"”’'](?P<tail>.*)$", re.S)
#: A name that is not quoted runs to the end of what was said ("called Shopping with milk, eggs and bread" is
#: titled that, the owner's Q5), unless a word that can only introduce text ("saying", "that says") or a colon follows it.
_PLAIN_NAME = re.compile(rf"^(?P<name>.+?)(?:\s+{_JOIN.replace('(?:with|', '(?:')}\s+|\s*:\s*)(?P<tail>.+)$", re.I | re.S)
_BODY_LEAD = re.compile(rf"^\s*(?:{_JOIN}\s+|[:,;-]\s*)", re.I)


def _name_and_words(rest: str) -> str:
    """`"Shopping" with milk, eggs and bread` as "Shopping\nMilk, eggs and
    bread": a name, then what the note says, as its title line and its body;
    a name alone is just the name. Quoted or not, with any joining word."""
    rest = rest.strip()
    quoted = _QUOTED_NAME.match(rest)
    if quoted and (not quoted.group("tail").strip() or _BODY_LEAD.match(quoted.group("tail"))):
        title, body = quoted.group("name").strip(), _BODY_LEAD.sub("", quoted.group("tail"), count=1).strip()
    else:
        plain = _PLAIN_NAME.match(rest)
        title, body = (plain.group("name").strip(), plain.group("tail").strip()) if plain else (rest, "")
    return f"{_cap(title)}\n{_cap(body)}" if title and body else _cap(title)


def _note_at_the_end(rest: str) -> dict | None:
    """"write down that the hotel is booked at the end of the lisbon trip note": an add, not a new note."""
    at_end = _split_last(rest, (" at the end of ",))
    found = _one_target(at_end[1]) if at_end else None
    if found and at_end[0].strip() and found.get("single"):
        return {"intent": "append", **found, "content": _cap(at_end[0])}
    return None


#: An act with nothing to write is still the act: asked for its words, never
#: read as a search of the notes (INBOX 1507).
_BARE_NOTE = frozenset({
    "make a note", "take a note", "new note", "quick note", "create a note", "write a note", "add a note",
    "save a note", "make note", "start a note", "start a new note", "make a new note", "create a new note",
    "write a new note", "note to self", "write something down", "jot something down", "note something down",
    "write it down", "jot it down", "make a quick note", "take a quick note",
})


#: What "make a note ..." can be followed by that is a setting of a note, not its words.
_NOTE_SETTINGS = frozenset({"private", "public", "locked", "secret", "hidden", "pinned", "archived"})


def _wordless_note(head: str, rest: str) -> dict | None | bool:
    """A "note ..." with nothing to write (G2): None for a look-up or a setting ("note about
    suica", "make a note private" are never a new note), the ask for its words for "make a
    note about suica", False when `rest` carries words to save."""
    if rest.lower().strip(" .") in _NOTE_SETTINGS:
        return None
    if rest.lower().startswith("about ") and ":" not in rest:
        return {"intent": "new_note", "content": "", "no_subject": True} if head != "note" else None
    return False


def _note_lead(rest: str) -> tuple[str, bool]:
    """`rest` without its "that", "saying", "called" ...; whether that was a name."""
    for lead in ("that ", "saying ", "of ", "about ", "to say ", *_NAMED):
        if rest.lower().startswith(lead):
            return rest[len(lead):], lead in _NAMED
    return rest, False


def _new_note(text: str) -> dict | None:
    low = text.lower()
    if low.strip(" .:-") in _BARE_NOTE:
        return {"intent": "new_note", "content": "", "no_subject": True}
    for head, needs_colon in _NOTE_HEADS_NEW:
        if not (low.startswith(head + " ") or low.startswith(head + ":")):
            continue
        rest = text[len(head):].lstrip()
        if head == "remember that" and rest.lower().startswith(("i ", "i'm ", "i’m ", "i've ", "i’ve ")):
            return None  # a preference of the person's, never a note (act_registry save_user_preference)
        if needs_colon and not rest.startswith(":") and not rest.lower().startswith((*_NAMED, "about ")):
            return None
        rest = rest.lstrip(" :-")
        if (wordless := _wordless_note(head, rest)) is not False:
            return wordless
        rest, named = _note_lead(rest)
        if named:
            said = _name_and_words(rest)
            return {"intent": "new_note", "content": said} if said else None
        appended_to = _note_at_the_end(rest)
        if appended_to:
            return appended_to
        rest = _cap(rest)
        return {"intent": "new_note", "content": rest} if rest else None
    return None


_FIND_HEADS = ("search for ", "look for ", "look up ", "show me ", "where is ", "where's ",
               "where are ", "get me ", "find ", "search ", "show ", "list ")
_OPEN_HEADS = ("take me to ", "jump to ", "pull up ", "bring up ", "go to ", "open ")
_FREE_FIND = ("find ", "search for ", "search ", "look for ", "look up ")
_LIST_HEADS = ("show me ", "show ", "list ", "get me ")
_WHOLE_LISTING = re.compile(r"(?:me )?(?:all |every )?(?:of )?(?:my |the |your )?(?:notes|entries)(?: please| pls| plz)?[?.!]*", re.I)


_ON_THE_WEB = re.compile(r"(?:the )?(?:web|internet|online)\b", re.I)


def _note_topic(rest: str) -> bool:
    """Whether what follows "search" is a topic in the notes: not a question,
    and not the web ("search the web for trains" is a web search, not a note
    find about "web", INBOX 801)."""
    return not _ASKING.match(rest) and not _ON_THE_WEB.match(rest)


def _listing(text: str, head: str, rest: str) -> dict | None:
    """A find that is a listing: {} for "show all my notes" (the newest
    notes, listed by the read route, not a find about "all my": the routing
    gold, 2026-10-11); "list my work notes" the Work notes, or the notes
    tagged work (ledger row 442); None for any other find."""
    if _WHOLE_LISTING.fullmatch(rest):
        return {}
    #: "show my newest notes", "list the notes I've made": the recent-notes
    #: listing the composer answers, never a find for the word "newest" (INBOX 1590).
    if head in _LIST_HEADS and re.search(r"\b(?:notes|entries)\b", rest, re.I) and note_recency.is_recency_ask(rest):
        return {}
    if head in _LIST_HEADS:
        filed = filed_listing(text)
        if filed:
            return {"intent": "find", "about": filed, "filed": filed}
    return None


#: "stuff ive mentioned abt gym": the filler before the topic is not part of it.
_TOPIC_FILLER = re.compile(
    r"^(?:(?:any ?thing|every ?thing|some ?thing|stuff|things|notes?|whatever|all) )?"
    r"(?:(?:that |which )?(?:i|ive|i've|i have|ive) )?(?:(?:mentioned|said|wrote|written|noted|saved|made|put|jotted|talked|typed) )?"
    r"(?:(?:about|abt|on|regarding|re|around|for) )?",
    re.I,
)
_NOTES_SCOPE = re.compile(r"\s+(?:in|from|within|across|inside) (?:all )?(?:of )?(?:my|the|your) (?:notes|notebook|entries)$", re.I)
_MENTIONING = re.compile(r"(?:what|which) notes (?:mention|contain|include) (?P<topic>.+?)[?.!\s]*", re.I)
_ASKED_FIND = re.compile(
    r"(?:do i have (?:any ?thing|any notes?|notes?)|(?:are there|is there|have i got)(?: any)?(?: notes?)?(?: anything)?|any notes?|"
    r"what notes (?:are about|do i have)|(?:show|give|get) me (?:everything|anything|all(?: of)? (?:my )?notes?))"
    r"(?: (?:i )?(?:wrote|have|saved|made|took))? (?:on|about|for|regarding|mentioning|mention|with|containing) (?P<topic>.+?)[?.!\s]*",
    re.I,
)


#: "what do my notes mentioning test say", "notes with test in them", "notes
#: that contain the word test" (INBOX 1487): the notes that hold a word, all
#: of them, listed by the notes search, never one note's best sentence. A bare
#: "with" counts only as "with X in them" ("notes with images" is a kind).
_HOLDERS = r"(?:(?:all|any|some) (?:of )?)?(?:my |the |our )?(?:notes|entries)"
_HOLDING = (
    r"(?:(?:that |which |where i )?(?:mentioning|mentions?|mentioned|containing|contains?|including|includes?|have|has|say|says|use|name|talk about)"
    r"|with(?= (?:the )?(?:words?|phrase|term) | [\w' -]{1,40} in (?:them|it)\W*(?:say\W*)?$))"
)
_WORD_NOTES = re.compile(
    r"(?:(?:please )?(?:(?:what|which) (?:do|does|did) |tell me what |show me what |what(?:'s| is) in |what are |which of |"
    r"(?:show(?: me)?|list|find|give me|get me|search for|look for|pull up|bring up) )(?:all )?)?"
    rf"{_HOLDERS} (?:do )?{_HOLDING} (?:the )?(?:(?:words?|phrase|term) )?(?P<topic>.+?)(?: in (?:them|it|there))?"
    r"(?: (?:say|says|tell me|have in them|have|hold|contain|mention))?[?.!\s]*",
    re.I,
)


def _word_notes(text: str) -> dict | None:
    """The find for a word the notes hold, or None."""
    found = _WORD_NOTES.fullmatch(text.strip())
    topic = _drop_article(found["topic"].strip()) if found else ""
    if not topic or re.match(r"(?:about|on|for|regarding)\b", topic, re.I) or not _note_topic(topic) or _asks_a_kind(text):
        return None
    return {"intent": "find", "about": topic}


_WHATS_IN = re.compile(
    r"(?:what(?:'s|s| is) in (?:my |the )?(?P<a>[\w&-]+(?: [\w&-]+)?) (?:category|folder|tag)"
    r"|(?:pull up|bring up) (?:my |the )?(?:notes|entries) (?:tagged(?: with)?|in|under) #?(?P<b>[\w&-]+(?: [\w&-]+)?))[?.!\s]*",
    re.I,
)


def _asks_a_kind(text: str) -> bool:
    from tessellate.ai import composer_lists  # on first use: the composer is not loaded by importing the commands

    return composer_lists.holding_ask(text) is not None


def _asks_an_order(text: str) -> bool:
    """"List my notes in order": the order is not a word to find (the composer lists them)."""
    from tessellate.ai import composer_lists

    #: "show my goals" and "list my lists" are the notes so headed (L254), listed by the composer too.
    return (composer_lists.list_order(text) or filed_name.kept_word(text)) is not None


def _find(text: str) -> dict | None:
    whats =_WHATS_IN.fullmatch(text.strip())
    if whats:
        filed = (whats["a"] or whats["b"]).strip()
        return {"intent": "find", "about": filed, "filed": filed}
    holding = _word_notes(text)
    if holding:
        return holding
    asked = _ASKED_FIND.fullmatch(text.strip()) or _MENTIONING.fullmatch(text.strip())
    if asked and _asks_a_kind(text):
        return None  # "what notes contain a checklist" asks for a kind of note, not a word (audit 1029 C34)
    if asked and _note_topic(asked["topic"]):
        about = _drop_article(_NOTES_SCOPE.sub("", asked["topic"].strip()))
        if about:
            return {"intent": "find", "about": about}
    return _find_by_head(text)


def _find_by_head(text: str) -> dict | None:
    """"open my lisbon note", "find notes about tea": the command a head opens."""
    low = text.lower()
    for heads, intent in ((_OPEN_HEADS, "open"), (_FIND_HEADS, "find")):
        head = next((h for h in heads if low.startswith(h)), None)
        if head is None:
            continue
        rest = text[len(head):].strip()
        if intent == "find" and (_sums_money(text) or _asks_an_order(text)):
            return None
        if intent == "find":
            listed = _listing(text, head, rest)
            if listed is not None:
                return listed or None
        return _found_object(intent, head, rest)
    return None


def _sums_money(text: str) -> bool:
    """"List my expenses" is the spending sum with its items, not a find for
    the word (INBOX 1456). Imported here: the money reader loads the composer."""
    from tessellate.ai import composer_money

    return composer_money.asks(text)


def _found_object(intent: str, head: str, rest: str) -> dict | None:
    """What an open or a find names: "#12", "note 12", a target, or for a
    free find ("find dentist") its topic."""
    #: A name the app cut short ("I had work today…", a chip's label).
    rest = _NOTES_SCOPE.sub("", rest).rstrip("…").rstrip()
    rest = find_topic.topic(rest) if intent == "find" else rest
    number = re.fullmatch(r"(?:(?:note|entry) )?#?(\d{1,9})", rest, re.IGNORECASE)
    if number and (rest.startswith("#") or not rest.isdigit()):
        return {"intent": intent, "note_id": int(number.group(1))}
    found = _target(rest)
    if found and found.get("about"):
        return {"intent": intent, "about": found["about"]}
    if intent == "find" and head in _FREE_FIND and rest and _note_topic(rest):
        about = _drop_article(_TOPIC_FILLER.sub("", _NOTES_SCOPE.sub("", rest), count=1)) or _drop_article(rest)
        about = find_topic.topic(about)  # "similar to my dentist one you know" searches "dentist" (B27)
        return {"intent": "find", "about": about} if about else None
    return None


_MEETING = re.compile(
    r"^(?:(?:start|begin|new|create|open|record|make|run|hold)(?: recording)?|take) (?:(?:a|an|the|new|my|our) )*meeting(?: notes?)?"
    r"(?: (about|on|for|called|named|titled|with) (.+)|: ?(.+))?$",
    re.IGNORECASE,
)
_NAMED_MEETING = re.compile(r"^(?:start|begin|record|open) (?:(?:a|an|the|my|our) )?([\w' -]{1,80}) meeting$", re.IGNORECASE)


def _meeting(text: str) -> dict | None:
    found = _MEETING.match(text)
    if found:
        word, said, colon = found.group(1), found.group(2), found.group(3)
        title = said or colon or ""
        if word and word.lower() == "with":
            return {"intent": "meeting", "title": f"Meeting with {title.strip()}"}
        return {"intent": "meeting", "title": _cap(_drop_article(title.strip()))}
    named = _NAMED_MEETING.match(text)
    if named:
        return {"intent": "meeting", "title": _cap(_drop_article(named.group(1).strip()))}
    return None


_SURFACES = {
    "settings": "settings", "the settings": "settings", "preferences": "settings",
    "graph": "graph", "the graph": "graph", "dashboard": "dashboard", "the dashboard": "dashboard", "home": "dashboard",
    "chat": "chat", "the chat": "chat", "library": "library", "the library": "library", "documents": "library",
    "timeline": "timeline", "the timeline": "timeline", "calendar": "timeline", "the calendar": "timeline", "reminders": "reminders",
    "my reminders": "reminders", "the reminders": "reminders", "notes": "notes", "my notes": "notes",
}


_CLOCK_UNIT = r"(?:hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)"
_CLOCK_ASK = re.compile(
    r"^(?:please )?(?:(?P<verb>set|start|begin|run|make|open|show)(?: me| up)?(?: a| an| the| my)?|(?=countdown|timer))"
    rf"(?: (?P<n1>\d+(?:\.\d+)?) ?(?P<u1>{_CLOCK_UNIT}))? ?(?P<kind>timer|countdown|pomodoro|stopwatch|clock)"
    rf"(?:(?: for| of)? (?P<n2>\d+(?:\.\d+)?) ?(?P<u2>{_CLOCK_UNIT}))?$")


def _clock_ask(text: str) -> dict | None:
    """"set a timer for 25 minutes", "start a pomodoro", "start a stopwatch": the Clock window
    opened on the right tab with the length ready. It starts nothing: Start is the person's press."""
    found = _CLOCK_ASK.match(text.strip(" .!").lower())
    if not found:
        return None
    kind = found.group("kind")
    if not found.group("verb") and not (found.group("n1") or found.group("n2")):
        return None  # a bare "timer" or "countdown" is a word to look up (1334, 1357 class B), not the Clock
    n, unit = (found.group("n1"), found.group("u1")) if found.group("n1") else (found.group("n2"), found.group("u2"))
    minutes = None
    if n is not None:
        minutes = round(float(n) * {"h": 60, "m": 1, "s": 1 / 60}[unit[0]], 3)
        minutes = int(minutes) if minutes == int(minutes) else minutes
    elif kind == "pomodoro":
        minutes = 25
    return {"intent": "navigate", "surface": "clock", "minutes": minutes, "tab": "stopwatch" if kind == "stopwatch" else "timer"}


def _navigate(text: str) -> dict | None:
    """"open settings", "go to the graph": a place in the app, not a note."""
    low = text.lower()
    for head in ("open ", "go to ", "take me to ", "show me ", "show ", "switch to "):
        if low.startswith(head):
            rest = low[len(head):].strip(" .")
            rest = rest.removesuffix(" tab").removesuffix(" page").removesuffix(" view").strip()
            if rest in _SURFACES:
                return {"intent": "navigate", "surface": _SURFACES[rest]}
    return None


def _plan_navigate(parsed: dict) -> dict:
    if parsed["surface"] == "clock":
        return _plan_clock(parsed)
    return {"line": f"Opening {parsed['surface']}.", "navigate": parsed["surface"]}


def _plan_clock(parsed: dict) -> dict:
    minutes = parsed.get("minutes")
    if parsed["tab"] == "stopwatch":
        line = "Opening the Clock on the stopwatch. Press Start when you are ready."
    elif minutes:
        say = f"{minutes:g} minute" + ("" if minutes == 1 else "s")
        line = f"Opening the Clock with {say} ready. Press Start to begin."
    else:
        line = "Opening the Clock. Pick a length and press Start."
    return {"line": line, "navigate": "clock", "minutes": minutes, "tab": parsed["tab"]}


def _one_target(text: str, *, bare: bool = False) -> dict | None:
    """The note a single-note verb names: "the boiler note", "my passport
    note", "this note", "the note about the boiler". `bare`: for a verb only a
    note can take, its title alone names it too ("pin the history essay")."""
    found = _target(text)
    if found:
        return found
    words = text.strip().split(" ")
    if words and words[-1].lower() in ("note", "entry"):
        about = _drop_article(" ".join(words[:-1]))
        if about:
            return {"about": about, "single": True}
    return _bare_target(text) if bare else None


def _delete(text: str) -> dict | None:
    low = text.lower()
    verb = next((v for v in ("delete ", "remove ", "bin ", "trash ", "throw away ", "get rid of ", "erase ", "discard ", "ditch ", "scrap ", "throw out ") if low.startswith(v)), None)
    if verb is None:
        return None
    rest = text[len(verb):].strip()
    if re.match(r"(?:the |a |my )?(?:tags?|labels?|reminders?|categor(?:y|ies)|board|map|document)\b", rest, re.I):
        return None
    found = _one_target(rest)
    if found is None and (found := _bare_target(rest)):
        found = {**found, "bare": True}  # a title alone named it: it must be the title (F3)
    return {"intent": "delete", **found} if found else None


def _pin(text: str) -> dict | None:
    low = text.lower()
    kept = _pinned_form(text)
    if kept:
        return kept
    for verb, intent in (("unpin ", "unpin"), ("pin ", "pin"), ("star ", "pin"), ("favourite ", "pin"), ("favorite ", "pin"),
                         ("unstar ", "unpin"), ("unfavourite ", "unpin"), ("unfavorite ", "unpin")):
        if low.startswith(verb):
            rest = text[len(verb):].strip()
            for tail in (" to the top", " at the top", " to top", " to the sidebar"):
                if rest.lower().endswith(tail):
                    rest = rest[: -len(tail)].strip()
            found = _one_target(rest, bare=True)
            return {"intent": intent, **found} if found else None
    return None


#: Verbs that take a tag off a note; all but "untag" need the word tag or label said.
_UNTAG_VERBS = ("untag", "remove", "take", "delete", "strip", "drop", "clear", "unlabel")
_TAG_WORD = re.compile(r"^(?:the |a )?(?:tags?|labels?) ", re.I)
_TAG_TAIL = re.compile(r" (?:tags?|labels?)$", re.I)


#: "keep the passport note pinned", "put the budget note at the top": a pin said without the verb.
_PIN_VERBS = ("keep ", "put ", "move ", "bring ")
_PIN_TAILS = (" pinned", " at the top", " to the top", " on top", " at top", " to top")


def _pinned_form(text: str) -> dict | None:
    low = text.lower()
    verb = next((v for v in _PIN_VERBS if low.startswith(v)), None)
    tail = next((t for t in _PIN_TAILS if low.endswith(t)), None)
    if not verb or not tail:
        return None
    found = _one_target(text[len(verb): -len(tail)].strip(), bare=True)
    return {"intent": "pin", **found} if found else None


_NOTE_ABOUT = re.compile(r"^(?:the |this |my )?(?:note|entry) (?:about|on|called|named|titled) (.+)$", re.I)


def _untag(text: str) -> dict | None:
    """"untag the budget note finance", "remove the tag travel from X",
    "take the urgent tag off this note", "strip the tag money from X"."""
    verb, _, body = text.partition(" ")
    if verb.lower() not in _UNTAG_VERBS or not body:
        return None
    lead = _TAG_WORD.match(body)
    split = _split_last(body[lead.end():] if lead else body, (" from ", " off "))
    if not split:
        named = _NOTE_ABOUT.match(body)  # "untag the note about boiler" names a note and no tag (L-chat-29)
        if named and verb.lower() in ("untag", "unlabel"):
            return {"intent": "untag", "about": _drop_article(named.group(1).strip()), "single": True, "tags": []}
        found = _note_then_tags(body) if verb.lower() in ("untag", "unlabel") else None
        return {**found, "intent": "untag"} if found else None
    tags, target = split
    tail = _TAG_TAIL.search(tags)
    if verb.lower() not in ("untag", "unlabel") and not (lead or tail):
        return None
    tags = _tags(_drop_article(tags[: tail.start()] if tail else tags))
    found = _target(target)
    return {"intent": "untag", **found, "tags": tags} if found and tags else None


#: (verb, intent, the words that split the two notes).
_LINK_VERBS = (
    ("unlink ", "unlink", (" from ", " and ")), ("disconnect ", "unlink", (" from ", " and ")),
    ("link ", "link", (" to ", " with ", " and ")), ("connect ", "link", (" to ", " with ", " and ")),
    ("relate ", "link", (" to ", " with ", " and ")), ("join ", "link", (" to ", " with ", " and ")),
    ("associate ", "link", (" to ", " with ", " and ")),
)


def _link(text: str) -> dict | None:
    low = text.lower()
    for verb, intent, seps in _LINK_VERBS:
        if low.startswith(verb):
            split = _split_last(text[len(verb):], seps)
            if not split:
                return None
            a, b = (_one_target(part.strip(), bare=True) for part in split)
            if a and b and a.get("about") and b.get("about"):
                numbered = {k: v for k, v in (("note_id", a.get("note_id")), ("other_id", b.get("note_id"))) if v is not None}
                return {"intent": intent, "about": a["about"], "other": b["about"], "single": True, **numbered}
            return None
    return None


def _rename_called(text: str) -> dict | None:
    """"call the budget note household budget", "title this note meeting notes"."""
    low = text.lower()
    head = next((h for h in ("call ", "title ", "name ", "retitle ") if low.startswith(h)), None)
    cut = low.find(" note ")
    if head is None or cut <= len(head):
        return None
    found = _one_target(text[len(head): cut + len(" note")].strip())
    #: A title is a short noun phrase: a clause before "note" is a sentence.
    if found and found.get("about") and not _bare_target(found["about"]):
        return None
    title = text[cut + len(" note "):].strip(" '\"“”")
    for lead in ("as ", "to "):
        if title.lower().startswith(lead):
            title = title[len(lead):]
    return {"intent": "rename", **found, "title": title} if found and title and len(title) <= 200 else None


def _rename(text: str) -> dict | None:
    low = text.lower()
    called = _rename_called(text)
    if called:
        return called
    body = text.split(" ", 1)[1] if low.startswith(("rename ", "retitle ")) else ""
    for lead in ("change the title of ", "change the name of ", "change my title of ", "set the title of ", "set the name of "):
        if low.startswith(lead):
            body = text[len(lead):]
    if not body:
        return None
    #: The target ends at the first " to " after the word note ("the Atlas
    #: note to Trip to Lisbon"), else at the first one: a title may hold
    #: "to"/"as" itself, a split at the last would drop its words (C41).
    cut = re.search(r"(?i)\b(?:note|doc|document|page|list)(\s+(?:to|as)\s+)", body) or re.search(r"(?i)(\s(?:to|as)\s)", body)
    if not cut or cut.start(1) <= 0:
        return None
    target, title = body[: cut.start(1)], body[cut.end():]
    found = _one_target(target.strip(), bare=True)
    title = title.strip(" '\"“”")
    if found and title and len(title) <= 200:
        return {"intent": "rename", **found, "title": title, **_other_splits(body, cut.start(1))}
    return None


def _other_splits(body: str, first: int) -> dict:
    """Every later " to " of an unquoted rename is another place the old name could end
    ("rename Trip to Spain to Trip to Portugal"): `plan` keeps the longest one that names a note (L47)."""
    alts = []
    for later in re.finditer(r"(?i)\s(?:to|as)\s", body):
        if later.start() <= first:
            continue
        found, title = _one_target(body[: later.start()].strip(), bare=True), body[later.end():].strip(" '\"“”")
        if found and found.get("about") and title and len(title) <= 200:
            alts.append({"about": found["about"], "title": title})
    return {"alts": alts} if alts else {}


#: Verbs that put words on a note; the flag says the target must be a note or
#: a list-like name, so "put this note in projects" stays a filing.
_APPEND_VERBS = {"add": False, "append": False, "put": True, "stick": True, "pop": True, "tack": True, "update": True}
_APPEND_EXCEPT = ("add tag", "add the tag", "add a tag", "add label", "add the label", "add a reminder", "add a note")
_LINE_NOUN = re.compile(r"^(?:a |one |another )?(?:line|bullet|item|entry|point|row)s? (?:on )?(?=to |onto |on to |in |into )", re.I)
_LISTISH = ("list", "checklist", "log", "journal", "diary", "tracker")


def _append_parts(verb: str, body: str) -> tuple[str, str] | None:
    """(the words, the note's name) of "add X to Y", "add a line to Y: X",
    "append to Y: X", "update Y with X", or None."""
    body = _LINE_NOUN.sub("", body)
    low = body.lower()
    if verb == "update":
        split = body.split(" with ", 1)
        return (split[1], split[0]) if len(split) == 2 else None
    for lead in ("to ", "onto ", "on to "):
        if low.startswith(lead):
            rest = body[len(lead):]
            for sep in (": ", " saying ", " that says "):
                if sep in rest:
                    target, words = rest.split(sep, 1)
                    return words, target
            return None
    split = _split_last(body, (" to ", " onto ", " on ", " in ", " into "))
    return (split[0], split[1]) if split else None


def _starter_place(found: dict | None, target: str) -> bool:
    """The daily note, and "my journal" (a note called that, else today's): the
    composer's own (starter acts), not an append to a note found by name."""
    about = str((found or {}).get("about", "")).lower()
    return bool(re.fullmatch(r"(?:my )?(?:journal|diary)", target.strip().lower()) or about.startswith(("today", "yesterday", "tomorrow", "daily")))


def _append(text: str) -> dict | None:
    low = text.lower()
    verb, _, body = text.partition(" ")
    needs_list = _APPEND_VERBS.get(verb.lower())
    if needs_list is None or low.startswith(_APPEND_EXCEPT) or not body:
        return None
    parts = _append_parts(verb.lower(), body)
    if not parts:
        return None
    words, target = parts
    #: "add milk to my shopping list": a thing that is theirs (my, our) or a
    #: list-like name is a title, though it says no "note".
    #: "add to the Q4 report: words" names its note by the colon (R9-12).
    colon = bool(re.match(r"(?:to|onto|on to) [^:]+: ", body, re.I))
    named = colon or target.lower().startswith(("my ", "our ")) or target.lower().split(" ")[-1] in _LISTISH
    found = _one_target(target.strip(), bare=named)
    if _starter_place(found, target):
        return None
    if needs_list and not (found and (named or target.lower().rstrip().endswith(("note", "entry")))):
        return None
    words = words.strip(" '\"“”")
    if found and found.get("single", True) and words:
        return {"intent": "append", **found, "single": True, "content": _cap(words)}
    return None


_SUMMARISE_HEADS = (
    "summarise ", "summarize ", "sum up ", "give me a summary of ", "give me a quick summary of ", "give me a short summary of ",
    "quick summary of ", "short summary of ", "a summary of ", "summary of ", "tl;dr ", "tldr ", "recap ", "what is the gist of ",
    "what's the gist of ", "the gist of ", "gist of ",
)
_WROTE = re.compile(r"^(everything|all) (?:that )?i(?:'ve| have)? (?:wrote|written|noted|said) ", re.I)


def _summarise(text: str) -> dict | None:
    low = text.lower()
    for head in _SUMMARISE_HEADS:
        if low.startswith(head):
            rest = _WROTE.sub(r"\1 ", text[len(head):].strip())
            found = _target(rest) or (_one_target(rest, bare=True) if rest.lower().startswith(("my ", "our ")) else None)
            if found and found.get("about"):
                return {"intent": "summarise", "about": found["about"], **({"note_id": found["note_id"]} if found.get("note_id") is not None else {})}
            whole = re.match(r"(?:all )?(?:of )?(?:my |the )?notes\b(?: (?:from|for|in) )?(.*)$", rest, re.I)
            if whole:
                #: "summarise my notes from this week": the notes of a while.
                return {"intent": "summarise", "about": whole.group(1).strip() or "notes"}
    return None


_SIMILAR = re.compile(
    r"^(?:(?:please|can you|could you)\s+)?(?:(?:find|show|get|list|give)(?:\s+me)?\s+)?(?:(?:the|any|all|some|other|more)\s+)*(?:notes?\s+)?(?:that\s+(?:are|is)\s+)?(?:similar to|like|related to|close to)\s+(?P<t>.+?)[?.!]*$",
    re.I,
)


def _similar(text: str) -> dict | None:
    """"find notes similar to the boiler note", "similar to note 12": the notes close in meaning to one (L-chat-29)."""
    found = _SIMILAR.match(text)
    if not found or not re.search(r"\bsimilar\b|\bnotes? like\b|\bthose like\b|\bnotes? (?:related|close) to\b", text, re.I):
        return None
    #: Only a note named as one ("the boiler note", "note 12", "the lisbon one"): "similar to my dentist
    #: one you know" is the owner's search for the dentist (B27), never a bare-word target.
    target = _target(found.group("t"))
    return {"intent": "similar", **target} if target and target.get("single", True) else None


#: Arguments of an act that are the person's own words (never respelt).
OWN_WORDS = ("content", "title", "tags", "text", "said", "old", "new")


#: What an act names keeps slang as typed but a misspelling put right (the
#: lookup is helped by it); what it writes keeps every word as typed.
_KEYS_NAMED = ("about", "asked")
_WRITTEN = (*OWN_WORDS, "on_list")
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")


def _respellings(text: str, fixed: str, fixes: list) -> list[tuple[str, str, bool]]:
    """Each word the speller changed one for one, as (chosen, typed, slang).
    A chosen word the person also typed somewhere is left out: "at" put back
    as "oat" would undo their own "at"."""
    from difflib import SequenceMatcher

    typed, read_as = _WORD.findall(text.lower()), _WORD.findall(fixed.lower())
    put_right = {(str(a).lower(), str(b).lower()) for a, b in fixes}
    pairs = []
    for op, i1, i2, j1, j2 in SequenceMatcher(None, typed, read_as, autojunk=False).get_opcodes():
        if op == "replace" and i2 - i1 == j2 - j1:
            pairs += [(b, a, (a, b) not in put_right) for a, b in zip(typed[i1:i2], read_as[j1:j2]) if b not in typed]
    return pairs


def _put_back(value, pairs: list[tuple[str, str, bool]]):  # noqa: ANN001, ANN202
    if isinstance(value, list):
        return [_put_back(v, pairs) for v in value]
    if not isinstance(value, str):
        return value
    for chosen, typed, _ in pairs:
        value = re.sub(rf"\b{re.escape(chosen)}\b", lambda m, t=typed: t[:1].upper() + t[1:] if m.group(0)[:1].isupper() else t, value, flags=re.I)
    return value


def _as_typed(found: dict, text: str, fixed: str, fixes: list) -> dict:
    """The person's own words back in the act (audit 1028 E9, 1029 C40):
    "delte my uni note" names their category Uni, not "university", and "add
    uni fees to the todo list" writes "Uni fees". The speller served the verb."""
    pairs = _respellings(text, fixed, fixes)
    if not pairs:
        return found
    slang = [p for p in pairs if p[2]]
    out = dict(found)
    for key in _WRITTEN:
        if key in out:
            out[key] = _put_back(out[key], pairs)
    for key in _KEYS_NAMED:
        if key in out and slang:
            out[key] = _put_back(out[key], slang)
    return out


def _words_as_typed(found: dict, text: str, now: datetime, locale: str | None) -> dict:
    """The act's own words from the typed reading, for the same intent."""
    from tessellate.ai import question_noise

    head, _, tail = (text or "").partition(" ")
    typed = read(text, now, locale) or (read(f"{question_noise.repair(head)} {tail}", now, locale) if tail else None)
    #: A reminder's words are cut at its time ("tmrw" is left in the typed
    #: reading), so those are taken only when they are the same length.
    if typed is None or typed.get("intent") != found.get("intent"):
        return found
    own = {k: typed[k] for k in OWN_WORDS if k in typed and k in found and (not isinstance(typed[k], str) or len(typed[k].split()) == len(str(found[k]).split()))}
    return {**found, **own}


def read_typed(text: str, now: datetime, locale: str | None = None) -> dict | None:
    """`read` of the sentence as the speller puts it right ("remnd me to pay
    rent on friday", "delte my old wifi note"), else as typed: the owner's
    typos are part of the gold (`fixtures/composer/tasks_1011.json`)."""
    from tessellate.ai import question_noise

    fixes: list = []
    fixed = question_noise.repair(question_noise.tidy(text or ""), fixed=fixes)
    found = (read(fixed, now, locale) if fixed and fixed != text else None) or read(text, now, locale)
    #: The words an act writes are the person's own, never spell-corrected
    #: ("add oat milk to the packing list" must not write "At milk"); the
    #: speller only serves the verb and the target (audit 1029 C40).
    if found is not None and fixed != text:
        found = _as_typed(_words_as_typed(found, text, now, locale), text, fixed, fixes)
    narrower = _narrower(question_noise.tidy(text or ""), found, now, locale) if text else None
    if narrower is not None:
        return narrower
    if found is not None or not text:
        return found
    return _slipped(question_noise.tidy(text), now, locale)


def _slipped(tidy: str, now: datetime, locale: str | None) -> dict | None:
    """One word a slip from a word the commands read ("pin the dentist noe",
    "unlnk the gym note"), read so when that makes it a command (O3)."""
    from tessellate.ai import question_noise

    takes = lambda t: read(t, now, locale) is not None  # noqa: E731
    #: A slip that lands on another word ("remiders" is "re" and "mid" and "ers", "skull") is read as the
    #: command word only when the commands then take the sentence.
    guided = question_noise.guided(tidy, takes)
    if guided:
        return read(guided, now, locale)
    #: A real word swapped for another ("oven" for "open", "last" for "list") is kept only when it makes one of the
    #: parity acts' own sentences; "oven timer" and "my last three notes" are questions, not the Clock or a list.
    real = question_noise.guided(tidy, takes, real_to=parity_acts.words())
    parsed = read(real, now, locale) if real else None
    return parsed if parsed and parsed.get("intent") in parity_acts.INTENTS | {"untag"} else None

#: Acts named by a noun the broad acts would swallow on a slip: "delete the
#: skull Weekly tidy" is the skill, not a note called "skull Weekly tidy";
#: "find noes similar to" is similar notes, "make a mid map" a mind map.
_NARROW = {"delete": {"delete_skill", "delete_document"}, "find": {"similar"}, None: {"make_map", "similar", "board_card", "set_theme"}}


def _narrower(tidy: str, found: dict | None, now: datetime, locale: str | None) -> dict | None:
    """The narrower act one slipped word away, when the sentence read as a
    broad one (or none); None when no such reading exists."""
    from tessellate.ai import question_noise

    wanted = _NARROW.get(found.get("intent") if found else None)
    if not wanted:
        return None
    phrases = " ".join(f"{a.label} {a.example}" for a in act_registry.ACTS.values() if a.intent in wanted).lower()
    reading = question_noise.guided(tidy, lambda t: (read(t, now, locale) or {}).get("intent") in wanted, real_to=frozenset(re.findall(r"[a-z]{4,}", phrases)))
    return read(reading, now, locale) if reading else None


#: Intent reads the typed commands through the leaf (act_registry.py says why).
act_registry.typed_reader = read_typed


def _time_of(words: str, now: datetime, locale: str | None) -> datetime | None:
    """A time said after "until" or "to" ("friday", "tomorrow 5pm", "2 hours"),
    read by the recogniser; a bare length counts from now."""
    return when.resolve(words, now, locale=locale) or when.resolve("in " + words, now, locale=locale)


#: Matched on single-spaced text (see `read`), words joined by one space, so
#: a run of blanks has one reading and the match stays linear.
_TO_THE_BIN = re.compile(r"^(?:move|put|send|throw|chuck) (\S+(?: \S+)*?) (?:in|into|to) the (?:bin|trash|rubbish|recycle bin|rubbish bin|trash can)$", re.I)


def read(text: str, now: datetime, locale: str | None = None) -> dict | None:
    """The command `text` is, as {"intent", ...arguments}, or None. `locale`
    orders a numeric date in a reminder ("3/4"); none reads day first."""
    command, question, polite, urgent = _fold_urgent(text)
    if not command or composer_calendar.bulk(command):
        return None
    command = composer_calendar.restate(command)
    #: "move the lentil soup note to the bin" says delete in other words.
    binned = _TO_THE_BIN.match(" ".join(command.split()))
    if binned:
        command = f"delete {binned.group(1)}"
    if re.match(r"(?i)archive\b", command):
        #: Decision 42: archiving stays a UI action; no act archives.
        return None
    found = _read_folded(command, question, polite, urgent, now, locale)
    lead = next((w for w in _CASUAL if command.lower().startswith(w)), None)
    if found is None and lead:
        found = _read_folded(command[len(lead):].lstrip(" ,"), question, True, urgent, now, locale)
    return found


#: "call Anna": a bare imperative to a person, a task not a search. A name as typed (capitalised), a kin
#: word, "the dentist" or "my boss", and for the phone verbs a name in lower case ("call anna", B25).
_KIN = r"mum|mom|dad|nan|nana|gran|granny|grandma|grandpa|auntie|aunty|uncle"
_BARE_CALL = re.compile(
    rf"^(?i:(?P<verb>call|ring|phone|text|email|message|ping|whatsapp))\s+(?P<who>(?:[A-Z][\w'’-]+(?: [A-Z][\w'’-]+)?)|(?i:{_KIN})|(?i:(?:the|my|our) [a-z]+))(?P<more>\s+(?i:(?:on|at|by|about|for|tomorrow|tonight|today|this|next|in)\b).+)?$"
    rf"|^(?i:(?P<verb2>call|ring|phone))\s+(?P<who2>[a-z][a-z'’-]{{1,20}})$"
)
#: What a lower-case "call X" is not a person: a pronoun, a time or a place.
_NOT_A_PERSON = frozenset({"me", "it", "us", "back", "them", "him", "her", "you", "again", "later", "now", "today", "tomorrow", "tonight", "home", "off", "out", "up", "down", "in", "over", "this", "that", "these", "those", "ahead", "away"})


def _bare_call(text: str, now: datetime, locale: str | None) -> dict | None:
    """"call Anna" is "remind me to call Anna": the same reminder, asking when (composer-r8)."""
    found = _BARE_CALL.match(text)
    who = found and (found.group("who") or found.group("who2"))
    if not found or who.lower() in _NOT_A_PERSON:
        return None
    if found.group("who2"):  # "call anna": the name is said with its capital
        text = f"{found.group('verb2')} {who[:1].upper()}{who[1:]}"
    return _reminder(f"remind me to {text}", now, locale)


def _read_folded(command: str, question: bool, polite: bool, urgent: bool, now: datetime, locale: str | None) -> dict | None:
    for reader in (address.read_set, object_acts.read_make, lambda t: parity_acts.read(t, _one_target, lambda w: _time_of(w, now, locale)), lambda t: surface_acts.read(t, _one_target), anchor_acts.read, task_acts.read_checklist_note, _meeting, _clock_ask, lambda t: _reminder(t, now, locale), lambda t: task_acts.read_add(t, lambda r: _reminder(r, now, locale)),
                   task_acts.read_uncomplete, task_acts.read_complete, task_acts.read_cancel, lambda t: task_acts.read_snooze(t, lambda w: _time_of(w, now, locale)), lambda t: _bare_call(t, now, locale), _new_note, _untag, _tag, _move, _delete, _pin, _link, object_acts.read_rename, lambda t: object_acts.read_restore(t, _one_target), _rename,
                   _append, _similar, _summarise, _navigate, _find):
        found = reader(command)
        if found is None:
            continue
        if question and not polite and found["intent"] in WRITE_INTENTS:
            # "Note: is the boiler code 4471?" asks; it does not tell.
            return None
        if urgent and found["intent"] == "reminder" and not found.get("time_given"):
            #: "asap" is when: a few minutes on, said so, and the card shows it.
            found = {**found, "due_at": now + timedelta(minutes=10), "time_given": True}
        return found
    return None


@dataclass
class Command:
    """One act, read from a sentence (decision 38): its verb, its object in
    the person's own words, when (a reminder's), whether it waits for Confirm
    (`confirm`: delete always does), and the arguments `plan` reads."""

    verb: str
    object: str
    when: datetime | None
    confirm: bool
    args: dict = field(default_factory=dict)


#: The slot that names the object of an act, by intent.
_OBJECT_KEY = {
    "navigate": "surface", "rename_tag": "old", "rename_category": "old", "merge_categories": "from", "to_reminders": "source",
    **dict.fromkeys(("new_note", "append"), "content"),
    **dict.fromkeys(("set_name", "create_category", "delete_category", "delete_tag", "run_skill", "delete_document", "delete_skill"), "name"),
    "remember": "preference",
}


def _object_of(found: dict, intent: str) -> str:
    """What the act is done to, as the card and the history name it."""
    if intent == "reminder":
        #: The reminder's own words as typed after the time came off, first
        #: letter as typed ("call Sam"); the reminder stores them capitalised.
        return found.get("said") or found["text"]
    if intent == "meeting":
        return found.get("title") or "meeting"
    if intent in _OBJECT_KEY:
        return found[_OBJECT_KEY[intent]]
    if found.get("note_id") is not None:
        return f"note {found['note_id']}"
    return found.get("about") or found.get("title") or ("these notes" if found.get("these") else "")


def parse(text: str, now: datetime) -> Command | None:
    """The `Command` `text` is, or None for a sentence that is not one."""
    found = read(text, now)
    if found is None:
        return None
    intent = found["intent"]
    obj = _object_of(found, intent)
    return Command(
        verb=_VERB_OF[intent],
        object=obj,
        when=found.get("due_at"),
        confirm=intent in CONFIRM_INTENTS,
        args=found,
    )


# --- plan ----------------------------------------------------------------------


def _content_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[\w']+", text.lower()) if len(w) > 1 and w not in _STOP]


_STOP = frozenset({"the", "a", "an", "my", "of", "and", "or", "to", "in", "on", "for", "with", "about", "all"})


def _notes_about(session: Session, about: str, single: bool) -> list:
    """The notes "about Z" names: every word of Z in the note's text or tags.

    Read as words, not by meaning, on purpose: these notes are about to be
    written to, and a write wants the notes that say the thing, not the ones
    that are near it. Ranked by the search the agent's own `search_notes`
    uses, so "the note about Z" is that search's first match.
    """
    from tessellate.core import deps
    from tessellate.entry import manager
    from tessellate.search import search_manager

    words = _content_words(about)
    if not words:
        return []
    found = search_manager.retrieve_detailed(session, about, deps.get_embeddings(), limit=_MAX_NOTES)
    picked = []
    for entry in found.entries:
        if entry.id in found.connected_ids or entry.is_deleted:
            continue
        hay = (entry.content or "").lower() + " " + " ".join(manager.entry_tags(entry)).lower()
        if all(re.search(rf"\b{re.escape(w)}", hay) for w in words):
            picked.append(entry)
    return picked[:1] if single else picked


def _attached(session: Session, note_ids: list[int] | None) -> list:
    from tessellate.entry import manager

    out = []
    for note_id in note_ids or []:
        entry = manager.get_entry(session, int(note_id))
        if entry is not None:
            out.append(entry)
    return out


def _existing_category(session: Session, name: str) -> str | None:
    from tessellate.core.database import Category

    wanted = name.casefold()
    for existing in session.scalars(select(Category.name)):
        if existing and existing.casefold() == wanted:
            return existing
    return None


def _split_allowed(entries: list) -> tuple[list, list[dict]]:
    """(the notes a write may touch, the ones it may not, with the reason)."""
    ok, skipped = [], []
    for entry in entries[:_MAX_NOTES]:
        if entry.is_deleted:
            skipped.append({"id": entry.id, "reason": "binned"})
        elif entry.is_private:
            skipped.append({"id": entry.id, "reason": "private"})
        else:
            ok.append(entry)
    return ok, skipped


def _which(parsed: dict, session: Session, note_ids: list[int] | None) -> tuple[list, str]:
    """The notes a tag or move names, and how to say which they are."""
    if parsed.get("these"):
        return _attached(session, note_ids), "the attached notes"
    if parsed.get("note_id") is not None:
        return _attached(session, [parsed["note_id"]]), f"numbered {parsed['note_id']}"
    about = parsed.get("about") or ""
    return _notes_about(session, about, bool(parsed.get("single"))), f"about “{about}”"


#: What the card says under its label: the person decides, nothing has run.
CONFIRM_NOTICE = "Nothing changes until you confirm, and Undo takes it back."
_SKIP_REASONS = {
    "private": "it is private", "binned": "it is in the bin", "failed": "it could not be changed", "stale": "it changed since the card was made",
    "unfound": "no open task or reminder has that name", "unclear": "more than one fits, so say it with more of its name",
}


def _card(label: str, steps: list[dict], skipped: list[dict] | None = None, items: list[str] | None = None) -> dict:
    """The act's card (decision 38): the exact change, the notes it names,
    the steps Confirm runs."""
    return {
        "type": "act",
        "name": "command",
        "label": label,
        "steps": steps,
        "skipped": skipped or [],
        "items": items or [],
        "notice": CONFIRM_NOTICE,
        #: The line the composer says above the card already reads the label (`_confirm`), so the card
        #: does not repeat it (L57: the bubble said the same sentence twice). A model's proposed card
        #: has no such line; `acts.propose` takes this back.
        "label_said": True,
    }


def _skipped_said(skip: dict) -> str:
    """One skipped row as `not_done` says it: a note by its number, a task by its name."""
    why = _SKIP_REASONS.get(skip.get("reason"), "it could not be changed")
    if skip.get("id"):
        return f"note {skip['id']} ({why})"
    return f"“{skip['name']}” ({why})" if skip.get("name") else _SKIP_REASONS.get(skip.get("reason"), "a step failed")


def not_done(skipped: list[dict]) -> str:
    """"Not done: note 12 (it is private)." for the notes a change left."""
    if not skipped:
        return ""
    said = [_skipped_said(s) for s in skipped]
    return "Not done: " + ", ".join(said) + "."


def summarise_done(labels: list[str], skipped: list[dict], say=None) -> str:  # noqa: ANN001
    """The one line a run ends with: what was done, then what was not."""
    #: A tool's label may open with its icon ("ph:trash Moved note 13 ..."),
    #: which the page draws only at the start of a line: taken off here.
    done = "; ".join(re.sub(r"^ph:[\w-]+\s+", "", label).rstrip(".") for label in labels if label)
    line = (say(done) if say else f"Done: {done}.") if done else "Nothing was changed."
    return f"{line} {not_done(skipped)}".strip()


def _when_words(due: datetime) -> str:
    return f"{due.strftime('%a')} {due.day} {due.strftime('%b')} at {due.strftime('%H:%M')}"


def _clock(due: datetime) -> str:
    """"9am", "9:30am", "noon", "midnight", "5pm", "12:39pm": the hour as
    people say it, always with its half of the day, so a card never mixes
    "at 9" with "at 3pm" (L-chat-25)."""
    hour, minute = due.hour, due.minute
    if minute == 0 and hour in (0, 12):
        return "midnight" if hour == 0 else "noon"
    said = str(hour % 12 or 12) + (f":{minute:02d}" if minute else "")
    return said + ("pm" if hour >= 12 else "am")


def _how_soon(due: datetime, now: datetime) -> str:
    """"in 45 minutes", "in an hour", "in about 2 hours": a time within three
    hours said by how soon it is (audit 1029 C47), else ""."""
    #: Both read as wall-clock time, as the day test below them is.
    minutes = round((due.replace(tzinfo=None) - now.replace(tzinfo=None)).total_seconds() / 60)
    if not 0 < minutes <= 180:
        return ""
    if minutes < 60:
        return f"in {minutes} minute{'' if minutes == 1 else 's'}"
    hours = round(minutes / 60)
    about = "" if minutes % 60 == 0 else "about "
    return f"in {about}{'an hour' if hours == 1 else f'{hours} hours'}"


def reminder_when(due: datetime, now: datetime, default_clock: bool = False) -> str:
    """When, said against today (INBOX 734): "today at 5pm", "tomorrow at
    9", "on Friday at 9", "on 21 October at 9". A clock the person did not
    say is named as the default: "on Tuesday at 9am (the default)" (audit
    1031 C41)."""
    soon = _how_soon(due, now)
    if soon:
        return f"{soon}, at {_clock(due)}"
    clock = _clock(due)
    if default_clock:
        clock = f"{clock} (the default)"
    days = (due.date() - now.date()).days
    if days == 0:
        day = "today"
    elif days == 1:
        day = "tomorrow"
    elif 1 < days < 7:
        day = f"on {due.strftime('%A')}"
    else:
        day = f"on {due.day} {due.strftime('%B')}" + (f" {due.year}" if due.year != now.year else "")
    return f"{day} at {clock}"


#: Verbs a reminder opens with, left out when finding the note it is about.
_TASK_VERBS = frozenset("call ring phone text email message book buy pay send check collect pick get see meet ask tell renew cancel finish start fix write read".split())


def _reminder_note(session: Session, said: str, note_ids: list[int] | None):  # noqa: ANN202
    """The note a reminder comes from: the one attached, else the first note
    holding every word of its object ("call the dentist": the Dentist note)."""
    attached = _attached(session, note_ids)
    if len(attached) == 1:
        return attached[0]
    words = [w for w in _content_words(said) if w not in _TASK_VERBS]
    if not words:
        return None
    found = _notes_about(session, " ".join(words), single=True)
    if not found or getattr(found[0], "is_private", False):
        return None
    #: One common word in a body is not a source ("call mum" met the Lentil
    #: soup note): the object must name the title, or two words must meet
    #: (audit 1030 A16).
    title = note_title(found[0].content, size=48).lower()
    if len(words) < 2 and not all(re.search(rf"\b{re.escape(w)}", title) for w in words):
        return None
    return found[0]


def _task_into_note(session: Session, parsed: dict, note_ids: list[int] | None) -> dict | None:
    """The plan that appends a task to a note called that ("add milk to my
    to-do list"), or None when no note is."""
    if parsed.get("on_list") and not parsed.get("time_given"):
        #: "add buy stamps to my todo": a line on the note called that, or one offered (R3-33).
        return task_acts.plan_task_line(session, parsed, _card, lambda note: note_title(note.content, size=48), _confirm)
    #: "add milk to my to-do list" when a note is called that: the note
    #: gets the line, as before tasks were acts (E10).
    #: `_fold` reads "to-do" as "to do"; a title keeps its hyphen.
    for asked in {parsed["asked"], re.sub(r"\bto do\b", "to-do", parsed["asked"])}:
        alt = _append(asked)
        if alt and not alt.get("these") and _resolve_one(session, alt.get("about"), None, False)[0] is not None:
            return _plan_one(session, alt, note_ids)
    return None


def _plan_task(session: Session, parsed: dict) -> dict:
    """Complete, cancel or snooze the task a sentence names (`task_acts`)."""
    intent = parsed["intent"]
    title = lambda note: note_title(note.content, size=48)  # noqa: E731
    if intent == "cancel":
        return task_acts.plan_cancel(session, parsed, _card, title)
    if intent == "snooze":
        from tessellate.core import deps
        from tessellate.core.config import user_now

        now = user_now(deps.get_config()).replace(tzinfo=None)
        return task_acts.plan_snooze(session, parsed, _card, title, lambda due: reminder_when(due, now), now)
    if intent == "uncomplete":
        return task_acts.plan_uncomplete(session, parsed, _card, title)
    return task_acts.plan_complete(session, parsed, _card, title)


#: How a stored repeat is said after the first time (R9-12).
_REPEAT_WORDS = {"daily": "every day", "weekly": "every week", "monthly": "every month"}


def _plan_reminder(session: Session, parsed: dict, note_ids: list[int] | None) -> dict:
    """The card for a reminder, or a task with a day."""
    #: "Remind you on Friday at 9: call the dentist" (INBOX 734): the
    #: person's own words after the colon, the time said against today,
    #: and the note it comes from, which the reminder is attached to.
    from tessellate.core import deps
    from tessellate.core.config import user_now

    if parsed.get("anchor"):
        parsed = anchor_acts.settle(session, parsed, user_now(deps.get_config()).replace(tzinfo=None))
    due = parsed["due_at"]
    if due is None:
        return {"line": parsed.get("ask", _ASK_WHAT_AND_WHEN)}
    when_said = reminder_when(due, user_now(deps.get_config()).replace(tzinfo=None), bool(parsed.get("clock_unsaid")))
    if parsed.get("no_subject"):
        #: Only a time was said: the words are asked, not stored as "5pm".
        return {"line": f"What should I remind you about {when_said}?"}
    when_said += (
        "" if parsed.get("time_given") else " (no time was said)"
    )
    said = parsed.get("said") or parsed["text"]
    again = _REPEAT_WORDS.get(parsed.get("recurring") or "")
    label = f"{'Add a task due' if parsed.get('task') else 'Remind you'} {when_said}{f', then {again}' if again else ''}: {said}"
    arguments = {"text": parsed["text"], "due_at": due.isoformat(), **({"recurring": parsed["recurring"]} if again else {})}
    note = _reminder_note(session, said, note_ids)
    if note is not None:
        arguments["note_id"] = note.id
    steps = [{"name": "set_reminder", "arguments": arguments}]
    card = _card(label, steps, items=[_item(note)] if note is not None else None)
    if _open_reminder_at(session, parsed["text"], due):
        #: The same words at the same time exist: said, with nothing to confirm (audit 1028 E29).
        return {"line": f"You already have a reminder “{_clip(parsed['text'], 60)}” {when_said}."}
    if _has_open_reminder(session, parsed["text"]):
        return _add_another(f"a reminder “{_clip(parsed['text'], 60)}”", card)
    return {"line": f"{label}.", "card": card}


def _add_another(what: str, card: dict) -> dict:
    """The same act twice is asked, not repeated: the card waits for Confirm
    (audit 1029 C48), so a double send never makes two."""
    return {"line": f"You already have {what}. Add another? Confirm below and I'll add it.", "card": card, "duplicate": True}


def _has_note_saying(session: Session, content: str) -> bool:
    from tessellate.core.database import Entry

    wanted = " ".join(content.split()).casefold()
    rows = session.scalars(select(Entry.content).where(Entry.deleted_at.is_(None), Entry.is_private.is_(False)).order_by(Entry.id.desc()).limit(200)).all()
    return any(" ".join((c or "").lstrip("# ").split()).casefold() == wanted for c in rows)


def _open_reminder_at(session: Session, text: str, due) -> bool:  # noqa: ANN001
    """Whether a waiting reminder says `text` at the same minute as `due`."""
    from tessellate.core.database import Reminder

    wanted = " ".join(text.split()).casefold()
    rows = session.execute(select(Reminder.text, Reminder.due_at).where(Reminder.done.is_(False), Reminder.deleted_at.is_(None)).limit(500)).all()
    minute = due.replace(second=0, microsecond=0, tzinfo=None)
    return any(" ".join((t or "").split()).casefold() == wanted and d is not None and d.replace(second=0, microsecond=0, tzinfo=None) == minute for t, d in rows)


def _has_open_reminder(session: Session, text: str) -> bool:
    from tessellate.core.database import Reminder

    wanted = " ".join(text.split()).casefold()
    rows = session.scalars(select(Reminder.text).where(Reminder.done.is_(False), Reminder.deleted_at.is_(None)).limit(500)).all()
    return any(" ".join((t or "").split()).casefold() == wanted for t in rows)


def _no_notes_to_tag_or_move(parsed: dict, which: str, intent: str) -> str:
    """What to say when no note was found to tag or move."""
    if parsed.get("these"):
        return (
            "Attach the notes first with the paperclip, or say which, like: "
            + ("tag my notes about the trip with travel." if intent == "tag" else "move my notes about the plumber to Home.")
        )
    return f"I found no note {which}, so there is nothing to {'tag' if intent == 'tag' else 'move'}."


def _plan_tag_or_move(session: Session, parsed: dict, note_ids: list[int] | None, intent: str) -> dict:
    """The card that tags notes or moves them to a category."""
    entries, which = _which(parsed, session, note_ids)
    if not entries:
        return {"line": _no_notes_to_tag_or_move(parsed, which, intent)}
    ok, skipped = _split_allowed(entries)
    items = [_item(e) for e in ok]
    count = f"{len(ok)} note{'' if len(ok) == 1 else 's'}"
    if len(ok) == 1:  # the note is named by its title, never "1 note about “Car”" (B24)
        count, which = "the note", f"“{note_title(ok[0].content, size=48)}”"
    if intent == "tag":
        tags = " ".join(f"#{t}" for t in parsed["tags"])
        steps = [{"name": "tag_note", "arguments": {"note_ids": [e.id for e in ok], "add": parsed["tags"]}}] if ok else []
        label = f"Tag {count} {which} {tags}"
    else:
        existing = _existing_category(session, parsed["category"])
        category = existing or parsed["category"]
        steps = [{"name": "edit_note", "arguments": {"note_id": e.id, "category": category}} for e in ok]
        label = f"Move {count} {which} to {category}" + ("" if existing else " (a new category)")
    if not ok:
        return {"line": summarise_done([], skipped)}
    return {
        "line": _confirm(label) + (f" {not_done(skipped)}" if skipped else ""),
        "card": _card(label, steps, skipped, items),
    }


def _plan_new_note(session: Session, parsed: dict) -> dict:
    if parsed.get("no_subject"):
        return {"line": "What should the note say? Send it as “make a note: …” and I'll save it."}
    into = task_acts.plan_into_list(session, parsed, _card) if parsed.get("checklist") else None
    if into is not None:
        return into
    steps = [{"name": "create_note", "arguments": {"content": parsed["content"]}}]
    #: A named note ("called X with Y") has a title line and a body: said as
    #: `“X”: Y`, never with the line break in the sentence.
    title, _, body = parsed["content"].partition("\n")
    title = title.lstrip("# ")
    body = "" if re.fullmatch(r"(?:[-*+]\s+\[ \]\s*)+", body.strip()) else body  # an empty checklist line is not words to say (L194)
    label = f"Make a new note “{_clip(title, 50)}”: {_clip(body.strip(), 50)}" if body.strip() else f"Make a new note: “{_clip(title, 80)}”"
    card = _card(label, steps)
    if _has_note_saying(session, parsed["content"]):
        return _add_another(f"a note “{_clip(title, 60)}”", card)
    return {"line": f"{label}.", "card": card}


def _plan_meeting(parsed: dict) -> dict:
    title = parsed.get("title") or ""
    steps = [{"name": "start_meeting", "arguments": {"title": title}}]
    named = f" “{title}”" if title else ""
    return {
        "line": f"Start a meeting{named}.",
        "card": _card(f"Start a meeting{named}", steps),
    }


def _plan_untag(session: Session, parsed: dict, note_ids: list[int] | None) -> dict:
    entries, which = _which(parsed, session, note_ids)
    ok, skipped = _split_allowed(entries)
    if not ok:
        return {"line": f"I found no note {which} to take the tag off." if not skipped else summarise_done([], skipped)}
    if not parsed["tags"]:
        return {"line": f"Which tag should come off the note {which}? Say it again with the tag, like: untag the {parsed.get('about') or 'boiler'} note finance."}
    tags = " ".join(f"#{t}" for t in parsed["tags"])
    label = f"Take {tags} off {len(ok)} note{'' if len(ok) == 1 else 's'} {which}"
    steps = [{"name": "tag_note", "arguments": {"note_ids": [e.id for e in ok], "remove": parsed["tags"]}}]
    return {"line": _confirm(label), "card": _card(label, steps, skipped, [_item(e) for e in ok])}


def _already_there(session: Session, parsed: dict, note_ids: list[int] | None) -> str:
    """"Oat milk is already on your Shopping list." when the line to add is an open item of that note (R9-12), else ""."""
    entry = _resolve_one(session, parsed.get("about"), note_ids, bool(parsed.get("these")), parsed.get("note_id"))[0]
    if entry is None or not act_steps.already_open(entry.content or "", parsed["content"]):
        return ""
    return f"{parsed['content'].rstrip('.')} is already on your {note_title(entry.content, size=48)}."


def plan(session: Session, parsed: dict, note_ids: list[int] | None = None) -> dict:
    """What the command would do: {"line", "card"?, "tool"?}. Writes nothing."""
    if parsed["intent"] == "rename" and parsed.get("alts"):
        #: A split whose old name is a note's whole title wins ("rename Trip to Spain to Trip to Portugal"), else the longest that matches by words.
        exact = lambda about: any(note_title(n.content, size=200).lower() == about.lower() for n in _notes_about(session, about, False))  # noqa: E731
        picked = object_acts.pick_note_split(parsed, exact)
        parsed = picked if picked is not parsed else object_acts.pick_note_split(parsed, lambda about: bool(_notes_about(session, about, False)))
    said = _already_there(session, parsed, note_ids) if parsed["intent"] == "append" else ""
    if said:
        return {"line": said}
    planned = _plan_intent(session, parsed, note_ids)
    card = planned.get("card")
    if card and planned.get("line") in (card["label"], f"{card['label']}."):
        #: The owner's order (2026-11-10): no act runs at once. A plan that says only
        #: its label is a card that waits for Confirm or a typed yes, said as one.
        planned["line"] = _confirm(card["label"])
    if parsed.get("leftover") and planned.get("card"):
        #: A second request on the end of a rename is said back, not done or dropped.
        planned = {**planned, "line": f"{planned['line']} Then say “{parsed['leftover']}” and I will plan that next."}
    return planned


def _plan_intent(session: Session, parsed: dict, note_ids: list[int] | None) -> dict:
    intent = parsed["intent"]
    if parsed.get("task") and parsed.get("asked"):
        into_note = _task_into_note(session, parsed, note_ids)
        if into_note is not None:
            return into_note
    if intent == "reminder":
        return _plan_reminder(session, parsed, note_ids)
    if intent in ("complete", "uncomplete", "cancel", "snooze"):
        return _plan_task(session, parsed)
    if intent == "new_note":
        return _plan_new_note(session, parsed)
    if intent == "meeting":
        return _plan_meeting(parsed)
    if intent in ("tag", "move"):
        return _plan_tag_or_move(session, parsed, note_ids, intent)
    if intent in _OBJECT_INTENTS:
        return _plan_object(session, parsed, note_ids)
    if _deletes_all(parsed):
        return _plan_delete_all(session, parsed["about"])
    if intent in ("delete", "pin", "unpin", "rename", "append", "link", "unlink"):
        return _plan_one(session, parsed, note_ids)
    if intent == "untag":
        return _plan_untag(session, parsed, note_ids)
    if intent == "navigate":
        return _plan_navigate(parsed)
    if intent in READ_INTENTS:
        return _plan_read(session, parsed)
    raise ValueError(intent)


_OBJECT_INTENTS = frozenset({"rename_tag", "rename_category", "create_category", "restore", "set_name"}) | parity_acts.INTENTS | surface_acts.INTENTS


def _plan_object(session: Session, parsed: dict, note_ids: list[int] | None) -> dict:
    """The acts on a kind of thing (a tag, a category, a note's text): `object_acts` and `parity_acts`."""
    if parsed["intent"] in surface_acts.INTENTS:
        return surface_acts.plan(session, parsed, note_ids, _parity_helpers())
    if parsed["intent"] in parity_acts.INTENTS:
        return parity_acts.plan(session, parsed, note_ids, _parity_helpers(), _now_for_plan())
    return object_acts.plan(session, parsed, object_acts.Helpers(_card, _confirm, _item, note_title, summarise_done))


def _now_for_plan() -> datetime:
    from tessellate.core import deps
    from tessellate.core.config import user_now

    return user_now(deps.get_config()).replace(tzinfo=None)


def _parity_helpers() -> dict:
    """What `parity_acts` borrows: the card, the Confirm line, the note helpers and the time words."""
    return {"card": _card, "confirm": _confirm, "item": _item, "note_title": note_title, "summarise_done": summarise_done, "clip": _clip,
            "resolve_one": _resolve_one, "split_allowed": _split_allowed, "when_words": lambda due, now: reminder_when(due, now, False)}


def _voice() -> str:
    """The composer's voice, the `composer_voice` preference (decision 72)."""
    try:
        from tessellate.core import deps

        value = deps.get_config().get_preference("composer_voice", "natural")
    except Exception:  # noqa: BLE001  # no preference is the default voice
        return "natural"
    return "professional" if value in ("professional", "plain") else "natural"


def _confirm(label: str) -> str:
    """"Move the note “Gym plan” to the bin. Confirm to do it.", one of eight."""
    from tessellate.ai import composer_replies

    return _said(composer_replies.act_line(composer_replies.CONFIRM, _voice(), tuple(_LAST), label=label))


def _ahead(due: datetime, now: datetime) -> bool:
    """A time said that has not gone by: one that has ("tonight at 8", said at
    ten) is asked again rather than set in the past, which the store refuses."""
    try:
        return due > now
    except TypeError:  # a naive time against an aware clock: not judged here
        return True


#: "set a reminder" with nothing after it (INBOX 1507).
_ASK_WHAT_AND_WHEN = "What should I remind you about, and when? Say it as “remind me to call Sam on Friday at 9”."


def ask_when_for(parsed: dict) -> str:
    """The one question a reminder with no time asks: when, or which day
    for a day that does not exist (audit 1028 E26)."""
    if parsed.get("impossible"):
        return f"There is no {parsed['impossible']}. Which day should I remind you on?"
    if not (parsed.get("said") or parsed.get("text")):
        return _ASK_WHAT_AND_WHEN
    return ask_when(parsed.get("said") or parsed["text"], thing=bool(parsed.get("thing")))


#: A task said as a thing, not a doing ("don't let me forget the bins"):
#: reminded about, never "remind you to the bins" (INBOX 1459).
_THING = re.compile(r"^(?:the|my|a|an|your|our|his|her|their|this|that|these|those)\b", re.I)


def ask_when(said: str, thing: bool = False) -> str:
    """"When should I remind you to call the dentist?", one of four."""
    from tessellate.ai import composer_replies, realise

    #: Said back to the person: "do my tax return" is "do your tax return".
    said = realise.shift_person(said.rstrip("."))
    line = composer_replies.act_line(composer_replies.ASK_WHEN, _voice(), tuple(_LAST), said=said)
    if thing or _THING.match(said):
        line = line.replace(f" to {said}", f" about {said}")
    return _said(line)


def _which_note(about: str) -> str:
    from tessellate.ai import composer_replies

    return _said(composer_replies.act_line(composer_replies.WHICH_NOTE, _voice(), tuple(_LAST), about=about))


#: The last act lines said in this process, so the next opens unlike them
#: (`phrasing.choose`); an act's line is not in the chat history it reads.
_LAST: deque[str] = deque(maxlen=3)


def _said(line: str) -> str:
    _LAST.append(line)
    return line


def _the_titled(found: list, about: str) -> object | None:
    """The one note whose title is what was named: exactly, else the only one it starts. A title that is
    exactly the name wins over longer titles that start the same way: "pin the Gym note" with "Gym plan"
    beside it (audit D2)."""
    said = about.strip().lower()
    titles = [(e, note_title(e.content, size=48).strip().lower()) for e in found]
    for same in (lambda t: t == said, lambda t: t.startswith(said)):
        hit = [e for e, t in titles if same(t)]
        if len(hit) == 1:
            return hit[0]
    return None


def _title_holds(entry, about: str) -> bool:  # noqa: ANN001
    """Whether the note's title carries every word of `about` (singular or plural)."""
    title = {w.rstrip("s") for w in re.findall(r"[\w'’-]+", note_title(entry.content, size=120).lower())}
    wanted = [w.rstrip("s") for w in re.findall(r"[\w'’-]+", about.lower())]
    return bool(wanted) and all(w in title for w in wanted)


def _resolve_one(session: Session, about: str | None, note_ids: list[int] | None, these: bool, number: int | None = None) -> tuple[object | None, str]:
    """The one note a single-note act names, or None and the question to ask
    (decision 24's shape: one question, the candidates named). `number`: the
    note was named by its number ("pin note 12"), looked up, not searched."""
    if number is not None:
        found_one = _attached(session, [number])
        return (found_one[0], "") if found_one else (None, f"I found no note numbered {number}.")
    if these:
        attached = _attached(session, note_ids)
        if len(attached) == 1:
            return attached[0], ""
        return None, "Which note do you mean? Attach it with the paperclip, or name it, like: delete the boiler note."
    found = _notes_about(session, about or "", single=False)
    if not found:
        return None, _which_note(about or "")
    if len(found) > 1:
        titled = _the_titled(found, about or "")
        if titled:
            return titled, ""
        names = " or ".join(f"“{note_title(e.content, size=48)}”" for e in found[:3])
        return None, f"Which note about “{about}”: {names}?"
    return found[0], ""


def retitled(content: str, title: str) -> str:
    """`content` with its title line (the first line, heading or not) replaced
    by `# title`: the old title is not left behind as body text and the heading
    is never doubled (audit 1029 C41)."""
    lines = content.split("\n")
    at = next((i for i, line in enumerate(lines) if line.strip()), None)
    if at is None:
        return f"# {title}\n"
    lines[at] = f"# {title}"
    return "\n".join(lines)


def _deletes_all(parsed: dict) -> bool:
    """"delete all notes about Z" or "delete my Z notes": plural, by subject."""
    return parsed["intent"] == "delete" and bool(parsed.get("about")) and parsed.get("single") is False


def _plan_delete_all(session: Session, about: str) -> dict:
    """"delete all notes about Z": every match goes on the card, counted, so
    "all" is never quietly the one best match (audit 1028 E66)."""
    found = _notes_about(session, about, single=False)
    if not found:
        return {"line": _which_note(about)}
    ok, skipped = _split_allowed(found)
    if not ok:
        return {"line": summarise_done([], skipped)}
    steps = [{"name": "delete_note", "arguments": {"note_id": e.id}} for e in ok]
    if len(ok) == 1:
        label = f"Move the only note about “{about}”, “{note_title(ok[0].content, size=48)}”, to the bin"
    else:
        label = f"Move the {len(ok)} notes about “{about}” to the bin"
    return {"line": _confirm(label), "card": _card(label, steps, skipped, [_item(e) for e in ok])}


def _one_steps(session: Session, intent: str, parsed: dict, entry, name: str) -> dict:  # noqa: ANN001
    """`{"steps", "label"}` for one named note's act, or `{"line"}` when the other note is not found."""
    if intent == "delete":
        steps = [{"name": "delete_note", "arguments": {"note_id": entry.id}}]
        label = f"Move the note {name} to the bin"
    elif intent in ("pin", "unpin"):
        steps = [{"name": "pin_note", "arguments": {"note_id": entry.id, "pinned": intent == "pin"}}]
        #: The noun the app shows: its menu says "Add to Favourites" (audit 1031 C41).
        label = f"Add the note {name} to Favourites" if intent == "pin" else f"Take the note {name} out of Favourites"
    elif intent == "rename":
        new_content = retitled(entry.content or "", parsed["title"])
        steps = [act_steps.locked_edit(entry.id, entry.content, new_content)]
        label = f"Rename the note {name} to “{parsed['title']}”"
    elif intent == "append":
        new_content = act_steps.appended(entry.content or "", parsed["content"])
        steps = [act_steps.locked_edit(entry.id, entry.content, new_content)]
        label = f"Add “{_clip(parsed['content'], 80)}” to the end of {name}"
    else:
        other, question = _resolve_one(session, parsed.get("other"), None, False, parsed.get("other_id"))
        if other is None:
            return {"line": question}
        if other.id == entry.id:
            return {"line": "That names the same note twice. Which two notes do you mean?"}
        tool = "link_notes" if intent == "link" else "unlink_notes"
        steps = [{"name": tool, "arguments": {"note_id": entry.id, "other_note_id": other.id}}]
        label = f"{'Link' if intent == 'link' else 'Unlink'} {name} {'and' if intent == 'link' else 'from'} “{note_title(other.content, size=48)}”"
    return {"steps": steps, "label": label}


def _plan_one(session: Session, parsed: dict, note_ids: list[int] | None) -> dict:
    """Delete, pin, rename, add to, link: one note, named or attached."""
    intent = parsed["intent"]
    entry, question = _resolve_one(session, parsed.get("about"), note_ids, bool(parsed.get("these")), parsed.get("note_id"))
    if entry is None and intent == "append":
        entry, question = _the_list_note(session, parsed, note_ids, question)
        if entry is None:
            return _new_list_offer(session, parsed) or {"line": question}
    if entry is None:
        return {"line": question}
    ok, skipped = _split_allowed([entry])
    if not ok:
        return {"line": summarise_done([], skipped)}
    name = f"“{note_title(entry.content, size=48)}”"
    if intent == "delete" and parsed.get("bare") and not _title_holds(entry, parsed.get("about") or ""):
        #: "remove milk" after a shopping list names a thing on the list, not the note that holds the word (F3).
        return {"line": f"“{parsed.get('about')}” is not the name of a note, but {name} holds it. To bin that note, say: delete the {note_title(entry.content, size=48)} note."}
    built = _one_steps(session, intent, parsed, entry, name)
    if "line" in built:
        return built
    steps, label = built["steps"], built["label"]
    card = _card(label, steps, skipped, [_item(entry)])
    if intent in CONFIRM_INTENTS:
        return {"line": _confirm(label), "card": card}
    return {"line": label, "card": card}


#: A place a thing is added to that reads as a list the person keeps ("the packing list", "my groceries").
_LIST_NAME = re.compile(r"^(?:my |the |our )?(?P<name>[a-z][a-z' -]{1,40}? list|groceries|shopping)$", re.I)


def _the_list_note(session: Session, parsed: dict, note_ids: list[int] | None, question: str) -> tuple:
    """"the shopping list" is the note called Shopping: the add finds it by its name without "list"."""
    listed = _LIST_NAME.match((parsed.get("about") or "").strip())
    bare = re.sub(r"\s+list$", "", listed.group("name"), flags=re.I) if listed else ""
    if not bare or bare.lower() == listed.group("name").lower() or not _notes_about(session, bare, False):
        return None, question
    return _resolve_one(session, bare, note_ids, False, parsed.get("note_id"))


def _new_list_offer(session: Session, parsed: dict) -> dict | None:
    """One rule for every list add (the owner's Q6): it asks first. "add milk to the shopping list" with no such
    note offers to make that note with the item on it, as a missing todo note does (`task_acts.plan_task_line`);
    None when the place is no list or some note answers to it (the question of which one stands)."""
    listed = _LIST_NAME.match((parsed.get("about") or "").strip())
    if not listed or _notes_about(session, parsed["about"], False):
        return None
    title = _cap(listed.group("name").strip())
    item = _cap(str(parsed.get("content") or "").strip())
    if not item:
        return None
    label = f"Make a note “{title}” with “{item}” on it"
    return {"line": f"You have no {title.lower()} note yet. {_confirm(label)}", "card": _card(label, [{"name": "create_note", "arguments": {"content": f"# {title}\n\n- [ ] {item}"}}])}


def _item(entry) -> str:  # noqa: ANN001
    """A note as a card item or a line says it: its title, never its id (audit 1028 E64)."""
    return note_title(entry.content, size=48) or "Untitled note"


def _read_numbered(session: Session, parsed: dict) -> tuple | str:
    """("get_note", its arguments, its result, the line) for a note named by its number, or the line that says it is not there."""
    from tessellate.ai import tools

    result = tools.execute_tool(session, "get_note", {"note_id": parsed["note_id"]})
    if "error" in result:
        return "I could not open that note: it does not exist, or it is private."
    title = note_title(str(result.get("content") or ""), size=60) or "that note"
    line = f"Here is “{title}”. Open it from the row below."
    if parsed["intent"] == "summarise":  # a numbered note is summarised from its own text, never searched for by its number (L-chat-29)
        body = " ".join(str(result.get("content") or "").split("\n", 1)[-1].split())
        line = f"“{title}” says: {_clip(body, 240)}" if body else f"“{title}” is empty."
    return "get_note", {"note_id": parsed["note_id"]}, result, line


def _plan_similar(session: Session, parsed: dict) -> dict:
    """"find notes similar to the boiler note": the agent's own `find_similar_notes` over the one note named (L-chat-29)."""
    from tessellate.ai import agent_policy, cards, tools

    entry, question = _resolve_one(session, parsed.get("about"), None, False, parsed.get("note_id"))
    if entry is None:
        return {"line": question}
    result = tools.execute_tool(session, "find_similar_notes", {"note_id": entry.id})
    title = note_title(entry.content, size=60)
    if "error" in result or not result.get("similar"):
        return {"line": f"I found no note similar to “{title}”."}
    found = result["similar"]
    names = ", ".join(f"“{note_title(str(n.get('content') or n.get('title') or ''), size=40)}”" for n in found[:5])
    event = {"type": "tool", "name": "find_similar_notes", "arguments": {"note_id": entry.id}, "label": result.get("label") or "find_similar_notes", "ok": True,
             "touched": agent_policy._touched_items(result), "cards": cards.result_cards("find_similar_notes", result)}
    return {"line": f"Notes close in meaning to “{title}”: {names}.", "tool": event}


def _clip(text: str, cap: int) -> str:
    return text if len(text) <= cap else text[: cap - 1].rstrip() + "…"


def _filed_notes(session: Session, filed: str) -> tuple | None:
    """("list_notes", its arguments, its result, the line) for the notes in
    the category `filed`, else tagged `filed`; None when neither holds any."""
    from tessellate.ai import tool_say, tools

    for key in ("category", "tag"):
        args = {key: filed, "limit": 8}
        result = tools.execute_tool(session, "list_notes", args)
        if isinstance(result, dict) and result.get("total_matching"):
            said = tool_say.say("list_notes", result, args)
            return "list_notes", {key: filed}, result, f"{said['lead']}\n\n{said['body']}"
    return None


def _plan_read(session: Session, parsed: dict) -> dict:
    """Find or open: run the agent's own search and hand back its tool event."""
    from tessellate.ai import cards, tool_say, tools
    from tessellate.ai import agent_policy

    if parsed["intent"] == "similar":
        return _plan_similar(session, parsed)
    if parsed.get("note_id") is not None:
        numbered = _read_numbered(session, parsed)
        if isinstance(numbered, str):
            return {"line": numbered}
        name, args, result, line = numbered
    elif parsed.get("filed") and (listed := _filed_notes(session, parsed["filed"])):
        name, args, result, line = listed
    else:
        about = parsed["about"]
        result = tools.execute_tool(session, "search_notes", {"query": about, "limit": 8})
        if "error" in result or not result.get("notes"):
            return {"line": f"I found no note about “{about}”."}
        if parsed["intent"] == "open":
            result = {**result, "notes": result["notes"][:1]}
        name, args = "search_notes", {"query": about}
        said = tool_say.say("search_notes", result, {"query": about})
        #: An exact title is the note itself, not the closest one (F13 c, 1110): "open it" after Kyoto ideas.
        exact = bool(result["notes"]) and note_title(str(result["notes"][0].get("content") or ""), size=60).lower() == about.strip().lower()
        line = (
            f"{'Here it is:' if exact else f'The closest note about “{about}” is'} {said['body'].lstrip('- ').strip()}"
            if parsed["intent"] == "open"
            else f"{said['lead']}\n\n{said['body']}"
        )
    event = {
        "type": "tool",
        "name": name,
        "arguments": args,
        "label": result.get("label") or name,
        "ok": True,
        "touched": agent_policy._touched_items(result),
        "cards": cards.result_cards(name, result),
    }
    return {"line": line, "tool": event}


# --- run -----------------------------------------------------------------------


def _start_meeting(session: Session, args: dict) -> dict:
    from tessellate.api.routes_meetings import MeetingCreate, create_meeting
    from tessellate.core import deps
    from tessellate.core.config import user_now

    now = user_now(deps.get_config())
    out = create_meeting(MeetingCreate(title=str(args.get("title") or "")[:200], when=now.strftime("%Y-%m-%dT%H:%M")), session)
    return {
        "id": out.id,
        "title": str(args.get("title") or ""),
        "open": {"kind": "meeting", "id": out.id},
        "undo": {"tool": "delete_note", "arguments": {"note_id": out.id}},
    }


def _bin_reminder(session: Session, args: dict) -> dict:
    from tessellate.api.routes_reminders import delete_reminder
    from tessellate.core.database import Reminder

    held = session.get(Reminder, int(args["reminder_id"]))
    named = f"“{_clip(held.text, 60)}”" if held is not None and held.text else "that reminder"
    delete_reminder(int(args["reminder_id"]), session)
    return {
        "binned": int(args["reminder_id"]),
        "label": f"Cancelled reminder {named}",
        "undo": {"tool": "restore_reminder", "arguments": {"reminder_id": int(args["reminder_id"])}},
    }


def _step_undo(name: str, args: dict, result: dict):  # noqa: ANN202
    """The step that reverses one that ran: the tool's own, or the one this
    module knows for a reminder, a completed task and a link."""
    step_undo = result.get("undo")
    if name == "set_reminder" and result.get("id") is not None and not result.get("existing"):
        step_undo = {"tool": "bin_reminder", "arguments": {"reminder_id": result["id"]}}
    if name == "complete_reminder":
        step_undo = task_acts.undo_step(name, args)
    if name == "save_user_preference" and (result.get("proposal") or {}).get("id") is not None:
        step_undo = {"tool": "drop_preference", "arguments": {"id": result["proposal"]["id"]}}
    if name == "link_notes" and not step_undo:
        step_undo = {"tool": "unlink_notes", "arguments": {"note_id": args.get("note_id"), "other_note_id": args.get("other_note_id")}}
    return step_undo


def _failure_reason(error: str) -> str:
    """The skip reason a tool's refusal stands for."""
    if "is private" in error:
        return "private"
    return "stale" if "changed since" in error else "failed"


def _run_one(session: Session, name: str, args: dict, tools) -> dict:  # noqa: ANN001
    """One step's result: the composer's own steps first, then the tool table."""
    if name == "start_meeting":
        return _start_meeting(session, args)
    if name == "bin_reminder":
        return _bin_reminder(session, args)
    if name in task_acts.OWN_STEPS:
        return task_acts.run_step(session, name, args)
    if name in ("set_theme", "restore_document", "drop_preference"):
        return surface_acts.run_step(session, name, args)
    if name == "set_display_name":
        from tessellate.core import deps

        return address.run_step(deps.get_config(), args)
    if name in ("rename_tag", "rename_category", "restore_note", "delete_tag") and (refusal := object_acts.guard(session, name, args)):
        return {"error": refusal}
    return tools.execute_tool(session, name, args)


def run(session: Session, steps: list[dict], skipped: list[dict] | None = None, say=None) -> dict:  # noqa: ANN001
    """Run a confirmed card's steps: {"summary", "undo", "open"?, "ok"}.

    Every step is tried even when one fails, and each failure is a "Not done"
    in the line rather than a stop: a person who confirmed tagging five notes
    gets the four that could be tagged and is told about the fifth.
    """
    from tessellate.ai import tools

    done: list[tuple[str, dict, dict]] = []
    failed: list[dict] = list(skipped or [])
    undo: list[dict] = []
    opened = None
    for step in steps:
        name = str(step.get("name") or "")
        args = dict(step.get("arguments") or {})
        if name not in RUNNABLE:
            failed.append({"id": None, "reason": "failed"})
            continue
        name, args = act_steps.settle_step(session, name, args)
        result = _run_one(session, name, args, tools)
        if "error" in result:
            reason = _failure_reason(str(result["error"]))
            failed.append({"id": args.get("note_id"), "reason": reason})
            continue
        done.append((name, args, result))
        step_undo = act_steps.lock_undo(session, name, args, _step_undo(name, args, result))
        if isinstance(step_undo, dict):
            undo.extend(step_undo["steps"] if step_undo.get("tool") == "batch" else [step_undo])
        opened = result.get("open") or opened
    summary = summarise_done([str(r.get("label") or n.replace("_", " ")) for n, _a, r in done], failed, say)
    out = {
        "ok": bool(done),
        "summary": summary,
        "label": summary,
        "undo": [{"name": u["tool"], "arguments": u.get("arguments") or {}} for u in undo if u.get("tool")],
    }
    if opened:
        out["open"] = opened
    return out


act_registry.READER = read  # for the composer (act_registry.READER)
