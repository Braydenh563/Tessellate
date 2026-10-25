"""Study help with no model: quiz me, flashcards, key terms, a short summary
(INBOX 1351: "just as good and extremely smart" without Ollama).

`answer(ctx)` reads a question and returns a `Reply` or None. Everything it
says about a note is that note's own words (`study.py`); the frames around
them ("Correct.", "Not quite. Your note says:") have several wordings, chosen
by the chat's seed so a retry reads differently and the same chat reads the
same.

A quiz keeps no state on the server. Each question is asked under a header
line, `**Quiz on <topic>** · question 2 of 6 · score 1 of 1`; the next turn
finds the last such header in the dialogue, rebuilds the same deck from the
same notes in the same order, grades the reply against the question asked,
and writes the next header. If the notes changed meanwhile and the question
is no longer in the deck, the quiz says so and starts over.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from itertools import zip_longest

from tessellate.ai import study

QUIZ_LENGTH = 6
MAX_QUIZ = 12
CARDS_SHOWN = 4

# --- the shapes a turn arrives in -----------------------------------------------------

_LEAD = r"(?:(?:please|pls|plz|can you|could you|can we|would you|lets|let's|let us|i want you to|i want to|i'd like you to|i'd like to|i would like to|go on|ok|okay|hey)[, ]+)*"
_FROM = r"(?:on|about|from|over|of|for|in|covering|using|out of|around)"
_THIS = re.compile(r"^(?:this|that|the|my|current|open|opened|latest|newest|last)?\s*(?:note|one|page|lecture|doc|document|file)?s?$|^(?:it|this note|that note|this one|the open note|here)$", re.I)

_QUIZ = (
    re.compile(rf"^{_LEAD}(?:quiz|test|question|drill|grill|examine|check)\s+(?:me|us)\b\s*(?:{_FROM}\s+)?(?P<t>.*)$", re.I),
    re.compile(rf"^{_LEAD}(?:(?:do|start|have|give me|run|begin|make me|set me|ask me|get me|create|generate|write)\s+)?(?:a|an|another|some|one more|(?P<n>\d{{1,2}}))?\s*(?:quick\s+|short\s+|little\s+|practice\s+|mini\s+)?(?:quiz(?:zes)?|practice questions?|practice test|test questions?|exam questions?|revision questions?|questions)\s*(?:{_FROM}\s+(?P<t>.*))?$", re.I),
    re.compile(rf"^{_LEAD}(?:test my knowledge|check my knowledge|check what i know|see what i know)\s*(?:{_FROM}\s+)?(?P<t>.*)$", re.I),
    re.compile(r"^(?:help me |let's |lets |i need to |i have to |i want to |time to |i should )(?:revise|study|cram|practi[sc]e|review for)\s+(?P<t>.+)$", re.I),
    re.compile(rf"^{_LEAD}(?:can i|could i|may i) (?:get|have|do) (?:a|an) (?:quick |short )?quiz\s*(?:{_FROM}\s+(?P<t>.*))?$", re.I),
)
_FLASH = (
    re.compile(rf"^{_LEAD}(?:make|create|generate|build|write|prepare|produce|give me|get me|do|draw up|put together|turn)\s+(?:me\s+)?(?:(?:some|a set of|a deck of|a few|\d+|my|the)\s+)?(?:flash\s?-?cards?|study cards?|revision cards?|cue cards?|index cards?)\b\s*(?:{_FROM}\s+)?(?P<t>.*)$", re.I),
    re.compile(rf"^{_LEAD}(?:turn|convert|make|change)\s+(?P<t>.+?)\s+(?:in)?to\s+(?:flash\s?-?cards?|study cards?|a quiz)$", re.I),
    re.compile(r"^flash\s?-?cards?\s*(?:" + _FROM + r"\s+)?(?P<t>.*)$", re.I),
)
_TERMS = (
    re.compile(
        rf"^{_LEAD}(?:what (?:are|is|were)|what['’]?s|list|show|give me|tell me|find|name|extract|pull out|get|display|read me)\s+(?:me\s+)?(?:all\s+)?(?:of\s+)?(?:the\s+)?(?:\d+\s+)?"
        rf"(?:key|main|important|core|central|essential|major|new|technical|useful)?\s*(?:terms|vocab(?:ulary)?|keywords?|key words|concepts|terminology|definitions)\b\s*(?:{_FROM}\s+)?(?P<t>.*)$", re.I),
    re.compile(rf"^{_LEAD}(?:glossary|vocab(?:ulary)?|key terms|keywords?)\s*(?:{_FROM}\s+)?(?P<t>.*)$", re.I),
)
_SUMMARY = re.compile(
    rf"^{_LEAD}(?P<brief>briefly\s+|quickly\s+)?(?:summari[sz]e|sum up|recap|run through|run me through|go over|give me (?:a |an |the )?(?:quick |short |brief |rough )?(?:summary|recap|overview|rundown|run-?down|tl;?dr|gist)(?:\s+{_FROM})?|tl;?dr(?:\s+{_FROM})?|"
    rf"what (?:did|have|do|was|were) (?:we|i|you) (?:cover|covered|learn|learnt|learned|study|studied|go over|discuss)(?:\s+(?:in|on|during|at|about))?|what(?:['’]?s| is| was) (?:covered|inside)(?:\s+(?:in|on))?|"
    rf"what(?:['’]?s| is) the (?:gist|summary|point|main idea)\s+{_FROM})\s*(?P<t>.*)$", re.I)

_WHOLE_NOTEBOOK = re.compile(r"^(?:all |every |each )?(?:of )?(?:my |the )?(?:notes|notebook|everything|stuff)$", re.I)
_ASKED_ON = re.compile(r"\b(?:in|using)\s+(?:\d+|a few|some)\s+(?:bullet points?|bullets|sentences|lines|points)\.?$", re.I)
_FILLER = re.compile(r"\b(?:please|pls|thanks|thank you|for me|now)\b|[?.!]+$", re.I)


@dataclass
class Ctx:
    """Everything a study answer reads: the question, the notebook's notes
    (newest first, each `{id, content, created_at}`), the dialogue, the
    clock and the chat's seed."""

    question: str
    notes: list[dict]
    now: datetime
    history: list[dict] = field(default_factory=list)
    seed: str = ""
    open_ids: list[int] = field(default_factory=list)
    follow_kind: str = ""
    said: str = ""
    asked: str = ""
    reminders: list[dict] = field(default_factory=list)
    ask: bool = False
    prefer_numbers: bool = True

    @property
    def last_answer(self) -> str:
        return str(self.history[-1].get("answer") or "") if self.history else ""


