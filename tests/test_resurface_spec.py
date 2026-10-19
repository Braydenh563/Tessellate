"""Resurfacing (WORLD_CLASS_PLAN 15, I4): the spec. Strict-xfail until built.

Three cards a day: notes that are fading (old, unlinked, unopened) and close
to what the person is doing now. The fading score is computed nightly into
`note_scores`; the request-time step multiplies by cosine to a context
vector and drops anything marked "never again" (a correction, I7).
"""

from __future__ import annotations

#: Kept as a header rather than a marker: every one of these passes now
#: (`ai/resurface.py`, `api/routes_resurface.py`), and the file stays the
#: contract they have to keep passing against.
BUILT = "WORLD_CLASS 15 I4: resurfacing, built 2026-09-12"


def test_an_old_unlinked_unopened_note_outranks_a_linked_recent_one(session):
    from datetime import datetime, timedelta

    from tessellate.ai import resurface
    from tessellate.entry import manager

    old = manager.create_entry(session, "interview prep notes from the spring", tags=[])
    old.created_at = datetime.now() - timedelta(days=120)
    fresh = manager.create_entry(session, "notes from today's standup", tags=[])
    other = manager.create_entry(session, "a note linked to today's", tags=[])
    # `create_link` is what this is called; the spec guessed a name.
    manager.create_link(session, fresh, other)
    fresh.access_count = 5
    session.commit()
    resurface.compute_scores(session)
    ranked = resurface.ranked(session, limit=10)
    assert [e.id for e in ranked].index(old.id) < [e.id for e in ranked].index(fresh.id)


def test_the_context_vector_reorders_the_top_three(session, fake_embeddings):
    from tessellate.ai import resurface
    from tessellate.entry import manager

    # `b` shares a tag with `a` and `c` shares nothing. Before 2026-10-03 this
    # asserted an unrelated `b` came back with no vectors at all; that was the
    # measured bug ("close to this" listing the newest notes), so with no
    # vector to measure by, close now means joined, and `c` is left out.
    a = manager.create_entry(session, "sourdough starter feeding schedule", tags=["baking"])
    b = manager.create_entry(session, "hiking boots for the weekend trip", tags=["Baking"])
    c = manager.create_entry(session, "tax return paperwork", tags=[])
    session.commit()
    resurface.compute_scores(session)
    with_context = resurface.for_context(session, context_entry_id=a.id, limit=3)
    assert with_context and with_context[0].id != a.id  # never the context note itself
    assert b.id in [e.id for e in with_context]
    assert c.id not in [e.id for e in with_context]


def test_never_again_is_honoured_across_restarts(ai_client):
    for i in range(12):
        ai_client.post("/entries", json={"content": f"an old idea number {i} about gardening"})
    ai_client.post("/resurface/compute")
    first = ai_client.get("/resurface").json()["items"]
    assert len(first) == 3
    ai_client.post("/learned/corrections", json={"kind": "dismiss_resurface", "subject": {"entry_id": first[0]["id"]}})
    ai_client.post("/resurface/compute")
    later = ai_client.get("/resurface").json()["items"]
    assert first[0]["id"] not in [item["id"] for item in later]


def test_the_daily_three_are_stable_within_a_day_and_change_across_days(ai_client):
    for i in range(30):
        ai_client.post("/entries", json={"content": f"idea {i} about something forgotten"})
    ai_client.post("/resurface/compute")
    today = ai_client.get("/resurface?as_of=2026-09-08").json()["items"]
    again = ai_client.get("/resurface?as_of=2026-09-08").json()["items"]
    tomorrow = ai_client.get("/resurface?as_of=2026-09-09").json()["items"]
    assert today == again
    assert today != tomorrow


def test_a_small_notebook_returns_nothing_rather_than_the_same_three_forever(ai_client):
    for i in range(5):
        ai_client.post("/entries", json={"content": f"note {i}"})
    ai_client.post("/resurface/compute")
    assert ai_client.get("/resurface").json()["items"] == []


