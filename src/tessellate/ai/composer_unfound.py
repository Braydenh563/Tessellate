"""The question's words no note found: which are missing and how the
answer says so in one line.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer._missing` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import functools
import re

from tessellate.ai import composer_frame, composer_tables, recognise as rec
from tessellate.ai.composer_answer import _Answer
from tessellate.ai.composer_ask import _alternatives, _holds, _stem, _stem_plain
from tessellate.ai.composer_read import NoteView
from tessellate.core.lazyre import lazy_compile


#: Words too short or too common to report as missing: a two-letter word
#: missing from a note says nothing about the note.
_MISSING_MIN = 3


def _one_edit(a: str, b: str) -> bool:
    """One letter added, dropped or changed: "gamin" for "gaming"."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return a[i + 1 :] == b[i + 1 :] or a[i:] == b[i + 1 :]
    return True


def _seen(term: str, found: set[str]) -> bool:
    """A word asked is not missing when a note has it in another shape: a
    past form ("buy" in "I just bought"), or the word mistyped ("gamin" for
    "gaming"), which said "I couldn't find any reference to buy or gamin"
    under the answer that quoted both (owner, 2026-10-12)."""
    from tessellate.ai import factgraph

    stem = _stem(term)
    #: The dropped "g" ("gamin", "runnin") stems as its own word.
    if stem in found or (term.lower().endswith("in") and _stem(term + "g") in found):
        return True
    factgraph._tables()
    if any(factgraph._PAST.get(word) == stem for word in found):
        return True
    #: The agent of a verb ("teaches" in "Teacher is Lucía", R9-2).
    if len(stem) >= 5 and any(word in (stem + "er", stem + "r", stem + "or") for word in found):
        return True
    return len(stem) >= 4 and any(_one_edit(stem, word) for word in found if word[:1] == stem[:1])


#: Words that tell the composer how to answer, never what to find: a note
#: that does not hold "sentences" is not missing anything (audit 1029 C37).
_INSTRUCTION_STEMS = frozenset(
    _stem_plain(w)
    for w in """main two three four five six seven eight nine ten both sentence paragraph line point bullet tag category categories
    improve improvement related similar recur recurring older newer oldest newest favourite favorite best worst everything
    summary list top first second third biggest largest smallest cheapest priciest
    gist overview story stuff style preferred prefer relationship give quick rough general overall kind sort type
    recorded outgoing mean meaning refer referring exact
    number figure amount value count tally mark fit archive finish show tell pin flag
    find display fetch dig pull out bring grab locate retrieve""".split()
)


#: Function words of the other languages a notebook is written in, which are
#: never a topic the notes could be missing: "que sé sobre Tokyo" is not
#: missing "sobre" (round 2 E26). Words that are also English are left out.
_FOREIGN = frozenset(
    """sobre que qué sé de del la las el los por para sin como cómo ist wie der das über und mit ein eine les des une dans pour
    mein meine dein avec qui est sul della dei che nel não uma com dos mes sur""".split()
)


#: An adverb says how, not what: "what did I personally think", "is it
#: actually recorded" are never missing their "personally" (stress run 2026-10-30).
_MANNER = lazy_compile(r"(?:ally|ely|ently|antly|ously|ively|edly|icitly)$|^(?:simply|merely|basically|honestly|truly|mostly|mainly|barely|nearly|hardly)$", re.I)


def _quoted_words(out: _Answer, views: list[NoteView]) -> set[str]:
    """Words of the sentences the answer quoted and of the notes it named."""
    quoted = {w for v in views for s in v.sentences if s.key in out.cited for w in s.words}
    quoted |= {w for v in views if v.id in out.named for w in v.title_words | v.filed_words}
    return quoted


@functools.lru_cache(maxsize=1)
def _shape_stems() -> dict[str, str]:
    return {_stem(word): shape for word, shape in composer_tables.SHAPE_WORDS.items()}


def _says_every(stems, sentence, view) -> bool:  # noqa: ANN001
    """Every question word is in the sentence, its note's name, or its shape."""
    words = set(sentence.words) | view.title_words
    return all(_holds(t, words) or _said_by_shape(t, sentence.text) for t in stems)


def _said_by_shape(term: str, quoted_text: str) -> bool:
    """A question word the sentence says by its shape ("money" by "$40")."""
    shape = composer_tables.SHAPE_WORDS.get(term.lower()) or _shape_stems().get(_stem(term))
    return bool(shape and rec.says_shape(shape, quoted_text))


#: Words that frame a question rather than name its topic, read from its
#: shape: the word after "how" ("how hot"), the verb after "do I" or "I've"
#: ("do I turn", "have I seen"), and aggregate, pronoun and comparison words.
#: Named as "not mentioned" they told the person a note was missing a word
#: no note would hold (audit 1030 Z16: "turn", "seen", "total", "him").
_FRAME_SHAPES = lazy_compile(
    r"\bhow (?!to\b)(\w+)"
    r"|\b(?:do|does|did|can|could|should|would|will|have|has|had|am|is|are|was|were) (?:i|we|you) (?:\w+ly )?(?!a\b|an\b|the\b)(\w+)"
    r"|\b(?:i|we)(?:'ve|'d|'ll| have| had| will)? (?!have\b|had\b|am\b|was\b)(\w+)"
    r"|\bwhat (\w+s) (?:in|into|inside|with|on)\b"
    #: An order's verb ("mark what I spent", "give me my", "tell me the") and the
    #: verb of "what tag fits my budget" (audit 1028 E22).
    r"|^\s*(?:please\s+|(?:can|could) you\s+)?(\w+)\s+(?:me\s+|us\s+)?(?:what|how|all|every|everything|my|the)\b"
    r"|\b(?:what|which)\s+\w+\s+(\w+s)\s+(?:my|the|a|an|your|our)\b",
    re.I,
)