@dataclass
class Reply:
    text: str
    offer: dict | None = None
    asks: list[str] = field(default_factory=list)


def pick(seed: str, key: str, options: tuple | list) -> str:
    return options[int.from_bytes(hashlib.sha1(f"{seed}|{key}".encode()).digest()[:4], "big") % len(options)]


# --- finding the note ---------------------------------------------------------------

_TOPIC_NOISE = re.compile(r"\b(?:my|the|notes?|about|on|of|for|in|from|and|a|an|all|everything|please|stuff|material|topic|chapter notes)\b", re.I)


def _title(note: dict) -> str:
    return study.title_of(str(note.get("content") or ""))


def _body_matches(wanted: list[str], ctx: Ctx, limit: int) -> list[dict]:
    scored: list[tuple[int, int, dict]] = []
    for i, n in enumerate(ctx.notes):
        low = str(n.get("content") or "").lower()
        if all(w in low for w in wanted):
            scored.append((-sum(low.count(w) for w in wanted), i, n))
    scored.sort(key=lambda row: row[:2])
    return [row[2] for row in scored[:limit]]


def topic_notes(topic: str, ctx: Ctx, limit: int = 3) -> list[dict]:
    """The notes a topic names: those whose title holds every word of it,
    else those whose text does, best first. An empty topic, or "this note", is
    the note that is open. Empty when nothing fits."""
    topic = _FILLER.sub(" ", topic or "").strip(" ,")
    if not topic or _THIS.match(topic):
        return [n for n in ctx.notes if n.get("id") in ctx.open_ids][:limit]
    wanted = study.content_stems(_TOPIC_NOISE.sub(" ", topic))
    if not wanted:
        return []
    exact = [n for n in ctx.notes if _title(n).lower() == topic.lower()]
    if exact:
        return exact[:1]
    titled = [n for n in ctx.notes if set(wanted) <= set(study.content_stems(_title(n)))]
    return titled[:limit] or _body_matches(wanted, ctx, limit)


