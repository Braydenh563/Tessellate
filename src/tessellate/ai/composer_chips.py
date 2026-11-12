"""The chips that continue a conversation (fable-composer-1110 F5).

A chip is the next thing a person would ask, taken from what the answer showed (the turn's
frame: its notes, the person, the days, the list rows), never from the question's leftover
words, never the question just asked, and a button that acts only proposes: "Remind me the
day before" opens the usual Confirm card. Pure: the callers hand in the frame, the notes the
frame names and the chat's earlier questions. The model-off and model-on paths both call it.
"""

from __future__ import annotations

import re

from tessellate.ai import composer_frame

MAX_CHIPS = 4
#: The generic trio (`composer_talk.acts_for`): only on a first turn or after a stumped one.
GENERIC = frozenset({"what did i write this week?", "notebook statistics", "what can you do?"})
#: The answer to a reminder with no time says its own choices (`composer_replies.ASK_WHEN`).
#: Under a hello or thanks that has no answer before it to resume (L48).
STARTERS = ["What is due soon?", "What did I write yesterday?", "What are my open tasks?"]
TIME_CHIPS = ["Tomorrow at 9", "Friday afternoon", "In an hour"]
_ASKS_TIME = re.compile(r"\b(?:when|what time|at what time)\b[^?\n]*\b(?:remind|reminder|reminded)\b[^?\n]*\?\s*$", re.I)
_ABOUT = re.compile(r"^(?P<head>.*?\b(?:about|on|for|of)) (?P<subject>(?:the )?[^?]+?)\?$", re.I)
_NAMED = re.compile(r"^(?:When did I (?:last )?write about|What(?:'s| is) the latest on|What else have I saved about|What do I know about|What else do my notes say about|Tell me more about) ", re.I)
_ARTICLE = {"the", "a", "an", "my", "our"}
_SHAPE_STOP = frozenset("and of in on for with to a an the my our is".split())

#: (what the note says, the question it opens, a word that means the answer already said it)
_FACTS = [
    (r"\bwith (?:Dr|Mr|Mrs|Ms|[A-Z][a-z]+)\b", "Who is it with?", "with"),
    (r"\bask (?:about|him|her|them)\b", "What should I ask?", "ask"),
    (r"\b(?:in room|room [A-Z]?\d|at [A-Z][a-z]+ [A-Z])", "Where is it?", "room"),
    (r"\bbring\b", "What should I bring?", "bring"),
    (r"[$£€]\d|\bcost\b|\bprice\b", "How much does it cost?", "$"),
    (r"\b(?:worth|grade|covers)\b", "What does it cover?", "covers"),
]
_PERSON_FACTS = [
    ("birthday", "When is {p}'s birthday?"),
    (r"\blikes?\b|\bloves?\b|\bprefers?\b", "What does {p} like?"),
    (r"\bnumber\b|\bphone\b", "What is {p}'s number?"),
    (r"\bvisit|\bmoved\b|\bcoming\b", "What is {p} up to?"),
]


def norm(chip: str) -> str:
    """A question without its case, punctuation or "'s": "What's the latest on X?" and "What is the latest on X" are one."""
    text = re.sub(r"[^\w\s]", " ", str(chip).lower().replace("what's", "what is"))
    return " ".join(w for w in text.split() if w not in {"the", "a", "last"})


def _words(text: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z][a-z-]+", text.lower().replace("'s", "").replace("’s", ""))}


_THING = re.compile(r"(?:\b(?:the|a|an|my|our|your|his|her|their)|['’]s) (?:[a-z]+ )?([a-z]{3,})", re.I)
_NAME = re.compile(r"(?<=[a-z,] )([A-Z][a-z]{2,})")


def vocabulary(notes: list[dict], frame: dict) -> set[str]:
    """The words the notes call things: title words, tags, the person, what they say after an article and their names; never the question's own words."""
    vocab = _words(str(frame.get("person") or ""))
    for note in notes:
        vocab |= _words(composer_frame.note_title(note))
        tags = note.get("tags") or []
        vocab |= _words(" ".join(str(t) for t in tags) if isinstance(tags, list) else str(tags))
        body = str(note.get("content") or "")
        #: What the notes put after "the", "my" or "'s" is a thing; a capital mid-sentence is a name.
        vocab |= _words(" ".join(_THING.findall(body) + _NAME.findall(body)))
    return vocab


def _subject_parts(subject: str) -> tuple[str, list[str]]:
    words = subject.split()
    owner = words[0].lower() if words and words[0].lower() in _ARTICLE else ""
    return owner, (words[1:] if owner else words)


def _named_by_notes(core: list[str], vocab: set[str]) -> bool:
    content = [w for w in _words(" ".join(core)) if w not in _SHAPE_STOP]
    return 0 < len(core) <= 4 and bool(content) and all(w in vocab for w in content)


