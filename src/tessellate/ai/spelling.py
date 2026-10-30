"""A general speller for typed questions (Brief 90, INBOX 837).

`question_noise.repair` read the asking words and left the rest of a question
as typed, on the reasoning that a subject word is the person's own. The
owner's real typing says otherwise ("redeisgn", "knoe", "thier", "noficiations",
"westen"): most of what people mistype is ordinary words, and a misspelt
word reaches every reader downstream (the intent rules, the place a clock is
asked for, the Guide's keywords). This module is the general pass:

* a word list (`common_words`, plus the app's own help text, whose counts
  also settle a tie: "user" beats "sure" here), with endings and prefixes
  worked out rather than listed;
* an edit-distance search that is strict about what it will change. A short
  word must be a cheap slip (a swap, a neighbouring key, a doubled letter) or
  a dropped letter with its first and last letters kept; "pasta" is not
  "past", and "tacos" is not "tacks";
* split words joined and run-together words split ("a nd", "thes ebuttons",
  "whena ny"), only where the pieces are words;
* words the person's notes hold, names, capitals and acronyms never changed.

A word it is unsure of is reported with the other reading it was near, so the
composer offers "Did you mean" instead of guessing silently.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from functools import lru_cache

from tessellate.ai import variants


#: Abbreviations typed as they are: never read as a typo of a small word.
KNOWN_SHORT = frozenset(
    "ai ui ux pc tv ok os js id ip ocr pdf url api app css html gps sms qr usb vpn wifi lan pin gb mb kb ms tag faq pr ci "
    "ml nlp llm gpu cpu ram rom ssd hd md png jpg gif csv txt doc xls "
    "yo vs ty ya ye hm uh um oh ah eh ha hi he we us ex re ta np ik ig tbh imo idk irl brb "
    "am an as at aw ax be bi by do er go id if in is it la lo ma me mi mu my no nu of om on op or ow ox pa pi so to up".split()
)

#: Small words a one-letter slip in a short token is read towards, with how
#: common each is: the prior that makes "odf the" "of" and not "off".
FUNCTION_PRIOR = {
    "of": 0.6, "be": 0.3, "its": 0.0, "in": 0.4, "on": 0.4, "to": 0.4, "and": 0.6, "the": 0.6, "for": 0.3, "with": 0.3, "from": 0.3,
    "but": 0.3, "not": 0.3, "you": 0.3, "are": 0.3, "was": 0.3, "can": 0.3, "all": 0.1, "or": 0.3, "is": 0.3,
    "it": 0.3, "at": 0.2, "by": 0.2, "an": 0.2, "my": 0.2, "me": 0.2, "if": 0.2, "so": 0.2, "do": 0.2,
    "must": 0.2, "will": 0.2, "also": 0.7, "that": 0.3, "this": 0.3, "have": 0.3, "what": 0.3, "when": 0.3, "how": 0.3,
}
#: The app's own subject words: a near tie goes to them ("typeos" is "typos",
#: not "types"), because this is the notebook people type their typos into.
OWN_WORDS = frozenset({"typo", "typos", "ocr"})
#: Phrases a near tie is settled by: (before, reading, after) -> a bonus.
#: "a loit of" is "a lot of", "on tis own" is "on its own".
CONTEXT_READINGS = {("a", "lot", "of"): 0.6, ("", "lot", "of"): 0.4, ("on", "its", "own"): 0.8, ("its", "own", ""): 0.0}
#: A mistyped acronym is read as itself when the next word is one it leads:
#: "cor workspace" is "ocr workspace" (not "for").
ACRONYM_LEADS = {
    "ocr": frozenset("workspace scan scans reading reader text engine".split()),
    "pdf": frozenset("file files page pages document reader".split()),
    "url": frozenset("link links address field".split()),
}
#: Words that are not the head of a phrase after an article ("the suer" is
#: "the user", not "the sure"): a near tie goes to the other reading.
NOT_AFTER_ARTICLE = frozenset("sure such very quite just even only also too so still then than now here there really maybe".split())
#: Small words that take no ending: "thes" is a slip for "these", not "the" + s.
NO_ENDINGS = frozenset("the and but for not you are was can her his its our who how why may any all one off out per via yet nor too".split())
NOT_AFTER_A = frozenset("those these whose them they their there".split())
PREPOSITIONS = frozenset("of in on to for at by with from about off up".split())
DETERMINERS = frozenset("the a an my your this that these those his her our their its some any".split())

#: A trailing "n" is "n't" with the apostrophe left out ("doesn follow").
CONTRACTION_STEMS = {
    "doesn": "does not", "didn": "did not", "isn": "is not", "wasn": "was not", "weren": "were not", "aren": "are not",
    "hasn": "has not", "haven": "have not", "hadn": "had not", "wouldn": "would not", "couldn": "could not",
    "shouldn": "should not", "mustn": "must not", "needn": "need not", "don": "do not",
}

_PREFIXES = ("re", "un", "dis", "mis", "pre", "non", "over", "under", "out", "inter", "sub", "semi", "anti", "auto", "multi")
#: (ending, letters to put back on the stem). "ise" endings come off whole:
#: "professionalising" is "professional" + "ising".
_ENDINGS = (
    ("isations", ("",)), ("isation", ("",)), ("izations", ("",)), ("ization", ("",)),
    ("ising", ("",)), ("izing", ("",)), ("ised", ("",)), ("ized", ("",)), ("ises", ("",)), ("izes", ("",)),
    ("ise", ("",)), ("ize", ("",)),
    ("ings", ("", "e")), ("ing", ("", "e")), ("ies", ("y",)), ("ied", ("y",)), ("ves", ("f", "fe")), ("ed", ("", "e")), ("es", ("",)), ("s", ("",)),
    ("ers", ("", "e")), ("er", ("", "e")), ("est", ("", "e")), ("ly", ("",)), ("ness", ("",)), ("ment", ("",)),
    ("ments", ("",)), ("ful", ("",)), ("less", ("",)), ("able", ("", "e")),
)

#: Spelling limits by length of the stem being matched; see `_accept`.
_CHEAP = 0.6


def _limit(n: int) -> float:
    if n <= 3:
        return 0.0
    if n == 4:
        return _CHEAP
    if n == 5:
        return 1.0
    if n == 6:
        return 1.2
    if n <= 8:
        return 1.1
    if n <= 11:
        return 1.5
    return 2.0


#: Returns the help topics (dicts); help_chat registers it when it loads. A
#: registry rather than an import: help_chat imports the speller's callers, so
#: the speller naming it back was an import cycle.
_topic_source: Callable[[], list] | None = None


def set_topic_source(source: Callable[[], list]) -> None:
    """Hand the speller the app's help topics, and drop what it cached from
    the word list alone."""
    global _topic_source  # noqa: PLW0603
    _topic_source = source
    _app_counts.cache_clear()
    _dictionary.cache_clear()
    #: Both are read from the dictionary just dropped.
    _index.cache_clear()
    _candidates.cache_clear()


def _help_text() -> str | None:
    """The app's help topics as one string, or None when they cannot be read.

    Empty until `help_chat` registers its topics, which the help route does
    before any question is read; a test or script that skips the route loads
    `help_chat` first (tests/conftest.py does). The speller cannot load it
    itself: `help_chat` reaches this module through `question_noise`, and an
    `importlib` call here made the three one import cycle."""
    try:
        return " ".join(
            " ".join([str(t.get("title", "")), str(t.get("body", "")), " ".join(t.get("keywords") or [])])
            for t in (_topic_source() if _topic_source else [])
            if isinstance(t, dict)
        )
    except Exception:  # noqa: BLE001 - a missing help must not stop a question being read
        import logging  # only on this failure path: the cold import is budgeted

        logging.getLogger(__name__).debug("the help topics could not be read; questions are read without them", exc_info=True)
        return None


@lru_cache(maxsize=1)
def _app_counts() -> Counter:
    """Word counts over the app's own help text: its vocabulary, and what
    breaks a tie between two readings. Empty when the help is not loadable
    (the speller then runs on the word list alone)."""
    text = _help_text()
    if text is None:
        return Counter()
    text = text.lower()
    counts = Counter(w for w in re.findall(r"[a-z]+", text) if len(w) >= 3)
    #: The help quotes the typos it puts right ("keybord" the shortcuts): a
    #: word met only inside quotes and on no word list is an example, not
    #: the app's vocabulary, or the speller would leave that very typo alone.
    unquoted = set(re.findall(r"[a-z]+", _QUOTED.sub(" ", text)))
    from tessellate.ai.common_words import WORDS
    from tessellate.ai.common_words_more import MORE

    for word in [w for w in counts if w not in unquoted and w not in WORDS and w not in MORE and w not in english()]:
        del counts[word]
    return counts


_QUOTED = re.compile(r'"[^"\n]{1,80}"|\u201c[^\u201d\n]{1,80}\u201d')


#: The general English list lives with the spelling pairs (`variants`, a
#: leaf: search reads it too, and must not reach the speller's help text).
english = variants.english


#: A long word of the general list is a target, never above a listed word:
#: "knowledgable" is "knowledgeable", while "suer" stays "user".
ENGLISH_TARGET_MIN = 9
ENGLISH_TARGET_WEIGHT = 0.3


@lru_cache(maxsize=1)
def _dictionary() -> dict[str, float]:
    """The words a misspelling is corrected towards, each with a weight: the
    word list at 1, the app's own words by how often its help uses them, and
    the documentation's long words (seven letters or more) at half: a short
    real word is too near other short words to be a target."""
    #: Imported here, not at the top: the lists cost milliseconds the composer's
    #: import budget does not have (`test_the_composer_imports_without_the_database_layer`).
    from tessellate.ai.common_words import WORDS
    from tessellate.ai.common_words_more import MORE

    weights: dict[str, float] = {w: 1.0 for w in WORDS}
    for word, count in _app_counts().items():
        weights[word] = weights.get(word, 0.0) + count
    for word in MORE:
        if len(word) >= 7:
            weights.setdefault(word, 0.5)
    for word in english():
        if len(word) >= ENGLISH_TARGET_MIN:
            weights.setdefault(word, ENGLISH_TARGET_WEIGHT)
    return weights


@lru_cache(maxsize=1)
def _recognised() -> frozenset:
    """Every word that is a word, so is left alone: the targets and all the
    documentation's words besides."""
    from tessellate.ai.common_words_more import MORE

    return frozenset(_dictionary()) | MORE | english()


