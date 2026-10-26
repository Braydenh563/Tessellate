"""The composer controls needle (CHAT_PLAN 1353: "the composer needs to
control needle and be good at using it").

needle is a 121M-parameter tool-calling model that writes no prose
(`needle_provider.py`). With no chat model the composer is the one in charge
of a tool turn, in four steps:

1. **The composer decides** whether the turn is a tool act, and which
   (`decide`), from the person's words. needle is never asked "is this an
   act" and never picks among seventy tools for these.
2. **needle only extracts the slots.** It is offered the one decided tool
   (`offer`), so its grammar can only fill that call's arguments.
3. **The composer validates** them (`validate`): a time is read by
   `ai/recognise.py` through `ai/when.py` against the person's clock, a
   missing slot is filled from the request's own words where they say it,
   and what still fails becomes a question, never a guess and never a call.
4. **The composer writes the prose**: the question for a gap, and the
   confirmation once the tool ran (`confirm`), in the person's voice
   (`composer_compose`).

Pure functions over strings, dates and dicts, so the tests drive them with a
fake needle transport and a fixed clock.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from tessellate.ai import composer_compose as compose
from tessellate.ai import recognise
from tessellate.ai import when as when_words

#: The acts the composer decides on its own, by the words that ask for them.
_ACTS: tuple[tuple[str, re.Pattern], ...] = (
    ("set_reminder", re.compile(
        r"\b(?:remind me|set (?:a |an )?(?:reminder|alarm)|add (?:a |an )?reminder|make (?:a |an )?reminder|reminder (?:to|for|about)|don'?t let me forget|ping me)\b", re.I)),
    ("create_note", re.compile(
        r"^(?:please |can you |could you )?(?:make|create|add|write|start|jot down|note down|save|take)\s+(?:me )?(?:a |an |this )?(?:new )?(?:note|memo)\b|^(?:note|jot) (?:down|this)\b", re.I)),
)
_LEAD_IN = re.compile(
    r"^(?:please |can you |could you |hey |ok |okay )*(?:remind me|set (?:a |an )?(?:reminder|alarm)(?: for me)?|add (?:a |an )?reminder|make (?:a |an )?reminder|"
    r"don'?t let me forget|ping me)\s*(?:to |about |that |for |:)?\s*", re.I)
_NOTE_LEAD = re.compile(
    r"^(?:please |can you |could you )*(?:make|create|add|write|start|jot down|note down|save|take)\s+(?:me )?(?:a |an |this )?(?:new )?(?:note|memo)\s*(?:that says|saying|about|called|titled|:)?\s*|^(?:note|jot) (?:down|this)\s*:?\s*", re.I)


def decide(text: str, offered: set[str] | frozenset[str]) -> str | None:
    """The tool a turn is an act of, or None when it is not one the composer
    knows (a read, a count, a search: the engine answers those, and needle's
    own pick is only the last resort for everything else)."""
    said = " ".join(str(text or "").split())
    for tool, cue in _ACTS:
        if tool in offered and cue.search(said):
            return tool
    return None


def offer(schemas: list[dict], tool: str) -> list[dict]:
    """The one schema needle is shown for a decided act."""
    return [s for s in schemas if s.get("name") == tool]


@dataclass(frozen=True)
class Verdict:
    """What validating one extraction came to: a call to make, or the
    sentence that asks for what is missing."""

    call: dict | None = None
    say: str = ""


def _reminder(args: dict, text: str, now: datetime, mood: compose.Mood) -> Verdict:
    said = str(args.get("when") or "").strip()
    body = str(args.get("text") or "").strip()
    request = _LEAD_IN.sub("", " ".join(text.split()))
    read = recognise.parse_reminder_text(request, now)
    #: A sentence that was only a time keeps itself as its text: no subject.
    if read and read["text"].lower().strip(" .") == request.lower().strip(" ."):
        read = {**read, "text": ""}
    call: dict = {}
    if said:
        if when_words.resolve(said, now) is None:
            return Verdict(say=compose.say("act_baddate", mood, said=said))
        call["when"] = said
    elif read:
        call["due_at"] = read["due_at"].isoformat()
    else:
        return Verdict(say=compose.say("act_ask", mood, missing="when it should go off"))
    body = body or (read["text"] if read else "")
    if not body:
        return Verdict(say=compose.say("act_ask", mood, missing="what the reminder is for"))
    return Verdict(call={"text": body, **call})


def _note(args: dict, text: str, mood: compose.Mood) -> Verdict:
    content = str(args.get("content") or "").strip() or _NOTE_LEAD.sub("", " ".join(text.split())).strip()
    if not content:
        return Verdict(say=compose.say("act_ask", mood, missing="what the note should say"))
    return Verdict(call={"content": content})


def validate(tool: str, calls: list[dict], text: str, now: datetime, mood: compose.Mood) -> Verdict:
    """needle's extraction for `tool` checked by the composer. `calls` are
    needle's calls (`{"function": {"name", "arguments"}}`), maybe none. Slots
    the extraction left empty are read from `text`; what cannot be read is
    asked for in a sentence."""
    args: dict = {}
    for call in calls:
        fn = call.get("function") or {}
        if fn.get("name") == tool and isinstance(fn.get("arguments"), dict):
            args = fn["arguments"]
            break
    return _reminder(args, text, now, mood) if tool == "set_reminder" else _note(args, text, mood)


def call_for(tool: str, call: dict) -> dict:
    """A validated call in the agent's raw shape."""
    return {"function": {"name": tool, "arguments": call}}


def _reminder_what(result: dict, args: dict) -> str:
    text = str(result.get("text") or args.get("text") or "that").strip()
    text = text[:1].lower() + text[1:] if text[:2] != text[:2].upper() else text
    due = result.get("due_at")
    try:
        at = datetime.fromisoformat(str(due))
        when = f"{at:%A} {at.day} {at:%B} at {at:%H:%M}"
    except ValueError:
        when = str(result.get("due") or "the time you gave")
    return f"set a reminder to {text} for {when}"


def confirm(tool: str, result: dict, args: dict, mood: compose.Mood) -> str | None:
    """The composer's confirmation of a tool that ran, or None for a tool it
    does not word itself (`tool_say` words those, including a saved note,
    whose reply names the category and tags the tool chose)."""
    if tool == "set_reminder":
        return compose.say("act_done", mood, what=_reminder_what(result, args))
    return None


def nothing_fits(mood: compose.Mood) -> str:
    """The line for a turn no tool fits, with no model to write one."""
    return compose.say("act_none", mood)
