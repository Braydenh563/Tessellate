"""A tag word's matching key, apart from `tagging` so `lexical_filing` can fold
category names without importing `tagging` (which imports it: test_no_import_cycles)."""

from __future__ import annotations

#: The abbreviations a student's notes use for a subject, folded as `tokens`
#: folds them ("stats" is "stat"). A spelling map, not a classifier: it only
#: lets a tag the person already uses be found under its short name.
ABBREVIATIONS = {
    "stat": "statistic",
    "uni": "university",
    "bio": "biology",
    "chem": "chemistry",
    "math": "mathematic",
    "psych": "psychology",
    "econ": "economic",
    "phys": "physic",
}


def stem(word: str) -> str:
    """A word's matching key: `tokens`' plural fold, then a light ending fold
    ("running" and "run", "gaming" and "game"), then the abbreviations."""
    word = ABBREVIATIONS.get(word, word)
    for ending in ("ing", "ed"):
        if len(word) > len(ending) + 2 and word.endswith(ending):
            word = word[: -len(ending)]
            if len(word) > 2 and word[-1] == word[-2] and word[-1] not in "aeiouls":
                word = word[:-1]
            break
    return word[:-1] if len(word) > 3 and word.endswith("e") else word