def _mask(word: str) -> int:
    bits = 0
    for ch in word:
        bits |= 1 << (ord(ch) - 97) if "a" <= ch <= "z" else 0
    return bits


@lru_cache(maxsize=1)
def _index() -> dict[int, list[tuple[str, int]]]:
    """Base words by length, each with its letter mask: the cheap filter that
    keeps the edit-distance search to a few dozen words."""
    by_len: dict[int, list[tuple[str, int]]] = {}
    for word in _dictionary():
        by_len.setdefault(len(word), []).append((word, _mask(word)))
    return by_len


def _stems(word: str):
    """(prefix, stem, ending, how) readings of a word: the stem is a candidate
    base. `how` says what was done to the stem, so the ending can be put back
    ("hoping" is "hope" + ing; "stopped" is "stop" + ped)."""
    yield "", word, "", ""
    for ending, backs in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            core = word[: -len(ending)]
            #: "generateing" is not "generate" + ing: a stem in a lone "e"
            #: drops it before an ending that starts with a vowel.
            if ending == "es" and not core.endswith(("s", "x", "z", "ch", "sh", "o")):
                continue
            dropped_e = ending[:1] in ("i", "e") and ending not in ("es", "ies", "ied") and core.endswith("e") and not core.endswith("ee")
            for back in backs:
                if back == "" and dropped_e:
                    continue
                yield "", core + back, ending, {"e": "e", "y": "y", "f": "f", "fe": "f"}.get(back, "")
            #: A doubled last letter is the stopped/planning rule, which only
            #: those endings follow ("propper" is not "prop" + per).
            if len(core) >= 4 and core[-1] == core[-2] and ending in ("ing", "ings", "ed"):
                yield "", core[:-1], ending, "dbl"