_FRAME_WORDS = frozenset(
    _stem_plain(w)
    for w in """total sum plus overall whole altogether notebook theme themes him her them myself yourself ourselves
    more less sooner later further farther right now ingredient ingredients contents details information
    new brief valid name schedule appointment""".split()
)


#: The shape an order asks the answer to take, read from the sentence: "as a
#: table", "in two snippets", "the top three memos", and after an order verb
#: "in a haiku", "with a timeline". No list of formats: the position names it
#: (audit 1029 C37; a bare "in a hotel" with no order verb stays a topic).
_SHAPE_ASKED = lazy_compile(
    r"\bas (?:a |an |the )?(\w+)"
    r"|\bin (?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|a few|a couple of) (\w+)"
    r"|\b(?:top|first|last|best|worst|latest|newest|oldest)\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(\w+)",
    re.I,
)
_ORDER_SHAPE = lazy_compile(
    r"^\s*(?:please\s+|(?:can|could|would) you\s+(?:please\s+)?)?(?:summari[sz]e|give|write|draft|explain|describe|show|tell|list|put|format|turn|sum)\b"
    r"(?:(?!\b(?:what|which|who|where|when|how|about|my|our)\b).)*?\b(?:in|with) (?:a|an) (\w+)",
    re.I,
)


@functools.lru_cache(maxsize=256)
def _frame_stems(question: str) -> frozenset[str]:
    said = {w for m in _FRAME_SHAPES.finditer(question or "") for w in m.groups() if w}
    said |= {w for m in _SHAPE_ASKED.finditer(question or "") for w in m.groups() if w}
    said |= {w for m in _ORDER_SHAPE.finditer(question or "") for w in m.groups() if w}
    return frozenset(_stem(w) for w in said) | _FRAME_WORDS


#: A word that is no thing the notes could hold: a manner, a feeling, a verb form or a small
#: everyday word ("very", "stressed", "stops", "good", "minus"). Calling it missing is a tail a
#: person would not say (fable-composer-1110 F7.1); only a noun-like word is.
_NOT_A_NOUN = lazy_compile(r"(?:ed|ing|ly|ful|less|ish)$", re.I)
_SMALL_WORDS = frozenset(
    "very good bad far well sure fine nice great big small minus plus those these turn turns stop stops start starts "
    "helpful stressed worried tired happy sad more most less least much many some any again still just really quite".split()
)


#: A verb of the thing is not the thing: "Stay one night at a quinta" is an
#: instruction, so it does not stand in for the "hotel" someone asked which they
#: booked (the blind panel's Q10). The synonym group still finds notes.
_VERB_SYNONYMS = frozenset({"stay", "staying", "stayed"})


def _is_unfound(out: _Answer, term: str, found: set[str], quoted: set[str], quoted_text: str = "") -> bool:
    if term.lower() in _SMALL_WORDS or _NOT_A_NOUN.search(term) or re.fullmatch(r"(?=.*[.,$%£€])[\d.,$%£€]+", term):
        return False
    if len(term) < _MISSING_MIN or _stem(term) in _INSTRUCTION_STEMS or _MANNER.search(term) or _seen(term, found):
        return False
    if term.lower() in _FOREIGN:
        return False
    if _stem(term) in _frame_stems(out.question or ""):
        return False
    if (_alternatives(_stem(term)) - _VERB_SYNONYMS) & quoted or _said_by_shape(term, quoted_text):
        return False
    return not out.question or term.lower() in out.question.lower()


def _unfound_terms(out: _Answer, terms: list[str], views: list[NoteView]) -> list[str]:
    found: set[str] = set()
    for view in views:
        found |= view.words | view.title_words | view.filed_words
    #: A synonym counts as found only in a sentence the answer quoted: "trip
    #: cost" answered by the budget's own line is not missing "cost", but a
    #: "hotel" no quote (or quoted note's name) stands in for is still said
    #: to be missing.
    quoted = _quoted_words(out, views)
    quoted_text = " ".join(s.text for v in views for s in v.sentences if s.key in out.cited)
    return [t for t in terms if _is_unfound(out, t, found, quoted, quoted_text)]


def _missing(out: _Answer, terms: list[str], views: list[NoteView]) -> None:
    """"None of these notes mention “hotel”." for the question's words that no
    note found contains, measured over every word of every one of them.

    Said of "these notes", the ones found, and not of the notebook: retrieval
    chose them, and a claim about every note would be a claim nothing here
    measured."""
    missing = _unfound_terms(out, terms, views)
    if not missing or len(missing) == len(terms):
        return
    #: The one note the answer quoted is only its title ("Thai green curry"): that is what it has, not that
    #: its words are missing (R9-15).
    quoted = [v for v in views if any(s.key in out.cited for s in v.sentences)]
    only = composer_frame.own_title(str(quoted[0].note.get("content") or "").strip()) if len(quoted) == 1 else ""
    if only:
        out.t("para", "bare_a", "open_quote").asked(only).t("close_quote", "bare_b")
        return
    out.t("para", "missing")
    for i, word in enumerate(missing[:3]):
        if i:
            out.t("or")
        out.t("open_quote").asked(word).t("close_quote")
    out.t("stop")
