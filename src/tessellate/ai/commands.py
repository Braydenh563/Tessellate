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
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import reminder_parser, task_acts, when
from tessellate.ai import act_registry
from tessellate.ai.act_registry import CONFIRM_INTENTS
from tessellate.ai.filed_name import filed_listing

#: The verbs of the grammar (decision 38), as said in `Command.verb`.
VERBS = ("remind", "complete", "cancel", "snooze", "tag", "untag", "file", "rename", "pin", "unpin", "link", "unlink", "delete", "create", "add", "summarise", "find", "open")
#: The intents `read` gives, each with its verb.
_VERB_OF = {
    "reminder": "remind", "tag": "tag", "untag": "untag", "move": "file", "rename": "rename", "pin": "pin",
    "unpin": "unpin", "link": "link", "unlink": "unlink", "delete": "delete", "new_note": "create",
    "meeting": "create", "append": "add", "complete": "complete", "cancel": "cancel", "snooze": "snooze", "summarise": "summarise", "find": "find", "open": "open", "navigate": "open",
}
#: The intents that write: each is shown as a card.
WRITE_INTENTS = frozenset({"reminder", "tag", "untag", "move", "rename", "pin", "unpin", "link", "unlink", "delete", "new_note", "meeting", "append", "complete", "cancel", "snooze"})
#: Read only: answered at once, nothing to confirm.
READ_INTENTS = frozenset({"find", "open", "navigate", "summarise"})
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
    {"set_reminder", "tag_note", "edit_note", "create_note", "delete_note", "restore_note",
     "pin_note", "link_notes", "unlink_notes", "start_meeting", "bin_reminder", "complete_reminder", "restore_reminder", "snooze_reminder"}
)

_MAX_TEXT = 300
_MAX_NOTES = 50

# --- parse ---------------------------------------------------------------------
#
# Every pattern runs on text already folded to single spaces and capped at
# `_MAX_TEXT`, and splits are done with `str` methods where a lazy `.+?` would
# otherwise sit before a separator (CodeQL, polynomial regular expression).

_POLITE = ("please ", "can you ", "could you ", "would you ", "will you ", "i want to ",
           "i'd like to ", "i would like to ", "let's ", "lets ", "ok ", "okay ")
_TRAILING = (" please", " pls", " plz", " for me", " thanks", " thank you", " ty", " thx")
_ASKING = re.compile(r"^(?:what|who|where|when|how|why|which|whether|if|of|out)\b", re.IGNORECASE)


def _fold(text: str) -> tuple[str, bool, bool]:
    """(the command text, said as a question, said politely)."""
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
    return text, question, polite


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


def _target(text: str) -> dict | None:
    """Which notes a phrase names: the attached ones ("these notes") or the
    ones a search finds ("my notes about Z", "my Z notes"), or None."""
    low = text.lower().strip()
    if low in _THESE:
        return {"these": True, "single": _THESE[low]}
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
        return None
    rest = reminder_parser.unhedged(rest)
    parsed = reminder_parser.parse_relative(rest, now) or when.parse_reminder_text(rest, now, locale=locale)
    if parsed is not None:
        parsed = {**parsed, "text": reminder_parser.without_conditions(parsed["text"]) or parsed["text"]}
    if parsed is None:
        if about:
            # "Remind me about my trip" with no time is a question as often
            # as a request; a reminder needs the time said.
            return None
        due, said, words = when.resolve("tomorrow", now), False, rest
    else:
        due, said, words = parsed["due_at"], True, parsed["text"]
    words = _without_lead(words, ("to ", "about ", "that ", "for "), once=False)
    said_words = words.strip(" ,.;:-")
    if rest[:1].islower():
        #: As typed: the time parser raises the first letter for the stored
        #: reminder; the object is said back in the person's own case.
        said_words = said_words[:1].lower() + said_words[1:]
    words = _cap(words)
    if not words or due is None:
        return None
    return {"intent": "reminder", "text": words[:500], "said": said_words[:500], "due_at": due, "time_given": said and _ahead(due, now)}