def _readings(word: str):
    for stem_prefix, stem, ending, how in _stems(word):
        yield stem_prefix, stem, ending, how
    for prefix in _PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 5:
            rest = word[len(prefix):]
            for _, stem, ending, how in _stems(rest):
                yield prefix, stem, ending, how


def is_word(word: str, known=(), strict: bool = False) -> bool:  # noqa: ANN001
    """Whether `word` (lower case) is a word: listed, or a listed word with an
    ending or prefix, or one the person's notes hold. `strict` is the listed
    words alone: "lastest" is "last" and "est" to the long rule and no word."""
    if word in known:
        return True
    if strict:
        return not word.isalpha() or word in _recognised()
    return _is_word(word)


@lru_cache(maxsize=8192)
def _is_word(word: str) -> bool:
    if not word.isalpha():
        return True
    seen = _recognised()
    if word in seen:
        return True
    return any(
        stem in seen and len(stem) >= 3 and not (ending and stem in NO_ENDINGS) and not _y_then_ending(stem, ending, how)
        for _, stem, ending, how in _readings(word)
    )


def _y_then_ending(stem: str, ending: str, how: str) -> bool:
    """A stem of four letters or more in a consonant and "y" with a comparative
    or past ending put straight on ("shortyer", "happyer", "busyer", "babyed"):
    the "y" becomes "i" ("happier") or goes, so this is a slip, not "shorty" and
    "er". A three-letter stem keeps it ("flyer", "dryer", "shyer")."""
    return not how and ending in ("er", "ers", "est", "ed", "es") and len(stem) >= 4 and stem.endswith("y") and stem[-2] not in "aeiou"


def _rebuild(prefix: str, base: str, ending: str, how: str) -> str:
    if how == "e" and base.endswith("e") and ending[:1] in ("a", "e", "i", "o", "u", "y"):
        base = base[:-1]
    elif how == "y" and base.endswith("y"):
        base = base[:-1]
    elif how == "f" and base.endswith(("fe", "f")):
        #: "knives" is "knife" + ves: the stem's last "f" or "fe" gives way.
        base = base[: -2 if base.endswith("fe") else -1]
    elif how == "dbl":
        base = base + base[-1]
    return prefix + base + ending


def _vowel_slip(typed: str, base: str) -> bool:
    """One vowel for another in a word of six or more: the commonest slip."""
    if len(typed) != len(base) or len(base) < 6:
        return False
    odd = [(x, y) for x, y in zip(typed, base) if x != y]
    return len(odd) == 1 and odd[0][0] in "aeiou" and odd[0][1] in "aeiou"


