"""UK, Australian and US spellings read as one word (INBOX 895, the owner:
UK/AU and US spelling both handled).

"organise" and "organize", "colour" and "color", "centre" and "center",
"travelled" and "traveled" name the same thing. The pairs are not a list
typed here: they are found in the English list the documents editor already
ships (`frontend/vendor/wordlist/en.txt`, US and UK spellings both, read
through `spelling.english`), by the regular differences between the two
(-ise and -ize, -our and -or, -re and -er, a doubled l before an ending,
-ogue and -og, -ence and -ense, ae and oe), each kept only when both
spellings are in the list. A handful of words that follow no rule are named.

Search asks for both forms (`fts_group`), which is the index read both ways
without rebuilding it; the composer compares words by `canonical` (the US
form, arbitrarily, as the key), and answers keep the note's own spelling
because they are made from the note's text.
"""

from __future__ import annotations

import re
from functools import lru_cache

#: (UK pattern, US replacement), tried on the word's end or middle.
_RULES = (
    (re.compile(r"is(e|ed|es|ing|ation|ations|er|ers|able|ational)$"), r"iz\1"),
    (re.compile(r"ys(e|ed|es|ing|er|ers)$"), r"yz\1"),
    (re.compile(r"our(s|ed|ing|ite|ites|able|ful|less|ism|ist|er|ers)?$"), r"or\1"),
    (re.compile(r"([tb])re(s)?$"), r"\1er\2"),
    (re.compile(r"([tb])red$"), r"\1ered"),
    (re.compile(r"([tb])ring$"), r"\1ering"),
    (re.compile(r"ogue(s)?$"), r"og\1"),
    (re.compile(r"ence(s)?$"), r"ense\1"),
    (re.compile(r"ae(?=[a-z])"), "e"),
    (re.compile(r"oe(?=[a-z])"), "e"),
)
#: A doubled l before an ending ("travelled", "cancelling", "labelled"),
#: only when the stem with one l is the word ("fill" keeps "filled").
_DOUBLE_L = re.compile(r"^(.+[aeiou])ll(ed|ing|er|ers)$")
#: Pairs no rule makes.
NAMED = (
    ("grey", "gray"), ("greys", "grays"), ("programme", "program"), ("programmes", "programs"),
    ("aluminium", "aluminum"), ("jewellery", "jewelry"), ("plough", "plow"), ("moustache", "mustache"),
    ("pyjamas", "pajamas"), ("sceptical", "skeptical"), ("sceptic", "skeptic"), ("mould", "mold"),
    ("fulfil", "fulfill"), ("fulfils", "fulfills"), ("enrol", "enroll"), ("enrols", "enrolls"),
    ("skilful", "skillful"), ("judgement", "judgment"), ("ageing", "aging"), ("practise", "practice"),
    ("practised", "practiced"), ("practising", "practicing"), ("manoeuvre", "maneuver"),
    #: Not spellings but the same pairing: an irregular plural meets its
    #: singular in search ("find notes about knives" meets "Knife sharpening").
    ("knives", "knife"), ("shelves", "shelf"), ("loaves", "loaf"), ("wives", "wife"), ("leaves", "leaf"),
)
#: Two words a rule pairs that mean different things ("prise" a lid, a "prize").
_NOT_PAIRS = frozenset("prise prised prises prising".split())
#: Long enough that a rule cannot pair two unrelated short words ("tour" and "tor").
_MIN = 5


#: A cheap test per rule, so the regex runs on the few words it can change.
_GUARDS = (
    lambda w: "is" in w, lambda w: "ys" in w, lambda w: "our" in w, lambda w: w.endswith(("tre", "bre", "tres", "bres")),
    lambda w: w.endswith(("tred", "bred")), lambda w: w.endswith(("tring", "bring")), lambda w: "ogue" in w,
    lambda w: "ence" in w, lambda w: "ae" in w and len(w) >= 8, lambda w: "oe" in w and len(w) >= 8,
)


def _us_forms(word: str, words: frozenset) -> list[str]:
    out = []
    for (pattern, replacement), guard in zip(_RULES, _GUARDS):
        if not guard(word):
            continue
        candidate = pattern.sub(replacement, word, count=1)
        if candidate != word and candidate in words:
            out.append(candidate)
    double = _DOUBLE_L.match(word) if "ll" in word else None
    if double and double.group(1) + "l" in words and double.group(1) + "ll" not in words:
        candidate = double.group(1) + "l" + double.group(2)
        if candidate in words:
            out.append(candidate)
    return out


def _wordlist_path():  # noqa: ANN202
    """`frontend/vendor/wordlist/en.txt`, the documents editor's English list
    (tier 60, US and UK spellings both; `docs/THIRD_PARTY.md`), wherever the
    app is run from: the checkout, or a frozen bundle's root."""
    import sys
    from pathlib import Path

    roots = [Path(__file__).resolve().parents[3]]
    if getattr(sys, "frozen", False):
        roots.insert(0, Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)))
    for root in roots:
        path = root / "frontend" / "vendor" / "wordlist" / "en.txt"
        if path.is_file():
            return path
    return None