def _tag(text: str) -> dict | None:
    low = text.lower()
    if low.startswith(("tag ", "label ")):
        body = text.split(" ", 1)[1]
        return _tag_with(body) or _note_then_tags(body) or _tag_these(body)
    for lead in ("add the tags ", "add the tag ", "add tags ", "add tag ", "add the label ", "add label ", "add a tag ", "add a label "):
        if low.startswith(lead):
            split = _split_last(text[len(lead):], (" to ",))
            if split:
                tags, target = split
                found = _target(target) or _bare_target(target)
                if found and _tags(tags):
                    return {"intent": "tag", **found, "tags": _tags(tags)}
    if low.startswith("give "):
        #: "give my gym log the tag fitness"
        split = _split_last(text[len("give "):], (" the tag ", " the tags ", " the label ", " a tag ", " a label "))
        if split:
            target, tags = split
            found = _target(target) or _bare_target(target)
            if found and _tags(tags):
                return {"intent": "tag", **found, "tags": _tags(tags)}
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
    cut = body.lower().rfind(" note ")
    if cut <= 0:
        return None
    found = _one_target(body[: cut + len(" note")].strip())
    tags = _tags(body[cut + len(" note "):])
    return {"intent": "tag", **found, "tags": tags} if found and tags else None


_BIN_WORDS = {"bin", "the bin", "trash", "the trash", "recycle bin", "the recycle bin"}


def _move(text: str) -> dict | None:
    low = text.lower()
    verb = next((v for v in ("move ", "file ", "put ", "send ") if low.startswith(v)), None)
    if verb is None:
        return None
    split = _split_last(text[len(verb):], (" to ", " into ", " in ", " under "))
    if not split:
        return None
    target, category = split
    found = _target(target) or (_bare_target(target) if verb in ("move ", "file ") else None)
    if not found:
        return None
    category = _drop_article(category.strip())
    low_cat = category.lower()
    for tail in (" category", " folder"):
        if low_cat.endswith(tail):
            category = category[: -len(tail)]
    if category.lower().startswith("category "):
        category = category[len("category "):]
    category = category.strip(" '\"")
    if not category or category.lower() in _BIN_WORDS or len(category) > 120:
        return None
    return {"intent": "move", **found, "category": category}


_NOTE_HEADS_NEW = (
    ("note to self", False), ("note that", False), ("new note", True), ("quick note", True), ("make a note", False),
    ("take a note", False), ("save a note", False), ("add a note", False), ("create a note", False),
    ("write a note", False), ("jot down", False), ("write down", False), ("note down", False),
    ("save this", True), ("creat a note", False), ("make note", False), ("note", True),
)


_NAMED = ("called ", "titled ", "named ")


def _new_note(text: str) -> dict | None:
    low = text.lower()
    for head, needs_colon in _NOTE_HEADS_NEW:
        if not (low.startswith(head + " ") or low.startswith(head + ":")):
            continue
        rest = text[len(head):].lstrip()
        if needs_colon and not rest.startswith(":") and not rest.lower().startswith(_NAMED):
            return None
        rest = rest.lstrip(" :-")
        for lead in ("that ", "saying ", "of ", "about ", "to say ", *_NAMED):
            if rest.lower().startswith(lead):
                rest = rest[len(lead):]
                break
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


_WHATS_IN = re.compile(
    r"(?:what(?:'s|s| is) in (?:my |the )?(?P<a>[\w&-]+(?: [\w&-]+)?) (?:category|folder|tag)"
    r"|(?:pull up|bring up) (?:my |the )?(?:notes|entries) (?:tagged(?: with)?|in|under) #?(?P<b>[\w&-]+(?: [\w&-]+)?))[?.!\s]*",
    re.I,
)


