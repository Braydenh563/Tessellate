"""Find notes that say the same thing twice.

A notebook you actually use accumulates near-duplicates: the same thought
captured on two days, a note re-typed because the first one was hard to find,
a shopping list rewritten rather than edited.

Detection here is deliberately arithmetic rather than AI, normalise the text
and compare word overlap. That means it works with nothing running, it's
instant, and it's explainable: the score is a percentage of shared words, not
a black box. The AI's job comes later and is optional, at merge time, where
judgement genuinely helps.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterator
from itertools import islice

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core.database import Entry

# Below this, two notes are merely on the same topic rather than duplicates.
# Chosen high on purpose: a false positive invites someone to merge two notes
# that only looked alike, and that loses writing.
DEFAULT_THRESHOLD = 0.72

# How many notes one scan reads. It was 500 because every pair was compared
# (125,000 comparisons, over 25 s at the cap), which also meant a notebook past
# 500 notes never had its newer notes looked at, the ones most likely to repeat
# an older one. `_similar_pairs` below only compares notes that share one of
# their rarest words, so the cap is a memory bound now, not a time one.
MAX_SCAN = 5000


_NON_WORD = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Lowercase, strip punctuation and collapse whitespace."""
    return _SPACES.sub(" ", _NON_WORD.sub(" ", (text or "").lower())).strip()


def _word_set(text: str) -> set[str]:
    return {word for word in normalise(text).split() if len(word) > 1}


def _prepare(text: str) -> tuple[str, frozenset[str]]:
    """What a pair comparison needs from one note, computed once per note.

    The scan used to call `similarity` on every pair, which normalised both
    texts every time: four regex passes per pair, so a notebook of n notes
    paid them n(n-1)/2 times over for n distinct texts (60 notes: 1,770 pairs,
    about 196 ms of a request that does nothing else).
    """
    norm = normalise(text)
    return norm, frozenset(word for word in norm.split() if len(word) > 1)


def _score(left: tuple[str, frozenset[str]], right: tuple[str, frozenset[str]]) -> float:
    if left[0] == right[0]:
        return 1.0
    a, b = left[1], right[1]
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def similarity(a: str, b: str) -> float:
    """0..1 overlap between two notes, by shared words (Jaccard).

    Identical text scores 1.0. Word order is ignored on purpose: "milk and
    eggs" and "eggs and milk" are the same shopping list.
    """
    return _score(_prepare(a), _prepare(b))


def _similar_pairs(
    prepared: list[tuple[str, frozenset[str]]], threshold: float
) -> Iterator[tuple[int, int, float]]:
    """Every pair `(i, j)`, i < j, scoring at least `threshold`, with its score.

    Not every pair is compared. With each note's words in one global order,
    rarest first, two sets with Jaccard >= t must share a word in the first
    `len - ceil(t * len) + 1` of the larger-or-equal one's *probing* prefix and
    the first `len - ceil(2t / (1 + t) * len) + 1` of the smaller one's
    *indexing* prefix, provided notes are visited smallest first (the prefix
    filter of set-similarity joins, as in PPJoin). So a note is compared only
    with earlier (smaller) notes that share one of its few rarest words, then
    the size bound and the exact score decide. The result is exactly what the
    all-pairs loop returned; only the pairs that could not qualify are never
    looked at. Notes with identical text are joined to the first copy only
    (same group, same score of 1.0, without k(k-1)/2 pairs for k copies).
    """
    document_frequency = Counter(word for _norm, words in prepared for word in words)
    index: dict[str, list[int]] = defaultdict(list)
    first_with_text: dict[str, int] = {}
    bound = 2 * threshold / (1 + threshold)
    for i in sorted(range(len(prepared)), key=lambda n: (len(prepared[n][1]), n)):
        norm, words = prepared[i]
        candidates: set[int] = set()
        if norm in first_with_text:
            candidates.add(first_with_text[norm])  # the same text: 1.0, even with no words
        else:
            first_with_text[norm] = i
        ordered = sorted(words, key=lambda word: (document_frequency[word], word))
        size = len(ordered)
        probe = size - math.ceil(threshold * size - 1e-9) + 1
        for word in ordered[: max(probe, 0)]:
            candidates.update(index[word])
        keep = size - math.ceil(bound * size - 1e-9) + 1
        for word in ordered[: max(keep, 0)]:
            index[word].append(i)
        for j in candidates:
            if prepared[j][0] == norm:
                if first_with_text[norm] != j:
                    continue  # joined to the first copy already
            elif len(prepared[j][1]) < threshold * size:
                continue  # `j` is no larger than `i`: Jaccard <= |j| / |i|
            if norm == prepared[j][0]:
                score = 1.0
            else:
                # One intersection, the union from the sizes: `_score` does
                # the same sum with two set operations, and this is the line
                # every surviving candidate pays for.
                other = prepared[j][1]
                shared = len(words & other)
                score = shared / (size + len(other) - shared) if shared else 0.0
            if score >= threshold:
                yield (j, i, score) if j < i else (i, j, score)


