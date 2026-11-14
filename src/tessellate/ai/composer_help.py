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

from tessellate.ai import composer_property, grounding, utilities
from tessellate.ai.composer_ask import _stem, _words
from tessellate.ai.composer_body import length_wish
from tessellate.ai.composer_dialogue import _MORE
from tessellate.ai.composer_phrases import PHRASES
from tessellate.ai.composer_quote import _pick
from tessellate.ai.composer_read import NoteView
from tessellate.search import query as query_understanding
from tessellate.core.lazyre import lazy_compile


#: A message this short that names one of the app's own tools ("timer",
#: "countdown", "pomodoro") is a request for the tool as much as a search.
_FEATURE_WORDS = 3


#: Words that make a request polite or pointed without naming anything: "undo
#: the last change" asks for Undo as much as "undo" does (Z64).
_FEATURE_FILLER = frozenset({"the", "a", "an", "my", "that", "this", "it", "last", "latest", "please"})


#: "and last week?" carries on the question before; it is not asking for the Timeline tab. "who wrote it" is a
#: question about a note, not the name of a tool (R9-9).
_ABOUT_AN_ANSWER = lazy_compile(r"^\s*(?:is|are|was|what|what's|whats|who|when|where|why|how|do|does|did|can|the)\b|\b(?:it|its|one|they|them)\b", re.I)
_CARRIES_ON = lazy_compile(r"^\s*(?:and|but|or|also|then|who)\b", re.I)


def _may_name_a_tool(question: str, words: list[str]) -> bool:
    """Short enough, and not a follow-on or a length control ("tell me more",
    "shorter", "and last week?"), which is about the answer before, never a
    tool: the Follow-up trail's help line says "tell me more" in its own words."""
    return bool(words) and len(words) <= _FEATURE_WORDS and not (
        _MORE.match(question) or length_wish(question) or _CARRIES_ON.match(question)
    )


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


def _undo_lead(words: list[str]) -> str:
    """Typed "undo" or "redo" after a change asks for the thing itself, so the
    keys come first, not a note that the word is not in the notes (round 2 E7)."""
    said = [w for w in words if w not in _FEATURE_FILLER and w not in ("change", "changes", "action")]
    if said == ["undo"]:
        return "Press Undo in the status bar, or Ctrl+Z when you are not typing in a box, to take back your last change. "
    if said == ["redo"]:
        return "Press Redo in the status bar, or Ctrl+Shift+Z or Ctrl+Y when you are not typing in a box, to bring back what you undid. "
    return ""


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
    lead = _undo_lead(words) or f"“{said[:1].upper()}{said[1:]}” is one of the app's own tools, not something in your notes. "
    return _result([("template", lead), ("help", _short_line(best[0]), best[1])], "help")


#: The longest help sentence an offer repeats under a note answer.
_OFFER_WORDS = 20


def _short_line(line: str) -> str:
    """A help line as one short sentence: the line itself when it is a line, else
    where to read the steps (D21: "what is my name" answered a Settings paragraph)."""
    return line if len(line.split()) <= _OFFER_WORDS else "Open its Help topic for the steps."


def offered(result: dict | None, question: str) -> dict | None:
    """A note does mention the word a short message names as a feature
    ("timer" with a Kitchen timer note): the note answers, and the tool is
    offered after it from the same help line (INBOX 1334, the open half).
    The digest and `compose` both answer a chat turn, so both pass through."""
    if not result or result.get("shape") in ("help", None) or result.get("missed") or not result.get("parts"):
        return result
    #: A question about an answer ("is it this week", "the second one", "what's in it") names no tool.
    if _ABOUT_AN_ANSWER.search(question or ""):
        return result
    best = _feature_help(question, [])
    if best is None:
        return result
    #: A topic's whole step sentence is a paragraph under a note answer ("phone" got 600 characters
    #: on opening the notebook over the network): past a line, the offer points to the topic (R3-7).
    line = _short_line(best[0])
    more = [("template", PHRASES["feature_offer"]), ("help", line, best[1])]
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
        frozenset({"delete", "remove", "bin", "trash", "clear", "erase", "discard", "throw", "toss"}),
        frozenset({"move", "relocate", "shift", "transfer", "file", "refile"}),
        frozenset({"change", "switch", "pick", "choose", "edit", "rename", "retitle"}),
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
    if _RETITLING.search(question):
        doing |= {"rename", "retitle"}
        wanted = (wanted - {"title", "name", "titles", "names"}) | {"rename"}
    if _RESTORING.search(question) and not re.search(r"\bback ?ups?\b", question, re.I):
        doing |= {"delete", "bin"}
    return {"wanted": wanted, "named": named, "pairs": _help_pairs(question), "doing": doing, "asked_exception": bool(_EXCEPTION_ASKED.search(question)), "listed": bool(_EXCEPTION_LISTED.search(question)), "emptying": bool(_EMPTYING.search(question)), "direct": _direct_object(question, verb)}