def category_notes(topic: str, ctx: Ctx, limit: int = 6) -> list[dict]:
    """The notes filed under the category a topic names ("flashcards from
    Uni"); empty when the topic is no category of the notebook."""
    wanted = _FILLER.sub(" ", topic or "").strip(" ,").lower()
    wanted = re.sub(r"^(?:my|the|all)\s+|\s+notes?$", "", wanted).strip()
    if not wanted:
        return []
    #: "my lecture notes" is the category "Lecture notes" as well as "Lecture".
    names = {wanted, f"{wanted} notes"}
    return [n for n in ctx.notes if str(n.get("category") or "").lower() in names][:limit]


def _link(note: dict) -> str:
    return f"[**{_title(note) or 'Untitled'}**](#/notes/{note['id']})"


def _newest_with_cards(ctx: Ctx, count: int = 3, need: int = 3) -> list[dict]:
    out = []
    for n in ctx.notes[:60]:
        if len(study.cards(str(n.get("content") or ""))) >= need:
            out.append(n)
            if len(out) >= count:
                break
    return out


def _which_note(ctx: Ctx, what: str, verb: str) -> Reply:
    near = _newest_with_cards(ctx) or ctx.notes[:3]
    names = [_title(n) for n in near if _title(n)]
    if not names:
        return Reply(pick(ctx.seed, "nonotes", (
            "There is no note to work from yet. Write a few lines of notes, then ask again.",
            "Your notebook has nothing I can study from yet.",
        )))
    text = pick(ctx.seed, "which", (
        f"Which note should I {what}? Open one and ask again, or name it.",
        f"I need a note to {what}. Name one, or open it first.",
        f"Which note do you want to {what}? Open it, or say its name.",
    ))
    return Reply(text + "\n\nA few that have enough to work with: " + "; ".join(f"“{n}”" for n in names) + ".", asks=[f"{verb} {n}" for n in names])


def _nothing_named(ctx: Ctx, topic: str, verb: str) -> Reply:
    near = _newest_with_cards(ctx)
    names = [_title(n) for n in near if _title(n)]
    text = f"I did not find a note about “{topic.strip(' .?')}”."
    if names:
        text += " These have material to work with: " + "; ".join(f"“{n}”" for n in names) + "."
    return Reply(text, asks=[f"{verb} {n}" for n in names])


def _split_n(topic: str) -> tuple[str, int | None]:
    found = re.search(r"\b(?:with|using|of|and give me)?\s*(\d{1,2})\s+(?:questions?|cards?|flash\s?cards?)\b", topic or "", re.I)
    if not found:
        return topic, None
    return (topic[: found.start()] + topic[found.end():]).strip(" ,"), int(found.group(1))


# --- the entry --------------------------------------------------------------------

def match(question: str) -> tuple[str, str, int | None] | None:
    """(kind, topic, count) when a question is a study request, else None."""
    text = " ".join((question or "").split())
    if not text or len(text) > 240:
        return None
    for kind, patterns in (("flash", _FLASH), ("terms", _TERMS), ("quiz", _QUIZ)):
        for pattern in patterns:
            found = pattern.match(text)
            if found:
                topic = (found.groupdict().get("t") or "").strip()
                topic, n = _split_n(topic)
                count = n or (int(found.group("n")) if "n" in found.groupdict() and found.group("n") else None)
                return kind, topic, count
    found = _SUMMARY.match(text)
    if found:
        topic = _ASKED_ON.sub("", (found.group("t") or "").strip()).strip()
        return ("summary-brief" if found.group("brief") else "summary"), topic, None
    return None