def _accept(typed: str, base: str, d: float) -> bool:
    """Whether a distance is close enough for these two words. A word of the
    same length must be a cheap slip (a swap, a neighbouring key, a doubled
    letter) unless it is long: "hallway" is not "halfway" and "paid" is not
    "pair". A word a letter or more longer or shorter is read when it keeps
    its first and last letters (short) or is long enough to be unmistakable
    ("pasta" is not "past")."""
    n = len(typed)
    if d == 0:
        return False
    if len(typed) == len(base):
        return d <= _limit(n) and (d <= _CHEAP or _vowel_slip(typed, base) or (n >= 9 and d <= 1.0))
    #: A letter dropped or added: a long word within its allowance, a short
    #: one when its first letter (and, under six letters, its last) is kept
    #: and a whole edit is allowed ("ahnd" is "and", "pasta" is not "past").
    if n >= 7:
        return d <= _limit(n)
    if n == 6:
        return d <= _limit(n) and typed[0] == base[0]
    return d <= 1.0 and typed[0] == base[0] and typed[-1] == base[-1]


@lru_cache(maxsize=4096)
def _candidates(stem: str, distance):  # noqa: ANN001
    """The list words near a stem, as (distance, -weight, word); cached, since
    one question is read many times over (`composer.rephrase`). It said so
    and was not, and one typo cost 4 to 10 s (audit 1030 Z65)."""
    index = _index()
    weights = _dictionary()
    mask = _mask(stem)
    out: list[tuple[float, float, str]] = []
    for n in range(len(stem) - 2, len(stem) + 3):
        for base, bmask in index.get(n, ()):
            if (mask ^ bmask).bit_count() > 5:
                continue
            d = distance(stem, base)
            if _accept(stem, base, d):
                out.append((d, -weights[base], base))
    return tuple(out)


def _prefix_kept(word: str, distance):  # noqa: ANN001
    """A five-letter word that keeps its first three letters is a last-two-
    letters slip ("ghose" is near "ghost"), though a whole substitution is
    refused to `_accept`; it is only a reading, and the word frequency still
    decides between it and a nearer, commoner word ("those"). Whole words
    only: on a stem it read "comoser" as "comeser"."""
    if len(word) != 5:
        return []
    weights = _dictionary()
    out = []
    for base, _ in _index().get(5, ()):
        if base[:3] == word[:3] and base != word:
            d = distance(word, base)
            if d <= 1.0:
                out.append((d, -weights[base], base))
    return out


def _own(stem: str, known, distance):  # noqa: ANN001
    """The person's own words a stem is near, weighted above the word list: a
    note that says "hotel" makes "hotle" a hotel."""
    mask = _mask(stem)
    out = []
    for base in known:
        if abs(len(base) - len(stem)) > 2 or len(base) < 4 or (mask ^ _mask(base)).bit_count() > 5:
            continue
        d = distance(stem, base)
        if _accept(stem, base, d):
            out.append((d, -4.0, base))
    return out


def _ending_fits(base: str, ending: str, how: str) -> bool:
    """Whether `ending` can go on the list word `base` the way `how` says
    ("generateing" cannot; "comess" cannot)."""
    if (how == "y" and not base.endswith("y")) or (how == "e" and not base.endswith("e")):
        return False
    if how == "" and ending[:1] in ("i", "e") and ending not in ("es", "ies", "ied") and base.endswith("e") and not base.endswith("ee"):
        return False
    #: A plural "s" is not put on a word that already ends where "es" goes: "chess"
    #: is not "comes" + s ("comess").
    return not (ending == "s" and base.endswith(("s", "x", "z", "ch", "sh")))


#: A plural determiner agrees with the noun after it ("those notes", not
#: "those cursor"): the reading is cheaper before a plural-looking word and
#: dearer before a singular one.
PLURAL_DETERMINERS = frozenset(("those", "these"))
_AGREEMENT = 0.5
#: The first letter is the one a typist hits deliberately, so a reading that
#: only swaps it ("those" for "ghose", a neighbouring key, or "whose") costs
#: more than one that keeps the word's start ("ghost").
_FIRST_KEY_SLIP = 0.7


def _slip_penalty(word: str, rebuilt: str, after: str) -> float:
    """What a reading costs beyond its edit distance for how it sits: a
    changed first letter and nothing else, and a plural determiner before a
    noun that is not plural."""
    cost = 0.0
    if len(word) == len(rebuilt) and word[1:] == rebuilt[1:]:
        cost += _FIRST_KEY_SLIP
    if rebuilt in PLURAL_DETERMINERS and after.isalpha():
        cost += -_AGREEMENT if after.endswith("s") and not after.endswith("ss") else _AGREEMENT
    return cost


