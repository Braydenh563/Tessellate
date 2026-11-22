"""Row 6's before-and-after: paragraph vectors on a seeded notebook.

    PYTHONPATH=src .venv/bin/python scratchpad/chunk_retrieval_bench.py [notes]

No torch: a hashed bag-of-words embedder (384 signed buckets, sublinear term
frequency), which has the property that matters here and nothing more: a
note's vector is the average of what it says, so one paragraph in eight is
an eighth of it. A real model dilutes the same way; how much better its
paragraph scores are than these is not measured here.

The notebook: notes of one to eight paragraphs, each paragraph on one of 40
topics (twenty topic words each) padded with filler shared by every note,
and three words of its own (a name, a place, a thing) that no other
paragraph has. A query is two of a paragraph's own words and four of its
topic's, asked of a long note's middle paragraph: the case one vector per
note loses, since short notes on the same topic share the four.

Reports recall@1, recall@5 and MRR of `semantic_search`, its median time,
and the time to store one eight-paragraph note, with `chunks.ENABLED` off
(the note vector alone, as before row 6) and on.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
import tempfile
import time
import zlib
from pathlib import Path

import numpy as np

from tessellate.ai.embeddings import EmbeddingService
from tessellate.ai import wiring  # noqa: F401
from tessellate.core import deps
from tessellate.core.database import Entry
from tessellate.search import chunks, search_manager

DIM = 384


class HashEmbeddings(EmbeddingService):
    def __init__(self) -> None:
        super().__init__(model_manager=None, ollama_client=None)  # type: ignore[arg-type]

    def backend_id(self) -> str:
        return "bench:hash-384"

    def active_model(self) -> str:
        return "hash-384"

    def is_ready(self) -> bool:
        return True

    def embed_text(self, text: str):
        vector = np.zeros(DIM, dtype="float32")
        counts: dict[str, int] = {}
        for word in text.lower().split():
            word = word.strip(".,:;#")
            if word:
                counts[word] = counts.get(word, 0) + 1
        for word, n in counts.items():
            h = zlib.crc32(word.encode())
            vector[h % DIM] += (1.0 if (h >> 16) & 1 else -1.0) * (1.0 + np.log(n))
        return vector


def corpus(n_notes: int, rng: random.Random):
    topics = [[f"topic{t}word{i}" for i in range(20)] for t in range(40)]
    filler = [f"common{i}" for i in range(300)]
    notes, targets = [], []
    unique = 0
    for n in range(n_notes):
        k = rng.choice([1, 1, 2, 3, 5, 8])
        paragraphs = []
        for p in range(k):
            topic = rng.randrange(40)
            own = [f"name{unique}", f"place{unique}", f"thing{unique}"]
            unique += 1
            words = rng.choices(topics[topic], k=18) + rng.choices(filler, k=22) + own
            rng.shuffle(words)
            paragraphs.append(" ".join(words) + ".")
            if k >= 5 and 0 < p < k - 1:
                targets.append((n, topic, own))
        notes.append(f"Note {n}\n\n" + "\n\n".join(paragraphs))
    queries = []
    for n, topic, own in rng.sample(targets, min(300, len(targets))):
        words = rng.sample(own, 2) + rng.sample(topics[topic], 4)
        queries.append((n, " ".join(words)))
    return notes, queries


def run(n_notes: int) -> None:
    rng = random.Random(7)
    data = Path(tempfile.mkdtemp(prefix="chunkbench-"))
    deps.init_app_state(data_dir=data)
    service = HashEmbeddings()
    deps.override_ai(embeddings=service)
    session = deps.get_db().session()
    notes, queries = corpus(n_notes, rng)
    ids = []
    for content in notes:
        entry = Entry(content=content, tags=json.dumps([]))
        session.add(entry)
        session.flush()
        ids.append(entry.id)
    session.commit()
    started = time.perf_counter()
    for entry in session.query(Entry).all():
        service.store_for_entry(session, entry)
    print(f"{n_notes} notes stored in {time.perf_counter() - started:.1f}s; "
          f"{session.execute(__import__('sqlalchemy').text('select count(*) from chunk_vectors')).scalar()} paragraph rows")

    long_note = max(notes, key=lambda c: c.count("\n\n"))
    probe = session.get(Entry, ids[notes.index(long_note)])

    for enabled in (False, True):
        chunks.ENABLED = enabled
        chunks.reset()
        ranks, times = [], []
        search_manager.semantic_search(session, "warm", service, limit=10)
        for n, query in queries:
            t0 = time.perf_counter()
            found = search_manager.semantic_search(session, query, service, limit=10)
            times.append((time.perf_counter() - t0) * 1000)
            order = [entry.id for entry, _score in (found or [])]
            ranks.append(order.index(ids[n]) + 1 if ids[n] in order else None)
        r1 = sum(1 for r in ranks if r == 1) / len(ranks)
        r5 = sum(1 for r in ranks if r and r <= 5) / len(ranks)
        mrr = sum(1 / r for r in ranks if r) / len(ranks)
        save = []
        for _ in range(5):
            if not enabled:
                original = service._store_chunks
                service._store_chunks = lambda *a, **k: 0  # type: ignore[method-assign]
            probe.content = probe.content + " edit"
            session.commit()
            t0 = time.perf_counter()
            service.store_for_entry(session, probe)
            save.append((time.perf_counter() - t0) * 1000)
            if not enabled:
                service._store_chunks = original  # type: ignore[method-assign]
        label = "paragraphs on " if enabled else "note vector only"
        print(
            f"{label}: recall@1 {r1:.2f}  recall@5 {r5:.2f}  MRR {mrr:.3f}  "
            f"search median {statistics.median(times):.2f} ms (p95 {sorted(times)[int(len(times) * .95)]:.2f})  "
            f"store one long note {statistics.median(save):.1f} ms  ({len(queries)} queries)"
        )
    session.close()


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 1000)