def answer(ctx: Ctx) -> Reply | None:
    question = ctx.question
    brief = False
    if ctx.follow_kind == "length" and question.lower().startswith("briefly,"):
        question, brief = question[8:].strip(), True
    detail = ctx.follow_kind == "length" and question.rstrip("?. ").lower().endswith("in detail")
    if detail:
        question = re.sub(r"\s+in detail\W*$", "", question, flags=re.I)
    found = match(question)
    if found:
        kind, topic, count = found
        if kind.startswith("summary"):
            level = -1 if (brief or kind == "summary-brief") else 1 if (detail or ctx.follow_kind == "more") else 0
            return _summary(ctx, topic, level)
        if kind == "terms":
            return _terms(ctx, topic, more=ctx.follow_kind == "more")
        if kind == "flash":
            return _flashcards(ctx, topic)
        return _start_quiz(ctx, topic, count)
    return _continue_quiz(ctx)


# --- summary, terms, flashcards ---------------------------------------------------

def _target(ctx: Ctx, topic: str, verb: str, what: str, *, strict: bool) -> tuple[list[dict] | None, Reply | None]:
    """The notes a request names, or the reply that asks which. `strict`
    (a summary or terms request): a topic that names no note is not ours."""
    notes = topic_notes(topic, ctx)
    if notes:
        return notes, None
    cleaned = _FILLER.sub(" ", topic or "").strip(" ,")
    if strict and _WHOLE_NOTEBOOK.match(cleaned):
        #: "an overview of my notes" is the notebook's, which the digest reads.
        return None, None
    if not cleaned or _THIS.match(cleaned):
        return None, _which_note(ctx, what, verb)
    if strict:
        return None, None
    return None, _nothing_named(ctx, topic, verb)


def _summary_text(ctx: Ctx, notes: list[dict], parts: list, level: int) -> str:
    note = notes[0]
    head = pick(ctx.seed, "sumhead", (
        f"The short version of {_link(note)}:", f"Here is {_link(note)} in short:", f"{_link(note)}, boiled down:",
    )) if level <= 0 else f"{_link(note)} in more detail:"
    lines = [head, ""]
    for title, sents in parts:
        title = "" if title == _title(note) else title
        lines.append("- " + (f"**{title}**: " if title else "") + " ".join(sents))
    if len(notes) > 1:
        lines += ["", "Other notes that match: " + "; ".join(_link(n) for n in notes[1:]) + "."]
    more = sum(len(s) for _t, s in study.summary(str(note.get("content") or ""), 1)) > sum(len(s) for _t, s in parts)
    if level < 1 and more:
        lines += ["", "Say “more” for the rest."]
    return "\n".join(lines)


def _summary(ctx: Ctx, topic: str, level: int) -> Reply | None:
    #: A category by name ("summarise my lecture notes" for the category
    #: "Lecture notes") is all of its notes, not the one whose title has the
    #: word; a note titled exactly as asked still wins.
    named = category_notes(topic, ctx, limit=8)
    if len(named) > 1 and not any(_title(n).lower() == (topic or "").strip().lower() for n in ctx.notes):
        return _summaries(ctx, named)
    notes, reply = _target(ctx, topic, "Summarise", "summarise", strict=True)
    if not notes:
        return reply
    if re.search(r"\bnotes\b", topic or "", re.I) and len(notes) > 1 and not re.search(r"\bthis\b", topic or "", re.I):
        return _summaries(ctx, notes)
    parts = study.summary(str(notes[0].get("content") or ""), level)
    if not parts:
        return Reply(f"{_link(notes[0])} has too little in it to summarise.")
    return Reply(_summary_text(ctx, notes, parts, level))