def _reading_row(word: str, before: str, after: str, prefix: str, ending: str, how: str, d: float, negw: float, base: str, distance):  # noqa: ANN001, ANN202
    """One scored reading `(score, rebuilt word, weight)` of `word` as the list
    word `base` with its ending put back, or None when the stem and ending do
    not fit or it is the typed word itself."""
    if not _ending_fits(base, ending, how):
        return None
    rebuilt = _rebuild(prefix, base, ending, how)
    if rebuilt == word:
        return None
    #: After an article the head is a noun: adverbs lose a near tie.
    penalty = 0.5 if before in DETERMINERS and base in NOT_AFTER_ARTICLE else 0.0
    #: Nor does a plural or relative determiner follow an article ("a those cursor").
    if before in ("a", "an", "the") and base in NOT_AFTER_A:
        penalty += 0.7
    #: Ranked by the whole word, not the stem: "professionaly" is one
    #: doubled letter from "professionally", two edits from "professionly".
    whole = d if rebuilt == base else distance(word, rebuilt)
    #: A vowel for a vowel is the commonest slip in a long word
    #: ("restert" is "restart"); a prefix reading ("restreet") loses to it.
    if _vowel_slip(word, rebuilt):
        whole = min(whole, 0.6)
    if prefix:
        penalty += 0.3
    if rebuilt in OWN_WORDS:
        penalty -= 0.3
    penalty -= CONTEXT_READINGS.get((before, rebuilt, after), 0.0)
    penalty += _slip_penalty(word, rebuilt, after)
    return whole + penalty - 0.8 * FUNCTION_PRIOR.get(rebuilt, 0.0), rebuilt, -negw


_Y_ENDING = re.compile(r"^([a-z]{2,}[^aeiouy])y(er|ers|est|ed)$")


def _y_to_i(word: str) -> str | None:
    """A long stem in a consonant and "y" with an ending put straight on is
    the "y" turned to "i": "happyer" is "happier", "busyer" is "busier",
    "babyed" is "babied". Only when that is a listed word, so "shortyer"
    ("shorty" and "er", "shortier" is no word) is read by the nearer-word rule."""
    m = _Y_ENDING.match(word)
    rebuilt = f"{m.group(1)}i{m.group(2)}" if m else ""
    return rebuilt if rebuilt in _recognised() else None


def _scored_readings(word: str, after: str, before: str, distance, known) -> list[tuple[float, str, float]]:  # noqa: ANN001
    """Every reading of a misspelt word as a list word (with its ending put
    back), scored; the lowest score is the nearest."""
    scored: list[tuple[float, str, float]] = []
    for prefix, stem, ending, how in _readings(word):
        if len(stem) < 4:
            continue
        near = [*_candidates(stem, distance), *_own(stem, known, distance)]
        if not prefix and not ending:
            near += _prefix_kept(stem, distance)
        for d, negw, base in near:
            row = _reading_row(word, before, after, prefix, ending, how, d, negw, base, distance)
            if row:
                scored.append(row)
    return scored


def _fix(word: str, after: str, before: str, distance, known=()):  # noqa: ANN001
    """The chosen reading of a misspelt word and the other reading it was near,
    as (chosen, alternative) or None. `known` are the person's own words (their
    notes'), which a misspelling is read towards before any list word."""
    if len(word) < 4:
        return _fix_short(word, after, before, distance)
    if slipped := _y_to_i(word):
        return slipped, None
    scored = _scored_readings(word, after, before, distance, known)
    if not scored:
        return _one_off(word) or _hidden_small(word, after)
    scored.sort(key=lambda row: (round(row[0] / 0.2), -row[2], row[0]))
    best = scored[0]
    pool = [row for row in scored if row[1] != best[1]]
    #: A rival must be the same kind of reading (not "calendarer" for "calender").
    other = next((row for row in pool if row[0] - best[0] <= 0.35 and _same_shape(best[1], row[1], word)), None)
    #: A rival nearly as near and as common: unsure, so offered.
    return best[1], (other[1] if other else None)


def _one_off(word: str):
    """A five-letter non-word one letter from exactly one list word ("linal"
    is "final"): a whole substitution is allowed only when nothing else is
    that near, which is what keeps "hallway" from being "halfway"."""
    if len(word) != 5:
        return None
    from tessellate.ai.common_words import WORDS  # noqa: PLC0415 - the lists cost import time

    #: Only an everyday word is a target ("tacos" is not "macos").
    found = [
        base for base, _ in _index().get(5, ())
        if base in WORDS and sum(1 for x, y in zip(word, base) if x != y) == 1 and base[0] != "" and base[-1] == word[-1]
    ]
    return (found[0], None) if len(found) == 1 else None


def _hidden_small(word: str, after: str = ""):
    """A small word with one stray letter at an end, or in the wrong order
    ("ehte" is "the", "ist" is "is"): read as the small word, when no list
    word is near."""
    if len(word) not in (3, 4):
        return None
    for cand in sorted(FUNCTION_PRIOR, key=lambda c: -FUNCTION_PRIOR[c]):
        if len(cand) != len(word) - 1:
            continue
        for rest in (word[1:], word[:-1]):
            if rest == cand or (len(cand) == 3 and sorted(rest) == sorted(cand)):
                return cand, None
    return None


def _same_shape(a: str, b: str, typed: str) -> bool:
    """Two readings of one typed word that differ in length by at most a
    letter: the second is offered only then (not "calendarer" for "calender")."""
    return abs(len(a) - len(b)) <= 1


