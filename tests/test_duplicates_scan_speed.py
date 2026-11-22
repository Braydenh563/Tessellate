"""The duplicate scan returns what the all-pairs loop returned, without
comparing every pair (measured 196 ms at 60 notes before, 8 to 15 ms after; the
500-note cap took over 25 s, and 2,000 notes now scan in about 0.7 s).
"""

from __future__ import annotations

import random
import time

import pytest

from tessellate.entry import duplicates


def _brute(texts: list[str], threshold: float) -> dict[tuple[int, int], float]:
    """The old all-pairs loop. Notes with identical text are joined to the
    first of them only (a star, not every pair): the same groups and the same
    best score, without k(k-1)/2 pairs for k copies."""
    first_of: dict[str, int] = {}
    out = {}
    for i, text in enumerate(texts):
        first_of.setdefault(duplicates.normalise(text), i)
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            norm = duplicates.normalise(texts[j])
            if duplicates.normalise(texts[i]) == norm and first_of[norm] != i:
                continue
            score = duplicates.similarity(texts[i], texts[j])
            if score >= threshold:
                out[(i, j)] = score
    return out


def _fast(texts: list[str], threshold: float) -> dict[tuple[int, int], float]:
    prepared = [duplicates._prepare(t) for t in texts]
    return {(i, j): s for i, j, s in duplicates._similar_pairs(prepared, threshold)}


@pytest.mark.parametrize("threshold", [0.4, 0.72, 0.9, 1.0])
def test_the_pruned_scan_finds_exactly_the_pairs_the_full_loop_finds(threshold):
    rng = random.Random(11)
    vocab = [f"w{n}" for n in range(60)] + ["a", "I", "the", "and"]
    texts = []
    for _ in range(160):
        if texts and rng.random() < 0.35:
            words = rng.choice(texts).split()
            for _ in range(rng.randint(0, 3)):
                if words:
                    words[rng.randrange(len(words))] = rng.choice(vocab)
            rng.shuffle(words)
        else:
            words = [rng.choice(vocab) for _ in range(rng.randint(0, 14))]
        texts.append(" ".join(words) + rng.choice(["", ".", "!"]))
    texts += ["", "", "a", "A!", "I", "..."]  # no words at all, or only one-letter ones
    assert _fast(texts, threshold) == pytest.approx(_brute(texts, threshold))


def test_two_thousand_notes_scan_in_about_a_second():
    rng = random.Random(5)
    vocab = [f"word{n}" for n in range(3000)] + "the a of and to in for with".split()
    texts = []
    for _ in range(2000):
        if texts and rng.random() < 0.1:
            words = rng.choice(texts).split()
            words[rng.randrange(len(words))] = "edited"
        else:
            words = [rng.choice(vocab) for _ in range(rng.randint(30, 90))]
        texts.append(" ".join(words) + ".")
    prepared = [duplicates._prepare(t) for t in texts]
    # Best of three: one pass on a loaded CI runner read 2.51 s against 0.57 s
    # locally; the fastest pass is the code's cost, the rest is the neighbours.
    elapsed = float("inf")
    for _ in range(3):
        started = time.perf_counter()
        found = list(duplicates._similar_pairs(prepared, duplicates.DEFAULT_THRESHOLD))
        elapsed = min(elapsed, time.perf_counter() - started)
    assert found  # the near-copies were seeded in
    assert elapsed < 2.0, f"{elapsed:.2f}s"


def _dense(texts: list[str], threshold: float) -> dict[tuple[int, int], float]:
    prepared = [duplicates._prepare(t) for t in texts]
    return {(i, j): s for i, j, s in duplicates._similar_pairs_dense(prepared, threshold)}


@pytest.mark.parametrize("threshold", [0.4, 0.72, 0.9, 1.0])
def test_the_dense_scan_finds_exactly_the_pairs_the_full_loop_finds(threshold):
    """ARCH-11 (audit 2026-10-05): the matrix product is the same answer."""
    rng = random.Random(23)
    vocab = [f"w{n}" for n in range(40)] + ["a", "I", "the", "and"]
    texts = []
    for _ in range(200):
        if texts and rng.random() < 0.35:
            words = rng.choice(texts).split()
            rng.shuffle(words)
        else:
            words = [rng.choice(vocab) for _ in range(rng.randint(0, 14))]
        texts.append(" ".join(words) + rng.choice(["", ".", "!"]))
    texts += ["", "", "a", "A!", "I", "...", "same words", "same words", "words same"]
    assert _dense(texts, threshold) == pytest.approx(_brute(texts, threshold))


def test_a_small_vocabulary_takes_the_dense_scan_and_stays_quick():
    """The audit's notebook: thousands of notes over a few hundred words, where
    no word is rare and the prefix filter compares nearly every pair in
    Python (86 s at 5,000 notes on a live server). 1,500 such notes took
    14.5 s through the prefix filter on the box that measured it."""
    rng = random.Random(3)
    vocab = [f"w{n}" for n in range(300)]
    texts = [" ".join(rng.choice(vocab) for _ in range(140)) for _ in range(1500)]
    texts.append(texts[7] + " extra")
    prepared = [duplicates._prepare(t) for t in texts]
    started = time.perf_counter()
    found = list(duplicates._scan(prepared, duplicates.DEFAULT_THRESHOLD))
    elapsed = time.perf_counter() - started
    assert (7, 1500) in {(i, j) for i, j, _s in found}
    assert elapsed < 4.0, f"{elapsed:.2f}s"


