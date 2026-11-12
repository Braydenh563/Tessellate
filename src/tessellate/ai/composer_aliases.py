"""The names a subject goes by in the person's own notes (W7b B7).

"What's the latest on sourdough" read the notes that say "sourdough", so a newer note that says
"Doug the starter is bubbly again" never reached the answer: the person's sourdough note says
"My sourdough starter is called Doug". The notes about a subject name it in passing ("X is called
Y", "I named it Y"); those names, and the thing the subject word is attached to ("starter"), are
read from the notes already found and widen the pool to the notes that say them. No synonym table,
and nothing invented: only a name a note of the subject itself gives. Pure words plus one query."""

from __future__ import annotations

import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from tessellate.core.database import LIKE_ESCAPE, Entry, like_escape

#: "my sourdough starter is called Doug", "the starter was named Doug".
_CALLED = re.compile(r"(?P<np>[\w'’ -]{1,60}?)\b(?:is|are|was|were) (?:called|named|nicknamed) (?P<name>[A-Z][\w'’-]{2,24})")
#: "I named it Doug", "we call her Doug".
_NAMED = re.compile(r"\b(?:i|we) (?:named|called|nicknamed) (?:it|him|her|them) (?P<name>[A-Z][\w'’-]{2,24})")
#: A "latest" ask: the newest note that fits. The digest reads the same pattern (`composer_digest._LATEST_ASK`).
LATEST_ASK = re.compile(
    r"\b(?:latest|newest|most recent|recently|lately)\b|\bwhen did i last\b|\bwhat(?:'s|s| is)\s+new\s+(?:with|on|about)\b"
    r"|\bnews\s+(?:on|about|with)\b|\bwhere am i (?:at )?with\b", re.I)
MAX_ALIASES = 4
MAX_EXTRA = 5
#: A sentence start is capitalised without being a name.
_NOT_NAMES = frozenset("The This That These Those There Here What When Where Which While With Without Today Tomorrow Yesterday".split())
_SAFE_HEAD = re.compile(r"[a-z]{4,24}")


def _line_names(line: str, subject: set[str]) -> list[str]:
    """The names one line gives the subject (and the noun it is attached to), in the order written."""
    found: list[str] = []
    if not any(w in line.lower() for w in subject):
        return found
    for m in _CALLED.finditer(line[:600]):
        words = re.findall(r"[\w'’-]+", m.group("np").lower())
        if subject & set(words):
            found += [m.group("name"), words[-1] if words[-1] not in subject and _SAFE_HEAD.fullmatch(words[-1]) else ""]
    return found + [m.group("name") for m in _NAMED.finditer(line[:600])]


def names_for(subject_words: list[str], texts: list[str]) -> list[str]:
    """The names the `texts` (notes already about the subject) give it, plus the noun the subject word
    modifies ("starter" in "sourdough starter" when it is the thing called). Capitalised names keep
    their case; at most `MAX_ALIASES`, none that is one of the subject's own words."""
    subject = {w.lower() for w in subject_words if w}
    if not subject:
        return []
    found = [name for text in texts for line in str(text or "").splitlines() for name in _line_names(line, subject)]
    out: list[str] = []
    for name in found:
        if name and name not in _NOT_NAMES and name.lower() not in subject and name not in out:
            out.append(name)
    return out[:MAX_ALIASES]


def _says(content: str, alias: str) -> bool:
    flags = 0 if alias[:1].isupper() else re.I
    return re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", content or "", flags) is not None


def widen(session: Session, subject: str, entries: list[Entry], *, skip: bool = False) -> tuple[list[Entry], list[str]]:
    """`entries` plus the newest notes that say a name the subject's own notes give it, and those names
    (so the caller can count the notes as holding the subject). Unchanged when the notes name nothing or `skip`."""
    words = re.findall(r"[a-z0-9]+", (subject or "").lower())
    aliases = [] if skip else names_for(words, [e.content or "" for e in entries])
    if not aliases:
        return entries, []
    have = {e.id for e in entries}
    clauses = [Entry.content.ilike(f"%{like_escape(a)}%", escape=LIKE_ESCAPE) for a in aliases]
    rows = session.scalars(
        select(Entry).where(Entry.is_deleted == False, Entry.is_private == False, Entry.is_board == False, or_(*clauses))  # noqa: E712
        .order_by(Entry.created_at.desc(), Entry.id.desc()).limit(MAX_EXTRA * 4)
    )
    extra = [e for e in rows if e.id not in have and any(_says(e.content, a) for a in aliases)][:MAX_EXTRA]
    return (entries + extra, aliases) if extra else (entries, [])


def read(question: str, notes: list[dict]) -> dict:
    """`{subject stem: stems of the names its notes give it}` for a one-subject question over `notes`;
    empty when the notes name nothing. The caller sets it on `composer_ask.ALIASES` for a "latest" ask."""
    from tessellate.ai import composer_ask  # the defining module; this one is read by search, which the composer imports

    terms = composer_ask.subject_terms(question)
    stems = {composer_ask._stem(t) for t in terms}  # noqa: SLF001
    if len(stems) != 1:
        return {}
    holding = [str(n.get("content") or "") for n in notes if stems & set(composer_ask._words(str(n.get("content") or "")))]  # noqa: SLF001
    names = names_for([t.lower() for t in terms], holding)
    return {next(iter(stems)): frozenset(composer_ask._stem(n) for n in names)} if names else {}  # noqa: SLF001


def enter(question: str, notes: list[dict]):  # noqa: ANN201
    """Set the names for a "latest on X" ask and return the token to `composer_ask.ALIASES.reset`."""
    from tessellate.ai import composer_ask  # at the call: it reads the composer

    found = read(question, notes) if LATEST_ASK.search(question or "") else {}
    return composer_ask.ALIASES.set(found)
