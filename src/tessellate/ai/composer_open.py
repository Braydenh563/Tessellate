"""A question about the note that is open, answered from that note alone.

The 22-10 bug doc: "Ask tab replies are identical across notes, long, and list
dates and links instead of answering the question." A question with no subject
of its own ("What's left to do?", "When is the deadline?", "Who is involved?")
asked with a note open used to search the whole notebook, so every note gave
the same reply. Here the open note answers, in a sentence or two of its own
words, chosen for what was asked:

- `left`: the checklist items still open, else the sentences that say what to
  do ("Book the tram pass before we go.");
- `when`: the sentences that carry a date, not every date in the note;
- `who`: the people the note names;
- `point`: handled by the digest's "Summarise this" (`composer_digest._THIS`).

Every clause is the note's sentence, or a count or list of names read off it
(the composer's rule, `composer.py`); the connecting words are `PHRASES`,
several per kind, chosen by a hash of the question and the turn's salt.
"""

from __future__ import annotations

import hashlib
import re

from tessellate.ai import recognise

PHRASES: dict[str, str] = {
    "open_left_a1": "Still open here: ",
    "open_left_a2": "What is left in this note: ",
    "open_left_a3": "Two things to do next: ",
    "open_left_a4": "Next up, going by this note: ",
    "open_left_one": "One thing is left: ",
    "open_left_none": "Nothing in this note is marked as still to do.",
    "open_left_text": "This note does not keep a checklist, but it says: ",
    "open_done_a1": "Done so far: ",
    "open_done_a2": "Already ticked off: ",
    "open_done_none": "Nothing in this note is ticked off yet.",
    "open_done_no_list": "This note does not keep a checklist.",
    "open_when_a1": "The date this note gives: ",
    "open_when_a2": "On timing, this note says: ",
    "open_when_a3": "Here is what it says about when: ",
    "open_when_none": "This note does not give a date or a deadline.",
    "open_who_a1": "The people named here: ",
    "open_who_a2": "This note names: ",
    "open_who_a3": "Mentioned in this note: ",
    "open_who_none": "This note does not name anyone.",
    "open_who_end": ".",
    "open_and": " and ",
    "open_comma": ", ",
}

#: The question's kind. Anchored on the asking words, so a subject-bearing
#: question ("when is the dentist") falls to `reads_note`'s subject check.
_KINDS: tuple[tuple[str, re.Pattern], ...] = (
    ("left", re.compile(
        r"\bwhat(?:'s| is| else)?\s+(?:is |are )?(?:left|remaining|outstanding|still (?:to do|open|needed))\b|"
        r"\bwhat\s+(?:do|should|must|can|could)\s+i\s+(?:still\s+)?(?:do|need to|have to)\b|"
        r"\bwhat(?:'s| is)\s+next\b|\bnext steps?\b|\bto-?dos?\b|\baction items?\b|\bremaining tasks?\b|"
        r"\bwhat\s+(?:do|should)\s+i\s+do\b|\bwhat\s+(?:is\s+)?still\s+outstanding\b|"
        #: "what is not done yet", "how many are left", "what's unpacked" (audit 1030 Z33).
        r"\bwhat(?:'s| is| are)\s+(?:not\s+(?:done|finished|ticked|checked|packed|complete\w*)|un(?:done|ticked|checked|packed|finished|complete\w*))\b|"
        r"\bhow\s+many\b[^?]*\b(?:left|remaining|open|to\s+go)\b", re.I)),
    ("done", re.compile(
        r"\bwhat(?:'s| is| have i| has been)?\s+(?:i\s+)?(?:done|finished|ticked(?: off)?|checked(?: off)?|packed|completed)\b|"
        r"\bwhat\s+have\s+i\s+(?:done|finished|ticked|packed|completed)\b|\bhow\s+many\b[^?]*\b(?:done|ticked|checked|packed|finished|complete\w*)\b", re.I)),
    ("who", re.compile(
        r"\bwho\b[^?]*\b(?:involved|mentioned|named|in (?:it|this)|on (?:it|this)|there)\b|\bwhich people\b|\bwho(?:'s| is) here\b|"
        r"\bwho(?:'s| is) (?:this|it)(?: note)? (?:about|for|with)\b", re.I)),
    ("when", re.compile(
        r"\bdeadlines?\b|\bdue (?:date|when|by)\b|\bwhen\s+(?:is|does|do|did|are|will|should|was)\s+(?:it|this|that|we)?\s*(?:due|happening|happen|start|end|finish|over)?\b|"
        r"\bwhat (?:dates?|days?)\b|\b(?:which|any|all the|list the|show the|what are the) (?:dates?|days?|deadlines?)\b|\bdates?\b[^?]*\b(?:mentioned|in (?:it|this|here)|given|named|are there)\b|\bby when\b|\bwhen is (?:it )?due\b|\bwhen\s+(?:is|are)\s+the\b", re.I)),
    ("point", re.compile(
        r"\b(?:main|key|big|core)\s+(?:point|idea|takeaway)s?\b|\btake-?aways?\b|\bwhat(?:'s| is)\s+important\b|\bwhat matters\b|\bgist\b", re.I)),
)

