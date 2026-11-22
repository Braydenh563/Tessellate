"""L-world-class-872: the duplicate scan on 5,000 notes that share their words
took 31 s, a Python step for each of 12.5 million matching pairs. The pairs
now come as array blocks and only a pair joining two groups takes a Python
step. Counted, not timed: the blocks, the per-pair path left unused, and the
groups equal to a plain union-find over every pair."""

from __future__ import annotations

import random

import pytest

from tessellate.entry import duplicates


def _reference(prepared, threshold):
    """The groups a one-pair-at-a-time union-find makes, as sets of indexes."""
    parent = list(range(len(prepared)))

    def root(x):
        while parent[x] != x:
            x = parent[x]
        return x

    best: dict[int, float] = {}
    for i in range(len(prepared)):
        for j in range(i):
            s = duplicates._score(prepared[i], prepared[j])
            if s >= threshold:
                a, b = root(i), root(j)
                top = max(s, best.pop(a, 0.0), best.get(b, 0.0))
                if a != b:
                    parent[a] = b
                best[b] = top
    groups: dict[int, set] = {}
    for x in range(len(prepared)):
        groups.setdefault(root(x), set()).add(x)
    return {frozenset(g): round(best[r], 9) for r, g in groups.items() if len(g) > 1}


def _texts(n, words, seed):
    rng = random.Random(seed)
    vocab = [f"w{k}" for k in range(words)]
    out = [" ".join(rng.sample(vocab, rng.randint(1, 8))) for _ in range(n)]
    out += out[: n // 10]  # exact copies
    return out + ["", "!!"]


@pytest.mark.parametrize("words", [12, 400])
def test_the_groups_equal_a_union_find_over_every_pair(words):
    prepared = [duplicates._prepare(t) for t in _texts(300, words, words)]
    roots, top = duplicates._groups(len(prepared), duplicates._scan_blocks(prepared, duplicates.DEFAULT_THRESHOLD))
    got: dict[int, set] = {}
    for x, r in enumerate(roots):
        got.setdefault(r, set()).add(x)
    mine = {frozenset(g): round(top[r], 9) for r, g in got.items() if len(g) > 1}
    assert mine == _reference(prepared, duplicates.DEFAULT_THRESHOLD)


def test_a_notebook_sharing_its_words_takes_blocks_not_pairs(monkeypatch):
    rng = random.Random(7)
    vocab = [f"w{k}" for k in range(16)]
    prepared = [duplicates._prepare(" ".join(rng.sample(vocab, 14))) for _ in range(2_000)]
    monkeypatch.setattr(duplicates, "_similar_pairs", lambda *a: pytest.fail("the per-pair path"))
    blocks = list(duplicates._scan_blocks(prepared, duplicates.DEFAULT_THRESHOLD))
    pairs = sum(len(s) for _l, _e, s in blocks)
    assert pairs > 100_000  # the dense case the row is about
    assert len(blocks) <= len(prepared) // duplicates.DENSE_SLICE + 2


def test_a_word_of_its_own_in_every_note_keeps_the_dense_scan(monkeypatch):
    """The /tidy case: near-identical notes, each with one word no other note
    holds. Those words add nothing to a shared count, so they take no column
    and the scan stays the matrix product (29.7 s to 1.7 s at 5,000 notes)."""
    shared = [f"w{k}" for k in range(30)]
    texts = [" ".join(shared + [f"own{i}"]) for i in range(600)]
    prepared = [duplicates._prepare(t) for t in texts]
    assert len(duplicates._vocabulary(prepared)) == 30
    monkeypatch.setattr(duplicates, "_similar_pairs", lambda *a: pytest.fail("the per-pair path"))
    roots, top = duplicates._groups(len(prepared), duplicates._scan_blocks(prepared, duplicates.DEFAULT_THRESHOLD))
    assert len(set(roots)) == 1
    assert top[roots[0]] == pytest.approx(30 / 32)


@pytest.mark.parametrize("words", [12, 400])
def test_one_off_words_still_count_in_the_score(words):
    texts = _texts(200, words, words + 1)
    texts = [f"{t} solo{i}" if i % 3 == 0 else t for i, t in enumerate(texts)]
    prepared = [duplicates._prepare(t) for t in texts]
    got: dict[int, set] = {}
    roots, top = duplicates._groups(len(prepared), duplicates._dense_blocks(prepared, duplicates.DEFAULT_THRESHOLD))
    for x, r in enumerate(roots):
        got.setdefault(r, set()).add(x)
    mine = {frozenset(g): round(top[r], 9) for r, g in got.items() if len(g) > 1}
    assert mine == _reference(prepared, duplicates.DEFAULT_THRESHOLD)