def _two_letter_reading(word: str, after: str, distance):  # noqa: ANN001, ANN202
    """Two letters are read only as a small word with its first letter
    dropped ("nd" is "and", "dn" is the same letters swapped), its letters
    swapped ("ro" is "or") or one key off ("od" is "of")."""
    pool = [
        cand for cand in FUNCTION_PRIOR
        if (len(cand) == 3 and sorted(cand[1:]) == sorted(word))
        or (len(cand) == 2 and cand != word and (cand == word[::-1] or distance(word, cand) <= 0.5))
    ]
    #: Before an article a small word is a preposition ("od the" is "of the").
    #: Before "to" a preposition cannot stand ("ot to" is "it to", not "of to").
    pool.sort(key=lambda c: -(
        FUNCTION_PRIOR[c]
        + (0.5 if after in DETERMINERS and c in PREPOSITIONS else 0.0)
        + (0.5 if after == "to" and c == "it" else -0.5 if after == "to" and c in PREPOSITIONS else 0.0)
    ))
    return (pool[0], pool[1] if len(pool) > 1 else None) if pool else None


def _short_candidates(word: str, before: str, after: str, pool, limit: float, distance) -> list[tuple[float, str]]:  # noqa: ANN001
    scored = []
    for cand in pool:
        if abs(len(cand) - len(word)) > 1:
            continue
        d = distance(word, cand)
        #: A letter dropped from a small word that keeps its first and last
        #: letters ("mut" for "must") costs a whole edit but is the commonest slip.
        dropped = len(cand) == len(word) + 1 and cand[0] == word[0] and cand[-1] == word[-1]
        #: A stray last letter ("ist" for "is") is a cheap slip too.
        if cand == word[:-1]:
            d, dropped = min(d, 0.6), True
        if 0 < d <= (1.0 if dropped else limit) and (cand[0] == word[0] or cand[-1] == word[-1] or sorted(cand) == sorted(word)):
            scored.append((d - FUNCTION_PRIOR.get(cand, 0.0) - CONTEXT_READINGS.get((before, cand, after), 0.0), cand))
    return scored


def _fix_short(word: str, after: str, before: str, distance):  # noqa: ANN001
    """A two- or three-letter token that is no word: read as a small word only
    when a letter was dropped or swapped, and between words (not alone)."""
    if len(word) < 2 or word in KNOWN_SHORT or not (after or before):
        return None
    if len(word) == 2:
        return _two_letter_reading(word, after, distance)
    context_prep = after in DETERMINERS
    scored = _short_candidates(
        word, before, after, PREPOSITIONS if context_prep else frozenset(FUNCTION_PRIOR), 1.0 if context_prep else _CHEAP, distance
    )
    if not scored:
        return _hidden_small(word, after)
    scored.sort()
    best = scored[0]
    other = next((row for row in scored[1:] if row[0] - best[0] <= 0.35), None)
    return best[1], (other[1] if other else None)


_CLOCK_SLIPS = {"thre": "three", "tree": "three", "fiev": "five", "fve": "five", "sevn": "seven", "eigth": "eight", "nien": "nine", "tewlve": "twelve", "twelv": "twelve", "elevn": "eleven"}


def _fixed_phrase(word: str, after: str) -> tuple[str, None] | None:
    """The readings that need no scoring: the article run into a noun
    ("abutton"), "the" before a date, and a mistyped acronym before a word it leads."""
    if len(word) >= 6 and word[0] == "a" and _is_word(word[1:]):
        return "a " + word[1:], None
    #: "as ther 17th": no "there" is followed by a date, so it is "the".
    if word in ("ther", "thre", "teh", "hte") and after[:1].isdigit():
        return "the", None
    #: "at thre oclock": a clock word follows only a number, whatever the
    #: corpus counts of "there" say (CI be58a63: new help text tipped it).
    if after in ("oclock", "o'clock", "am", "pm") and word in _CLOCK_SLIPS:
        return _CLOCK_SLIPS[word], None
    for acronym, leads in ACRONYM_LEADS.items():
        if len(word) == 3 and word != acronym and sorted(word) == sorted(acronym) and after.lower() in leads:
            return acronym, None
    return None


def fix(word: str, *, after: str = "", before: str = "", known=(), distance=None):  # noqa: ANN001
    """`(chosen, alternative)` for a misspelt lower-case word, else None.
    A word the list knows, the person's notes hold, or that carries a digit or
    apostrophe is never changed."""
    if not word.isalpha() or word in known or word in KNOWN_SHORT:
        return None
    if distance is None:
        distance = _default_distance
    if _is_word(word):
        return _respelt(word, distance) or _rare_real(word, distance)
    special = _fixed_phrase(word, after)
    if special:
        return special
    read = _fix(word, after.lower(), before.lower(), distance, known)
    #: "it liks" is "it likes": a verb after a third-person subject.
    if read and read[0] == "like" and word.startswith("lik") and before.lower() in ("it", "he", "she", "who", "that", "everyone", "nobody"):
        return "likes", "like"
    return read


#: Words the app is written in that neither list has yet: targets like the
#: help's own words ("intractable results" is "interactable results").
APP_WORDS = frozenset("interactable clickable hoverable draggable resizable dockable".split())