def _summaries(ctx: Ctx, notes: list[dict]) -> Reply:
    """Several notes asked for together ("summarise my COMP2001 notes"): each
    in a line or two, newest first, never the first one alone."""
    lines = [pick(ctx.seed, "multihead", (f"{len(notes)} notes match. The short version of each:", f"Here are your {len(notes)} matching notes, one short paragraph each:")), ""]
    for note in notes:
        parts = study.summary(str(note.get("content") or ""), -1)
        body = " ".join(" ".join(sents) for _t, sents in parts[:2]) or "Too little in it to summarise."
        lines += [f"- {_link(note)}: {body}"]
    return Reply("\n".join(lines))


def _terms(ctx: Ctx, topic: str, *, more: bool = False) -> Reply | None:
    notes, reply = _target(ctx, topic, "Key terms in", "list the key terms of", strict=True)
    if not notes:
        return reply
    note = notes[0]
    found = study.key_terms(str(note.get("content") or ""), limit=24 if more else 10)
    if more:
        found = [t for t in found if f"**{t[0]}**" not in ctx.said][:14]
    if not found:
        return Reply(f"{_link(note)} has no bold words, definitions or section names I could take for terms." if not more
                     else "That was every term I could find.")
    head = pick(ctx.seed, "termhead", (
        f"Key terms in {_link(note)}:", f"The terms {_link(note)} leans on:", f"What {_link(note)} defines or stresses:",
    ))
    lines = [head, ""] + [f"- **{t}**" + (f": {g}" if g else "") for t, g in found]
    if not more and len(study.key_terms(str(note.get("content") or ""), limit=24)) > len(found):
        lines += ["", "Say “more” for the rest."]
    return Reply("\n".join(lines), asks=[f"Quiz me on {_title(note)}"])


def deck_text(note: dict, deck: list[study.Card]) -> str:
    return deck_text_titled(_title(note), deck)


def deck_text_titled(title: str, deck: list[study.Card]) -> str:
    out = [f"# Flashcards: {title}", ""]
    for card in deck:
        out += [f"**Q:** {card.q}", f"**A:** {card.a}", ""]
    return "\n".join(out).rstrip() + "\n"


def _pooled_deck(topic: str, group: list[dict]) -> list[study.Card]:
    """A few of the best cards from each note of a category, interleaved so
    no one note fills the deck."""
    decks = []
    for note in group:
        cards = [c for c in study.cards(str(note.get("content") or "")) if c.kind != "pair"] or study.cards(str(note.get("content") or ""))
        decks.append(study.ordered(cards, _title(note), limit=6))
    out: list[study.Card] = []
    for row in zip_longest(*decks):
        out += [c for c in row if c is not None]
    return out[:24]


def _category_flashcards(ctx: Ctx, topic: str, group: list[dict]) -> Reply | None:
    deck = _pooled_deck(topic, group)
    if len(deck) < 2:
        return None
    name = str(group[0].get("category") or topic)
    label = "Save these as a note"
    shown = deck[:CARDS_SHOWN]
    sources = "; ".join(_link(n) for n in group[:4])
    lines = [pick(ctx.seed, "catflash", (
        f"I made {len(deck)} flashcards from your {name} notes ({len(group)} of them). The first {len(shown)}:",
        f"{len(deck)} cards across {len(group)} {name} notes, each in its note's own words. A few to start:",
        f"Here are {len(deck)} flashcards from {name}, a few from every note. The first {len(shown)}:",
    )), ""]
    for card in shown:
        lines += [f"**Q:** {card.q}", f"**A:** {card.a}", ""]
    lines += [f"From: {sources}.", "", label]
    return Reply("\n".join(lines), offer={"kind": "note", "label": label, "text": deck_text_titled(name, deck), "items": []},
                 asks=[f"Quiz me on {_title(group[0])}"])