#: Where the thing a doing is done to ends: "remove a tag from a note" is about
#: the tag, and the note only says where.
_PLACE_WORD = lazy_compile(r"\b(?:from|in|on|to|into|onto|of|out|off|for|at|about|by|with|between)\b")


def _direct_object(question: str, verb: str) -> set[str]:
    """The content words between the doing and the first place word, or empty
    when the doing is not found (the whole ask then counts)."""
    lowered = (question or "").lower()
    at = lowered.find(verb) if verb else -1
    if at < 0:
        return set()
    return set(_words(_PLACE_WORD.split(lowered[at + len(verb):], maxsplit=1)[0]))


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


#: What a topic's first sentence earns over a later one that shares a word more: a topic opens on its point (L-chat-41).
FIRST_LINE = 1.0
_HOW_TOP = lazy_compile(r"^\s*(?:how (?:do|can|should|would) (?:i|you|we)|how to|where (?:do|can|is|are)|can i|is there)\b", re.I)


def _opens_the_how_to(line: str, lines: list[str], first: bool) -> bool:
    """The topic's opening line leads a bare how-to only when it is a line: a 61-word inventory of the Dashboard is not the step (L229)."""
    return first and lines.index(line) == 0 and len(line.split()) <= _HELP_LEAD_WORDS


def _help_best(lines: list[str], ask: dict, doing: float = 0.0, first: bool = False) -> str:
    """The line that says the most; a later one must say more to lead (the
    topic opens on its point: "Link one note to another by typing [[" over
    the Suggestions sheet, which says "link" and "notes" too: the Guide's
    gold, 2026-10-11). `doing` is the extra a line earns for saying the verb
    asked, which picks among the clauses of one sentence. `first` is a how-to that names no act (the act's own sentence
    leads those): the topic's opening line then earns `FIRST_LINE`."""
    def says(line: str) -> bool:
        return bool(ask["doing"]) and any(_stem(d) in _help_have(line, set()) for d in ask["doing"])

    #: The opening line keeps its lead unless a later one says the verb asked and it does not ("add a reminder": the second line says "add").
    opens = not says(lines[0]) and any(says(line) for line in lines[1:])

    def score(line: str) -> float:
        verb = says(line)
        #: A listing of what cannot be done leads for the ask that wants it.
        listed = 3.0 if ask.get("listed") and _NO_UNDO.search(line) else 0.0
        return _help_shared(line, ask) + (doing if verb else 0.0) + listed - 0.05 * lines.index(line) + (FIRST_LINE if _opens_the_how_to(line, lines, first and not opens) else 0.0)

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
    "delete": ("delete", "remove", "trash", "bin", "erase", "discard", "throw", "toss"),
    "restore": ("restore", "recover", "undelete"),
    "move": ("move", "drag", "reorder", "relocate", "shift"),
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


#: "change a note's title": a rename said without its verb.
_RETITLING = lazy_compile(r"\b(?:change|edit|set|update|fix)\b.{0,20}\b(?:title|name)s?\b", re.I)

#: "get a note back", "bring it back": a restore said without its verb.
_BACK_PHRASE = lazy_compile(
    r"\b(?:get|bring|put|have|take)\b(?:\s+\w+){0,4}\s+back\b|\b(?:out of|from) (?:the |my )?(?:bin|trash|recycle bin)\b", re.I
)

#: Asked as a restore of something deleted (not of a backup): the bin sentence
#: is the one whose subject says it ("A deleted note ... goes to the bin").
_RESTORING = lazy_compile(r"\b(?:restor\w*|recover\w*|undelet\w*|retriev\w*)\b|" + _BACK_PHRASE.pattern, re.I)


def _help_act(question: str) -> str:
    """The act a how-to names (the first one typed), or ""."""
    if _BACK_PHRASE.search(question or ""):
        return "restore"
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
    #: "Say it in Chat" is the generated pointer to an act, not the Guide's own
    #: step: a topic that says the act itself leads over it ("how do I delete a
    #: note" is the bin sentence), and it answers when nothing else does.
    pointer = 4.0 if str(topic.get("id", "")).startswith("act-") else 0.0
    return _help_shared(line, ask) + named + early - long - pointer - 0.15 * place[0] - 0.05 * place[1] + _subject_fit(line, ask)