@lru_cache(maxsize=1)
def _common() -> frozenset:
    from tessellate.ai.common_words import WORDS
    from tessellate.ai.common_words_more import MORE

    return frozenset(WORDS) | MORE | APP_WORDS | frozenset(w for w, n in _app_counts().items() if n >= 3)


def _rare_real(word: str, distance):  # noqa: ANN001, ANN202
    """A rare word of the general list one dropped vowel from a word the app
    and everyday writing use ("intractable" for "interactable"): a real-word
    slip (Brief 104), read as the common word. Long words only; a name or a
    rare word the person's notes hold never reaches here (`known`)."""
    if len(word) < 9 or word in _common():
        return None
    if word not in _RARE:
        mask = _mask(word)
        near = sorted(
            (distance(word, base), base)
            for base in _common()
            if len(base) == len(word) + 1 and base[0] == word[0] and (mask ^ _mask(base)).bit_count() <= 1
        )
        _RARE[word] = (near[0][1], None) if near and near[0][0] <= 0.5 else None
    return _RARE[word]


_RESPELT: dict[str, tuple | None] = {}
_RARE: dict[str, tuple | None] = {}


def _respelt(word: str, distance):  # noqa: ANN001, ANN202
    if word not in _RESPELT:
        _RESPELT[word] = _respelt_uncached(word, distance)
    return _RESPELT[word]


def _respelt_uncached(word: str, distance):  # noqa: ANN001, ANN202
    """A long word that is a word only by the ending rules ("knowledgable" is
    "knowledge" + "able") while the general list spells it one letter
    otherwise ("knowledgeable"): the list's spelling, else None."""
    if len(word) < 8 or word in _recognised() or word in APP_WORDS or not english():
        return None
    mask = _mask(word)
    near = sorted(
        (distance(word, base), base)
        for base in english()
        if abs(len(base) - len(word)) == 1 and (mask ^ _mask(base)).bit_count() <= 1
    )
    return (near[0][1], None) if near and near[0][0] <= 0.5 else None


def _resegment(a: str, b: str, known) -> tuple[str, str] | None:  # noqa: ANN001
    """Two typed pieces re-cut at another place so that both are words:
    "thes" + "ebuttons" is "these" + "buttons". The nearest cut to the one
    typed, within three letters, with both halves of two letters or more."""
    joined = a + b
    best: tuple[int, int, str, str] | None = None
    for cut in range(2, len(joined) - 1):
        x, y = joined[:cut], joined[cut:]
        if (x, y) == (a, b) or abs(cut - len(a)) > 3:
            continue
        if is_word(x, known) and is_word(y, known):
            key = (abs(cut - len(a)), -min(len(x), len(y)))
            if best is None or key < best[:2]:
                best = (*key, x, y)
    if best is None:
        return _swapped_small(a, joined, known)
    return best[2], best[3]


def _swapped_small(a: str, joined: str, known) -> tuple[str, str] | None:  # noqa: ANN001
    """The space typed a letter early and the small word's letters swapped
    ("infoa dn" is "info and"): a word, then a small word's anagram."""
    for cut in range(4, len(joined) - 2):
        x, y = joined[:cut], joined[cut:]
        small = next((w for w in FUNCTION_PRIOR if len(w) == len(y) == 3 and sorted(w) == sorted(y)), None)
        if small and abs(cut - len(a)) <= 1 and is_word(x, known):
            return x, small
    return None


def _joined_or_cut(a: str, b: str, known) -> tuple[list[str], tuple[str, str]] | None:  # noqa: ANN001
    """The two lower-case alphabetic neighbours `a b` as one word ("a nd" is
    "and"), or re-cut into two ("thes ebuttons"): the pieces and the change
    to report, else None. Only where at least one piece is no word."""
    if (is_word(a, known) and is_word(b, known)) or a in known or b in known:
        return None
    whole = a + b
    #: A word only the general English list holds ("otto") is not a join:
    #: "ot to" is "it to".
    if len(whole) >= 3 and is_word(whole, known) and (whole in known or whole not in english() or whole in _dictionary()):
        return [whole], (f"{a} {b}", whole)
    #: A run-on pair is re-cut only when neither piece is a word
    #: ("thes ebuttons"); "the mantis" is a word and a rare word.
    cut = None if is_word(a, known) or is_word(b, known) else _resegment(a, b, known)
    return ([cut[0], cut[1]], (f"{a} {b}", f"{cut[0]} {cut[1]}")) if cut else None