def _asks_a_kind(text: str) -> bool:
    from tessellate.ai import composer_lists  # on first use: the composer is not loaded by importing the commands

    return composer_lists.holding_ask(text) is not None


def _find(text: str) -> dict | None:
    whats =_WHATS_IN.fullmatch(text.strip())
    if whats:
        filed = (whats["a"] or whats["b"]).strip()
        return {"intent": "find", "about": filed, "filed": filed}
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
        if intent == "find":
            listed = _listing(text, head, rest)
            if listed is not None:
                return listed or None
        return _found_object(intent, head, rest)
    return None


def _found_object(intent: str, head: str, rest: str) -> dict | None:
    """What an open or a find names: "#12", "note 12", a target, or for a
    free find ("find dentist") its topic."""
    rest = _NOTES_SCOPE.sub("", rest)
    number = re.fullmatch(r"(?:(?:note|entry) )?#?(\d{1,9})", rest, re.IGNORECASE)
    if number and (rest.startswith("#") or not rest.isdigit()):
        return {"intent": intent, "note_id": int(number.group(1))}
    found = _target(rest)
    if found and found.get("about"):
        return {"intent": intent, "about": found["about"]}
    if intent == "find" and head in _FREE_FIND and rest and _note_topic(rest):
        about = _drop_article(_TOPIC_FILLER.sub("", _NOTES_SCOPE.sub("", rest), count=1)) or _drop_article(rest)
        return {"intent": "find", "about": about} if about else None
    return None


_MEETING = re.compile(
    r"^(?:start|begin|new|create|open|record|make|run|hold) (?:(?:a|an|the|new|my|our) )*meeting(?: note)?"
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
    "timeline": "timeline", "the timeline": "timeline", "calendar": "timeline", "reminders": "reminders",
    "my reminders": "reminders", "notes": "notes", "my notes": "notes",
}


def _navigate(text: str) -> dict | None:
    """"open settings", "go to the graph": a place in the app, not a note."""
    low = text.lower()
    for head in ("open ", "go to ", "take me to ", "show me ", "show ", "switch to "):
        if low.startswith(head):
            rest = low[len(head):].strip(" .")
            rest = rest.removesuffix(" tab").removesuffix(" page").strip()
            if rest in _SURFACES:
                return {"intent": "navigate", "surface": _SURFACES[rest]}
    return None


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
    found = _one_target(rest, bare=True)
    return {"intent": "delete", **found} if found else None


def _pin(text: str) -> dict | None:
    low = text.lower()
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


def _untag(text: str) -> dict | None:
    low = text.lower()
    head = next((h for h in ("untag ", "remove the tag ", "remove tag ", "take the tag ", "take tag ") if low.startswith(h)), None)
    if head is None:
        return None
    split = _split_last(text[len(head):], (" from ", " off "))
    if not split:
        return None
    tags, target = split
    found = _target(target)
    if found and _tags(tags):
        return {"intent": "untag", **found, "tags": _tags(tags)}
    return None


def _link(text: str) -> dict | None:
    low = text.lower()
    for verb, intent, seps in (("unlink ", "unlink", (" from ", " and ")), ("link ", "link", (" to ", " with ", " and ")), ("connect ", "link", (" to ", " with ", " and "))):
        if low.startswith(verb):
            split = _split_last(text[len(verb):], seps)
            if not split:
                return None
            a, b = (_one_target(part.strip()) for part in split)
            if a and b and a.get("about") and b.get("about"):
                return {"intent": intent, "about": a["about"], "other": b["about"], "single": True}
            return None
    return None


def _rename(text: str) -> dict | None:
    low = text.lower()
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
        return {"intent": "rename", **found, "title": title}
    return None