def _flashcards(ctx: Ctx, topic: str) -> Reply:
    group = category_notes(topic, ctx)
    if len(group) >= 2:
        pooled = _category_flashcards(ctx, topic, group)
        if pooled:
            return pooled
    notes, reply = _target(ctx, topic, "Make flashcards from", "make flashcards from", strict=False)
    if not notes:
        return reply or _which_note(ctx, "make flashcards from", "Make flashcards from")
    note = notes[0]
    deck = [c for c in study.cards(str(note.get("content") or "")) if c.kind != "pair"] or study.cards(str(note.get("content") or ""))
    if not deck:
        return Reply(f"{_link(note)} has no definitions, lists or bold terms I can turn into cards. "
                     "Add a few lines like “Term: what it means” and ask again.")
    deck = study.ordered(deck, _title(note), limit=24)
    label = "Save these as a note"
    shown = deck[:CARDS_SHOWN]
    lines = [pick(ctx.seed, "flashhead", (
        f"I made {len(deck)} flashcards from {_link(note)}. The first {len(shown)}:",
        f"{len(deck)} flashcards from {_link(note)}, straight from its own words. The first {len(shown)}:",
        f"Here are {len(deck)} cards from {_link(note)}. A few to start:",
    )), ""]
    for card in shown:
        lines += [f"**Q:** {card.q}", f"**A:** {card.a}", ""]
    lines += ["Save them as a note and I can quiz you from them any time.", "", label]
    return Reply("\n".join(lines), offer={"kind": "note", "label": label, "text": deck_text(note, deck), "items": []},
                 asks=[f"Quiz me on {_title(note)}"])


# --- the quiz ----------------------------------------------------------------------

_HEADER = re.compile(r"\*\*Quiz on (?P<topic>.+?)\*\* · question (?P<n>\d+) of (?P<total>\d+)(?: · score (?P<score>\d+) of (?P<done>\d+))?(?: · round (?P<round>\d+))?")


def _deck(topic: str, ctx: Ctx, total: int, rounds: int = 1) -> tuple[dict | None, list[study.Card]]:
    notes = topic_notes(topic, ctx, limit=1)
    if not notes:
        return None, []
    deck = study.cards(str(notes[0].get("content") or ""))
    return notes[0], study.ordered(deck, topic if rounds <= 1 else f"{topic}#{rounds}", limit=total)


def _header(topic: str, n: int, total: int, score: int, done: int, rounds: int) -> str:
    return f"**Quiz on {topic}** · question {n} of {total}" + (f" · score {score} of {done}" if done else "") + (f" · round {rounds}" if rounds > 1 else "")


def _quiz_note(ctx: Ctx, topic: str) -> tuple[dict | None, Reply | None]:
    notes = topic_notes(topic, ctx, limit=1)
    cleaned = _FILLER.sub(" ", topic or "").strip(" ,")
    if not notes and (not cleaned or _THIS.match(cleaned)):
        notes = _newest_with_cards(ctx, count=1, need=3)
        if not notes:
            return None, _which_note(ctx, "quiz you on", "Quiz me on")
    if not notes:
        return None, _nothing_named(ctx, topic, "Quiz me on")
    return notes[0], None


def _start_quiz(ctx: Ctx, topic: str, count: int | None) -> Reply:
    note, reply = _quiz_note(ctx, topic)
    if note is None:
        return reply
    name = _title(note)
    total = max(1, min(MAX_QUIZ, count or QUIZ_LENGTH))
    rounds = 1 + sum(1 for t in ctx.history if f"**Quiz on {name}**" in str(t.get("answer") or "") and "question 1 of" in str(t.get("answer") or ""))
    deck = study.ordered(study.cards(str(note.get("content") or "")), name if rounds <= 1 else f"{name}#{rounds}", limit=total)
    if len(deck) < 2:
        return Reply(f"{_link(note)} has too little I can ask about: I look for definitions (“X is Y”, “Term: meaning”), bold terms, lists under headings and Q: / A: pairs. "
                     "Add a few and ask again.")
    opener = pick(ctx.seed, f"quizopen{rounds}", (
        f"Quiz on {_link(note)}, {len(deck)} questions, from your own notes.",
        f"Let's go: {len(deck)} questions from {_link(note)}.",
        f"{len(deck)} questions on {_link(note)}. Answer in your own words.",
        f"Ready? {len(deck)} questions drawn from {_link(note)}.",
        f"Here come {len(deck)} questions on {_link(note)}, all from what you wrote.",
        f"Round {rounds} on {_link(note)}: {len(deck)} questions." if rounds > 1 else f"First round on {_link(note)}: {len(deck)} questions.",
    ))
    tip = "_Answer in your own words. Say “hint”, “skip” or “stop” at any time._"
    return Reply(f"{opener}\n\n{_header(name, 1, len(deck), 0, 0, rounds)}\n\n{deck[0].q}\n\n{tip}", asks=QUIZ_CHIPS)


