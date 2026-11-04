"""Help with the app itself: a question about one of its own tools answered
from the help sentences, and a utility (a sum, a date) worked out.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer.help_line` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import functools
import re
from datetime import datetime

from tessellate.ai import grounding, utilities
from tessellate.ai.composer_ask import _stem, _words
from tessellate.ai.composer_body import length_wish
from tessellate.ai.composer_dialogue import _MORE
from tessellate.ai.composer_phrases import PHRASES
from tessellate.ai.composer_quote import _pick
from tessellate.ai.composer_read import NoteView
from tessellate.search import query as query_understanding


#: A message this short that names one of the app's own tools ("timer",
#: "countdown", "pomodoro") is a request for the tool as much as a search.
_FEATURE_WORDS = 3


#: Words that make a request polite or pointed without naming anything: "undo
#: the last change" asks for Undo as much as "undo" does (Z64).
_FEATURE_FILLER = frozenset({"the", "a", "an", "my", "that", "this", "it", "last", "latest", "please"})


def _may_name_a_tool(question: str, words: list[str]) -> bool:
    """Short enough, and not a follow-on or a length control ("tell me more",
    "shorter"), which is about the answer before, never a tool: the Follow-up
    trail's help line says "tell me more" in its own words."""
    return bool(words) and len(words) <= _FEATURE_WORDS and not (_MORE.match(question) or length_wish(question))


def _feature_help(question: str, absent: list[str]) -> tuple[str, str] | None:
    """The help line of the app feature a two- or three-word message names
    (the words are the line's own), or None."""
    words = [w for w in re.findall(r"[a-z]+", (question or "").lower()) if w not in _FEATURE_FILLER]
    if not _may_name_a_tool(question or "", words):
        return None
    from tessellate.ai import help_chat

    best = help_line(question, help_chat.topics_for(question or ""))
    if best is None:
        return None
    #: The thing asked for is named in the help line itself: "spare key
    #: where" is a lost key, not the keyboard shortcuts (test_composer_eval_741).
    #: Outside the line's own examples: "who is Sam" is a person, not the
    #: Names tool whose help line quotes "Sam" and "Sam Lee" as its example;
    #: "what about running?" is a follow-up, not the Follow-up trail topic
    #: that gives it in brackets as one.
    line = re.sub(r"\"[^\"]*\"|“[^”]*”|‘[^’]*’|\([^)]*\)", " ", best[0])
    wanted = absent or [w for w in words if len(w) >= 4]
    if not wanted or not all(re.search(rf"\b{re.escape(w)}", line, re.I) for w in wanted):
        return None
    return best


def _feature_instead(question: str, absent: list[str]) -> dict | None:
    """Nothing in the notes, and a two- or three-word message that names an
    app feature (INBOX 1334, "timer\\" got "Which note might it be in?"):
    say the notes are silent on it in one clause, then how to use the feature
    from the Guide's topic. None for anything longer or no topic."""
    best = _feature_help(question, absent)
    if best is None:
        return None
    words = re.findall(r"[a-z]+", (question or "").lower())
    said = absent[0] if absent else " ".join(words)
    #: The feature first: "Nothing in your notes mentions timer" was a
    #: not-found answer to a request for the timer (INBOX 1357, class B).
    lead = f"“{said[:1].upper()}{said[1:]}” is one of the app's own tools, not something in your notes. "
    return _result([("template", lead), ("help", best[0], best[1])], "help")


def offered(result: dict | None, question: str) -> dict | None:
    """A note does mention the word a short message names as a feature
    ("timer" with a Kitchen timer note): the note answers, and the tool is
    offered after it from the same help line (INBOX 1334, the open half).
    The digest and `compose` both answer a chat turn, so both pass through."""
    if not result or result.get("shape") in ("help", None) or result.get("missed") or not result.get("parts"):
        return result
    best = _feature_help(question, [])
    if best is None:
        return result
    more = [("template", PHRASES["feature_offer"]), ("help", best[0], best[1])]
    return {**result, "parts": [*result["parts"], *more], "text": result["text"] + "".join(part[1] for part in more)}


def _help_answer(question: str) -> dict | None:
    """A how-to answered by the step sentence of the Help topic it names
    (decision 36's help register): the sentence of the best topic that
    shares the most of the question's words, then where to read the rest.
    None when no topic matches."""
    from tessellate.ai import help_chat

    from tessellate.ai import intent

    question = intent.request_core(question or "")
    best = help_line(question, help_chat.topics_for(question))
    if best is None:
        return None
    #: The topic's sentence is the protected span; the pointer after it varies
    #: by chat and turn like any opener (decision 51), so "Ask again" in help
    #: does not repeat itself word for word.
    more = _pick(question, "help_more", [PHRASES[k] for k in ("help_more", *(f"help_more_{n}" for n in range(2, 11)))])
    parts = [("help", best[0], best[1]), ("template", more)]
    return _result(parts, "help")


