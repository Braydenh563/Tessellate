"""Scale-test the notebook past a few hundred notes (roadmap ANALYSIS.md §34).

The project's own outside review flagged this directly: "Everything here is
tested against tens of notes and reasoned about for thousands... this is the
failure that arrives silently, as 'the app got slow,' years in." Nothing in
the test suite generates a large notebook, so whether that prediction is
right has never actually been checked. This script does the check: build a
synthetic notebook, then time the operations the review named by name
(`_suggested_neighbours`, `_graph_neighbours`, the `/graph` endpoint) plus
the ordinary search path, against a size nobody's real notebook has hit yet.

Not a pytest test — generating 50k rows takes real time (see the numbers
this prints) and this is a one-off measurement, not something that should
run on every `pytest tests/`. Run by hand:

    PYTHONPATH=src .venv/bin/python scripts/scale_test.py [N]

N defaults to 50,000. Findings get written into ANALYSIS.md §34 by hand
after a run, not generated automatically — the point is a human decision
about whether a number is fine or worth fixing, not a threshold this script
enforces.
"""

from __future__ import annotations

import json
import random
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select  # noqa: E402

from tessellate.ai.embeddings import vector_to_bytes  # noqa: E402
from tessellate.ai import wiring  # noqa: E402,F401
from tessellate.core import deps  # noqa: E402
from tessellate.core.database import Category, EmbeddingRecord, Entry  # noqa: E402

FAKE_BACKEND = "fake:keywords-v1"

# The same four topic buckets tests/fakes.py's FakeEmbeddingService scores
# text into, so a generated notebook has real (not random) cosine structure —
# a random-vector fixture would make every similarity search look artificially
# fast, since nothing would ever cluster.
_TOPIC_WORDS = {
    0: ["recipe", "cook", "kitchen", "dinner", "bake"],
    1: ["project", "deadline", "meeting", "work", "client"],
    2: ["garden", "plant", "soil", "water", "bean"],
    3: ["misc", "note", "idea", "thought", "reminder"],
}
_ALL_WORDS = [w for words in _TOPIC_WORDS.values() for w in words]
TAGS = [f"tag{i}" for i in range(25)]
CATEGORIES = ["Work", "Home", "Garden", "Recipes", "Ideas", "Journal", "Projects"]


def _topic_vector(text: str):
    import numpy as np

    lowered = text.lower()
    vector = np.zeros(4, dtype="float32")
    for axis, words in _TOPIC_WORDS.items():
        if any(word in lowered for word in words):
            vector[axis] = 1.0
    if not vector.any():
        vector[3] = 1.0
    return vector