_STOP = re.compile(r"^(?:stop|quit|end|exit|finish|enough|done|cancel|that'?s enough|i'?m done|no more|stop the quiz|end quiz|end the quiz|that will do)\W*$", re.I)
_SKIP = re.compile(r"^(?:skip|pass|next|i (?:don'?t|do not) know|idk|no idea|dunno|don'?t know|not sure|give up|show me|show answer|answer|what is it|what'?s the answer|tell me|reveal)\W*$", re.I)
_HINT = re.compile(r"^(?:hint|a hint|clue|a clue|give me a hint|help|help me|i need a hint|any hints?)\W*$", re.I)
_AGAIN = re.compile(r"^(?:repeat|again|say that again|what was the question|what was that|repeat the question|pardon)\W*$", re.I)


def _last_header(answer: str) -> re.Match | None:
    found = None
    for found in _HEADER.finditer(answer or ""):
        pass
    return found


def _asked_question(answer: str, header: re.Match) -> str:
    rest = answer[header.end():].lstrip("\n")
    return rest.split("\n\n", 1)[0].strip()


def _quiz_place(ctx: Ctx, header: re.Match) -> tuple | None:
    """(topic, n, total, score, done, rounds, note, deck, card) for the question the last answer asked, or None when the notes changed."""
    topic, n, total = header.group("topic"), int(header.group("n")), int(header.group("total"))
    score, done, rounds = int(header.group("score") or 0), int(header.group("done") or 0), int(header.group("round") or 1)
    note, deck = _deck(topic, ctx, total, rounds)
    asked = _asked_question(ctx.last_answer, header)
    index = next((i for i, c in enumerate(deck) if c.q == asked), None)
    if note is None or index is None:
        return None
    return topic, n, total, score, done, rounds, note, deck, deck[index]


def _quiz_command(ctx: Ctx, reply: str, place: tuple) -> Reply | None:
    topic, n, total, score, done, rounds, note, deck, card = place
    head = _header(topic, n, total, score, done, rounds)
    if _AGAIN.match(reply):
        return Reply(f"{head}\n\n{card.q}")
    if _HINT.match(reply):
        return Reply(f"Hint: {study.hint(card)}\n\n{head}\n\n{card.q}")
    if _STOP.match(reply):
        return _finish(ctx, topic, note, deck, score, done, stopped=True)
    return None


_REQUESTISH = re.compile(
    r"^(?:ok(?:ay)?[, ]+|so[, ]+|and[, ]+|please[, ]+|thanks?(?: you)?[, ]+)*(?:what|how|why|when|where|who|which|tell|show|open|list|find|search|remind|add|create|make|write|give|can|could|would|will|please|"
    r"thanks?|thank|hello|hi|hey|summari[sz]e|plan|quiz|flash|outline|compare|delete|set|turn|start|go|do you|are you|is there|i want|i need|i'd like|let'?s)\b", re.I)


def _off_topic(reply: str, card: study.Card) -> bool:
    """A message that is a request or a greeting and shares no word with the
    question or its answer: not an attempt, so it ends the quiz."""
    if not _REQUESTISH.match(reply) or _SKIP.match(reply) or _HINT.match(reply) or _STOP.match(reply) or _AGAIN.match(reply):
        return False
    said = reply.split(None, 1)[1] if " " in reply else ""  # the opening verb ("list") is the request, not the answer
    return not set(study.content_stems(said)) & set(study.content_stems(f"{card.q} {card.a}"))


QUIZ_CHIPS = ["Hint", "Skip", "Stop the quiz"]