#: Verbs of one doing, for the help line: a sentence saying "add" answers
#: "how do I make" half as well as one saying "make".
_HELP_DOING: dict[str, frozenset[str]] = {
    word: group - {word}
    for group in (
        frozenset({"make", "create", "add", "new", "set", "start", "type"}),
        frozenset({"delete", "remove", "bin", "trash", "clear"}),
        frozenset({"change", "switch", "pick", "choose", "edit"}),
        frozenset({"find", "search", "look", "open"}),
        frozenset({"stop", "disable", "pause", "off", "hide"}),
        frozenset({"see", "view", "show", "list", "read"}),
    )
    for word in group
}


#: Words that count a quarter: how many, not what ("two notes", "lots").
_HELP_WEAK = frozenset("one two three four five lots many several all every".split())


def _help_verb(question: str) -> str:
    """The doing a how-to asks about, its first word after the asking frame
    ("export" in "how do I export my notes"), or ""."""
    from tessellate.ai import help_chat

    frame = help_chat._HOW_FRAME.match(question or "")
    rest = _words(question[frame.end():]) if frame else []
    return rest[0] if rest else ""


def _help_pairs(question: str) -> set[str]:
    """Adjacent content words of a question, as typed ("back up", "hide
    unlinked"), the asking and counting words left out."""
    typed = re.findall(r"[a-z0-9]+", (question or "").lower())
    content = [bool(_words(w)) and w not in _HELP_WEAK for w in typed]
    return {f"{typed[i]} {typed[i + 1]}" for i in range(len(typed) - 1) if content[i] and content[i + 1]}


def _help_ask(question: str, topic: dict) -> dict:
    """What a question asks of one topic, for scoring its sentences."""
    #: Every word of the question counts here, "note" included: the asking
    #: words that are noise in a notebook ("note") name the control in Help.
    wanted = set(_words(question))
    #: The topic's own name is what every one of its sentences is about, so it
    #: counts half: the verb asked ("make") is what picks the sentence. Unless
    #: the name is the verb asked: "how do I export my notes" in import-export
    #: led with Tidy up duplicates, since "notes" outweighed a halved "export".
    verb = _help_verb(question)
    named = set(_words(str(topic.get("id", "")).replace("-", " "))) - {verb}
    doing = {verb, *_HELP_DOING.get(verb, ())} if verb else set()
    return {"wanted": wanted, "named": named, "pairs": _help_pairs(question), "doing": doing, "asked_exception": bool(_EXCEPTION_ASKED.search(question))}


def _help_have(line: str, doing: set[str]) -> set[str]:
    """The stems a sentence says. The doing asked in a past form describes, it
    does not instruct: "how do I change the widgets" led with the Dashboard's
    inventory sentence, on "what changed" and "edited" (the owner,
    2026-10-27), over the one that says how ("Edit layout and Widgets")."""
    return {_stem(w) for w in query_understanding.search_terms(line) if not (w.endswith("ed") and any(d.startswith(_stem(w)) for d in doing))}


def _help_one(w: str, h: str) -> bool:
    """A word and its longer form ("remind", "reminder") are one word here."""
    return h == w or (min(len(h), len(w)) >= 5 and (h.startswith(w) or w.startswith(h)))


def _help_shared(line: str, ask: dict) -> float:
    """How much of the question a sentence says: a word each, a weak or topic
    word less, a verb of the same doing ("make" for "set") half a word (INBOX
    787: "how do I make a reminder" led with how the tab is laid out), two
    content words side by side ("back up", "hide unlinked": the control's
    name) half a word more."""
    wanted, named = ask["wanted"], ask["named"]
    have = _help_have(line, ask["doing"])
    hits = sum(0.25 if w in _HELP_WEAK else 0.5 if w in named else 1 for w in wanted if any(_help_one(w, h) for h in have))
    kin = sum(1 for w in wanted if not any(_help_one(w, h) for h in have) and any(_help_one(g, h) for g in _HELP_DOING.get(w, ()) for h in have))
    said = " " + " ".join(re.findall(r"[a-z0-9]+", line.lower())) + " "
    return hits + 0.5 * kin + 0.5 * sum(1 for p in ask["pairs"] if f" {p} " in said)


def _help_best(lines: list[str], ask: dict, doing: float = 0.0) -> str:
    """The line that says the most; a later one must say more to lead (the
    topic opens on its point: "Link one note to another by typing [[" over
    the Suggestions sheet, which says "link" and "notes" too: the Guide's
    gold, 2026-10-11). `doing` is the extra a line earns for saying the verb
    asked, which picks among the clauses of one sentence."""
    def score(line: str) -> float:
        verb = bool(ask["doing"]) and any(_stem(d) in _help_have(line, set()) for d in ask["doing"])
        return _help_shared(line, ask) + (doing if verb else 0.0) - 0.05 * lines.index(line)

    return max(lines, key=lambda line: (score(line), -lines.index(line)))