def clean(chip: str, vocab: set[str], titles: set[str]) -> str:
    """The chip with a grammatical subject, or "" when its subject is no thing the notes name
    ("the Kyoto", "finish piranesi", "the latest on badly", "feeling pretty tired today, slept badly")."""
    found = _ABOUT.match(chip) if isinstance(chip, str) and not chip.startswith("Open ") and _NAMED.match(chip) else None
    if not found:
        return chip
    subject = found.group("subject").strip()
    owner, core = _subject_parts(subject)
    if "," in subject or not _named_by_notes(core, vocab):
        return ""
    name = " ".join(core)
    #: A lone proper name takes no article: "the Kyoto" is "Kyoto".
    if owner == "the" and len(core) == 1 and core[0][:1].isupper() and name.lower() not in titles:
        owner = ""
    return chip.replace(subject, f"{owner} {name}".strip(), 1)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _person_chips(person: str, body: str, said: str) -> list[str]:
    out = []
    for pattern, question in _PERSON_FACTS:
        if re.search(pattern, body, re.I) and not re.search(pattern, said, re.I):
            out.append(question.format(p=person))
    return out


def _fact_chips(body: str, said: str, asked: str) -> list[str]:
    out = []
    for pattern, question, spoken in _FACTS:
        if re.search(pattern, body) and spoken not in said.lower() and spoken not in asked.lower():
            out.append(question)
    return out


def _rows_chips(shown: list[dict]) -> list[str]:
    """What a pair of budgets raises, and the other rows of a list (an Open for each, not the first only)."""
    titles = [composer_frame.note_title(n) for n in shown]
    out = ["Which is higher?"] if len(shown) >= 2 and all(re.search(r"budget|cost|spend", t, re.I) for t in titles[:2]) else []
    named = composer_frame.title_line(shown[1].get("content") or "") if len(shown) >= 2 else ""
    return out + ([f"What does “{titles[1]}” say?"] if named and titles[1] else [])


def _day_chips(frame: dict, title: str, today: str) -> list[str]:
    """A reminder for a coming day, naming what it is for; a day already past is not reminded of."""
    coming = any(d > today for d in frame.get("dates") or [])
    return [f"Remind me about {title} the day before" if title else "Remind me the day before"] if coming else []


WEEK_CHIP = "What else is on that week?"


def week_chips(frame: dict, today: str) -> list[str]:
    """The agenda of a coming day's week; offered after the other chips, only where they leave room."""
    return [WEEK_CHIP] if any(d > today for d in (frame or {}).get("dates") or []) else []


def frame_chips(frame: dict, notes: list[dict], text: str, today: str = "") -> list[str]:
    """The next questions the turn's own frame opens, in the order a person would ask them: the
    person's other facts, the lead note's other facts, a coming day (a reminder), then the rows
    of a list and the question a pair of budgets raises."""
    by_id = {n.get("source_id", n.get("id")): n for n in notes}
    shown = [by_id[i] for i in (frame or {}).get("note_ids") or [] if i in by_id]
    if not shown:
        return []
    body, asked, person = str(shown[0].get("content") or ""), str(frame.get("ask") or ""), str(frame.get("person") or "")
    out = _person_chips(person, body, text) if person else []
    out += _fact_chips(body, text, asked) if len(shown) == 1 or not person else []
    return out + _day_chips(frame, composer_frame.note_title(shown[0]) if composer_frame.title_line(body) else "", today) + _rows_chips(shown)


def asks_time(text: str) -> bool:
    """Whether the answer ends by asking when a reminder should fire."""
    return bool(_ASKS_TIME.search(str(text or "").strip()))


def _frame_notes(session, frame: dict) -> list[dict]:  # noqa: ANN001
    """The notes a frame names, as the chips read them (id and text), those still there."""
    from sqlalchemy import select

    from tessellate.core.database import Entry

    ids = [i for i in frame.get("note_ids") or [] if isinstance(i, int)]
    rows = {e.id: {"id": e.id, "content": e.content} for e in session.scalars(select(Entry).where(Entry.id.in_(ids or [0]), Entry.deleted_at.is_(None)))}
    return [rows[i] for i in ids if i in rows]


def resume_chips(session, history: list[dict] | None, today: str, question: str) -> list[str]:  # noqa: ANN001
    """The chips a small-talk reply ("thanks") ends with: the last answer's own, so the chat can
    pick up where it was. Read from the frame the turn before was sent with; none without one."""
    turns = [t for t in history or [] if isinstance(t, dict)]
    frame = next((t["frame"] for t in reversed(turns) if t.get("frame")), None)
    if not frame:
        return []
    asked = [question, *(str(t.get("question") or "") for t in turns)]
    chips = [*frame_chips(frame, _frame_notes(session, frame), str(turns[-1].get("answer") or ""), today), *week_chips(frame, today)]
    return [c for c in chips if not spent(c, asked)][:MAX_CHIPS]


def lead(text: str) -> str:
    """The first line of an answer, as the repeat check reads it."""
    return str(text or "").strip().split("\n", 1)[0].strip()


def kind(chip: str) -> str:
    """What sort of next ask a chip is ("open", "what else do my notes say"): one of each sort is offered (C42)."""
    return re.split(r"\s(?:about|on|in|with)\s|[“\"]", chip.lower().replace("what's", "what is"))[0].strip()


def spent(chip: str, asked: list[str]) -> bool:
    """Whether the chat already asked this (a chip pressed, or the question itself)."""
    key = norm(chip)
    return any(norm(q) == key for q in asked)