def test_the_endpoint_is_fast_because_scores_are_precomputed(ai_client):
    import time

    for i in range(500):
        ai_client.post("/entries", json={"content": f"idea {i} about topic {i % 20}"})
    ai_client.post("/resurface/compute")
    # The embedding warm-up thread (ai/embeddings.py `start_warmup`) backfills
    # the 500 notes and builds the vector matrix in the background, and while
    # it runs it holds the GIL in long stretches: the first read then measured
    # 75 to 170ms against 12 to 25ms once it had finished. That is the
    # warm-up's cost, not this endpoint's, so the clock starts after it.
    import threading

    for thread in threading.enumerate():
        if thread.name == "embedding-warmup":
            thread.join(timeout=30)
    start = time.perf_counter()
    reply = ai_client.get("/resurface")
    elapsed = time.perf_counter() - start
    assert reply.status_code == 200 and len(reply.json()["items"]) == 3
    assert elapsed < 0.05


def test_a_first_read_computes_its_own_scores(client):
    """**The feature has to work with the AI switched off.**

    The night shift that was supposed to fill `note_scores`
    (`ai/autonomous.py`) only runs when the AI is on, so on a notebook with
    no model this panel would have shown nothing, for ever, with a backend
    that tests green: the "feature that never ran once" shape. The read
    refreshes the table itself when it is missing or a day old.
    """
    for index in range(12):
        client.post("/entries", json={"content": f"Note {index}\n\nSomething written down."})

    # No POST /resurface/compute anywhere in this test, deliberately.
    items = client.get("/resurface").json()["items"]
    assert len(items) == 3
    assert all(item["title"] for item in items)
    # The card says why it was chosen, in facts a person can check.
    assert all("opened" in item["reason"] for item in items)


def test_a_second_read_does_not_recompute(client):
    """The scan is the expensive half and must not be on every request."""
    from tessellate.ai import resurface

    for index in range(12):
        client.post("/entries", json={"content": f"Note {index}\n\nSomething written down."})
    client.get("/resurface")

    from tessellate.core import deps

    with deps.get_db().session() as session:
        assert resurface.ensure_fresh(session) is False


def test_the_ranking_route_is_the_order_not_the_daily_three(client):
    """The Notes tab's "Forgotten first" sort wants the order itself.

    `GET /resurface` answers "what are today's three", which is a rotation
    over the top of the ranking and is deliberately stable within a day.
    Folding a sort into it by raising its limit would have given one of the
    two the other's behaviour, so the ranking has its own route.
    """
    made = [
        client.post("/entries", json={"content": f"Note {index}\n\nWritten down."}).json()["id"]
        for index in range(14)
    ]

    rows = client.get("/resurface/all", params={"limit": 500}).json()["items"]
    assert len(rows) == len(made)
    assert {row["id"] for row in rows} == set(made)
    # Every row carries the reason, so a list can say why a note is where it
    # is without asking again per note.
    assert all(row["reason"] for row in rows)

    # No rotation: the same call twice is the same order.
    again = client.get("/resurface/all", params={"limit": 500}).json()["items"]
    assert [row["id"] for row in again] == [row["id"] for row in rows]


def test_a_dismissed_note_leaves_the_forgotten_order(client):
    """"Never again" is honoured by the sort as well as by the panel, or the
    note it was said about comes straight back at the top of a list."""
    for index in range(14):
        client.post("/entries", json={"content": f"Note {index}\n\nWritten down."})

    first = client.get("/resurface/all").json()["items"][0]["id"]
    client.post(
        "/learned/corrections",
        json={"kind": "dismiss_resurface", "subject": {"entry_id": first}},
    )
    after = [row["id"] for row in client.get("/resurface/all").json()["items"]]
    assert first not in after