#: The acts a how-to can name, and the words that say each in a help sentence
#: (the coordinator, 2026-10-31: "how do I export documents?" led with the
#: editor's four views, a sentence that never says export). A question that
#: names an act is answered by the sentence that names it, whichever matched
#: topic holds it.
_HELP_ACTS: dict[str, tuple[str, ...]] = {
    "export": ("export", "download"),
    "import": ("import", "bring"),
    "print": ("print", "pdf"),
    "share": ("share", "publish", "send"),
    "delete": ("delete", "remove", "trash", "bin"),
    "restore": ("restore", "recover", "undelete"),
    "move": ("move", "drag", "reorder"),
    "rename": ("rename", "retitle"),
    "attach": ("attach", "upload"),
    "pin": ("pin", "unpin", "star", "favourite", "favorite"),
}


@functools.lru_cache(maxsize=1)
def _help_act_stems() -> dict[str, frozenset[str]]:
    """The acts' stems, built on first use: `_stem` reads the spelling pairs
    (about 0.4 s to build), which the cold import is budgeted not to pay
    (tests/test_engine_budgets.py)."""
    return {act: frozenset(_stem(w) for w in words) for act, words in _HELP_ACTS.items()}


def _help_act(question: str) -> str:
    """The act a how-to names (the first one typed), or ""."""
    for word in re.findall(r"[a-z]+", (question or "").lower()):
        stem = _stem(word)
        for act, stems in _help_act_stems().items():
            if stem in stems:
                return act
    return ""


def _act_score(line: str, at: int, ask: set, stems: set[str], topic: dict, place: tuple[int, int]) -> float:
    """How well `line` leads for an act named at word `at`: shared words with
    the question, an early act word (a sentence that opens on the act is about
    it; one that mentions it in passing is not), the topic named for the act
    ("import-export"), a wall of a sentence being a poor lead, and a little
    for coming first (`place` is the topic's and the line's order)."""
    named = 2.0 if stems & {_stem(w) for w in str(topic.get("id", "")).split("-")} else 0.0
    early = 1.5 if at < 5 else 0.75 if at < 12 else 0.0
    long = 1.0 if len(line.split()) > _HELP_LEAD_WORDS else 0.0
    return _help_shared(line, ask) + named + early - long - 0.15 * place[0] - 0.05 * place[1] + _subject_fit(line, ask)


#: A sentence that lists what the thing cannot do, not how to do it.
_EXCEPTION = re.compile(r"\b(?:no undo|except|cannot|can't|never|nothing)\b", re.I)

#: The ask is about the exception itself ("why is there no undo", "permanently").
_EXCEPTION_ASKED = re.compile(r"\b(?:no undo|except\w*|cannot|can't|never|for good|permanent\w*|empty|why)\b", re.I)

#: Where a sentence's subject ends: its first verb or clause break.
_SUBJECT_END = re.compile(r"\s(?:goes|go|is|are|has|have|keeps|makes|lets|shows|says|covers|opens)\b|[,;:]")


def _subject_fit(line: str, ask: dict) -> float:
    """INBOX 1653: what a sentence is about outweighs a word it shares. A
    sentence whose subject carries the asked doing ("A deleted note ... goes to
    the bin") and the asked object leads; a list of exceptions ("Four things
    have no Undo") ranks below it unless the ask is about the exception."""
    head = _SUBJECT_END.split(line, maxsplit=1)[0]
    words = re.findall(r"[a-z]+", head.lower())
    #: delete, deleted and deleting are one doing here (`_help_one`).
    said = any(_help_one(d, w) for d in ask["doing"] for w in words)
    subject = {_stem(w) for w in words}
    objects = {_stem(w) for w in ask["wanted"] if w not in ask["doing"]}
    bonus = 2.5 if said and objects & subject else 0.0
    return bonus - (1.5 if _EXCEPTION.search(line) and not ask["asked_exception"] else 0.0)


def _act_lead(lead: str, stems: set[str], question: str, topic_id: str) -> str:
    """A long act sentence cut to its clause that names the act."""
    if len(lead.split()) <= _HELP_LEAD_WORDS:
        return lead
    clauses = [c for c in _clauses(lead) if stems & {_stem(w) for w in re.findall(r"[a-z]+", c.lower())}]
    return max(clauses, key=lambda c: _help_shared(c, _help_ask(question, {"id": topic_id}))) if clauses else lead