def _append(text: str) -> dict | None:
    low = text.lower()
    if not low.startswith(("add ", "append ")) or low.startswith(("add tag", "add the tag", "add a tag", "add label", "add the label", "add a reminder", "add a note")):
        return None
    split = _split_last(text.split(" ", 1)[1], (" to ",))
    if not split:
        return None
    words, target = split
    #: "add milk to my shopping list": a thing that is theirs (my, our) or a
    #: list-like name is a title, though it says no "note".
    listish = target.lower().startswith(("my ", "our ")) or target.lower().split(" ")[-1] in ("list", "checklist", "log", "journal", "diary", "tracker")
    found = _one_target(target.strip(), bare=listish)
    words = words.strip(" '\"“”")
    if found and found.get("single", True) and words:
        return {"intent": "append", **found, "single": True, "content": _cap(words)}
    return None


def _summarise(text: str) -> dict | None:
    low = text.lower()
    for head in ("summarise ", "summarize ", "sum up ", "give me a summary of "):
        if low.startswith(head):
            rest = text[len(head):].strip()
            found = _target(rest)
            if found and found.get("about"):
                return {"intent": "summarise", "about": found["about"]}
            whole = re.match(r"(?:all )?(?:of )?(?:my |the )?notes\b(?: (?:from|for|in) )?(.*)$", rest, re.I)
            if whole:
                #: "summarise my notes from this week": the notes of a while.
                return {"intent": "summarise", "about": whole.group(1).strip() or "notes"}
    return None


#: Arguments of an act that are the person's own words (never respelt).
OWN_WORDS = ("content", "title", "tags", "text", "said")


def _about_as_typed(found: dict, text: str, now: datetime, locale: str | None) -> dict:
    """Only slang spelled out, no misspelling put right: the notes a command
    names keep the person's own word ("delete notes about uni" is their
    category Uni, not "university"; audit 1028 E9)."""
    typed = read(text, now, locale)
    if typed is not None and typed.get("intent") == found.get("intent") and "about" in typed:
        return {**found, "about": typed["about"]}
    return found


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
    if found is not None and "about" in found and fixed != text and not fixes:
        found = _about_as_typed(found, text, now, locale)
    if found is not None and fixed != text:
        found = _words_as_typed(found, text, now, locale)
    if found is not None or not text:
        return found
    #: One word a slip from a word the commands read ("pin the dentist noe",
    #: "unlnk the gym note"), read so when that makes it a command (O3).
    guided = question_noise.guided(question_noise.tidy(text), lambda t: read(t, now, locale) is not None)
    return read(guided, now, locale) if guided else None


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
    command, question, polite = _fold(text)
    if not command:
        return None
    #: "move the lentil soup note to the bin" says delete in other words.
    binned = _TO_THE_BIN.match(" ".join(command.split()))
    if binned:
        command = f"delete {binned.group(1)}"
    if re.match(r"(?i)archive\b", command):
        #: Decision 42: archiving stays a UI action; no act archives.
        return None
    for reader in (_meeting, lambda t: _reminder(t, now, locale), lambda t: task_acts.read_add(t, lambda r: _reminder(r, now, locale)),
                   task_acts.read_complete, task_acts.read_cancel, lambda t: task_acts.read_snooze(t, lambda w: _time_of(w, now, locale)), _new_note, _untag, _tag, _move, _delete, _pin, _link, _rename,
                   _append, _summarise, _navigate, _find):
        found = reader(command)
        if found is None:
            continue
        if question and not polite and found["intent"] in WRITE_INTENTS:
            # "Note: is the boiler code 4471?" asks; it does not tell.
            return None
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


def parse(text: str, now: datetime) -> Command | None:
    """The `Command` `text` is, or None for a sentence that is not one."""
    found = read(text, now)
    if found is None:
        return None
    intent = found["intent"]
    if intent == "reminder":
        #: The reminder's own words as typed after the time came off, first
        #: letter as typed ("call Sam"); the reminder stores them capitalised.
        obj = found.get("said") or found["text"]
    elif intent in ("new_note", "append"):
        obj = found["content"]
    elif intent == "meeting":
        obj = found.get("title") or "meeting"
    elif intent == "navigate":
        obj = found["surface"]
    elif intent == "open" and found.get("note_id") is not None:
        obj = f"note {found['note_id']}"
    else:
        obj = found.get("about") or ("these notes" if found.get("these") else "")
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