def test_never_again_outlives_six_hundred_later_corrections(app_state):
    """**"Never again" has to mean never**, and it used to mean "until you
    file six hundred notes".

    `learning.corrections` takes the newest 500 rows and `boosts` asked for
    every kind at once, keeping the family's afterwards. So a dismissal
    followed by enough re-files fell outside the window, and the card it was
    said about came back. The corrections table only ever grows, so this was a
    matter of time rather than of scale.
    """
    from tessellate.ai import learning, resurface
    from tessellate.core import deps
    from tessellate.core.database import Entry

    db = deps.get_db()
    with db.session() as session:
        note = Entry(content="A note to be dismissed")
        session.add(note)
        session.commit()
        note_id = note.id

        learning.record(session, kind="dismiss_resurface", subject={"entry_id": note_id})
        for _ in range(600):
            learning.record(
                session, kind="refile", subject={"entry_id": note_id},
                from_value="Inbox", to_value="Recipes",
            )
        session.commit()

        assert (note_id,) in learning.boosts(session, kind="resurface"), (
            "the dismissal fell out of the read window, so the card comes back"
        )
        # And the ranking honours it: the note is gone from the list itself.
        assert note_id not in {entry.id for entry in resurface.ranked(session, limit=50)}


def test_the_context_ranking_survives_real_embedding_rows(session, fake_embeddings):
    """The route crashed on its first real call, and nothing here saw it.

    `for_context` read `row.vector` off an `EmbeddingRecord`, whose column is
    `embedding`. The test above has covered this function since it was built
    and passed the whole time, because with no `EmbeddingRecord` rows in the
    database the dict comprehension that touches the attribute never runs a
    single iteration: the bug lived inside a loop body nothing had ever
    entered. `GET /resurface/near/{entry_id}` had no caller either
    (INBOX 261), so the first request ever made to it, from the panel wired
    this morning, answered 500 with `AttributeError: 'EmbeddingRecord' object
    has no attribute 'vector'`.

    So this test writes the rows. It is the cheap shape of CLAUDE.md's second
    review question, "a feature that never ran once", applied to a code path
    rather than to a feature.
    """
    import struct

    from tessellate.ai import resurface
    from tessellate.core.database import EmbeddingRecord
    from tessellate.entry import manager

    anchor = manager.create_entry(session, "sourdough starter feeding schedule", tags=[])
    near = manager.create_entry(session, "sourdough loaf crumb and hydration", tags=[])
    far = manager.create_entry(session, "hiking boots for the weekend trip", tags=[])
    session.commit()

    #: Three unit vectors chosen by hand rather than embedded, so "near" and
    #: "far" are facts of the test rather than of whatever the fake service
    #: happens to return: `near` is the anchor exactly, `far` is orthogonal.
    vectors = {anchor.id: [1.0, 0.0], near.id: [1.0, 0.0], far.id: [0.0, 1.0]}
    for entry_id, values in vectors.items():
        session.add(
            EmbeddingRecord(
                entry_id=entry_id,
                embedding=struct.pack(f"<{len(values)}f", *values),
                dim=len(values),
                model_version="test",
            )
        )
    session.commit()
    resurface.compute_scores(session)

    got = resurface.for_context(session, context_entry_id=anchor.id, limit=2)
    ids = [entry.id for entry in got]
    assert anchor.id not in ids, "never the context note itself"
    assert near.id in ids
    assert ids.index(near.id) < ids.index(far.id) if far.id in ids else True


def test_the_near_route_answers_rather_than_raising(ai_client):
    """The route itself, end to end, because a helper that works and a route
    that 500s are different facts: this is the one the panel calls."""
    made = [
        ai_client.post("/entries", json={"content": f"a note about retries number {i}"}).json()
        for i in range(12)
    ]
    ai_client.post("/resurface/compute")
    answer = ai_client.get(f"/resurface/near/{made[0]['id']}")
    assert answer.status_code == 200, answer.text
    items = answer.json()["items"]
    assert made[0]["id"] not in [item["id"] for item in items]


