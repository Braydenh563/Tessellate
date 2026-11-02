"""A note's own questions and their answers, read with no model (INBOX 1466).

The owner: "cna the composer do the questions better?? or do it at all??".
The night pass (`ai/facts.py`) took only sentences ending "?", so "I wonder
whether the raised bed gets enough sun." and "Need to find out who services
it." never reached the Questions page, and a later note that said "the
raised bed gets six hours of sun" answered nothing, because the no-model
answer pass compared questions with stance sentences only.

This module is the text half, with no database and no import of `facts`:

* `cue`: a sentence that asks without a "?" ("I wonder", "not sure if",
  "need to find out", "should I", "how do I", "what's the best way");
* `not_asked`: a question that is not one to keep: rhetorical ("who knows",
  "isn't it?"), on a quoted line, or pasted from a page (a link in the note
  and a question that speaks to "you");
* `normal`: the form two notes' questions are compared in, so a template's
  question repeated in many notes is skipped (`facts._template_questions`);
* `best_answer`: the later sentence that states what a question asks about,
  by the words they share (or one word, when the notes are linked).

`facts` stores what these find as the same `question` and `answered` rows a
model's pass writes: one path, read by the Questions page as before.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from tessellate.search.query import is_topic_word, search_terms

#: A sentence that opens by asking, with or without its "?".
_OPENS = re.compile(
    r"^(?:should i|shall i|do i need|how (?:do|can|should|would) i|what(?:'s| is) the best way|"
    r"which (?:\w+ )?should i|where (?:do|can|should) i|when should i)\b",
    re.I,
)
#: Words anywhere in a sentence that say the writer does not know yet.
_DOUBTS = re.compile(
    r"\b(?:i (?:still |really )?wonder|wondering (?:whether|if|how|why|what|when|where|who|which)|"
    r"(?:not|unsure|never) (?:quite )?sure (?:if|whether|what|how|why|when|where|who|which)|"
    r"(?:need|have|want|got) to (?:find out|figure out|work out|check whether|check if|decide)|"
    r"(?:don'?t|do not) know (?:if|whether|how|what|when|where|who|which))\b",
    re.I,
)
#: List markers and emphasis before a sentence's own words.
_LEAD = re.compile(r"^(?:\s*(?:[-*+]|\d+[.)])\s+)?(?:\*\*|__|\*|_)?")
#: Questions nobody waits on an answer to.
_RHETORICAL = re.compile(
    r"^(?:who (?:knows|cares|would have thought|would've thought)|why (?:not|bother)|guess what|"
    r"what could (?:possibly )?go wrong|how hard can it be|what(?:'s| is) not to like|what else is new|"
    r"how (?:cool|great|amazing|crazy|weird|lovely|good|bad|funny) is that|am i right)\b"
    r"|,\s*(?:right|you know|isn'?t it|aren'?t they|don'?t you think|eh|huh|no)\s*\??$",
    re.I,
)
_URL = re.compile(r"https?://|www\.", re.I)
#: A line that is only an address (bare, in angle brackets, or as a link).
_URL_LINE = re.compile(r"^\s*(?:[-*]\s+)?(?:<?(?:https?://|www\.)\S+>?|\[[^\]]*\]\((?:https?://|www\.)[^)]*\))\s*$", re.I)
_YOU = re.compile(r"\byou(?:r|rs)?\b", re.I)
#: Words that make a sentence a question, not what it is about.
_ASKING = frozenset(
    "wonder wondering sure unsure need find figure work check decide know best way should shall "
    "whether still really quite out".split()
)
#: Below this many words a sentence is too thin to be an answer.
ANSWER_WORDS = 4
#: Words a question must share with a sentence before it counts as answered,
#: and the share of the question's words they must be.
SHARED_WORDS = 2
SHARED_SHARE = 0.4


def core(text: str) -> str:
    """`text` without its list marker or emphasis."""
    return text[_LEAD.match(text).end():].strip()


def cue(text: str) -> bool:
    """Whether a sentence asks something with no "?" at its end."""
    words = core(text)
    return bool(_OPENS.match(words) or _DOUBTS.search(words))


def asks(text: str) -> bool:
    """Whether a sentence is shaped as a question, with or without the mark."""
    return text.rstrip("*_ ").endswith("?") or cue(text)


def not_asked(content: str, start: int, end: int) -> bool:
    """A question-shaped sentence that is not one of the person's own
    questions: rhetorical, on a quoted line, or pasted from a page.
    (`facts.own_question` already turns away quotes, scripts, jokes and guide
    text; these are the kinds it did not see.)"""
    words = core(content[start:end])
    line_start = content.rfind("\n", 0, start) + 1
    if content[line_start:end].lstrip().startswith(">"):
        return True
    if _RHETORICAL.search(words.rstrip("*_ ")):
        return True
    return bool(_YOU.search(words) and _pasted(content, start, end))


def _only_urls(lines: list[str]) -> bool:
    return bool(lines) and all(_URL_LINE.match(line) for line in lines)


def _paragraph(lines: list[str], index: int, step: int) -> list[str]:
    """The paragraph past `index` in direction `step`, when blank lines come
    between: its non-blank lines, else []."""
    at = index + step
    if not 0 <= at < len(lines) or lines[at].strip():
        return []
    while 0 <= at < len(lines) and not lines[at].strip():
        at += step
    found: list[str] = []
    while 0 <= at < len(lines) and lines[at].strip():
        found.append(lines[at])
        at += step
    return found


def _pasted(content: str, start: int, end: int) -> bool:
    """A question sits with a page's address: a URL in its own line outside
    the question, on the line just above or below it, or a paragraph of only
    URLs just before or after it. A URL elsewhere in the note, in another
    paragraph, is the person's own note, not a paste around this question."""
    lines = content.split("\n")
    row = content.count("\n", 0, start)
    first = content.rfind("\n", 0, start) + 1
    last = content.find("\n", end)
    beside = content[first:start] + " " + content[end:len(content) if last < 0 else last]
    neighbours = [lines[i] for i in (row - 1, row + 1) if 0 <= i < len(lines)]
    if any(_URL.search(text) for text in [beside, *neighbours]):
        return True
    return _only_urls(_paragraph(lines, row, -1)) or _only_urls(_paragraph(lines, content.count("\n", 0, max(end - 1, start)), 1))