def _title(entry) -> str:  # noqa: ANN001
    """The note's name: its heading, or its first line, cut at a word."""
    from tessellate.ai import realise

    first = next((line for line in (entry.content or "").splitlines() if line.strip()), "")
    first = " ".join(first.lstrip("# ").split())
    return realise.cut_title(first, 48)


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
    about = parsed.get("about") or ""
    return _notes_about(session, about, bool(parsed.get("single"))), f"about “{about}”"


#: What the card says under its label: the person decides, nothing has run.
CONFIRM_NOTICE = "Nothing changes until you confirm, and Undo takes it back."
_SKIP_REASONS = {"private": "it is private", "binned": "it is in the bin", "failed": "it could not be changed"}


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
    }


def not_done(skipped: list[dict]) -> str:
    """"Not done: note 12 (it is private)." for the notes a change left."""
    if not skipped:
        return ""
    said = [f"note {s['id']} ({_SKIP_REASONS.get(s.get('reason'), 'it could not be changed')})" if s.get("id") else _SKIP_REASONS.get(s.get("reason"), "a step failed") for s in skipped]
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
    """"9", "9:30", "noon", "midnight", "5pm", "12:39pm", "12:39am": the
    hour as people say it. A morning from 7 is plain ("at 9"); the small
    hours and anything from noon say which half of the day."""
    hour, minute = due.hour, due.minute
    if minute == 0 and hour in (0, 12):
        return "midnight" if hour == 0 else "noon"
    said = str(hour % 12 or 12) + (f":{minute:02d}" if minute else "")
    return said + ("pm" if hour >= 12 else "am" if hour < 7 else "")


def reminder_when(due: datetime, now: datetime) -> str:
    """When, said against today (INBOX 734): "today at 5pm", "tomorrow at
    9", "on Friday at 9", "on 21 October at 9"."""
    days = (due.date() - now.date()).days
    if days == 0:
        day = "today"
    elif days == 1:
        day = "tomorrow"
    elif 1 < days < 7:
        day = f"on {due.strftime('%A')}"
    else:
        day = f"on {due.day} {due.strftime('%B')}" + (f" {due.year}" if due.year != now.year else "")
    return f"{day} at {_clock(due)}"


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
    return found[0] if found and not getattr(found[0], "is_private", False) else None


def _task_into_note(session: Session, parsed: dict, note_ids: list[int] | None) -> dict | None:
    """The plan that appends a task to a note called that ("add milk to my
    to-do list"), or None when no note is."""
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
    if intent == "cancel":
        return task_acts.plan_cancel(session, parsed, _card, _title)
    if intent == "snooze":
        from tessellate.core import deps
        from tessellate.core.config import user_now

        now = user_now(deps.get_config()).replace(tzinfo=None)
        return task_acts.plan_snooze(session, parsed, _card, _title, lambda due: reminder_when(due, now), now)
    return task_acts.plan_complete(session, parsed, _card, _title)


