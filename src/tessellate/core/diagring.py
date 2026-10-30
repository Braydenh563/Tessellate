"""Ring buffers behind the diagnostics report (INBOX 1430, the owner, 2026-10-28:
"improve the app's ability to register and log issues and lag and complexity so
I can just give you the logs").

The server half of the one copyable report in Settings, Logs: slow requests
(route, ms, status), exceptions with their frames, and slow database
statements. Memory only, bounded, and written so that nothing a person typed
can be in it:

- a route is the path with ids and long tokens replaced and no query string
  (`/search?q=my secret` is `/search`);
- a statement is the SQL text with every literal replaced by `?`, never its
  parameters;
- an exception keeps its type, a short message and the frames (file, line,
  function), never a local variable;
- every string has the home folder replaced by `~`.

The clock is a module attribute so a test can fix it.
"""

from __future__ import annotations

import re
import threading
import time
import traceback
from collections import deque

SLOW_REQUEST_MS = 1000
SLOW_QUERY_MS = 250
KEEP = 200
EXCEPTIONS_KEEP = 50

_lock = threading.Lock()
_requests: deque[dict] = deque(maxlen=KEEP)
_exceptions: deque[dict] = deque(maxlen=EXCEPTIONS_KEEP)
_queries: deque[dict] = deque(maxlen=KEEP)

#: A test sets this to a fixed function.
clock = time.time

#: Streams and long polls are slow by design (the browser half skips them too);
#: the log and diagnostics routes are the readers, not the subject.
#: The app's own scripts, styles and fonts are files, not work the app did.
_BY_DESIGN = re.compile(r"/(stream|events|lan-watch)\b|^/logs(/|$)|^/diagnostics|^/(js|css|vendor|fonts)/|\.(woff2?|wasm|png|svg|ico)$")
_ID_SEGMENT = re.compile(r"^(\d+|[0-9a-f]{8}-[0-9a-f-]{27}|[0-9a-f]{16,}|[A-Za-z0-9_-]{24,})$")
_HOME = re.compile(r"(/home/[^/\s\"']+|/Users/[^/\s\"']+|[A-Za-z]:\\Users\\[^\\\s\"']+|/root\b)")
_STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")
_NUMBER_LITERAL = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")


def redact(text: object, limit: int = 300) -> str:
    """One short line with the home folder named `~` and no line breaks."""
    line = _HOME.sub("~", " ".join(str(text).split()))
    return line if len(line) <= limit else line[: limit - 1] + "…"


def route_of(path: str) -> str:
    """`/entries/12/links?x=1` becomes `/entries/:id/links`."""
    segments = path.split("?")[0].split("/")
    return "/".join(":id" if _ID_SEGMENT.match(s) else s for s in segments)[:120] or "/"


def shape_of(statement: str) -> str:
    """The statement with its literals replaced: what ran, not what it ran on."""
    flat = _STRING_LITERAL.sub("?", " ".join(str(statement).split()))
    return _NUMBER_LITERAL.sub("?", flat)[:200]


def note_request(method: str, path: str, ms: float, status: int) -> None:
    if ms < SLOW_REQUEST_MS or _BY_DESIGN.search(path):
        return
    row = {"at": clock(), "method": method, "route": route_of(path), "ms": round(ms), "status": status}
    with _lock:
        _requests.append(row)


def _frame(f: traceback.FrameSummary) -> str:
    """`tessellate/api/routes_x.py:42 name`: the package tail, never the install folder."""
    parts = f.filename.replace("\\", "/").split("/")
    for marker in ("tessellate", "site-packages"):
        if marker in parts:
            parts = parts[len(parts) - 1 - parts[::-1].index(marker) :]
            break
    else:
        parts = parts[-2:]
    return redact(f"{'/'.join(parts)}:{f.lineno} {f.name}", 120)


def note_exception(path: str, exc: BaseException, ref: str = "") -> None:
    row = {
        "at": clock(),
        "ref": ref,
        "route": route_of(path),
        "type": type(exc).__name__,
        "message": redact(exc, 160),
        "frames": [_frame(f) for f in traceback.extract_tb(exc.__traceback__)[-6:]],
    }
    with _lock:
        _exceptions.append(row)


def note_query(statement: str, ms: float) -> None:
    if ms < SLOW_QUERY_MS:
        return
    with _lock:
        _queries.append({"at": clock(), "sql": shape_of(statement), "ms": round(ms)})


def slow_routes() -> list[dict]:
    """One row a method and route: count, slowest, typical, last status. Worst first."""
    with _lock:
        rows = list(_requests)
    table: dict[tuple[str, str], dict] = {}
    for r in rows:
        t = table.setdefault(
            (r["method"], r["route"]),
            {"method": r["method"], "route": r["route"], "n": 0, "sum": 0, "max_ms": 0, "status": r["status"]},
        )
        t["n"] += 1
        t["sum"] += r["ms"]
        t["max_ms"] = max(t["max_ms"], r["ms"])
        t["status"] = r["status"]
    out = [{**{k: v for k, v in t.items() if k != "sum"}, "avg_ms": round(t["sum"] / t["n"])} for t in table.values()]
    return sorted(out, key=lambda t: -t["max_ms"])[:15]


def slow_queries() -> list[dict]:
    with _lock:
        rows = list(_queries)
    table: dict[str, dict] = {}
    for r in rows:
        t = table.setdefault(r["sql"], {"sql": r["sql"], "n": 0, "max_ms": 0})
        t["n"] += 1
        t["max_ms"] = max(t["max_ms"], r["ms"])
    return sorted(table.values(), key=lambda t: -t["max_ms"])[:10]


def exceptions(limit: int = 10) -> list[dict]:
    """The newest exceptions; repeats of one type, route and last frame are counted."""
    with _lock:
        rows = list(_exceptions)
    groups: dict[tuple, dict] = {}
    for r in rows:
        key = (r["type"], r["route"], r["frames"][-1] if r["frames"] else "")
        g = groups.get(key)
        if g:
            g["n"] += 1
            g["last_at"] = r["at"]
        else:
            groups[key] = {**r, "n": 1, "last_at": r["at"]}
    return sorted(groups.values(), key=lambda g: -g["last_at"])[:limit]


def clear() -> None:
    with _lock:
        _requests.clear()
        _exceptions.clear()
        _queries.clear()


_hook = {"on": False}


def install_query_hook() -> None:
    """Time every statement on every engine: two `perf_counter` calls each."""
    if _hook["on"]:
        return
    _hook["on"] = True
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ARG001
        conn.info.setdefault("diag_t0", []).append(time.perf_counter())

    @event.listens_for(Engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ARG001
        started = conn.info.get("diag_t0")
        if started:
            note_query(statement, (time.perf_counter() - started.pop()) * 1000)