def normal(text: str) -> str:
    """The form questions are compared in across notes."""
    return " ".join(re.findall(r"[a-z0-9']+", core(text).lower()))


def _stem(word: str) -> str:
    for ending in ("ing", "ed", "es", "s"):
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            word = word[: -len(ending)]
            break
    return word[:5]


def stems(text: str) -> set[str]:
    """The subject words of `text`, cut to a shared stem ("services" and
    "service", "tomatoes" and "tomato")."""
    return {_stem(w) for w in search_terms(text) if is_topic_word(w) and w not in _ASKING and not w.isdigit()}


def subject(question: str, heading: str) -> set[str]:
    """What a question is about: its own words, and the first line of its
    note when it says too little alone ("Need to find out who services it."
    under "Boiler")."""
    own = stems(question)
    return own | stems(heading) if len(own) < SHARED_WORDS else own


def score(about: set[str], sentence: str, *, linked: bool) -> float:
    """How fully `sentence` states what a question `about` asks, 0 when it
    does not: two shared words and two fifths of the question's, or one
    shared word between linked notes."""
    shared = len(about & stems(sentence))
    if not about or not shared:
        return 0.0
    share = shared / len(about)
    enough = shared >= SHARED_WORDS and share >= SHARED_SHARE
    return share if enough or linked else 0.0


def answer_sentences(sentences: Iterable[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    """The sentences of a note that can answer: statements of some length."""
    return [
        (text, start, end)
        for text, start, end in sentences
        if not asks(text) and len(text.split()) >= ANSWER_WORDS
    ]


def best_answer(about: set[str], notes: Iterable[tuple[int, bool, list[tuple[str, int, int]]]]):  # noqa: ANN201
    """The best `(score, entry_id, text, start, end)` among `notes`, given as
    `(entry_id, linked, answer_sentences)`, or None."""
    best = None
    for entry_id, linked, found in notes:
        for text, start, end in found:
            value = score(about, text, linked=linked)
            if value and (best is None or value > best[0]):
                best = (value, entry_id, text, start, end)
    return best