def _plan_reminder(session: Session, parsed: dict, note_ids: list[int] | None) -> dict:
    """The card for a reminder, or a task with a day."""
    #: "Remind you on Friday at 9: call the dentist" (INBOX 734): the
    #: person's own words after the colon, the time said against today,
    #: and the note it comes from, which the reminder is attached to.
    from tessellate.core import deps
    from tessellate.core.config import user_now

    due = parsed["due_at"]
    when_said = reminder_when(due, user_now(deps.get_config()).replace(tzinfo=None)) + (
        "" if parsed.get("time_given") else " (no time was said)"
    )
    said = parsed.get("said") or parsed["text"]
    label = f"{'Add a task due' if parsed.get('task') else 'Remind you'} {when_said}: {said}"
    arguments = {"text": parsed["text"], "due_at": due.isoformat()}
    note = _reminder_note(session, said, note_ids)
    if note is not None:
        arguments["note_id"] = note.id
    steps = [{"name": "set_reminder", "arguments": arguments}]
    card = _card(label, steps, items=[f"#{note.id} {_title(note)}"] if note is not None else None)
    if _has_open_reminder(session, parsed["text"]):
        return _add_another(f"a reminder “{_clip(parsed['text'], 60)}”", card)
    return {"line": f"{label}.", "card": card, "run": True}


def _add_another(what: str, card: dict) -> dict:
    """The same act twice is asked, not repeated: the card waits for Confirm
    (audit 1029 C48), so a double send never makes two."""
    return {"line": f"You already have {what}. Add another? Confirm below and I'll add it.", "card": card}


def _has_note_saying(session: Session, content: str) -> bool:
    from tessellate.core.database import Entry

    wanted = " ".join(content.split()).casefold()
    rows = session.scalars(select(Entry.content).where(Entry.deleted_at.is_(None), Entry.is_private.is_(False)).order_by(Entry.id.desc()).limit(200)).all()
    return any(" ".join((c or "").lstrip("# ").split()).casefold() == wanted for c in rows)


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
    items = [f"#{e.id} {_title(e)}" for e in ok]
    count = f"{len(ok)} note{'' if len(ok) == 1 else 's'}"
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
    steps = [{"name": "create_note", "arguments": {"content": parsed["content"]}}]
    card = _card(f"Make a new note: “{_clip(parsed['content'], 80)}”", steps)
    if _has_note_saying(session, parsed["content"]):
        return _add_another(f"a note “{_clip(parsed['content'], 60)}”", card)
    return {"line": f"Make a new note: “{_clip(parsed['content'], 80)}”.", "card": card, "run": True}


def _plan_meeting(parsed: dict) -> dict:
    title = parsed.get("title") or ""
    steps = [{"name": "start_meeting", "arguments": {"title": title}}]
    named = f" “{title}”" if title else ""
    return {
        "line": f"Start a meeting{named}.",
        "card": _card(f"Start a meeting{named}", steps),
        "run": True,
    }


def _plan_untag(session: Session, parsed: dict, note_ids: list[int] | None) -> dict:
    entries, which = _which(parsed, session, note_ids)
    ok, skipped = _split_allowed(entries)
    if not ok:
        return {"line": f"I found no note {which} to take the tag off." if not skipped else summarise_done([], skipped)}
    tags = " ".join(f"#{t}" for t in parsed["tags"])
    label = f"Take {tags} off {len(ok)} note{'' if len(ok) == 1 else 's'} {which}"
    steps = [{"name": "tag_note", "arguments": {"note_ids": [e.id for e in ok], "remove": parsed["tags"]}}]
    return {"line": _confirm(label), "card": _card(label, steps, skipped, [f"#{e.id} {_title(e)}" for e in ok])}


def plan(session: Session, parsed: dict, note_ids: list[int] | None = None) -> dict:
    """What the command would do: {"line", "card"?, "tool"?}. Writes nothing."""
    intent = parsed["intent"]
    if parsed.get("task") and parsed.get("asked"):
        into_note = _task_into_note(session, parsed, note_ids)
        if into_note is not None:
            return into_note
    if intent == "reminder":
        return _plan_reminder(session, parsed, note_ids)
    if intent in ("complete", "cancel", "snooze"):
        return _plan_task(session, parsed)
    if intent == "new_note":
        return _plan_new_note(session, parsed)
    if intent == "meeting":
        return _plan_meeting(parsed)
    if intent in ("tag", "move"):
        return _plan_tag_or_move(session, parsed, note_ids, intent)
    if intent in ("delete", "pin", "unpin", "rename", "append", "link", "unlink"):
        return _plan_one(session, parsed, note_ids)
    if intent == "untag":
        return _plan_untag(session, parsed, note_ids)
    if intent == "navigate":
        return {"line": f"Opening {parsed['surface']}.", "navigate": parsed["surface"]}
    if intent in READ_INTENTS:
        return _plan_read(session, parsed)
    raise ValueError(intent)


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