def test_near_without_vectors_is_related_or_nothing(client):
    """Measured 2026-10-03 with no embedding backend: "Forgotten, and close
    to this" listed drafts and simply the newest notes, nothing related to
    the note open. Without a vector, close means a link either way, shared
    tags or the same (real) category; with none of those, nothing."""
    anchor = client.post("/entries", json={"content": "sourdough starter", "tags": ["baking"], "category": "Kitchen"}).json()
    linked = client.post("/entries", json={"content": "oven temperatures"}).json()
    client.post(f"/entries/{anchor['id']}/links", json={"target_id": linked["id"]})
    tagged = client.post("/entries", json={"content": "rye crumb", "tags": ["Baking"]}).json()
    same_cat = client.post("/entries", json={"content": "knife sharpening", "category": "Kitchen"}).json()
    unrelated = [client.post("/entries", json={"content": f"tax return part {i}"}).json() for i in range(8)]
    draft = client.post("/entries", json={"content": "draft", "tags": ["baking"], "is_draft": True}).json()
    archived = client.post("/entries", json={"content": "archived", "tags": ["baking"]}).json()
    client.post(f"/entries/{archived['id']}/archive")
    binned = client.post("/entries", json={"content": "binned", "tags": ["baking"]}).json()
    client.delete(f"/entries/{binned['id']}")
    client.post("/resurface/compute")

    ids = [item["id"] for item in client.get(f"/resurface/near/{anchor['id']}?limit=10").json()["items"]]
    assert set(ids) == {linked["id"], tagged["id"], same_cat["id"]}
    assert ids[0] == linked["id"], "a link is the strongest relation"
    for gone in (draft, archived, binned, *unrelated):
        assert gone["id"] not in ids

    lonely = unrelated[0]
    assert client.get(f"/resurface/near/{lonely['id']}").json()["items"] == []


def test_context_ranking_survives_vectors_of_another_dimension(session, fake_embeddings):
    """A notebook re-embedded with a different model holds two sizes at once
    until the rebuild ends. `/resurface/near/{id}` answered 500 ("shapes (384,)
    and (4,) not aligned"); a candidate whose vector cannot be compared to the
    anchor's is measured like one with none: kept only when it is joined."""
    import struct

    from tessellate.ai import resurface
    from tessellate.core.database import EmbeddingRecord
    from tessellate.entry import manager

    anchor = manager.create_entry(session, "sourdough starter feeding schedule", tags=["bread"])
    same = manager.create_entry(session, "sourdough loaf crumb and hydration", tags=["bread"])
    odd = manager.create_entry(session, "rye bread notes", tags=["bread"])
    session.commit()
    vectors = {anchor.id: [1.0, 0.0], same.id: [1.0, 0.0], odd.id: [1.0, 0.0, 0.0, 0.0]}
    for entry_id, values in vectors.items():
        session.add(
            EmbeddingRecord(
                entry_id=entry_id,
                embedding=struct.pack(f"<{len(values)}f", *values),
                dim=len(values),
                model_version="test",
            )
        )
    session.commit()
    resurface.compute_scores(session)

    ids = [entry.id for entry in resurface.for_context(session, context_entry_id=anchor.id, limit=5)]
    assert same.id in ids
    assert odd.id in ids, "the shared tag still joins it"


def test_scoring_survives_a_row_written_by_a_concurrent_request(session, monkeypatch):
    """`GET /resurface/near/{id}` 500ed with UNIQUE note_scores.entry_id when
    two requests both found the table stale: each read "no row yet", then both
    inserted. A second session writes the row after this one has read the
    existing rows and before it flushes."""
    from tessellate.ai import resurface
    from tessellate.core import deps
    from tessellate.core.database import NoteScore
    from tessellate.entry import manager
    from sqlalchemy import select

    entry = manager.create_entry(session, "a note two requests both score", tags=[])
    session.commit()
    real = resurface.score_for
    fired = []

    def racing(*args, **kwargs):
        if not fired:
            fired.append(1)
            other = deps.get_db().session()
            other.add(NoteScore(entry_id=entry.id, score=0.1))
            other.commit()
            other.close()
        return real(*args, **kwargs)

    monkeypatch.setattr(resurface, "score_for", racing)
    resurface.compute_scores(session)
    session.commit()
    rows = session.scalars(select(NoteScore).where(NoteScore.entry_id == entry.id)).all()
    assert len(rows) == 1