def test_a_long_tail_vocabulary_keeps_the_prefix_filter():
    rng = random.Random(5)
    vocab = [f"word{n}" for n in range(3000)]
    prepared = [duplicates._prepare(" ".join(rng.choice(vocab) for _ in range(40))) for _ in range(500)]
    work, words = duplicates._prefix_work(prepared, duplicates.DEFAULT_THRESHOLD)
    assert len(prepared) ** 2 * words / 2 >= work * duplicates.DENSE_PER_CANDIDATE


#: L-world-class-410 (2026-11-21): a note's own word, one no other note holds
#: ("Note 4123"), can never be shared, yet it counted in the dense scan's
#: vocabulary. Each note's number put 5,000 notes over 25 common words past
#: the dense budget, so the prefix filter compared nearly every pair in
#: Python: `GET /tidy` (the dashboard's Tidy badge) took 70 s and the
#: server's memory climbed to 2.1 GB. The matrix is built over shared words.
def _numbered(count: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    vocab = "harbor launch plan garden bread river budget meeting travel recipe draft notes ideas".split()
    return [f"note{n} " + " ".join(rng.choice(vocab) for _ in range(rng.randint(3, 30))) for n in range(count)]


@pytest.mark.parametrize("threshold", [0.4, 0.72, 0.9, 1.0])
def test_words_held_by_one_note_change_no_dense_answer(threshold):
    texts = _numbered(160, 11) + ["solo", "solo", "", "alone words here"]
    assert _dense(texts, threshold) == pytest.approx(_brute(texts, threshold))


def test_a_word_of_its_own_on_every_note_keeps_the_dense_scan():
    prepared = [duplicates._prepare(t) for t in _numbered(1500, 13)]
    work, words = duplicates._prefix_work(prepared, duplicates.DEFAULT_THRESHOLD)
    #: Only the 13 shared words make columns; the 1,500 numbers do not.
    assert words == 13
    started = time.perf_counter()
    list(duplicates._scan(prepared, duplicates.DEFAULT_THRESHOLD))
    assert time.perf_counter() - started < 4.0


def _reference_groups(prepared, threshold):
    """The old grouping: a union-find over every pair, best score per group."""
    parent = list(range(len(prepared)))

    def root(node):
        while parent[node] != node:
            node = parent[node]
        return node

    pairs = list(duplicates._scan(prepared, threshold))
    for i, j, _score in pairs:
        parent[root(i)] = root(j)
    members, top = {}, {}
    for index in range(len(prepared)):
        members.setdefault(root(index), []).append(index)
    for i, _j, score in pairs:
        top[root(i)] = max(top.get(root(i), 0.0), score)
    return sorted((group, top[root(group[0])]) for group in members.values() if len(group) > 1)



def _grouped(prepared, threshold):
    """Groups of two or more and each group's best score, from `_groups`. Its
    signature moved in the base merge (array blocks in, roots and scores out,
    L-world-class-872); what is asserted of it here is unchanged."""
    roots, top = duplicates._groups(len(prepared), duplicates._scan_blocks(prepared, threshold))
    members = {}
    for index, group in enumerate(roots):
        members.setdefault(group, []).append(index)
    return [(group, top[root]) for root, group in members.items() if len(group) > 1]


@pytest.mark.parametrize("threshold", [0.4, 0.72, 1.0])
@pytest.mark.parametrize("texts", ["numbered", "mixed"])
def test_groups_match_a_union_find_over_every_pair(threshold, texts):
    """L-world-class-410: groups and their best score are the old answer on
    both the dense path (numbered) and the prefix filter (mixed)."""
    if texts == "numbered":
        sample = _numbered(300, 5) + ["solo", "solo", ""]
    else:
        rng = random.Random(9)
        words = [f"w{n}" for n in range(400)]
        sample = [" ".join(rng.sample(words, rng.randint(2, 6))) for _ in range(300)] + ["x y", "x y z"]
    prepared = [duplicates._prepare(t) for t in sample]
    got = sorted(_grouped(prepared, threshold))
    assert [g for g, _s in got] == [g for g, _s in _reference_groups(prepared, threshold)]
    assert [s for _g, s in got] == pytest.approx([s for _g, s in _reference_groups(prepared, threshold)])


def test_millions_of_alike_pairs_group_in_seconds():
    """5,000 notes over 25 shared words had 11.5 million qualifying pairs and
    a 51 s `/tidy`; 2,500 such notes must group well inside 10 s."""
    rng = random.Random(3)
    words = [f"w{n}" for n in range(25)]
    sample = [f"note{n} " + " ".join(rng.sample(words, rng.randint(8, 14))) for n in range(2500)]
    prepared = [duplicates._prepare(t) for t in sample]
    started = time.perf_counter()
    groups = _grouped(prepared, 0.4)
    assert time.perf_counter() - started < 10.0
    assert sum(len(g) for g, _s in groups) > 2000
