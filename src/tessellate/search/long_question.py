"""What a long question is searched on (INBOX 1528).

The chat box takes 20,000 characters, and the search reads about 300 words
(`search_manager.SEARCH_QUERY_WORDS`). Those used to be the first 300, so a
pasted article with the question under it was searched on the article's
opening. A question over the limit is now searched on **its ask** (the last
sentence that reads as a question or a request, wherever it sits) plus the
few words of the paste the notebook tells apart best. The model still gets
the whole question; only the search narrows.

The weight of a word is the ranker's own: FTS5's bm25 idf over `search_index`
(`log((N - n + 0.5) / (n + 0.5))`, n the notes holding the word, counted
with the index's own tokenizer by a MATCH), saturated for how often the
paste says it with bm25's `k1`. No second weighting is invented here.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from sqlalchemy import text
from sqlalchemy.orm import Session

from tessellate.search import query as query_understanding

#: The ask is kept to this many words: a request that runs on is a paste.
ASK_WORDS = 60
#: Paste words added to the ask, and how many distinct words are priced at all
#: (a MATCH count each in one statement, about 20 microseconds apiece on 2,000 notes).
PASTE_TERMS = 4
PRICED_TERMS = 100
#: bm25's term-frequency saturation, FTS5's default.
_K1 = 1.2

_SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")
#: A sentence with no question mark reads as a request by its first word.
_REQUEST_LEAD = re.compile(
    r"^(?:and |so |then |now |also |but )?(?:please|tell me|explain|summari[sz]e|find|list|give|show|write|compare|describe|help|draft|"
    r"suggest|recommend|check|(?:can|could|would|will) you)\b",
    re.IGNORECASE,
)


def _sentences(text_value: str) -> list[str]:
    return [part.strip() for part in _SENTENCES.split(text_value) if part and part.strip()]


def ask_of(text_value: str) -> str:
    """The last sentence that reads as a question or a request; the last
    sentence when none does (an ask with no question mark sits last)."""
    sentences = _sentences(text_value)
    if not sentences:
        return ""
    for sentence in reversed(sentences):
        if sentence.endswith("?") or _REQUEST_LEAD.match(sentence):
            return sentence
    return sentences[-1]


def _index_size(session: Session) -> int:
    return int(session.execute(text("SELECT count(*) FROM search_index")).scalar() or 0)


def _notes_with(session: Session, words: list[str]) -> list[int]:
    """How many notes hold each word, in one statement (a statement apiece
    cost 35 ms for 250 words, mostly the ORM's overhead)."""
    parts = [f"(SELECT count(*) FROM search_index WHERE search_index MATCH :w{i})" for i in range(len(words))]
    row = session.execute(text("SELECT " + ", ".join(parts)), {f"w{i}": f'"{word}"' for i, word in enumerate(words)}).one()
    return [int(count or 0) for count in row]


def distinctive_terms(session: Session, paste: str, skip: set[str], count: int = PASTE_TERMS) -> list[str]:
    """The `count` words of `paste` that tell the notebook's notes apart best.

    A word no note holds is dropped (it cannot find anything), and so is one
    most notes hold (idf near zero). If the index cannot be read the paste's
    most repeated words stand in."""
    seen = Counter(word for word in query_understanding.search_terms(paste) if word not in skip and len(word) > 2)
    # Longer and repeated words are priced first when there are more than the
    # budget; the short common ones are the least likely to be distinctive.
    pool = sorted(seen, key=lambda word: -len(word) * (1 + math.log(seen[word])))[:PRICED_TERMS]
    if not pool:
        return []
    try:
        total = _index_size(session)
        weighted = []
        for word, holding in zip(pool, _notes_with(session, pool)):
            if holding:
                idf = math.log((total - holding + 0.5) / (holding + 0.5))
                weighted.append((idf * seen[word] * (_K1 + 1) / (seen[word] + _K1), word))
    except Exception:  # noqa: BLE001 - no index yet: the repeated words are what there is
        return sorted(pool, key=lambda word: -seen[word])[:count]
    weighted.sort(reverse=True)
    #: A word the reader takes for a time ("thursday", "march") would become a
    #: date filter on the whole question, so it is not carried over. Checked
    #: best first and only until `count` are kept: each check is a parse.
    kept: list[str] = []
    for weight, word in weighted:
        if weight > 0 and not query_understanding.understand(word).has_range:
            kept.append(word)
            if len(kept) == count:
                break
    return kept


def search_text(session: Session, query: str, words: int, chars: int) -> str:
    """`query` as is when it is within `words` and `chars`; else its ask plus
    the paste's distinctive words."""
    if len(query) <= chars and not _over_words(query, words):
        return query
    sentence = ask_of(query)
    ask = " ".join(sentence.split()[:ASK_WORDS])
    rest = query.replace(sentence, " ", 1)
    extra = distinctive_terms(session, rest, set(query_understanding.search_terms(ask)))
    return " ".join([ask, *extra])[:chars]


def _over_words(value: str, words: int) -> bool:
    return len(value.split(None, words)) > words