#: A sentence that lists what the thing cannot do, not how to do it.
_EXCEPTION = lazy_compile(r"\b(?:no undo|except|cannot|can't|never|nothing)\b", re.I)

#: The ask is about the exception itself ("why is there no undo", "permanently").
_EXCEPTION_ASKED = lazy_compile(r"\b(?:no undo|except\w*|cannot|can't|never|for good|permanent\w*|empty|why)\b", re.I)

_NO_UNDO = lazy_compile(r"\bno undo\b", re.I)

#: The sentence about emptying the bin, and the ask that wants it: it answers
#: "how do I empty the bin" and nothing about deleting one thing.
_EMPTYING_LINE = lazy_compile(r"\bempty the bin\b", re.I)
_EMPTYING = lazy_compile(r"\b(?:empt\w*|clear\w*|purge\w*|wipe\w*)\b", re.I)

#: The ask is for the list itself, not a word that merely touches it: "what
#: can't I undo", "what cannot be undone", "which things have no undo". The
#: list leads for these (a negated doing is a class, not a question).
_EXCEPTION_LISTED = lazy_compile(
    r"\b(?:can'?t|cannot|can not|couldn'?t|won'?t|never|no|not)\b.{0,15}\b(?:undo|undone|recover\w*|restor\w*|reversed?)\b|\bno undo\b|\birreversible\b", re.I
)

#: Where a sentence's subject ends: its first verb or clause break. A comma
#: inside a list is not one: "A deleted note, board, document, reminder goes
#: to the bin" has a subject of four things, and the ask names any of them.
_SUBJECT_END = lazy_compile(r"\s(?:goes|go|is|are|has|have|keeps|makes|lets|shows|says|covers|opens|adds|removes|moves|finds|takes|asks|puts|sets|clears|deletes|gives|needs|offers|lists|reads|saves)\b|[,;:]")
#: A comma inside a list of single words ("note, board, document or reminder").
_LIST_COMMA = lazy_compile(r"(?<=\w), (?=\w+(?:,| or | and ))")


def _subject_fit(line: str, ask: dict) -> float:
    """INBOX 1653: what a sentence is about outweighs a word it shares. A
    sentence whose subject carries the asked doing ("A deleted note ... goes to
    the bin") and the asked object leads; a list of exceptions ("Four things
    have no Undo") ranks below it unless the ask is about the exception."""
    head = _SUBJECT_END.split(_LIST_COMMA.sub(" ", line), maxsplit=1)[0]
    words = re.findall(r"[a-z]+", head.lower())
    #: delete, deleted and deleting are one doing here (`_help_one`).
    said = any(_help_one(d, w) for d in ask["doing"] for w in words)
    subject = {_stem(w) for w in words}
    objects = {_stem(w) for w in (ask["direct"] or ask["wanted"]) if w not in ask["doing"]}
    bonus = 2.5 if said and objects & subject else 0.0
    listing = _EXCEPTION.search(line)
    emptying = _EMPTYING_LINE.search(line) and not ask["emptying"]
    return bonus - (1.5 if listing and not ask["asked_exception"] else 0.0) - (3.0 if emptying else 0.0) + (3.0 if _NO_UNDO.search(line) and ask["listed"] else 0.0)


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


def _named_act(question: str) -> bool:
    """Whether a phrasing names an act the aliases know ("get rid of a note" is a delete): its own sentence leads."""
    from tessellate.ai import guide_aliases

    return any(name in guide_aliases.HARD for name, _ids in guide_aliases.intents(question))


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
    lead = _help_best(sentences, ask, first=bool(_HOW_TOP.match(question or "")) and not act and not _RETITLING.search(question or "") and not _named_act(question))
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


_JA_STOP = lazy_compile(r"([。！？])\.")


_UNTICK = lazy_compile(r"^(?:please |can you |could you )?(?:un-?tick|un-?check|un-?mark|un-?cross)\b", re.I)


def cannot_answer(question: str, notes: list[dict]) -> dict | None:
    """An ask no note settles, said in one line instead of a search for its words: "untick it"
    with no item the act reader could name (say which; audit 1030 Z37, "untick bread" itself is
    the act, `task_acts.read_uncomplete`), and "what is the table number" when no note gives one
    (never a note that only mentions the dinner or the booking; R3-2 residue)."""
    text = " ".join((question or "").split())
    line = ("Say which item to untick, like: untick buy milk. Press Undo on the card right after a tick to take it back."
            if _UNTICK.match(text) else composer_property.none_given(text, notes))
    return {**_result([("template", line)], "none"), "answered": True} if line else None


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
