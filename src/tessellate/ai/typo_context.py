"""Which word a slip was meant to be, read from its context (INBOX 1745).

The speller (`spelling.fix`) and the router-guided repair (`question_noise.guided`) find the words a slip is
near; this module chooses among them, and among the real words a slip may also be ("form" for "from", "skull"
for "skill"), by what surrounds the word:

1. the rest of the sentence: the word before and after it, and the other words in it;
2. the notebook's own vocabulary: a word that is a note title, a tag, a person or a list name is a strong
   candidate, and the words of the notes the question matches are a weaker one;
3. the previous turn's subject.

The cues describe how English is written, never one person's phrasing: a date word, a capitalised name or a
verb of origin follows "from" for a writer in any dialect, and the fixtures (`tests/test_typo_context_1745.py`)
hold every rule against US and UK spelling, second-language English, shorthand, shouting, and runs with no
punctuation. When two readings stay close the likelier is answered and the other is offered ("Did you mean ...?").
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import NamedTuple
from tessellate.core.lazyre import lazy_compile

_WORD = lazy_compile(r"[^\W\d_]{3,}")
_PAIR_WEIGHT = 1.0
_TITLE_WEIGHT = 2.0
_TEXT_WEIGHT = 0.5
_PREVIOUS_WEIGHT = 0.8
#: A cue next to the word, then one anywhere in the sentence.
_NEXT_TO = 1.5
_ANYWHERE = 0.75
#: The typed word is a real word, so it starts a little ahead; a very common one ("not", "from") further.
_TYPED_LEAD = 0.5
_COMMON_LEAD = 1.0
#: A lead this big is taken with no offer; a smaller one is taken and the other reading is offered.
SURE = 1.5


@dataclass(frozen=True)
class Context:
    """What the notebook and the conversation say, for one question."""

    own: dict[str, float] = field(default_factory=dict)
    previous: frozenset[str] = frozenset()
    #: Every two words the notes write side by side ("oat", "dairy"): a slip next to a word it has
    #: stood beside in the notebook is read as that word (L222).
    pairs: frozenset[tuple[str, str]] = frozenset()


CTX: ContextVar[Context | None] = ContextVar("typo_context", default=None)


def note_words(notes: Iterable[dict] | None) -> frozenset:
    """The words of the notes the question is asked of, lower case."""
    found: set[str] = set()
    for note in notes or []:
        found.update(re.findall(r"[^\W\d_]{3,}", f"{note.get('title') or ''} {note.get('content') or ''}".lower()))
    return frozenset(found)


def _grow(own: dict[str, float], words: Iterable[str], weight: float) -> None:
    for word in words:
        if own.get(word, 0.0) < weight:
            own[word] = weight


def of_notes(notes: Iterable[dict] | None, names: Iterable[str] = (), previous: str = "", lists: Iterable[str] = (), history: Iterable[dict] = ()) -> Context:
    """The context of a question asked of `notes`: titles, tags, categories, people and list names are the
    notebook's own words (strong), the rest of the text is its topic (weak)."""
    own: dict[str, float] = {}
    pairs: set[tuple[str, str]] = set()
    for note in notes or []:
        text = re.findall(r"[^\W\d_]+", f"{note.get('title') or ''} {note.get('content') or ''}".lower())
        pairs.update(zip(text, text[1:]))
        _grow(own, _WORD.findall(f"{note.get('title') or ''} {note.get('content') or ''}".lower()), _TEXT_WEIGHT)
        tags = [str(t) for t in note.get("tags") or []]
        _grow(own, _WORD.findall(" ".join([str(note.get("title") or ""), str(note.get("category") or ""), *tags]).lower()), _TITLE_WEIGHT)
    _grow(own, (str(n).lower() for n in names), _TITLE_WEIGHT)
    for name in lists:
        _grow(own, _WORD.findall(str(name).lower()), _TITLE_WEIGHT)
    #: The turn before: what it asked and what it answered.
    last = list(history)[-1:] or [{}]
    said = f"{previous} {last[0].get('question') or ''}"
    return Context(own, frozenset(_WORD.findall(said.lower())), frozenset(pairs))


class Cues(NamedTuple):
    """What tends to sit next to a word, and anywhere near it."""

    left: frozenset
    right: frozenset
    near: frozenset


def _c(text: str) -> frozenset:
    return frozenset(text.split())


#: Right-hand cues that stand for a class of token, not one word.
DATE, NAME = "<date>", "<name>"
_WHEN = _c(
    "last next this yesterday today tomorrow tonight earlier monday tuesday wednesday thursday friday saturday sunday "
    "january february march april may june july august september october november december "
    "jan feb mar apr jun jul aug sep sept oct nov dec the my our work home then now"
)

