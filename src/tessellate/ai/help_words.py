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