def _act_sentence(question: str, topics: list[dict], act: str) -> tuple[str, str] | None:
    """The sentence naming `act` that says the most of the question, over every
    matched topic (the first earns a little for coming first), with its
    topic's id; None when no matched topic names the act."""
    from tessellate.ai import help_chat

    stems = _help_act_stems()[act]
    best: tuple[float, str, str] | None = None
    for order, topic in enumerate(topics):
        ask = _help_ask(question, topic)
        for index, line in enumerate(help_chat.help_sentences(str(topic.get("body") or ""))):
            words = [_stem(w) for w in re.findall(r"[a-z]+", line.lower())]
            at = next((i for i, w in enumerate(words) if w in stems), None)
            if at is None:
                continue
            score = _act_score(line, at, ask, stems, topic, (order, index))
            if best is None or score > best[0]:
                best = (score, line, str(topic.get("id", "")))
    return None if best is None else (_act_lead(best[1], stems, question, best[2]), best[2])


def help_line(question: str, topics: list[dict]) -> tuple[str, str] | None:
    """The one sentence of the best topic that answers a how-to (its step
    sentence sharing the most of the question's words) and the topic's id:
    Chat's help register and the Guide's first line (decision 59, step 4),
    so help and chat say it in one voice. None with no topic."""
    if not topics:
        return None
    act = _help_act(question)
    named = _act_sentence(question, topics, act) if act else None
    if named is not None:
        return named
    topic = topics[0]
    from tessellate.ai import help_chat

    sentences = help_chat.help_sentences(str(topic.get("body") or ""))
    if not sentences:
        return None
    ask = _help_ask(question, topic)
    lead = _help_best(sentences, ask)
    #: A lead is a line, not an inventory (INBOX 1406: "how do I see what
    #: changed" got a 134-word sentence): over the budget, its best clause.
    if len(lead.split()) > _HELP_LEAD_WORDS:
        clauses = _clauses(lead)
        if len(clauses) > 1:
            lead = _help_best(clauses, ask, doing=0.5)
    return lead, str(topic.get("id", ""))


#: The longest sentence the Guide and Chat lead with whole.
_HELP_LEAD_WORDS = 40


def _semicolon_parts(sentence: str) -> list[str]:
    """A sentence cut at its `;` outside brackets and quotes."""
    parts, depth, quote, start = [], 0, False, 0
    for i, ch in enumerate(sentence):
        depth = max(0, depth + (ch in "([") - (ch in ")]"))
        quote ^= ch in "\"“”"
        if ch == ";" and not depth and not quote:
            parts.append(sentence[start:i])
            start = i + 1
    return [*parts, sentence[start:]]


def _clauses(sentence: str) -> list[str]:
    """A sentence's `;` clauses outside brackets and quotes, each a sentence
    of its own (capital first, its stop kept): "(a busy week; Tidy lists
    them)" is one thought, not two. One too short to answer alone belongs to
    the clause before."""
    out: list[str] = []
    for part in (p.strip() for p in _semicolon_parts(sentence)):
        if len(part.split()) < 5 and out:
            out[-1] += "; " + part
        elif part:
            out.append(part)
    ended = [c if c.endswith((".", "!", "?", "。", "！", "？")) else c + "." for c in out]
    return [c[:1].upper() + c[1:] for c in ended]


_JA_STOP = re.compile(r"([。！？])\.")


def _result(parts: list[tuple], shape: str, rows: list[dict] | None = None, next_parts: list | None = None) -> dict:
    """A composed result from its parts: the text is their join."""
    rows = rows or []
    quotes = "\n\n".join(row["sentence"] for row in rows)
    next_parts = next_parts or []
    return {
        #: A full-width stop already ends a sentence: no ASCII one follows it (audit 1031 C38).
        "text": _JA_STOP.sub(r"\1", "".join(part[1] for part in parts)),
        "grounding": rows,
        "support": grounding.support(quotes, rows),
        "shape": shape,
        "parts": parts,
        "next": ["".join(part[1] for part in chip) for chip in next_parts],
        "next_parts": next_parts,
    }


def _utility(question: str, now: datetime | None, salt: str) -> dict | None:
    """A utility's answer (decision 41): computed sentences, or a fixed line
    for what the app cannot do (the weather, translating with no model)."""
    found = utilities.answer(question, now, salt)
    if not found:
        return None
    parts = [("template", PHRASES[text]) if kind == "phrase" else (kind, text) for kind, text in found]
    return _result(parts, "utility")


def _in_window(view: NoteView, window: tuple, *, mentions: bool = True) -> bool:
    """Written in the window, or (E6) saying the day: a note that reads "3
    November at 2pm" or "Friday deadlift" is on that day for a question about
    the day, whenever it was written. `mentions=False` is a question about
    writing ("what did I write on Friday"), which only creation answers."""
    if mentions and view.note.get("dated_in_window"):
        return True
    return view.written is not None and window[0] <= view.written <= window[1]