#: The dense scan's budget, in multiply-adds (`n * n * vocabulary / 2`), and
#: how many of them cost what one candidate check in `_similar_pairs` costs.
#: Measured on the audit's 5,000-note notebook (305 distinct words, 144 a
#: note, load 12): the prefix filter checked about 8 million candidates and
#: took 160 s, because when every word is common no prefix is rare; the
#: dense scan's 3.8 billion multiply-adds took 1.2 s. On a real notebook's
#: long tail of rare words the prefix filter checks a few thousand and wins.
DENSE_MAX_WORK = 2e10
DENSE_PER_CANDIDATE = 500
#: Rows of the dense product per block: 512 x 5,000 float32 is 10 MB.
DENSE_BLOCK = 512


def _prefix_work(prepared: list[tuple[str, frozenset[str]]], threshold: float) -> tuple[int, int]:
    """(candidate checks the prefix filter would make at most, shared words).

    The upper bound `_similar_pairs` would read: every probe word's whole
    posting list. Cheap beside either scan (one count and one partial sort per
    note), and what decides which of the two runs.
    """
    import heapq

    document_frequency = Counter(word for _norm, words in prepared for word in words)
    work = 0
    for _norm, words in prepared:
        size = len(words)
        probe = max(size - math.ceil(threshold * size - 1e-9) + 1, 0)
        if probe:
            work += sum(heapq.nsmallest(probe, (document_frequency[word] for word in words)))
    return work, sum(1 for held in document_frequency.values() if held > 1)


def _vocabulary(prepared: list[tuple[str, frozenset[str]]]) -> dict[str, int]:
    """A column for each word two or more notes hold.

    A word only one note holds is in no pair's intersection, and the sizes
    the union is taken from are the whole sets (`_similar_pairs_dense`), so
    leaving it out changes no score. Counted in, a number or a name on every
    note ("Note 4123") made 5,000 notes over 25 shared words too wide for the
    dense scan: the prefix filter ran instead, 70 s and 2.1 GB on `/tidy`
    (L-world-class-410).
    """
    held = Counter(word for _norm, words in prepared for word in words)
    vocabulary: dict[str, int] = {}
    for _norm, words in prepared:
        for word in words:
            if held[word] > 1:
                vocabulary.setdefault(word, len(vocabulary))
    return vocabulary


def _word_matrix(prepared: list[tuple[str, frozenset[str]]], vocabulary: dict[str, int]):  # noqa: ANN202
    """One row a note, a 1.0 in the column of each word it holds."""
    import numpy as np

    matrix = np.zeros((len(prepared), len(vocabulary)), dtype=np.float32)
    for i, (_norm, words) in enumerate(prepared):
        if words:
            columns = [vocabulary[word] for word in words if word in vocabulary]
            if columns:
                matrix[i, columns] = 1.0
    return matrix


def _dense_blocks(prepared: list[tuple[str, frozenset[str]]], threshold: float):  # noqa: ANN202
    """`_similar_pairs_dense`'s pairs as arrays `(j, i, score)`, one block at a time.

    The test and the score are made over the whole block in numpy rather than
    pair by pair in Python: on 5,000 notes over a few hundred shared words
    11.5 million pairs qualify, and a Python loop per pair was most of a
    51 s `/tidy` (L-world-class-410). float64 division is the division
    `_similar_pairs` makes, so a pair at the threshold lands on the same side.
    """
    import numpy as np

    vocabulary = _vocabulary(prepared)
    n = len(prepared)
    first_with_text: dict[str, int] = {}
    text_id = np.empty(n, dtype=np.int64)
    copies_j: list[int] = []
    copies_i: list[int] = []
    for i, (norm, _words) in enumerate(prepared):
        if norm in first_with_text:
            copies_j.append(first_with_text[norm])
            copies_i.append(i)
        else:
            first_with_text[norm] = i
        text_id[i] = first_with_text[norm]
    if copies_i:
        yield (
            np.array(copies_j, dtype=np.int64),
            np.array(copies_i, dtype=np.int64),
            np.ones(len(copies_i), dtype=np.float64),
        )
    if not vocabulary or n < 2:
        return
    matrix = _word_matrix(prepared, vocabulary)
    sizes = np.array([len(words) for _norm, words in prepared], dtype=np.int64)
    sizes32 = sizes.astype(np.float32)
    for start in range(1, n, DENSE_BLOCK):
        stop = min(n, start + DENSE_BLOCK)
        shared = matrix[start:stop] @ matrix[:stop].T
        union = sizes32[start:stop, None] + sizes32[None, :stop] - shared
        #: A loose test in float32 over the block (counts are whole numbers,
        #: so half a word of slack loses no pair), then the exact score.
        near = shared >= threshold * union - 0.5
        near[:, :start] &= union[:, :start] > 0
        near[:, start:stop] &= np.tri(stop - start, k=-1, dtype=bool) & (union[:, start:stop] > 0)
        rows, js = np.nonzero(near)
        if not len(rows):
            continue
        i = rows + start
        common = shared[rows, js].astype(np.int64)
        # Same text was yielded above, from the first copy only.
        keep = (text_id[i] != text_id[js]) & (common > 0)
        i, js, common = i[keep], js[keep], common[keep]
        score = common / (sizes[i] + sizes[js] - common)
        keep = score >= threshold
        if keep.any():
            yield js[keep].astype(np.int64), i[keep], score[keep]


