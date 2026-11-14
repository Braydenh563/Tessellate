"""A calendar or a to-do list said in other words (CHAT_PLAN "Phrasing tests from real conversations").

People ask a notebook to "add dentist to my calendar for friday" or "check washing
up off my to do list". This app keeps reminders (they carry the date and the tick),
so those sentences are restated as the reminder sentences the acts already read; a
sentence that would empty a whole calendar or list is answered with how, never done
in bulk. Every restated sentence still ends in a card that waits for Confirm.
"""

from __future__ import annotations

import re
from tessellate.core.lazyre import lazy_compile

_LEAD = r"^(?:(?:hey|please|also|just|can you|could you|will you|would you|i need you to|i want you to|i need to|i must|i want to|i would like to|i'd like to)\s+)*"
_CAL = r"(?:calendar|schedule|planner|agenda|diary)"
_LIST = r"(?:[\w ]{0,25}?(?:to[- ]?do|task) list|list of (?:reminders|chores|housework)|reminders? list)"
_PLACE = rf"(?:my|the)\s+(?:{_CAL}|{_LIST})"
#: The to-do list the task acts already read ("put buy milk on my to-do list").
_PLAIN_TODO = lazy_compile(r"(?:^|\s)(?:my|the)\s+(?:to[- ]?do|task)\s+list$", re.IGNORECASE)
_WHEN = r"(?P<when>\s+(?:for|on)\s+\S.*)?"

_ADD = lazy_compile(
    rf"{_LEAD}(?P<verb>add|put|list|schedule|pencil in|write)\s+(?P<what>.+?)\s+(?:to|on|onto|in|into)\s+(?P<where>{_PLACE}){_WHEN}$",
    re.IGNORECASE,
)
_REMOVE = lazy_compile(
    rf"{_LEAD}(?:remove|delete|take|cancel|drop|get rid of|scratch)\s+(?P<what>.+?)\s+(?:off(?: of)?|from|out of)\s+{_PLACE}{_WHEN}$",
    re.IGNORECASE,
)
_NO_LONGER = lazy_compile(rf"{_LEAD}(?:remove|delete|cancel|clear|empty|wipe)\s+(?:out\s+)?{_PLACE}\b", re.IGNORECASE)
_TAKE_ALL = lazy_compile(rf"{_LEAD}(?:take|clear|remove)\s+(?:off|out)\s+(?:everything|all|it all)\s+(?:from|on|off|in)\s+{_PLACE}$", re.IGNORECASE)
_CHECK_OFF = lazy_compile(rf"{_LEAD}(?:check|tick|cross)\s+(?P<what>.+?)\s+off(?: of)?(?: on| from)?\s+{_PLACE}$", re.IGNORECASE)
_BARE = lazy_compile(r"^(?:(?:i'd like|i want|i need|i would like)\s+)?(?:to\s+)?(?:have\s+)?a reminder (?:made|set|created|added)$", re.IGNORECASE)
#: The app's alarm is an ordinary reminder (the Clock's "Set alarm" makes one), so setting one is the reminder act.
_SET_ALARM = lazy_compile(r"\b(?:set|add|put in|make|create|need|want)\b[^?]*?\b(?:an|another|a new|the|my) alarm\b", re.IGNORECASE)
_EVERYTHING = lazy_compile(r"^(?:everything|all|all of it|all of them|it all|the (?:whole|entire) (?:thing|list))$", re.IGNORECASE)

CLEAR_LINE = (
    "I do not clear a whole calendar or list in one go. Each item is a reminder: to drop one, say "
    "\"cancel the reminder about\" and what it is; to see what is there, say \"show my reminders\"."
)


def bulk(text: str) -> bool:
    """A sentence that would empty a calendar or a list, whole."""
    said = " ".join(str(text or "").split()).rstrip(" .!?")
    if _NO_LONGER.match(said) or _TAKE_ALL.match(said):
        return True
    gone = _REMOVE.match(said)
    return bool(gone and _EVERYTHING.match(gone.group("what").strip()))


def _item(what: str) -> str:
    """`what` without a trailing "event(s)". A suffix test, not a regex: a `\\s+` anchored at the end
    backtracks on a long run of spaces (CodeQL, polynomial regular expression)."""
    item = what.strip()
    for tail in ("events", "event"):
        if item.lower().endswith(tail) and item[: -len(tail)][-1:].isspace():
            return item[: -len(tail)].rstrip()
    return item


def restate(text: str) -> str:
    """`text` as the reminder sentence an act reads, else `text` as it was."""
    said = " ".join(str(text or "").split()).rstrip(" .!?")
    if _BARE.match(said):
        return "set a reminder"
    if _SET_ALARM.search(said):
        return re.sub(r"\b(?:an|another|a new) alarm\b", "a reminder", said, count=1, flags=re.IGNORECASE)
    added = _ADD.match(said)
    if added:
        what, when = _item(added.group("what")), added.group("when") or ""
        #: The plain to-do list keeps its own path (the task acts, the to-do note's line): "add" and "put" are
        #: read as they stand, the other verbs are said as "add" to reach it. A calendar, a list of reminders or
        #: a named list (spring cleaning) is a reminder.
        if not _PLAIN_TODO.match(added.group("where")):
            return f"remind me to {what}{when}"
        if added.group("verb").lower() not in ("add", "put"):
            return f"add {what} to {added.group('where')}{when}"
    gone = _REMOVE.match(said)
    if gone and not _EVERYTHING.match(gone.group("what").strip()) and not _PLAIN_TODO.search(said):
        return f"cancel the reminder about {_item(gone.group('what'))}"
    ticked = _CHECK_OFF.match(said)
    if ticked:
        return f"mark {ticked.group('what').strip()} as done"
    return text