def _continue_quiz(ctx: Ctx) -> Reply | None:
    header = _last_header(ctx.last_answer)
    reply = " ".join((ctx.asked or ctx.question).split())
    if header is None or not ctx.history or not reply:
        return None
    if reply.endswith("?") and len(reply.split()) >= 4 and not _AGAIN.match(reply):
        return None
    place = _quiz_place(ctx, header)
    if place is not None and _off_topic(reply, place[-1]):
        return None  # not an answer: the quiz ends and the older readers take the message
    if place is None:
        return Reply(pick(ctx.seed, "changed", (
            "Your notes changed since that question, so I have lost my place. Ask me to quiz you again and I will start fresh.",
            "I can no longer find that question in your notes, they have changed. Say “quiz me” to start over.",
        )))
    command = _quiz_command(ctx, reply, place)
    if command:
        return command
    topic, n, total, score, done, rounds, note, deck, card = place
    if _SKIP.match(reply):
        verdict, feedback = "skip", pick(ctx.seed, f"skip{n}", ("Skipped. The answer: {a}", "No problem. It is: {a}", "The answer was: {a}")).format(a=card.a)
    else:
        verdict = study.grade(reply, card)
        feedback = pick(ctx.seed, f"{verdict}{n}", _FEEDBACK[verdict]).format(a=card.a)
    score += 1 if verdict in ("right", "close") else 0
    done += 1
    if n >= len(deck):
        return _finish(ctx, topic, note, deck, score, done, lead=feedback)
    return Reply(f"{feedback}\n\n{_header(topic, n + 1, total, score, done, rounds)}\n\n{deck[n].q}", asks=QUIZ_CHIPS)


_FEEDBACK = {
    "right": ("Correct.", "Yes, that's it.", "Right.", "That's right.", "Good, that matches your note."),
    "close": ("Close enough, that counts. Your note says: {a}", "Nearly. Your note has it as: {a} I'll count it.", "Part of it, and I'll count it. The note says: {a}"),
    "wrong": ("Not quite. Your note says: {a}", "Not this time. The note says: {a}", "Missed that one. It is: {a}"),
}


def _finish(ctx: Ctx, topic: str, note: dict, deck: list[study.Card], score: int, done: int, *, lead: str = "", stopped: bool = False) -> Reply:
    pct = round(100 * score / done) if done else 0
    verdict = ("Strong." if pct >= 85 else "Solid." if pct >= 60 else "Worth another go.") if done else ""
    lines = [lead, ""] if lead else []
    if stopped and not done:
        lines.append("Stopped before any answer, so no score.")
    else:
        lines.append(f"Quiz finished on {_link(note)}: you got {score} of {done} ({pct} percent). {verdict}".strip())
    return Reply("\n".join(lines), asks=[f"Quiz me on {topic}", f"Make flashcards from {topic}"])


_OPEN = re.compile(r"^(?:ok(?:ay)?[, ]+|please[, ]+|can you |could you )*(?:open|show me|show|go to|take me to|pull up|bring up|jump to|find and open)\s+(?:my |the |all my |all the )?(?P<t>.+?)\W*$", re.I)
_OPEN_NOT = re.compile(r"^(?:a new|new|a|an|settings?|chat|the chat|help|guide|the guide|tab|statistics|calendar|timeline|graph|reminders?|tasks?|whiteboard|board|map|the app|search|library|inbox|today)\b", re.I)


def open_named(ctx: Ctx) -> Reply | None:
    """Ask cannot open things itself, but it can point: "open my lecture
    notes" is the links to the notes that name it."""
    found = _OPEN.match(" ".join((ctx.asked or ctx.question or "").split()))
    if not ctx.ask or not found:
        return None
    topic = found.group("t")
    if _OPEN_NOT.match(topic) or re.match(r"^(?:it|that|this)\b", topic, re.I):
        return None
    notes = topic_notes(topic, ctx, limit=5)
    if not notes:
        return None
    if len(notes) == 1:
        return Reply(pick(ctx.seed, "openone", ("Here it is:", "Open it from here:", "This one:")) + f" {_link(notes[0])}")
    return Reply(f"{len(notes)} notes match. Pick one:\n\n" + "\n".join(f"- {_link(n)}" for n in notes))