def _similar_pairs_dense(
    prepared: list[tuple[str, frozenset[str]]], threshold: float
) -> Iterator[tuple[int, int, float]]:
    """Exactly `_similar_pairs`'s pairs, by one matrix product per block.

    Each note is a row of 0s and 1s over the notebook's words; a block of rows
    times the earlier rows' transpose is every pair's shared-word count at
    once (float32 is exact far past any note's length). Same text is a star
    from the first copy, as there, including texts with no words at all.
    """
    for js, i, score in _dense_blocks(prepared, threshold):
        yield from zip(js.tolist(), i.tolist(), score.tolist())


def _use_dense(prepared: list[tuple[str, frozenset[str]]], threshold: float) -> bool:
    """Whether the dense product is cheaper than the prefix filter here.

    ARCH-11 (audit 2026-10-05): `/duplicates` took 86 s on a notebook whose
    5,000 notes shared a vocabulary of a few hundred words, the case where the
    prefix filter compares nearly every pair one at a time in Python.
    """
    work, words = _prefix_work(prepared, threshold)
    dense = len(prepared) ** 2 * words / 2
    return dense <= DENSE_MAX_WORK and dense < work * DENSE_PER_CANDIDATE


def _scan(prepared: list[tuple[str, frozenset[str]]], threshold: float) -> Iterator[tuple[int, int, float]]:
    """The prefix filter, or the dense product when every word is common."""
    if _use_dense(prepared, threshold):
        return _similar_pairs_dense(prepared, threshold)
    return _similar_pairs(prepared, threshold)


def _scan_blocks(prepared: list[tuple[str, frozenset[str]]], threshold: float):  # noqa: ANN202
    """`_scan`'s pairs as arrays `(i, j, score)`, a block at a time."""
    import numpy as np

    if _use_dense(prepared, threshold):
        yield from _dense_blocks(prepared, threshold)
        return
    pairs = _similar_pairs(prepared, threshold)
    while chunk := list(islice(pairs, 65536)):
        i, j, score = zip(*chunk)
        yield np.array(i, dtype=np.int64), np.array(j, dtype=np.int64), np.array(score, dtype=np.float64)


def _groups(prepared: list[tuple[str, frozenset[str]]], threshold: float) -> list[tuple[list[int], float]]:
    """Each group of two or more notes, as (indices, strongest pair's score).

    Union-find over the pairs, so three notes that each match the others are
    one group of three rather than three overlapping pairs. It runs in numpy a
    block at a time (union by smallest index, then full path halving), with
    each note's best score kept rather than every pair's: the strongest pair
    of a group is the best score of one of its members. The pair dictionary
    held 11.5 million entries on 5,000 alike notes (L-world-class-410).
    """
    import numpy as np

    n = len(prepared)
    label = np.arange(n, dtype=np.int64)
    best = np.zeros(n, dtype=np.float64)

    def settle() -> None:
        while True:
            jumped = label[label]
            if np.array_equal(jumped, label):
                return
            label[:] = jumped

    for i, j, score in _scan_blocks(prepared, threshold):
        np.maximum.at(best, i, score)
        np.maximum.at(best, j, score)
        while True:
            settle()
            left, right = label[i], label[j]
            apart = left != right
            if not apart.any():
                break
            high = np.maximum(left[apart], right[apart])
            low = np.minimum(left[apart], right[apart])
            np.minimum.at(label, high, low)
    settle()
    members: dict[int, list[int]] = {}
    for index, root in enumerate(label.tolist()):
        members.setdefault(root, []).append(index)
    return [
        (group, float(best[group].max()))
        for group in members.values()
        if len(group) > 1
    ]


#: How much of each note a duplicate group carries. The screen shows a
#: 160-character preview (`renderDuplicateGroups`), and the merge reads the
#: notes by id; the whole text of up to 500 groups was 8.2 MB in one response
#: on the audit's notebook (ARCH-11).
GROUP_TEXT_CHARS = 1000


def find_duplicates(
    session: Session, threshold: float = DEFAULT_THRESHOLD
) -> list[dict]:
    """Groups of notes that look like the same note, most similar first.

    Private notes are excluded: reporting one as a duplicate would reveal both
    that it exists and roughly what it says.
    """
    entries = list(
        session.scalars(
            select(Entry)
            .where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_private == False,  # noqa: E712
            )
            .order_by(Entry.id)
            .limit(MAX_SCAN)
        )
    )

    prepared = [_prepare(entry.content) for entry in entries]
    groups = []
    for group, top in _groups(prepared, threshold):
        groups.append(
            {
                "similarity": round(top, 3),
                "entries": [
                    {
                        "id": entries[index].id,
                        "content": (entries[index].content or "")[:GROUP_TEXT_CHARS],
                        "created_at": entries[index].created_at.isoformat(),
                        "tags": entries[index].tags,
                    }
                    for index in group  # entries are in id order, so members are too
                ],
            }
        )
    groups.sort(key=lambda g: -g["similarity"])
    return groups