#: Sets of words one slip apart that are each a word. Each reading lists what is written beside it. Chosen to
#: be words people confuse in any dialect (keyboard slips, homophones, second-language spellings), not a person's.
SENSES: dict[str, Cues] = {
    "from": Cues(
        _c("notes note messages message emails email mail texts text anything everything stuff entries written wrote write "
           "come comes coming came back away far taken copied quote quotes ideas people tell told heard hear learn learned "
           "pulled get got recipe recipes"),
        _c(f"{DATE} {NAME} _digit mum mom dad nan gran"), _c("since until till written wrote week month year ago monday tuesday wednesday thursday friday saturday sunday yesterday today tomorrow")),
    "form": Cues(
        _c("a the this that tax sign fill filled filling application contact new blank google booking feedback web paper "
           "online order entry consent"),
        _c("for about to is was has needs and"), _c("fill filled filling sign submit submitted tax application field fields")),
    "skill": Cues(
        _c("new your useful learn learned teach teaching life soft hard"),
        _c("for to and called named list set levels level"), _c("run use using skills learn learning improve practice train add make")),
    "skull": Cues(
        _c("human cracked broken fractured"),
        _c("and bone bones fracture fractured cracked hurts"), _c("bone bones head brain halloween skeleton fracture fractured helmet tattoo hurt")),
    "list": Cues(
        _c("a the my our your new shopping todo to-do packing grocery reading wish checklist this that"),
        _c("for of and called named is has items"), _c("add show shopping todo packing grocery items tick ticked what whats on make")),
    "last": Cues(
        _c("the at on"), _c("week month year night time day weekend few one two three summer winter"), _c("ago yesterday since")),
    "least": Cues(_c("at the"), _c("of one two three five ten"), _c("most")),
    "diary": Cues(
        _c("daily dear"), _c("entry entries note notes page pages"), _c("wrote write entry entries dear journal")),
    "dairy": Cues(
        _c("no free"), _c("free milk cheese products product aisle"), _c("milk cheese butter yoghurt yogurt cream cow cows farm allergy")),
    "note": Cues(_c("a the my this that new one last add make write create save pin delete open"), _c("about called named on for to in into"), _c("add make write create save show find open delete pin put move send throw chuck trash bin")),
    "not": Cues(
        _c("is are was were do does did can could will would should have has had am it that"),
        _c("sure working going enough yet just only the a an to there on in at"), _c("never no nothing")),
    "than": Cues(_c("more less better worse rather other bigger smaller older newer less fewer higher lower earlier later"),
                 _c("ten five two three the a an last usual before"), _c("more less")),
    "then": Cues(_c("and so but until just back"), _c("i we it he she they what the we"), _c("first next after before when if")),
    "quiet": Cues(_c("a the keep be very so quite"), _c("time place room day night hours"), _c("noise loud")),
    "quite": Cues(_c("not is was it very"), _c("a an good bad long big tired busy"), _c("really very")),
    "friend": Cues(_c("my our your his her old best close good new"), _c("called named is from"), _c("friends birthday invite")),
    "fiend": Cues(_c("fiendish"), _c("for"), _c("")),
}

#: Words that can be read as each other: the first of a set is what each is checked against.
CONFUSIONS: dict[str, tuple[str, ...]] = {
    "form": ("from",), "from": ("form",),
    "skull": ("skill",), "skill": ("skull",),
    "lest": ("list", "last", "least"), "list": ("lest",),
    "dairy": ("diary",), "diary": ("dairy",),
    "not": ("note",), "note": ("not",),
    "then": ("than",), "than": ("then",),
    "quite": ("quiet",), "quiet": ("quite",),
    "fiend": ("friend",),
}
#: Words so common in their own sense that only a plain cue moves them (a bare "not" is a word).
_RARE = frozenset(("lest", "fiend"))
_STAYS = frozenset(("not", "note", "then", "than", "from", "quite", "list", "last"))


def _plain(token: str) -> str:
    return (token or "").strip("?!.,:;\"'()").lower()


def seen(tokens: Iterable[str]) -> Counter:
    """The words of a sentence as `lean` reads them, counted: a caller that asks about every word of one long
    sentence builds this once and keeps it up to date, not one list a word (quadratic on a run of 50,000
    characters)."""
    return Counter(_plain(w) for w in tokens)


def swap(words: Counter, old: str, new: str) -> None:
    """`words` after the word `old` was read as `new`."""
    words[_plain(old)] -= 1
    words[_plain(new)] += 1