#: Words that name no subject: asking words, and the words each kind is made of.
_GENERIC = frozenset(
    "what whats when who whom which where how is are was were do does did can could should would will the a an this that these it its "
    "here there left remaining outstanding still next step steps todo todos action actions item items task tasks need needs have has "
    "to of in on at for by deadline deadlines due date day time main key point points idea takeaway takeaways important matters "
    "gist involved mentioned named people person me my i you we be get about any all open done packed ticked checked finished "
    "complete completed not yet un total many much dates days deadlines mention mentions mentioning include includes included contain contains contained given".split()
)

#: A to-do says it is owed ("need to", "must", "don't forget") wherever it
#: sits in the sentence, or opens on the verb ("Book the tram"). A sentence
#: that merely holds one of the verbs ("Flights cost $420 return") is a fact,
#: not a thing left to do (audit 1031 C29).
_OWED = re.compile(r"\b(?:need to|needs to|have to|has to|must|should|remember to|don't forget|do not forget|todo|to do|next step)\b", re.I)
_COMMAND = re.compile(
    r"^(?:then |also |and |please )?(?:book|buy|call|email|send|ask|check|finish|write|pay|order|renew|schedule|plan|prepare|fix|bring|take|pack|get|pick up|"
    r"collect|print|submit|sign|confirm|cancel|return|reply|clean|wash|charge)\b",
    re.I,
)


def _to_do(text: str) -> bool:
    return bool(_OWED.search(text) or _COMMAND.match(text.strip()))


_NAME = re.compile(r"[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?")
_NOT_NAMES = frozenset(
    "The This That These Those There Then They Their Here What When Where Which While With Without Will Would Should Could "
    "January February March April May June July August September October November December Monday Tuesday Wednesday Thursday "
    "Friday Saturday Sunday Three Four Five Six Seven Eight Nine Ten Book Buy Call Make Send Ask Check Finish Also Next".split()
)


def kind(question: str) -> str:
    """"left", "when", "who" or "point" when `question` is one of those asks,
    else "" (any other question is not this module's)."""
    q = " ".join((question or "").split())
    for name, pattern in _KINDS:
        if pattern.search(q):
            return name
    return ""


def _terms(question: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (question or "").lower().replace("'", ""))
    return [w for w in words if w not in _GENERIC and len(w) > 2]


def reads_note(question: str, note: dict) -> bool:
    """Whether the open `note` should answer `question`: it is one of the
    kinds above and every word that names a subject ("the dentist") is in
    the note, so a question about something else still searches the notebook."""
    if not kind(question):
        return False
    text = str(note.get("content") or "").lower()
    return all(_in_text(t, text) for t in _terms(question))


