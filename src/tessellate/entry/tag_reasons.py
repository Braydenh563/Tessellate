"""Why each offered tag is offered: the one line on its chip (decision 5).

A pure function of a note's text and its tags, so a list that reads the same
two hundred notes on every load remembers the answers. Out of the route file
(L-world-class-632); `tests/test_entries_preview.py` and
`tests/test_tag_reasons_cache_page.py` hold it.
"""

from __future__ import annotations

import collections
import hashlib
import threading
from collections import OrderedDict


#: Longest note whose reasons are remembered: the cache holds the text as its key.
REASONS_CACHE_CHARS = 20_000


def reasons(content: str, tags: list[str]) -> dict[str, str]:
    """Each offered tag's one line for its chip (decision 5: each explained).

    A pure function of the text and the tags (the taxonomy is read once per
    process), so a list that reads the same two hundred notes on every load
    remembers the answers: 5 ms a note was 2.2 of 3.4 profiled seconds of
    `GET /entries?limit=200` at 530 notes (BK10)."""
    if not tags or not content:
        return {}
    if len(content) > REASONS_CACHE_CHARS:
        return dict(_reasons_for(content, tuple(tags)))
    return dict(_cached_reasons(content, tuple(tags)))


def _reasons_for(content: str, tags: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    from tessellate.ai import tagging, taxonomy

    own = tagging.clean(content)
    hits = taxonomy.topic_hits(own)
    note_stems = tagging.stems(tagging.tokens(own))
    return tuple((tag, why) for tag in tags if (why := tagging.reason(tag, content, hits, note_stems, own)))


#: Rows the reasons cache keeps: more than a whole `GET /entries` page, or a list
#: read in order evicts each row before the next load reaches it and hits nothing.
REASONS_CACHE_ROWS = 5200


class _ReasonsCache:
    """`_reasons_for` remembered per (text, tags), keyed by a 16-byte digest of
    the text so 5,000 rows cost about 3 MB whatever the notes' length (L-world-class-161:
    the `lru_cache` it replaces held the text itself and was 1,024 rows, so a
    5,000 page thrashed it). Same `cache_clear` / `cache_info` as `lru_cache`."""

    Info = collections.namedtuple("Info", "hits misses maxsize currsize")

    def __init__(self, maxsize: int) -> None:
        self._rows: OrderedDict[tuple[bytes, tuple[str, ...]], tuple[tuple[str, str], ...]] = OrderedDict()
        self._maxsize, self._hits, self._misses = maxsize, 0, 0
        self._lock = threading.Lock()

    def __call__(self, content: str, tags: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
        key = (hashlib.blake2b(content.encode("utf-8", "surrogatepass"), digest_size=16).digest(), tags)
        with self._lock:
            found = self._rows.get(key)
            if found is not None:
                self._rows.move_to_end(key)
                self._hits += 1
                return found
            self._misses += 1
        value = _reasons_for(content, tags)  # outside the lock: it is the slow part
        with self._lock:
            self._rows[key] = value
            while len(self._rows) > self._maxsize:
                self._rows.popitem(last=False)
        return value

    def cache_clear(self) -> None:
        with self._lock:
            self._rows.clear()
            self._hits = self._misses = 0

    def cache_info(self) -> tuple:
        return self.Info(self._hits, self._misses, self._maxsize, len(self._rows))


_cached_reasons = _ReasonsCache(REASONS_CACHE_ROWS)