@lru_cache(maxsize=1)
def english() -> frozenset:
    """The general English list (Brief 104, INBOX 895: "insanely" read as
    "in sanely", "expansive" as "expensive"): every alphabetic word of four
    letters or more. Shorter entries are left out on purpose: the list holds
    "nd", "ny" and "od" as abbreviations, which are the owner's slips for
    "and", "any" and "of". Empty when the list is missing (the speller then
    runs on its own lists, as before)."""
    path = _wordlist_path()
    if path is None:
        return frozenset()
    with open(path, encoding="utf-8") as handle:
        return frozenset(w for w in (line.strip() for line in handle) if len(w) >= 4 and w.isalpha() and w.isascii())


@lru_cache(maxsize=1)
def short_english() -> frozenset:
    """The three-letter words of the general list that are words ("oat",
    "gin", "yam", "fog": audit 1030 Z66), which a three-letter slip is never
    read away from. Left out of `english`, whose short entries include
    abbreviations; here a vowel is required, which drops those."""
    path = _wordlist_path()
    if path is None:
        return frozenset()
    with open(path, encoding="utf-8") as handle:
        return frozenset(w for w in (line.strip() for line in handle) if len(w) == 3 and w.isalpha() and w.isascii() and set(w) & set("aeiouy"))



@lru_cache(maxsize=1)
def pairs() -> dict[str, str]:
    """Every UK or Australian spelling the list holds, mapped to its US one."""
    words = english()
    table: dict[str, str] = {}
    for word in words:
        if len(word) < _MIN or word in _NOT_PAIRS:
            continue
        for us in _us_forms(word, words):
            table.setdefault(word, us)
    table.update(NAMED)
    return table


@lru_cache(maxsize=1)
def _others() -> dict[str, tuple[str, ...]]:
    grouped: dict[str, set[str]] = {}
    for uk, us in pairs().items():
        group = grouped.setdefault(us, {us})
        group.add(uk)
    out: dict[str, tuple[str, ...]] = {}
    for group in grouped.values():
        for word in group:
            out[word] = tuple(sorted(group - {word}))
    return out


def canonical(word: str) -> str:
    """The one spelling a word is compared by: its US form, else itself."""
    low = word.lower()
    return pairs().get(low, low)


def forms(word: str) -> tuple[str, ...]:
    """The word and its other spellings, the word first."""
    low = word.lower()
    return (low, *_others().get(low, ()))


#: Past forms no suffix rule folds (moved here from the composer's stemmer so the
#: search finds "Ran" for "run", audit 1031 C15). Only forms that are rarely
#: another word: not "saw", "left", "found", "felt".
IRREGULAR_PAST = {
    "ran": "run", "wrote": "write", "written": "write", "ate": "eat", "eaten": "eat", "swam": "swim", "swum": "swim",
    "rode": "ride", "ridden": "ride", "drove": "drive", "driven": "drive", "bought": "buy", "went": "go", "gone": "go",
    "flew": "fly", "flown": "fly", "took": "take", "taken": "take", "made": "make", "sold": "sell", "gave": "give",
    "given": "give", "came": "come", "told": "tell", "spoke": "speak", "spoken": "speak", "slept": "sleep", "paid": "pay",
    "met": "meet", "began": "begin", "begun": "begin", "broke": "break", "broken": "break", "chose": "choose",
    "chosen": "choose", "forgot": "forget", "forgotten": "forget", "sent": "send", "built": "build", "heard": "hear",
    "won": "win", "lost": "lose", "sat": "sit", "stood": "stand", "taught": "teach", "caught": "catch",
    "brought": "bring", "drank": "drink", "drunk": "drink", "sang": "sing", "sung": "sing", "wore": "wear", "worn": "wear",
    "woke": "wake", "grew": "grow", "grown": "grow",
}


@lru_cache(maxsize=1)
def _irregular_siblings() -> dict[str, tuple[str, ...]]:
    """Each irregular verb's other written forms: "run" is "ran", "ran" is "run"."""
    grouped: dict[str, set[str]] = {}
    for form, lemma in IRREGULAR_PAST.items():
        grouped.setdefault(lemma, {lemma}).add(form)
    out: dict[str, tuple[str, ...]] = {}
    for group in grouped.values():
        for word in group:
            out[word] = tuple(sorted(group - {word}))
    return out


def fts_group(term: str) -> str:
    """One FTS5 term as every spelling of it: "colour" is "(colour OR color)",
    "organise*" is "(organise* OR organize*)". A term with one
    spelling is returned as it came."""
    star = term.endswith("*")
    core = term[:-1] if star else term
    spelt = forms(core)
    #: An irregular form joins whole, never as a prefix: "ran*" would find "random".
    irregular = _irregular_siblings().get(core.lower(), ())
    if len(spelt) == 1 and not irregular:
        return term
    return "(" + " OR ".join([*(f"{w}*" if star else w for w in spelt), *irregular]) + ")"