def _in_text(term: str, text: str) -> bool:
    """A subject word is in the note's text, as typed, as a plural or as the
    verb's irregular past ("meet" is "met": audit 1030 Z54)."""
    if term in text or term.rstrip("s") in text:
        return True
    from tessellate.ai import factgraph

    factgraph._tables()  # noqa: SLF001
    return any(factgraph._PAST.get(w) == term for w in set(re.findall(r"[a-z]+", text)))  # noqa: SLF001


def _pick(options: list[str], question: str, salt: str) -> str:
    digest = hashlib.sha1(f"{question.strip().lower()}:{salt}".encode()).digest()
    return options[digest[0] % len(options)]


def composer_voice() -> str:
    from tessellate.ai import composer_tables

    return composer_tables.DEFAULT_VOICE


def _say(out, key: str) -> None:  # noqa: ANN001
    out.parts.append(("template", PHRASES[key]))


def _quotes(out, sentences: list, view) -> None:  # noqa: ANN001
    for i, s in enumerate(sentences):
        if i:
            out.parts.append(("template", " "))
        out.q(s, [])


def _left(out, view, question: str, salt: str) -> None:  # noqa: ANN001
    open_tasks = [s for s in view.sentences if s.kind == "task" and s.done is False]
    if open_tasks:
        picked = open_tasks[:4]
        if len(picked) == 1:
            _say(out, "open_left_one")
        else:
            _say(out, _pick(["open_left_a1", "open_left_a2", "open_left_a4"], question, salt))
        for i, s in enumerate(picked):
            if i:
                _say(out, "open_and" if i == len(picked) - 1 else "open_comma")
            out.q(s, [])
        out.parts.append(("measure", "."))
        return
    if any(s.kind == "task" for s in view.sentences):
        _say(out, "open_left_none")
        return
    said = [s for s in view.sentences if s.kind in ("prose", "item") and _to_do(s.text)][:2]
    if not said:
        _say(out, "open_left_none")
        return
    _say(out, "open_left_text")
    _quotes(out, said, view)


def _done(out, view, question: str, salt: str) -> None:  # noqa: ANN001
    tasks = [s for s in view.sentences if s.kind == "task"]
    if not tasks:
        _say(out, "open_done_no_list")
        return
    ticked = [s for s in tasks if s.done][:4]
    if not ticked:
        _say(out, "open_done_none")
        return
    _say(out, _pick(["open_done_a1", "open_done_a2"], question, salt))
    for i, s in enumerate(ticked):
        if i:
            _say(out, "open_and" if i == len(ticked) - 1 else "open_comma")
        out.q(s, [])
    out.parts.append(("measure", "."))


def _when(out, view, question: str, salt: str) -> None:  # noqa: ANN001
    said = [s for s in view.sentences if s.kind != "picture" and recognise.dated_sentence(s.text)][:2]
    if not said:
        _say(out, "open_when_none")
        return
    _say(out, _pick(["open_when_a1", "open_when_a2", "open_when_a3"], question, salt))
    _quotes(out, said, view)


def _who(out, view, question: str, salt: str) -> None:  # noqa: ANN001
    found: list[str] = []
    for s in view.sentences:
        #: A capital that opens a sentence says nothing, so the first word is skipped.
        rest = s.text.split(None, 1)[1] if len(s.text.split(None, 1)) > 1 else ""
        for name in _NAME.findall(rest):
            if name.split()[0] in _NOT_NAMES:
                continue
            if name not in found:
                found.append(name)
    if not found:
        _say(out, "open_who_none")
        return
    _say(out, _pick(["open_who_a1", "open_who_a2", "open_who_a3"], question, salt))
    shown = found[:6]
    for i, name in enumerate(shown):
        if i:
            _say(out, "open_and" if i == len(shown) - 1 else "open_comma")
        out.term(name, view)
    _say(out, "open_who_end")