def build_notebook(session, n: int) -> None:
    rng = random.Random(42)
    categories = [Category(name=name) for name in CATEGORIES]
    session.add_all(categories)
    session.flush()
    category_ids = [c.id for c in categories]

    batch: list[Entry] = []
    entry_ids: list[int] = []
    t0 = time.perf_counter()
    for i in range(n):
        topic = rng.choice(list(_TOPIC_WORDS))
        words = _TOPIC_WORDS[topic] + rng.sample(_ALL_WORDS, 3)
        content = f"Note {i}: " + " ".join(rng.sample(words, len(words)))
        tags = rng.sample(TAGS, rng.choice([0, 0, 1, 1, 2, 3])) if rng.random() < 0.4 else []
        entry = Entry(
            content=content,
            category_id=rng.choice(category_ids),
            tags=__import__("json").dumps(tags),
        )
        batch.append(entry)
        if len(batch) >= 2000:
            session.add_all(batch)
            session.flush()
            entry_ids.extend(e.id for e in batch)
            batch = []
    if batch:
        session.add_all(batch)
        session.flush()
        entry_ids.extend(e.id for e in batch)
    session.commit()
    print(f"  inserted {n} entries in {time.perf_counter() - t0:.1f}s")

    # A thread here, a manual link there — sparse, the way a real notebook is.
    t0 = time.perf_counter()
    thread_count = 0
    for i, entry_id in enumerate(entry_ids):
        if i > 0 and rng.random() < 0.05:
            entry = session.get(Entry, entry_id)
            entry.parent_id = rng.choice(entry_ids[max(0, i - 50):i])
            thread_count += 1
    session.commit()
    print(f"  wired {thread_count} reply threads in {time.perf_counter() - t0:.1f}s")

    from tessellate.core.database import EntryLink

    t0 = time.perf_counter()
    link_count = min(2000, n // 10)
    links = [
        EntryLink(
            source_entry_id=rng.choice(entry_ids), target_entry_id=rng.choice(entry_ids)
        )
        for _ in range(link_count)
    ]
    session.add_all(links)
    session.commit()
    print(f"  added {link_count} manual links in {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    records = []
    for i, entry_id in enumerate(entry_ids):
        content = session.get(Entry, entry_id).content
        vector = _topic_vector(content)
        records.append(
            EmbeddingRecord(
                entry_id=entry_id,
                embedding=vector_to_bytes(vector),
                dim=4,
                model_version=FAKE_BACKEND,
            )
        )
        if len(records) >= 2000:
            session.add_all(records)
            session.flush()
            records = []
    if records:
        session.add_all(records)
    session.commit()
    print(f"  embedded {n} entries in {time.perf_counter() - t0:.1f}s")


def report_storage(session, data_dir: Path, n: int) -> None:
    """Disk cost, not just CPU cost — flagged mid-session as a second axis
    the review's "make the notebook survive being large" point didn't split
    out. A slow query is a bad afternoon; a notebook that silently eats
    gigabytes on a laptop is a support ticket that looks like a disk-full
    crash somewhere unrelated."""
    from sqlalchemy import func

    # Force WAL back into the main file before measuring — otherwise a big
    # write's real cost is split across two files, and the one most people
    # remember to check (tessellate.db) understates it until SQLite decides
    # to checkpoint on its own.
    session.connection().exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    session.commit()

    db_file = data_dir / "tessellate.db"
    db_bytes = db_file.stat().st_size if db_file.exists() else 0
    uploads_dir = data_dir / "uploads"
    uploads_bytes = (
        sum(f.stat().st_size for f in uploads_dir.rglob("*") if f.is_file())
        if uploads_dir.exists()
        else 0
    )

    # This fixture's embeddings are 4 floats (16 bytes) so cosine similarity
    # has real structure to compare against; a real backend is 384-1024 dims
    # (1536-4096 bytes) — a 100-250x difference concentrated entirely in one
    # table, so blanket-scaling the whole file would misprice everything
    # else by the same wrong factor. Measured separately and re-priced.
    embeddings_bytes = session.execute(
        select(func.coalesce(func.sum(func.length(EmbeddingRecord.embedding)), 0))
    ).scalar_one()
    non_embedding_bytes = db_bytes - embeddings_bytes
    real_dim_bytes = 384 * 4  # a common local sentence-transformer's output

    print(f"\nStorage after {n} notes:")
    print(f"  tessellate.db (checkpointed):  {db_bytes / 1e6:9.1f} MB")
    print(f"  — of which embeddings table:  {embeddings_bytes / 1e6:9.1f} MB "
          f"(this fixture's 4-dim vectors)")
    print(f"  uploads/ (attachments):       {uploads_bytes / 1e6:9.1f} MB")
    print(
        f"  with real ~384-dim embeddings instead: "
        f"{(non_embedding_bytes + n * real_dim_bytes) / 1e6:.0f} MB for {n} notes "
        f"({(non_embedding_bytes + n * real_dim_bytes) / n:.0f} bytes/note)"
    )
    scaled_200k = (non_embedding_bytes + n * real_dim_bytes) / n * 200_000
    print(
        f"  extrapolated to 200k real-embedding notes: {scaled_200k / 1e6:.0f} MB "
        f"— attachments (PDFs, images) are unbounded and stored separately in"
        f" uploads/, not part of this per-note rate at all."
    )


def timed(label: str, fn) -> float:
    t0 = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - t0
    size = len(result) if hasattr(result, "__len__") else ""
    print(f"  {label}: {elapsed * 1000:.0f}ms {f'({size} results)' if size != '' else ''}")
    return elapsed


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50_000

    with tempfile.TemporaryDirectory() as tmp:
        deps.init_app_state(data_dir=Path(tmp) / "data")
        from tests.fakes import FakeEmbeddingService, FakeOllama

        deps.override_ai(
            ollama=FakeOllama(running=False), embeddings=FakeEmbeddingService(available=True)
        )
        session = deps.get_db().session()

        print(f"Building a {n}-note notebook...")
        build_notebook(session, n)
        report_storage(session, Path(tmp) / "data", n)

        from tessellate.ai import tools as ai_tools
        from tessellate.api import routes_graph
        from tessellate.entry import manager
        from tessellate.search import search_manager

        # A note with tags AND embeddings AND some links, so every path below
        # actually does the work it's meant to rather than short-circuiting
        # on "nothing to compare".
        tagged_entry = session.scalars(
            select(Entry).where(Entry.tags != "[]").limit(1)
        ).first()

        print(f"\nTiming against {n} notes:")
        timed("manager.list_entries (GET /entries backing call)", lambda: manager.list_entries(session))
        timed(
            "search_manager.retrieve (hybrid keyword+semantic, GET /chat's search)",
            lambda: search_manager.retrieve(
                session, "garden bean water", deps.get_embeddings(), limit=5
            )[0],
        )
        timed(
            "routes_graph.graph() (GET /graph, no similarity)",
            lambda: _body(routes_graph.graph(similarity=False, session=session))["nodes"],
        )
        # O(n^2) by the route's own comment ("it's personal-notebook scale") —
        # already ~1s at 500 notes, so a literal run at 50k would take hours.
        # Off by default (?similarity=true is opt-in); skip the timing past a
        # size where it would dominate the whole script's wall-clock, and say
        # so rather than silently omitting it.
        if n <= 5000:
            timed(
                "routes_graph.graph(similarity=True) (GET /graph?similarity=true, O(n^2))",
                lambda: _body(routes_graph.graph(similarity=True, session=session))["edges"],
            )
        else:
            print(
                f"  routes_graph.graph(similarity=True): SKIPPED at n={n} — "
                f"O(n^2) and off by default, see the 5000-note run for its trend"
            )
        timed(
            "ai.tools._graph_neighbours (one note, the related_notes tool's per-node cost)",
            lambda: ai_tools._graph_neighbours(session, tagged_entry),
        )
        timed(
            "ai.tools._related_notes (depth=2, the actual agent tool call)",
            lambda: ai_tools._related_notes(
                session, {"note_id": tagged_entry.id, "depth": 2}
            ),
        )
        timed(
            "ai.tools._suggested_neighbours (one note, full embedding sweep)",
            lambda: ai_tools._suggested_neighbours(session, tagged_entry, set()),
        )
        session.close()
        deps.reset_app_state()


def _body(response) -> dict:  # noqa: ANN001
    """`/graph` answers with a cached, already-encoded Response, not a dict."""
    return json.loads(response.body)


if __name__ == "__main__":
    main()
