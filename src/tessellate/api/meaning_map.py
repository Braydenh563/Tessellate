"""What makes the Map of meaning read as a map (owner, 2026-11-22: "scattered
dots, almost no labels, no links, no sense of what it means").

`routes_graph_projection` flattens vectors to a plane; this module adds what a
map needs around that plane, all of it deterministic, local and numpy only:

* `word_vectors`: with no embedding model installed there are no stored
  vectors, so every note used to wait in a row under the map. The notes' own
  words (hashed TF-IDF) stand in, and the route says so (`source: "words"`).
* `pull_together`: after the PCA, each note is drawn a little toward its
  nearest neighbours by meaning, so a topic's notes sit as a group and two
  topics a PCA flattened on top of each other come apart.
* `ties`: each note's nearest two by meaning, drawn faintly so the map has
  lines to follow, as a link does.
* `clusters`: groups on the drawn plane, each named by the words its notes
  share and the rest do not.
"""

from __future__ import annotations

import math
import zlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

DIMS = 1024
#: A tie needs this cosine: words share little (a hashed bag of words), a
#: model's cosine for two unrelated short notes already sits near 0.4.
TIE_FLOOR = {"words": 0.12, "model": 0.55}
#: Neighbours that pull a note, rounds of pulling, and how hard each round.
PULL_K, PULL_ROUNDS, PULL_BY = 5, 8, 0.6
#: A cluster smaller than this is not named: a label over two dots is noise.
MIN_CLUSTER = 3
MAX_CLUSTERS = 12
LABEL_WORDS = 3


def _words(text: str) -> list[str]:
    from tessellate.ai import lexical_filing

    return lexical_filing.tokens(lexical_filing.clean(text))


def word_vectors(texts: dict[int, str]) -> dict[int, np.ndarray]:
    """`{id: unit vector}` from the notes' words: a hashed bag, each word
    weighted by how rare it is across the notes. A word only one note has
    cannot make two notes alike, so it is left out."""
    import numpy as np

    bags = {i: _words(t) for i, t in texts.items()}
    df: dict[str, int] = {}
    for words in bags.values():
        for w in set(words):
            df[w] = df.get(w, 0) + 1
    n = max(len(bags), 1)
    out: dict[int, np.ndarray] = {}
    for i, words in bags.items():
        v = np.zeros(DIMS, dtype=np.float32)
        counts: dict[str, int] = {}
        for w in words:
            if df[w] >= 2:
                counts[w] = counts.get(w, 0) + 1
        for w, c in counts.items():
            weight = (1 + math.log(c)) * (math.log((1 + n) / (1 + df[w])) + 1)
            v[zlib.crc32(w.encode()) % DIMS] += weight
        norm = float(np.linalg.norm(v))
        out[i] = v / norm if norm else v
    return out