def ask_when(said: str) -> str:
    """"When should I remind you to call the dentist?", one of four."""
    from tessellate.ai import composer_replies

    return _said(composer_replies.act_line(composer_replies.ASK_WHEN, _voice(), tuple(_LAST), said=said.rstrip(".")))


def _which_note(about: str) -> str:
    from tessellate.ai import composer_replies

    return _said(composer_replies.act_line(composer_replies.WHICH_NOTE, _voice(), tuple(_LAST), about=about))


#: The last act lines said in this process, so the next opens unlike them
#: (`phrasing.choose`); an act's line is not in the chat history it reads.
_LAST: deque[str] = deque(maxlen=3)


def _said(line: str) -> str:
    _LAST.append(line)
    return line


def _resolve_one(session: Session, about: str | None, note_ids: list[int] | None, these: bool) -> tuple[object | None, str]:
    """The one note a single-note act names, or None and the question to ask
    (decision 24's shape: one question, the candidates named)."""
    if these:
        attached = _attached(session, note_ids)
        if len(attached) == 1:
            return attached[0], ""
        return None, "Which note do you mean? Attach it with the paperclip, or name it, like: delete the boiler note."
    found = _notes_about(session, about or "", single=False)
    if not found:
        return None, _which_note(about or "")
    if len(found) > 1:
        titled = [e for e in found if _title(e).lower().startswith((about or "").lower())]
        if len(titled) == 1:
            return titled[0], ""
        names = " or ".join(f"“{_title(e)}”" for e in found[:3])
        return None, f"Which note about “{about}”: {names}?"
    return found[0], ""


_CHECK_LINE = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s")
_BULLET_LINE = re.compile(r"^\s*[-*+]\s+(?!\[)")
_ITEM_LEAD = re.compile(r"^\s*(?:[-*+]\s+)?(?:\[[ xX]\]\s+)?")


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


def appended(content: str, text: str) -> str:
    """`content` with `text` added at the end in the note's own shape: an item
    after a checklist is `- [ ] item`, after bullets `- item`, else a new
    paragraph (audit 1029 C42). One helper, so every add keeps the structure."""
    body = content.rstrip()
    last = next((line for line in reversed(body.split("\n")) if line.strip()), "")
    item = _ITEM_LEAD.sub("", text.strip(), count=1) or text.strip()
    if _CHECK_LINE.match(last):
        return f"{body}\n- [ ] {item}"
    if _BULLET_LINE.match(last):
        return f"{body}\n- {item}"
    return f"{body}\n\n{text}"


