"""The `EXPLAIN QUERY PLAN` pass over the app's real query set (WORLD_CLASS_PLAN 19.3).

Seeds a notebook of N notes (default 5,000) with tags, links, reminders,
documents, attachments, events and boards; calls every GET route the app
serves that needs no more than an entry id; records every SQL statement those
requests run, with its parameters; then asks SQLite for each distinct
statement's plan and times it. Prints the statements whose plan contains a
full `SCAN` of a table or a `TEMP B-TREE`, slowest first.

    PYTHONPATH=src .venv/bin/python scratchpad/plat1005_query_plans.py [N]

A measurement, not a test: `tests/test_query_plans.py` holds the assertions
for the queries this pass indexed.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from collections import OrderedDict
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
SKIP = re.compile(
    r"stream|/update|/models|/websearch|/webclip|/voice|/backups|export|download|"
    r"/support-bundle|/logs|/help/ask|/debug/profile|/instance|/media/\{|/files/\{|/sandbox|"
    r"/openapi|/changelog|/embedding-models|/extras|/ocr"
)


def _tail(statement: str) -> str:
    """The statement from its FROM on: the column list says nothing about a plan."""
    flat = " ".join(statement.split())
    at = flat.find(" FROM ")
    return (flat[:60] + " ..." + flat[at:] if at > 60 else flat)[:700]


def main() -> None:
    data = tempfile.mkdtemp(prefix="plat1005-qp-")
    os.environ["TESSELLATE_DATA_DIR"] = data
    from fastapi.testclient import TestClient
    from sqlalchemy import event

    from fakes import FakeEmbeddingService, FakeOllama
    from tessellate.api.app import create_app
    from tessellate.ai import wiring  # noqa: F401
    from tessellate.core import deps
    from tessellate.core.database import (
        AuditLog,
        Category,
        Conversation,
        Document,
        MediaUpload,
        Entry,
        EntryLink,
        Reminder,
        utcnow,
    )
    from test_list_limits import _routes

    deps.init_app_state()
    deps.override_ai(ollama=FakeOllama(running=False), embeddings=FakeEmbeddingService(available=False))
    session = deps.get_db().session()
    t0 = time.perf_counter()
    cats = [Category(name=f"Area {i}") for i in range(12)]
    session.add_all(cats)
    session.flush()
    now = utcnow()
    entries = []
    for i in range(N):
        e = Entry(
            content=f"# Note {i}\n\nAbout gardens and {i % 97} things, [[Note {i // 2}]].",
            category_id=cats[i % len(cats)].id,
            created_at=now - timedelta(minutes=i),
            updated_at=now - timedelta(minutes=i // 2),
            pinned=(i % 211 == 0),
            is_board=(i % 250 == 0),
            is_draft=(i % 300 == 1),
            access_count=i % 7,
        )
        e.tags = json.dumps([f"tag{i % 60}", f"tag{(i * 7) % 60}"])
        entries.append(e)
    session.add_all(entries)
    session.flush()
    for i in range(0, N, 3):
        session.add(EntryLink(source_entry_id=entries[i].id, target_entry_id=entries[(i * 13 + 1) % N].id))
    for i in range(0, N, 50):
        entries[i].is_deleted = True
        entries[i].deleted_at = now
    for i in range(1, N, 40):
        entries[i].archived_at = now
    for i in range(0, N, 25):
        session.add(Reminder(entry_id=entries[i].id, text=f"Remind {i}", due_at=now + timedelta(days=i % 30)))
    for i in range(N * 4):
        session.add(AuditLog(action="edited", entity_type="entry", entity_id=entries[i % N].id, actor="user"))
    for i in range(N):
        session.add(MediaUpload(filename=f"m{i}.png", original_name=f"pic {i}.png", created_at=now - timedelta(minutes=i)))
    for i in range(N // 5):
        session.add(Document(title=f"Doc {i}", content="text", updated_at=now - timedelta(minutes=i)))
        session.add(Conversation(title=f"Chat {i}", updated_at=now - timedelta(minutes=i)))
    session.commit()
    first = entries[5].id
    print(f"seeded {N} notes in {time.perf_counter() - t0:.1f}s; data {data}")

    app = create_app()
    client = TestClient(app)
    captured: OrderedDict[str, tuple] = OrderedDict()
    owner: dict[str, str] = {}
    current = {"route": ""}

    def before(_conn, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().upper().startswith(("SELECT", "WITH")):
            key = statement
            if key not in captured:
                captured[key] = parameters
                owner[key] = current["route"]

    engine = deps.get_db().engine
    event.listen(engine, "before_cursor_execute", before)
    hit = 0
    for route, path in _routes(app):
        if "GET" not in (route.methods or set()) or SKIP.search(path):
            continue
        params = re.findall(r"\{(\w+)\}", path)
        if params and params != ["entry_id"]:
            continue
        url = path.replace("{entry_id}", str(first))
        current["route"] = url
        try:
            client.get(url)
            hit += 1
        except Exception as exc:  # noqa: BLE001  # a probe: report and go on
            print("  error", url, type(exc).__name__)
    for extra in ("/entries?deleted=true", "/entries?archived=true", "/search?q=gardens", "/entries?limit=50"):
        current["route"] = extra
        client.get(extra)
    event.remove(engine, "before_cursor_execute", before)
    print(f"{hit} routes, {len(captured)} distinct SELECTs")

    raw = engine.raw_connection()
    findings = []
    try:
        cur = raw.cursor()
        for statement, parameters in captured.items():
            try:
                plan = cur.execute("EXPLAIN QUERY PLAN " + statement, parameters or ()).fetchall()
            except Exception:  # noqa: BLE001
                continue
            details = [row[-1] for row in plan]
            bad = [
                d for d in details
                if (re.match(r"SCAN \w+$", d) or re.match(r"SCAN \w+ USING INDEX", d) or "TEMP B-TREE" in d)
                and "sqlite_" not in d and "fts" not in d.lower()
                and not re.match(r"SCAN (CONSTANT ROW|\w+_\d+|anon_\d+)", d)
            ]
            if not bad:
                continue
            start = time.perf_counter()
            for _ in range(3):
                cur.execute(statement, parameters or ()).fetchall()
            ms = (time.perf_counter() - start) / 3 * 1000
            findings.append((ms, owner[statement], bad, statement))
    finally:
        raw.close()
    findings.sort(reverse=True)
    for ms, route, bad, statement in findings:
        print(f"\n{ms:8.2f} ms  {route}\n    {bad}\n    {_tail(statement)}")


if __name__ == "__main__":
    main()