def neighbours(matrix: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Each row's `k` most alike other rows by cosine, best first:
    `(indices, similarities)`, both `n x k`. Blocks of rows, so 5,000 notes of
    384 floats never hold the whole n x n table."""
    import numpy as np

    n = len(matrix)
    k = max(0, min(k, n - 1))
    if k == 0:
        return np.zeros((n, 0), dtype=np.int64), np.zeros((n, 0), dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    unit = matrix / np.where(norms == 0, 1, norms)
    idx = np.zeros((n, k), dtype=np.int64)
    sim = np.zeros((n, k), dtype=np.float32)
    for start in range(0, n, 512):
        block = unit[start : start + 512] @ unit.T
        rows = np.arange(block.shape[0])
        block[rows, rows + start] = -2.0
        top = np.argpartition(-block, k - 1, axis=1)[:, :k]
        scores = np.take_along_axis(block, top, axis=1)
        # Ties by index, so the same notes always give the same picture.
        order = np.argsort(-scores, axis=1, kind="stable")
        idx[start : start + 512] = np.take_along_axis(top, order, axis=1)
        sim[start : start + 512] = np.take_along_axis(scores, order, axis=1)
    return idx, sim


def pull_together(plane: np.ndarray, idx: np.ndarray, sim: np.ndarray) -> np.ndarray:
    """Each note moved part of the way to the mean of its neighbours that mean
    something alike (a cosine above zero), a few rounds."""
    import numpy as np

    if idx.shape[1] == 0:
        return plane
    weight = np.clip(sim, 0, None)
    total = weight.sum(axis=1, keepdims=True)
    held = (total[:, 0] > 0)[:, None]
    share = weight / np.where(total == 0, 1, total)
    out = plane.copy()
    for _ in range(PULL_ROUNDS):
        mean = (out[idx] * share[:, :, None]).sum(axis=1)
        out = np.where(held, (1 - PULL_BY) * out + PULL_BY * mean, out)
    return out


def ties(ids: list[int], idx: np.ndarray, sim: np.ndarray, source: str, cap: int = 3000) -> list[list]:
    """`[[a, b, score]]`: each note's nearest two by meaning above the floor,
    a pair once, the closest `cap` kept."""
    seen: dict[tuple[int, int], float] = {}
    floor = TIE_FLOOR[source]
    for row in range(len(ids)):
        for col in range(min(2, idx.shape[1])):
            score = float(sim[row, col])
            if score < floor:
                break
            a, b = sorted((ids[row], ids[int(idx[row, col])]))
            seen[(a, b)] = max(seen.get((a, b), 0.0), score)
    best = sorted(seen.items(), key=lambda kv: (-kv[1], kv[0]))[:cap]
    return [[a, b, round(s, 3)] for (a, b), s in best]


def _kmeans(points: np.ndarray, k: int) -> np.ndarray:
    """Labels from a farthest-first start and a dozen rounds: no randomness."""
    import numpy as np

    centres = [points[0]]
    for _ in range(k - 1):
        gap = np.min([((points - c) ** 2).sum(axis=1) for c in centres], axis=0)
        centres.append(points[int(np.argmax(gap))])
    centres = np.array(centres)
    labels = np.zeros(len(points), dtype=np.int64)
    for _ in range(12):
        labels = np.argmin(((points[:, None, :] - centres[None]) ** 2).sum(axis=2), axis=1)
        for c in range(k):
            if (labels == c).any():
                centres[c] = points[labels == c].mean(axis=0)
    return labels


def _name(members: list[int], bags: list[set[str]], df: dict[str, int]) -> str:
    """The words most of a group's notes say and few other notes do."""
    inside: dict[str, int] = {}
    for r in members:
        for w in bags[r]:
            inside[w] = inside.get(w, 0) + 1
    scored = []
    for w, count in inside.items():
        if count < 2 or w.isdigit():
            continue
        # How much of the group says it, and how much of what says it is the group.
        scored.append((-(count / len(members)) * (count / df[w]) ** 0.5 * math.log(1 + count), w))
    scored.sort()
    return ", ".join(w for _, w in scored[:LABEL_WORDS])


def clusters(ids: list[int], plane: np.ndarray, texts: dict[int, str]) -> list[dict]:
    """Groups of notes that sit together on the drawn plane, each named by the
    words most of its notes say and the rest of the notebook seldom does."""
    import numpy as np

    n = len(ids)
    if n < MIN_CLUSTER * 2:
        return []
    k = max(2, min(MAX_CLUSTERS, round(math.sqrt(n / 3))))
    labels = _kmeans(np.asarray(plane, dtype=np.float64), k)
    bags = [set(_words(texts.get(i, ""))) for i in ids]
    df: dict[str, int] = {}
    for bag in bags:
        for w in bag:
            df[w] = df.get(w, 0) + 1
    out = []
    for c in range(k):
        members = [r for r in range(n) if labels[r] == c]
        label = _name(members, bags, df) if len(members) >= MIN_CLUSTER else ""
        if label:
            out.append({"id": f"m{c}", "label": label, "ids": [ids[r] for r in members]})
    out.sort(key=lambda g: (-len(g["ids"]), g["id"]))
    return out