def _plan_one(session: Session, parsed: dict, note_ids: list[int] | None) -> dict:
    """Delete, pin, rename, add to, link: one note, named or attached."""
    intent = parsed["intent"]
    entry, question = _resolve_one(session, parsed.get("about"), note_ids, bool(parsed.get("these")))
    if entry is None:
        return {"line": question}
    ok, skipped = _split_allowed([entry])
    if not ok:
        return {"line": summarise_done([], skipped)}
    name = f"“{_title(entry)}”"
    if intent == "delete":
        steps = [{"name": "delete_note", "arguments": {"note_id": entry.id}}]
        label = f"Move the note {name} to the bin"
    elif intent in ("pin", "unpin"):
        steps = [{"name": "pin_note", "arguments": {"note_id": entry.id, "pinned": intent == "pin"}}]
        label = f"{'Pin' if intent == 'pin' else 'Unpin'} the note {name}"
    elif intent == "rename":
        new_content = retitled(entry.content or "", parsed["title"])
        steps = [{"name": "edit_note", "arguments": {"note_id": entry.id, "content": new_content}}]
        label = f"Rename the note {name} to “{parsed['title']}”"
    elif intent == "append":
        new_content = appended(entry.content or "", parsed["content"])
        steps = [{"name": "edit_note", "arguments": {"note_id": entry.id, "content": new_content}}]
        label = f"Add “{_clip(parsed['content'], 80)}” to the end of {name}"
    else:
        other, question = _resolve_one(session, parsed.get("other"), None, False)
        if other is None:
            return {"line": question}
        if other.id == entry.id:
            return {"line": "That names the same note twice. Which two notes do you mean?"}
        tool = "link_notes" if intent == "link" else "unlink_notes"
        steps = [{"name": tool, "arguments": {"note_id": entry.id, "other_note_id": other.id}}]
        label = f"{'Link' if intent == 'link' else 'Unlink'} {name} {'and' if intent == 'link' else 'from'} “{_title(other)}”"
    card = _card(label, steps, skipped, [f"#{entry.id} {_title(entry)}"])
    if intent in CONFIRM_INTENTS:
        return {"line": _confirm(label), "card": card}
    return {"line": label, "card": card, "run": True}


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
    from tessellate.ai import agent, cards, tool_say, tools

    if parsed.get("note_id") is not None:
        result = tools.execute_tool(session, "get_note", {"note_id": parsed["note_id"]})
        if "error" in result:
            return {"line": f"I could not open note #{parsed['note_id']}: it does not exist, or it is private."}
        name, args = "get_note", {"note_id": parsed["note_id"]}
        line = f"Here is note #{parsed['note_id']}. Open it from the row below."
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
        line = (
            f"The closest note about “{about}” is {said['body'].lstrip('- ').strip()}"
            if parsed["intent"] == "open"
            else f"{said['lead']}\n\n{said['body']}"
        )
    event = {
        "type": "tool",
        "name": name,
        "arguments": args,
        "label": result.get("label") or name,
        "ok": True,
        "touched": agent._touched_items(result),
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

    delete_reminder(int(args["reminder_id"]), session)
    return {
        "binned": int(args["reminder_id"]),
        "label": f"Cancelled reminder #{int(args['reminder_id'])}",
        "undo": {"tool": "restore_reminder", "arguments": {"reminder_id": int(args["reminder_id"])}},
    }


def _step_undo(name: str, args: dict, result: dict):  # noqa: ANN202
    """The step that reverses one that ran: the tool's own, or the one this
    module knows for a reminder, a completed task and a link."""
    step_undo = result.get("undo")
    if name == "set_reminder" and result.get("id") is not None:
        step_undo = {"tool": "bin_reminder", "arguments": {"reminder_id": result["id"]}}
    if name == "complete_reminder":
        step_undo = task_acts.undo_step(name, args)
    if name == "link_notes" and not step_undo:
        step_undo = {"tool": "unlink_notes", "arguments": {"note_id": args.get("note_id"), "other_note_id": args.get("other_note_id")}}
    return step_undo


def _run_one(session: Session, name: str, args: dict, tools) -> dict:  # noqa: ANN001
    """One step's result: the composer's own steps first, then the tool table."""
    if name == "start_meeting":
        return _start_meeting(session, args)
    if name == "bin_reminder":
        return _bin_reminder(session, args)
    if name in task_acts.OWN_STEPS:
        return task_acts.run_step(session, name, args)
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
        result = _run_one(session, name, args, tools)
        if "error" in result:
            reason = "private" if "is private" in str(result["error"]) else "failed"
            failed.append({"id": args.get("note_id"), "reason": reason})
            continue
        done.append((name, args, result))
        step_undo = _step_undo(name, args, result)
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