def _hits(word: str, left: str, right: str, right_raw: str, words: Counter) -> set[tuple[str, str]]:
    """The cues in the sentence that say `word`, each as (slot, cue)."""
    cues = SENSES.get(word)
    found: set[tuple[str, str]] = set()
    if not cues:
        return found
    if left in cues.left:
        found.add(("left", left))
    if right in cues.right:
        found.add(("right", right))
    elif DATE in cues.right and right in _WHEN:
        found.add(("right", DATE))
    elif "_digit" in cues.right and right[:1].isdigit():
        found.add(("right", "_digit"))
    elif NAME in cues.right and right_raw[:1].isupper():
        found.add(("right", NAME))
    found.update(("near", w) for w in cues.near if w != word and words.get(w, 0) > 0)
    return found


def _score(hits: set[tuple[str, str]], word: str, ctx: Context | None) -> float:
    """How well `word` fits where it stands: its own cues (a cue its rival has too says nothing, and is left out
    by the caller), the notebook's use of it, and the last turn's."""
    total = sum(_NEXT_TO if slot != "near" else 0.0 for slot, _ in hits)
    total += min(2 * _ANYWHERE, _ANYWHERE * sum(1 for slot, _ in hits if slot == "near"))
    if ctx:
        total += min(SURE, max(ctx.own.get(word, 0.0), ctx.own.get(word + "s", 0.0)))
        if word in ctx.previous or word + "s" in ctx.previous:
            total += _PREVIOUS_WEIGHT
    return total


def _pair_fit(word: str, left: str, right: str, ctx: Context | None) -> float:
    """What the notebook's own word pairs add to `word` standing between `left` and `right`."""
    if not ctx or not ctx.pairs:
        return 0.0
    return _PAIR_WEIGHT * ((left, word) in ctx.pairs) + _PAIR_WEIGHT * ((word, right) in ctx.pairs)


def speaks_for(readings) -> bool:  # noqa: ANN001
    """Whether context can choose among a misspelling's readings: only when it has cues for each. One-sided cues
    would outvote the speller ("i need ot to be": "not" has cues, "it" none), so the speller's order stands."""
    return all(r in SENSES for r in readings)


def lean(typed: str, readings: list[str], before: str, after_raw: str, sentence: Iterable[str] | Counter, real: bool) -> tuple[str, str | None]:
    """`(chosen, alternative)` for `typed` among `readings`, the typed word itself being one when `real` (it is a
    word, and starts ahead). The likeliest by context is chosen; when its lead is small the runner-up is
    offered. No alternative when the lead is sure or the runner-up has no support at all."""
    ctx = CTX.get()
    words = sentence if isinstance(sentence, Counter) else seen(sentence)
    left, right, low = _plain(before), _plain(after_raw), typed.lower()
    pool = [low, *[r for r in readings if r != low]] if real else list(readings)
    lead = _COMMON_LEAD if low in _STAYS else _TYPED_LEAD
    hits = {w: _hits(w, left, right, after_raw, words) for w in pool}
    scored = {
        w: _score(hits[w].difference(*(hits[o] for o in pool if o != w)), w, ctx) + _pair_fit(w, left, right, ctx) + (lead if real and w == low else 0.0)
        for w in pool
    }
    ranked = sorted(pool, key=lambda w: (-scored[w], pool.index(w)))
    best, other = ranked[0], (ranked[1] if len(ranked) > 1 else None)
    return best, (other if _worth_offering(scored, best, other, low) else None)


def _worth_offering(scored: dict[str, float], best: str, other: str | None, low: str) -> bool:
    """Whether the runner-up is offered back: its lead is small and it has some support. A word
    hardly ever meant ("lest", "fiend") is not offered."""
    if other is None or scored[best] - scored[other] >= SURE:
        return False
    return not ((other != low and scored[other] <= 0.0) or (other == low and low in _RARE))


def real_slip(tokens: list[str], i: int, words: Counter | None = None) -> tuple[str, str | None] | None:
    """`(chosen, alternative)` for the real word at `tokens[i]` when it may be another word, else None (it is
    not in a confusion set). `words` is `seen(tokens)` when the caller keeps it."""
    word = _plain(tokens[i])
    others = CONFUSIONS.get(word)
    if not others:
        return None
    return lean(word, list(others), tokens[i - 1] if i else "", tokens[i + 1] if i + 1 < len(tokens) else "", seen(tokens) if words is None else words, True)


def prefers(word: str, reading: str) -> bool:
    """True when the notebook says `word` is its own and `reading` is not ("run my skull" when "skull" is a note
    title and "skill" is nowhere in the notebook), so a router should not read it as `reading`."""
    ctx = CTX.get()
    return bool(ctx) and ctx.own.get(word, 0.0) >= _TITLE_WEIGHT > ctx.own.get(reading, 0.0)