def rejoin(tokens: list[str], known=(), skip=frozenset(), changes: list | None = None) -> list[str]:  # noqa: ANN001
    """Split words put back together and run-on pairs re-cut: "a nd" is "and",
    "whena ny" is "when any". Only where at least one piece is no word, and
    only into words; capitalised pieces (names), slang and numbers are left."""
    out: list[str] = []
    i = 0
    while i < len(tokens):
        a = tokens[i]
        b = tokens[i + 1] if i + 1 < len(tokens) else ""
        core_b = b.rstrip("?!.,:;")
        tail = b[len(core_b):]
        done = None
        if b and a.islower() and core_b.islower() and a.isalpha() and core_b.isalpha() and a not in skip and core_b not in skip:
            done = _joined_or_cut(a, core_b, known)
        if done is None:
            out.append(a)
            i += 1
            continue
        pieces, change = done
        if changes is not None:
            changes.append(change)
        out.extend([*pieces[:-1], pieces[-1] + tail])
        i += 2
    return out


_STRAY_SEMI = re.compile(r"(?<=[a-z]);(?=[a-z])")


def drop_stray(token: str, known=(), changes: list | None = None) -> str:  # noqa: ANN001
    """A semicolon struck inside a word ("natura;l", the key beside "l") taken
    out when what is left is a word and the pieces are not both words."""
    if ";" not in token:
        return token
    core = token.rstrip("?!.,:;")
    tail = token[len(core):]
    joined = core.replace(";", "")
    if _STRAY_SEMI.search(core) and joined.isalpha() and joined.islower() and is_word(joined, known):
        if changes is not None:
            changes.append((core, joined))
        return joined + tail
    return token


def split_run_on(word: str, known=()) -> tuple[str, str] | None:  # noqa: ANN001
    """A single unknown token that is two words run together, one of them a
    small word ("thenthe" is "then the", "ofthe" is "of the"). Only a small
    word makes the cut: "pancakes" is not "pan cakes"."""
    if len(word) < 6 or not word.isalpha() or is_word(word, known):
        return None
    small = DETERMINERS | PREPOSITIONS | frozenset(FUNCTION_PRIOR) | frozenset({"then", "when", "that", "what", "this", "are", "is"})
    for cut in range(2, len(word) - 1):
        head, tail = word[:cut], word[cut:]
        if (head in small or tail in small) and is_word(head, known) and is_word(tail, known) and min(len(head), len(tail)) >= 2:
            return head, tail
    return None


#: QWERTY neighbours: a slip to the next key is a cheaper edit than any other.
_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
_NEAR: dict[str, set[str]] = {}
for _r, _row in enumerate(_ROWS):
    for _c, _key in enumerate(_row):
        near = _NEAR.setdefault(_key, set())
        for dr in (-1, 0, 1):
            rr = _r + dr
            if 0 <= rr < len(_ROWS):
                for dc in (-1, 0, 1):
                    cc = _c + dc
                    if (dr or dc) and 0 <= cc < len(_ROWS[rr]):
                        near.add(_ROWS[rr][cc])


_SOUNDS = frozenset(frozenset(pair) for pair in ("dt", "bp", "gk", "sz", "ck", "cs", "fv"))


def _sub_cost(a: str, b: str) -> float:
    if a == b:
        return 0.0
    if b in _NEAR.get(a, ()):
        return 0.5
    #: Letters that sound alike are mixed up by ear ("instand", "bolier" no, "seperate").
    return 0.6 if frozenset((a, b)) in _SOUNDS else 1.0


def _gap_cost(word: str, i: int) -> float:
    """The cost of adding or dropping the i-th letter (1-based)."""
    return 0.4 if i > 1 and word[i - 1] == word[i - 2] else 0.5 if word[i - 1] in "aeiou" else 1.0


def distance(a: str, b: str) -> float:
    """Weighted edit distance: a neighbouring key 0.5, a swap of two letters
    0.6, a doubled letter added or dropped 0.4, a vowel 0.5, anything else 1."""
    a, b = a.lower(), b.lower()
    rows = [[0.0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        rows[i][0] = i * 1.0
    for j in range(1, len(b) + 1):
        rows[0][j] = j * 1.0
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            #: A doubled letter, or a vowel dropped as people do when they
            #: type fast ("lng", "whn", "mny"), is cheaper than other edits.
            drop, add = _gap_cost(a, i), _gap_cost(b, j)
            best = min(rows[i - 1][j] + drop, rows[i][j - 1] + add, rows[i - 1][j - 1] + _sub_cost(a[i - 1], b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                best = min(best, rows[i - 2][j - 2] + 0.6)
            rows[i][j] = best
    return rows[-1][-1]


_default_distance = distance


_WARMED = {"started": False}


def warm_in_background() -> None:
    """Build the word lists, the speller's index and the spelling pairs on
    the job pool's batch lane (`core/jobs.py`, the flaw-class lint: no new
    threads), once per process: the first question and the first search
    then do not pay about a second for them."""
    if _WARMED["started"]:
        return
    _WARMED["started"] = True
    from tessellate.core import jobs

    jobs.enqueue("warm", _warm, name="the spelling lists", dedupe_key="spelling-warm")


def _warm() -> None:
    try:
        _index()
        _recognised()
        _common()
        variants.pairs()
    except Exception:  # noqa: BLE001  # a warm-up that fails leaves the first use to build them
        import logging  # only on this failure path: the cold import is budgeted

        logging.getLogger(__name__).debug("spelling warm-up failed; the first question builds the lists", exc_info=True)
