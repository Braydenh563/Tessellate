"""Slash commands: exact, model-free answers typed as `/name [argument]`
(O6; BACKLOG "Slash commands in Chat and the composer", the owner,
2026-10-12: "One registry feeds the commands, `/help <command>` and the `/`
autocomplete, so they cannot drift").

**One registry, three readers.** `COMMANDS` is read by `answer` (the chat
route runs a typed command before any search), by `catalogue` (`GET
/chat/commands`, which the Chat box's "/" menu lists) and by `/help` itself.
A command answers as a sentence and, when it names notes, the rows
`tool_say` draws for a tool's notes (one look for the same thing), so the
two entrances to an action, a typed command and a tool call, read alike.

**Natural language equals the command** where the composer had no list of
its own: "which notes have no tags" runs `/untagged` (`infer`). "What did I
write last week" and "what have I saved recently" were answered before this
module, by the digest and the recency path, and keep their answers.

The four the brief names are here (`/recent [n]`, `/count [tag, category or
word]`, `/made <when>`, `/untagged`) and `/help [command]`; the rest are
`slash_more.MORE`. Each works with no model; a missing or unreadable argument
says how to type it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai import realise, slash_more
from tessellate.ai.slash_more import _more, _notes, _rows, _tags_of
from tessellate.ai.slash_table import TABLE

@dataclass(frozen=True)
class Command:
    name: str
    usage: str
    summary: str
    example: str
    run: Callable[[Session, str, datetime], str]


def _recent(session: Session, arg: str, now: datetime) -> str:
    entry, visible = _notes()
    n = slash_more.count_arg(arg)
    rows = list(session.scalars(select(entry).where(*visible).order_by(entry.created_at.desc(), entry.id.desc()).limit(n)))
    if not rows:
        return "You have no notes yet."
    lead = "Your newest note:" if len(rows) == 1 else f"Your {realise.count_word(len(rows))} newest notes:"
    return f"{lead}\n\n{_rows(session, rows)}"


def _count(session: Session, arg: str, now: datetime) -> str:
    entry, visible = _notes()
    total = session.scalar(select(func.count(entry.id)).where(*visible)) or 0
    word = arg.strip().lstrip("#").lower()
    if not word:
        return f"You have {realise.count_noun(total, 'note')}."
    def of_yours(n: int, said: str) -> str:
        return f"{realise.count_word(n).capitalize()} of your {total} notes {said}."

    tagged = sum(1 for raw in session.scalars(select(entry.tags).where(*visible)) if word in _tags_of(raw))
    if tagged:
        return of_yours(tagged, f"{'is' if tagged == 1 else 'are'} tagged #{word}")
    from tessellate.core.database import Category

    filed = session.scalar(
        select(func.count(entry.id)).join(Category, Category.id == entry.category_id).where(*visible, func.lower(Category.name) == word)
    ) or 0
    if filed:
        return of_yours(filed, f"{'is' if filed == 1 else 'are'} in {arg.strip()}")
    said = session.scalar(select(func.count(entry.id)).where(*visible, func.lower(entry.content).contains(word, autoescape=True))) or 0
    if said:
        return of_yours(said, f"{'mentions' if said == 1 else 'mention'} “{arg.strip()}”")
    return f"No note is tagged #{word}, filed in {arg.strip()} or mentions it. You have {realise.count_noun(total, 'note')} in all."


def _window(arg: str, today: date) -> tuple[date, date, str] | None:
    """The days `arg` names ("yesterday", "last week", "since 3 October"),
    read the way a question is (`composer.plan`)."""
    from tessellate.ai import composer

    plan = composer.plan(f"what did I write {arg}", today)
    if plan.window:
        return plan.window[0], plan.window[1], plan.window_phrase or arg
    return None


def _made(session: Session, arg: str, now: datetime) -> str:
    if not arg.strip():
        return "Say when: /made today, /made yesterday, /made last week or /made since 3 October."
    span = _window(arg.strip(), now.date())
    if span is None:
        return f"I couldn't read “{arg.strip()}” as a day or a span. Try /made yesterday, /made last week or /made in March."
    start, end, phrase = span
    entry, visible = _notes()
    rows = list(session.scalars(
        select(entry).where(*visible, entry.created_at >= datetime.combine(start, datetime.min.time()),
                            entry.created_at < datetime.combine(end + timedelta(days=1), datetime.min.time()))
        .order_by(entry.created_at.desc(), entry.id.desc())
    ))
    if not rows:
        from tessellate.ai import composer

        first, last = session.execute(select(func.min(entry.created_at), func.max(entry.created_at)).where(*visible)).one()
        return composer.empty_window(phrase, first.date() if first else None, last.date() if last else None, seed=arg)
    from tessellate.ai import composer

    lead = f"You wrote {realise.count_noun(len(rows), 'note')} {composer.window_said(phrase)}:"
    return f"{lead}\n\n{_rows(session, rows)}{_more(len(rows))}"


def _untagged(session: Session, arg: str, now: datetime) -> str:
    entry, visible = _notes()
    rows = [e for e in session.scalars(select(entry).where(*visible).order_by(entry.created_at.desc())) if not _tags_of(e.tags)]
    if not rows:
        return "Every note has at least one tag."
    lead = "One note has no tags:" if len(rows) == 1 else f"{realise.count_noun(len(rows), 'note').capitalize()} have no tags:"
    tail = "\n\nTag one from its row, or say “tag the … note with …”."
    return f"{lead}\n\n{_rows(session, rows)}{_more(len(rows))}{tail}"


def _help(session: Session, arg: str, now: datetime) -> str:
    asked = arg.strip().lstrip("/").lower()
    if asked in COMMANDS:
        command = COMMANDS[asked]
        return f"**{command.usage}**: {command.summary} For example, {command.example}."
    lines = "\n".join(f"- **{c.usage}**: {c.summary}" for c in COMMANDS.values())
    lead = f"There's no /{asked} command. " if asked else ""
    return f"{lead}Type one of these in the chat box; each answers from your notes with no AI:\n\n{lines}"


def _today(session: Session, arg: str, now: datetime) -> str:
    return _made(session, "today", now)


def _yesterday(session: Session, arg: str, now: datetime) -> str:
    return _made(session, "yesterday", now)


_RUN: dict[str, Callable[[Session, str, datetime], str]] = {
    "recent": _recent,
    "count": _count,
    "made": _made,
    "untagged": _untagged,
    "today": _today,
    "yesterday": _yesterday,
    **slash_more.RUN,
    "help": _help,
}

COMMANDS: dict[str, Command] = {row[0]: Command(*row, _RUN[row[0]]) for row in TABLE}

_TYPED = re.compile(r"^\s*/([a-z]+)\b\s*(.*)$", re.I | re.S)


def parse(text: str) -> tuple[str, str] | None:
    """`(name, argument)` for a typed command, or None for anything else (a
    path such as "/usr/bin" is not a command: no such name, and it says so
    only when the name is a word)."""
    typed = _TYPED.match(text or "")
    if not typed:
        return None
    return typed.group(1).lower(), typed.group(2).strip()


#: A list asked for in ordinary words, and the command it is: "which notes
#: have no tags", "what are my pinned notes", "show my 3 oldest notes", "do I
#: have any open todos", "give me a random note". Each needs a question or
#: request word first and the thing's own word after, so "pin the dentist
#: note" and "my oldest friend" are not commands. The first group, when it
#: holds digits, is the argument.
_ASKING = r"^(?:which|what|whats|show|list|give|any|do|are|find|pick|pull|surprise)\b"
_INFERRED = (
    ("untagged", re.compile(_ASKING + r".*\b(?:untagged|no tags?|without (?:any )?tags?|not tagged|haven'?t tagged)\b", re.I)),
    ("pinned", re.compile(_ASKING + r".*\bpinn?ed\b.*\bnotes?\b|" + _ASKING + r".*\bnotes?\b.*\bpinn?ed\b", re.I)),
    ("oldest", re.compile(_ASKING + r".*?\b(?:(\d+) )?oldest notes?\b", re.I)),
    ("todo", re.compile(_ASKING + r".*\b(?:open|unchecked|outstanding)\s+(?:to-?dos?|check ?boxes|tick ?boxes)\b", re.I)),
    ("random", re.compile(_ASKING + r".*\b(?:a|one) (?:random|rando?m) notes?\b", re.I)),
)


def _inferred(text: str) -> tuple[str, str] | None:
    for name, pattern in _INFERRED:
        found = pattern.search(text)
        if found:
            arg = found.group(1) if found.re.groups and found.group(1) else ""
            if name == "oldest" and not arg and not found.group(0).lower().endswith("notes"):
                #: "my oldest note" is one note (INBOX 1357, class E: it listed five).
                arg = "1"
            return name, arg
    return None


def infer(text: str) -> tuple[str, str] | None:
    """The command an ordinary sentence asks for, where the composer had no
    list of its own; None otherwise. A sentence with a slip in it ("wich
    notes are pined") is read as the speller puts it right."""
    from tessellate.ai import question_noise

    said = " ".join((text or "").split())
    if not said or len(said) > 160:
        return None
    return _inferred(said) or _inferred(question_noise.repair(question_noise.tidy(said)))


def answer(session: Session, text: str, now: datetime, *, typed_only: bool = False) -> str | None:
    """The command's answer for `text`, typed or (unless `typed_only`)
    inferred; None when `text` is neither."""
    read = parse(text) or (None if typed_only else infer(text))
    if read is None:
        return None
    name, arg = read
    command = COMMANDS.get(name)
    if command is None:
        return _help(session, name, now)
    return command.run(session, arg, now)


def catalogue() -> list[dict]:
    """The commands for the "/" menu: name, how to type it, what it does."""
    return [{"name": c.name, "usage": c.usage, "summary": c.summary, "example": c.example} for c in COMMANDS.values()]
