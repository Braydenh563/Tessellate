"""Words, weighted by rarity across topics (INBOX 1530 a).

"Is there a companion that can show outside of the app on my desktop?" reached
only The corner companion: its keyword "companion" is one word and matches
whole, while "outside" and "desktop" sit only in the desktop companion's
phrases ("companion outside the app", "desktop pet"), which never matched as
phrases. So a keyword phrase the question shares two or more words with now
scores by those words' rarity: how few topics hold the word anywhere in their
keywords. "outside" (one topic) outweighs "companion" (five).

Three limits keep it from moving what the question bank already gets right
(`tests/fixtures/help_questions.json`, 177 questions, unchanged):

* the shared words must sit in one phrase, so two unrelated keywords that
  each hold one word say nothing;
* only a word at most `RARE` topics hold counts ("note" and "show" say little);
* the band is a floor, not an addition (`max` with the topic's keyword score),
  so "record a meeting" is still the voice topic, whose two single-word
  keywords already score as much.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable

#: Weight of a held word against the same word as a whole keyword.
BAND = 0.6
#: A word held by more topics than this says too little to count.
RARE = 6

_PLURAL = re.compile(r"(?<=[^s])s$")


def stem(word: str) -> str:
    return _PLURAL.sub("", word) if len(word) > 3 else word


class WordBand:
    """The per-topic phrase index and the score it gives a question."""

    def __init__(self, topics: Iterable[dict], word: re.Pattern, stop: frozenset[str], keyword_in: Callable[[str, str], bool]) -> None:
        topics = list(topics)
        self._total = len(topics)
        self._word = word
        self._stop = stop
        self._keyword_in = keyword_in
        self._phrases: dict[str, list[tuple[str, frozenset[str]]]] = {}
        self._topics_with: dict[str, int] = {}
        for topic in topics:
            sets = [(k, self._words(k)) for k in topic["keywords"]]
            self._phrases[topic["id"]] = [(k, ws) for k, ws in sets if len(ws) >= 2]
            for w in set().union(*(ws for _, ws in sets)):
                self._topics_with[w] = self._topics_with.get(w, 0) + 1

    def _words(self, text: str) -> frozenset[str]:
        return frozenset(stem(w) for w in self._word.findall(text.lower()) if w not in self._stop and len(w) > 2)

    def score(self, question_words: Iterable[str], lowered: str, topic_id: str) -> float:
        """The best keyword phrase of the topic that the question holds two or
        more rare words of, short of the whole phrase (which scores on its own)."""
        asked = {stem(w) for w in question_words if len(w) > 2}
        best = 0.0
        for keyword, words in self._phrases[topic_id]:
            held = [w for w in words if w in asked and self._topics_with[w] <= RARE]
            if len(held) >= 2 and not self._keyword_in(keyword, lowered):
                best = max(best, BAND * sum(1.0 + math.log(self._total / self._topics_with[w]) for w in held))
        return best


def typo_of(word: str, keyword: str, english: frozenset[str] | set[str], least: int) -> bool:
    """`word` read as a typo of `keyword`. A real word is not a swapped letter
    ("mount" is not "count", L-chat-38); one letter more or less still reads
    ("phone" for "iphone")."""
    return len(word) >= least and not (word in english and len(word) == len(keyword)) and one_edit_apart(word, keyword)


def one_edit_apart(a: str, b: str) -> bool:
    """True when `a` becomes `b` by one insertion, deletion, substitution or
    swap of two neighbours: the typos a person makes in a help box ("remnder",
    "serach", "chnage")."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = [k for k in range(la) if a[k] != b[k]]
        if len(diff) == 1:
            return True
        return (
            len(diff) == 2
            and diff[1] == diff[0] + 1
            and a[diff[0]] == b[diff[1]]
            and a[diff[1]] == b[diff[0]]
        )
    if la > lb:
        a, b = b, a
    k = 0
    while k < len(a) and a[k] == b[k]:
        k += 1
    return a[k:] == b[k + 1 :]


# --- a word the English list does not hold (VC15) ----------------------------------


def _within(a: str, b: str, limit: int) -> int | None:
    """The edit distance between `a` and `b` (insert, delete, substitute, swap
    of neighbours) when it is at most `limit`, else None."""
    if abs(len(a) - len(b)) > limit:
        return None
    prev2: list[int] | None = None
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        row = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            row[j] = min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
            if prev2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                row[j] = min(row[j], prev2[j - 2] + 1)
        prev2, prev = prev, row
    return prev[-1] if prev[-1] <= limit else None


def forgive(words: Iterable[str], vocabulary: Iterable[str], english: frozenset[str]) -> dict[str, str]:
    """Each word that is not English, and is no topic's own word, mapped to the
    nearest word the topics use (two edits for a word of seven letters or more,
    one for five or six). A word the list holds is never touched: "quick
    thoughts" is spelt right, "thuoght" is not (CHAT_PLAN VC15, the word list
    `frontend/vendor/wordlist/en.txt`)."""
    vocab = sorted(set(vocabulary))
    fixes: dict[str, str] = {}
    for word in words:
        if len(word) < 5 or not word.isalpha() or word in english or word in vocab:
            continue
        limit = 2 if len(word) >= 7 else 1
        best: tuple[int, str] | None = None
        for candidate in vocab:
            distance = _within(word, candidate, limit)
            if distance is not None and (best is None or distance < best[0]):
                best = (distance, candidate)
        if best:
            fixes[word] = best[1]
    return fixes
