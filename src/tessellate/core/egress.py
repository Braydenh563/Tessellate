"""Every connection this process opens, recorded where it cannot be missed.

The privacy receipt (WORLD_CLASS_PLAN §2, standout 5) is "a page that proves,
from the app's own logs, that nothing left the machine". A log that each
network call had to remember to write would prove only that the calls which
remembered stayed home: the one that matters is the library three imports
deep that phones home on its own. So this is not a logger the fetch sites
call. It is a Python audit hook (PEP 578), installed once, which the
interpreter itself calls on every `socket.connect` and `socket.getaddrinfo`
in the process, from any module, any thread, any library, including the ones
this project did not write. Nothing can open a TCP connection or ask DNS for
a name without passing through `_hook`.

Three rules shape it, each because an audit hook is an unusual place to run
code:

- **It never raises.** An exception inside a hook propagates into the code
  that raised the event and aborts its operation: a receipt must never be
  the reason a connect failed. `_hook` catches everything.
- **It is cheap on every other event.** The interpreter calls every hook for
  every audited event (each `open`, each `import`), so the first line is one
  frozenset lookup and anything else returns at once.
- **It does no I/O.** Writing the ledger from inside a connect would put a
  disk write on the network path and re-enter the hook through `open`; the
  ledger is written by `flush`. The hook only queues one small job on
  `core/jobs.py`'s pool (`configure` says where the ledger is), which waits
  `FLUSH_DELAY` to batch a burst and then flushes, so a process that is
  killed loses at most that window of what it saw. `flush` also runs on
  every receipt read and at shutdown.

What it cannot see, said here and on the receipt: other programs. The model
server (Ollama, LM Studio, llama.cpp) and a SearXNG the app starts are
separate processes with their own sockets. The receipt names their addresses
instead (S6: "show the configured URL in the privacy receipt").
"""

from __future__ import annotations

import functools
import ipaddress
import json
import socket
import sys
import threading
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

#: The file under the data folder that carries the totals across launches.
LEDGER_NAME = "egress-ledger.json"
#: Destinations kept, per launch and in the ledger. A web search can touch
#: many hosts; past this the least recently used one is dropped from the
#: table, and the totals still count every connection, so bounding the table
#: never makes the receipt quieter than what happened.
MAX_DESTINATIONS = 256
#: The recent non-local events kept for the receipt's "last seen" list.
MAX_RECENT = 100
#: How long the flush job waits after the first unflushed connection before
#: it writes, so a web search that opens twenty sockets is one write, and the
#: most a hard kill can lose.
FLUSH_DELAY = 0.5

SCOPES = ("this_computer", "local_network", "internet")

_WATCHED = frozenset({"socket.connect", "socket.getaddrinfo"})
_LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain", "ip6-localhost"})

#: The modules that are *allowed* to reach out (tests/test_outbound_fetch_guard's
#: REACHES_THE_NETWORK), named the way a person reads them. A destination
#: reached from anywhere else shows its module name, which is itself a finding.
FEATURES = {
    "tessellate.search.websearch": "Web search",
    "tessellate.core.webclip": "Web clipper",
    "tessellate.ai.ollama_client": "Model server",
    "tessellate.ai.openai_client": "Model server",
    "tessellate.ai.provider_http": "Model server",
    "tessellate.search.searxng_install": "SearXNG install",
    "tessellate.search.searxng_docker": "SearXNG",
    "tessellate.api.routes_update": "Update check",
    "tessellate.core.extra_downloads": "Optional downloads",
    "tessellate.core.embedmodels": "Embedding model download",
    "tessellate.ai.embeddings": "Embedding model",
    #: Not a reach out: a device on this network opening the app (INBOX 894).
    "tessellate.core.lanserve": "Other devices",
}

#: What an incoming row is for, in the receipt's "For:" line.
INCOMING_PURPOSE = "A device on this network opened the app"

#: Modules that look a name up on a feature's behalf (the address guard
#: resolves before every fetch): the feature that called them is named, not
#: them. Measured 2026-10-11: a clipped page read "Memorymap.core.security".
_ON_BEHALF = frozenset({"tessellate.core.security"})

_lock = threading.Lock()
_installed = False
_since = time.time()
# (kind, host, port) -> {"count", "first", "last", "via", "name"}
_destinations: dict[tuple[str, str, int | None], dict] = {}
# ledger path -> (destination counts, scope totals) already written to *that*
# ledger by `flush`. Per path, so the flush job and a caller flushing
# to another file never consume each other's difference.
_flush_state: dict[str, tuple[dict[tuple[str, str, int | None], int], dict[str, int]]] = {}
_totals = {scope: 0 for scope in SCOPES}
# Held across a whole `flush`: it reads, adds to and rewrites one file, and
# the flush job, the receipt route and shutdown can all be in it at once.
_io_lock = threading.Lock()
# True from the moment `_record` queues a flush job until that job has
# taken what is pending: a bare flag, so the hook asks the pool for at most
# one job per burst and takes no lock to find out.
# (A one-key dict rather than a module global: the flag is set and read
# across functions and threads, and a container needs no `global`.)
_flush = {"queued": False}
_ledger_path: Path | None = None
_recent: deque = deque(maxlen=MAX_RECENT)
# The last name each thread looked up, so a connect to an address can say
# which name it was probably for ("140.82.112.3" is "api.github.com").
_last_lookup = threading.local()
_own_names: frozenset[str] = frozenset()

#: What the code reaching out was doing, in words (INBOX 807, the owner: "it
#: isnt really clear exactly what these were for"): "Downloading the English
#: OCR data", "Web search for 'gaming mouse'". Set by the caller around its
#: request (`purpose`); per thread, with the newest one still running anywhere
#: as the fallback, because a library that downloads on its own worker
#: threads (huggingface_hub) connects from a thread the caller never named.
_purpose = threading.local()
_open_purposes: list[str] = []
#: Distinct purposes a destination keeps, newest first.
MAX_PURPOSES = 5


@contextmanager
def purpose(words: object) -> Iterator[None]:
    """Name what the connections made inside the block are for."""
    text = " ".join(str(words or "").split())[:160]
    before = getattr(_purpose, "value", None)
    _purpose.value = text
    with _lock:
        _open_purposes.append(text)
    try:
        yield
    finally:
        _purpose.value = before
        with _lock:
            if text in _open_purposes:
                _open_purposes.remove(text)


def labelled(words):  # noqa: ANN001, ANN201
    """`purpose` as a decorator: `words` is a sentence, or a function of the
    call's own arguments returning one ("Web search for 'gaming mouse'")."""

    def wrap(func):  # noqa: ANN001, ANN202
        @functools.wraps(func)
        def inner(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            try:
                said = words(*args, **kwargs) if callable(words) else words
            except Exception:  # noqa: BLE001  # the label must never stop the call
                said = ""
            with purpose(said):
                return func(*args, **kwargs)

        return inner

    return wrap


def short(text: object, limit: int = 60) -> str:
    """A value cut to fit a purpose line."""
    one = " ".join(str(text or "").split())
    return one if len(one) <= limit else one[: limit - 1] + "…"


def _current_purpose() -> str | None:
    own = getattr(_purpose, "value", None)
    if own:
        return own
    with _lock:
        return _open_purposes[-1] if _open_purposes else None


def _add_purpose(row: dict, words: str | None) -> None:
    if not words:
        return
    kept = [words] + [p for p in row.get("purposes") or [] if p != words]
    row["purposes"] = kept[:MAX_PURPOSES]


def _now_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def scope_of(host: str) -> str:
    """Where `host` is: this computer, the local network, or the internet.

    A name that is not an address and not recognisably local is counted as
    the internet. The receipt errs toward saying more left, never less.
    """
    text = (host or "").strip().strip("[]").lower()
    if "%" in text:  # fe80::1%eth0, a scoped IPv6 address
        text = text.split("%", 1)[0]
    if text in _LOOPBACK_NAMES or text in _own_names:
        return "this_computer"
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        if text.endswith((".local", ".lan", ".home.arpa", ".internal")):
            return "local_network"
        return "internet"
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    if address.is_loopback or address.is_unspecified:
        return "this_computer"
    if address.is_private or address.is_link_local or not address.is_global:
        return "local_network"
    return "internet"


def _is_address(text: str) -> bool:
    try:
        ipaddress.ip_address(text.strip("[]").split("%", 1)[0])
    except ValueError:
        return False
    return True


def _caller() -> str | None:
    """The first frame on the stack from this app's own code, not this file."""
    try:
        frame = sys._getframe(2)
    except ValueError:
        return None
    depth = 0
    helper = None
    while frame is not None and depth < 80:
        name = frame.f_globals.get("__name__", "")
        if isinstance(name, str) and name.startswith(("tessellate.", "memorymap.")) and name != __name__:
            if name not in _ON_BEHALF:
                return name
            helper = helper or name
        frame = frame.f_back
        depth += 1
    return helper


def record_incoming(address: str) -> None:
    """A device on this network connected to the LAN port (INBOX 894).

    The audit hook sees `connect`, never `accept`, so core/lanserve.py calls
    this for each connection it lets in. One row per device address (its
    port changes with every connection and is left out), always in the
    local-network total: lanserve accepts only nearby clients, including a
    phone's global IPv6 address in this network's /64, which `scope_of`
    alone would count as the internet. Never what the device asked for."""
    if not isinstance(address, str) or not address:
        return
    host = address.split("%", 1)[0]
    #: A dual-stack socket reports an IPv4 phone as `::ffff:10.1.0.106` (CI's
    #: runner did); the receipt names it as the phone's own address.
    try:
        mapped = ipaddress.ip_address(host).ipv4_mapped
    except (ValueError, AttributeError):
        mapped = None
    if mapped is not None:
        host = str(mapped)
    _record("incoming", host, None, scope="local_network", via="tessellate.core.lanserve", why=INCOMING_PURPOSE)


def _record(  # noqa: PLR0913
    kind: str, host: str, port: int | None, *, scope: str | None = None, via: str | None = None, why: str | None = None
) -> None:
    scope = scope or scope_of(host)
    now = time.time()
    via = via or (_caller() if scope != "this_computer" else None)
    name = None
    if kind == "connect":
        looked = getattr(_last_lookup, "value", None)
        if looked and now - looked[1] < 30 and looked[0] != host:
            name = looked[0]
    else:
        _last_lookup.value = (host, now)
    if scope == "this_computer":
        # Counted, not tabled: a local model answers on loopback every turn,
        # and a table of those would bury the one line that matters.
        with _lock:
            _totals[scope] += 1
        return
    key = (kind, host, port)
    why = why or _current_purpose()
    with _lock:
        _totals[scope] += 1
        row = _destinations.get(key)
        if row is None:
            if len(_destinations) >= MAX_DESTINATIONS:
                oldest = min(_destinations, key=lambda k: _destinations[k]["last"])
                del _destinations[oldest]
            row = _destinations[key] = {"count": 0, "first": now, "last": now, "via": via, "name": name}
        row["count"] += 1
        row["last"] = now
        row["via"] = via or row["via"]
        row["name"] = name or row["name"]
        _add_purpose(row, why)
        _recent.append({"at": now, "kind": kind, "host": host, "port": port, "scope": scope, "via": via})
    # Only what left this computer queues a write: loopback traffic is
    # counted but not tabled, and a local model would otherwise write the
    # ledger every turn.
    _schedule_flush()


def _hook(event: str, args: tuple) -> None:
    if event not in _WATCHED:
        return
    try:
        if event == "socket.connect":
            address = args[1] if len(args) > 1 else None
            # AF_UNIX addresses are a path (str or bytes): a file, not a host.
            if not isinstance(address, tuple) or not address:
                return
            host = address[0]
            if isinstance(host, bytes):
                host = host.decode("ascii", "replace")
            if not isinstance(host, str):
                return
            port = address[1] if len(address) > 1 and isinstance(address[1], int) else None
            _record("connect", host, port)
        else:
            host = args[0] if args else None
            if isinstance(host, bytes):
                host = host.decode("ascii", "replace")
            if not isinstance(host, str) or not host:
                return
            if _is_address(host):
                # A numeric "lookup" is parsed on this machine and asks no
                # resolver anything; the connect that may follow is recorded.
                return
            port = args[1] if len(args) > 1 and isinstance(args[1], int) else None
            _record("lookup", host, port)
    except Exception:  # noqa: BLE001 - a hook that raises aborts the caller's connect (module docstring)
        # Exception, not BaseException: a Ctrl-C or SystemExit arriving here
        # must still stop the process; only a bug in the recorder is swallowed.
        return


def install() -> None:
    """Start watching. Idempotent; an audit hook cannot be removed again,
    which is the property that makes it a record rather than a courtesy."""
    global _installed, _own_names
    with _lock:
        if _installed:
            return
        _installed = True
    # This machine's own names count as this computer. Read before the hook
    # goes in: `gethostname` raises no watched event, but the names are
    # compared against every later one.
    try:
        own = socket.gethostname().lower()
        _own_names = frozenset({own, own.split(".", 1)[0], f"{own.split('.', 1)[0]}.local"})
    except OSError:
        _own_names = frozenset()
    sys.addaudithook(_hook)


def installed() -> bool:
    return _installed


def reset() -> None:
    """Forget this launch's record (tests; the hook stays installed)."""
    global _since
    with _lock:
        _flush["queued"] = False
        _destinations.clear()
        _flush_state.clear()
        _recent.clear()
        for scope in SCOPES:
            _totals[scope] = 0
        _since = time.time()


def since() -> str:
    return _now_iso(_since)


def totals() -> dict[str, int]:
    with _lock:
        return dict(_totals)


def _row_out(key: tuple, row: dict) -> dict:
    kind, host, port = key
    via = row.get("via")
    return {
        "kind": kind,
        "host": host,
        "port": port,
        "name": row.get("name"),
        "scope": "local_network" if kind == "incoming" else scope_of(host),
        "count": row["count"],
        "first": _now_iso(row["first"]) if isinstance(row["first"], (int, float)) else row["first"],
        "last": _now_iso(row["last"]) if isinstance(row["last"], (int, float)) else row["last"],
        "via": via,
        "feature": FEATURES.get(via or "", via),
        "purposes": list(row.get("purposes") or []),
    }


def destinations() -> list[dict]:
    """This launch's non-local destinations, most recent first."""
    with _lock:
        rows = [_row_out(key, dict(row)) for key, row in _destinations.items()]
    return sorted(rows, key=lambda r: r["last"], reverse=True)


def recent() -> list[dict]:
    with _lock:
        events = list(_recent)
    return [
        {**event, "at": _now_iso(event["at"]), "feature": FEATURES.get(event["via"] or "", event["via"])}
        for event in reversed(events)
    ]


def verdict(counts: dict[str, int]) -> str:
    """The one-word answer: the widest scope anything reached."""
    if counts.get("internet"):
        return "internet"
    if counts.get("local_network"):
        return "local_network"
    return "stayed_on_this_computer"


def _read_ledger(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        # Missing is the first launch; corrupt is a file somebody edited or a
        # disk that failed mid-write. Either way the ledger starts again
        # rather than the receipt failing, and it says when it started.
        return {}
    return data if isinstance(data, dict) else {}


def configure(path: Path | None) -> None:
    """Keep `path` current while the process runs (the app calls this at startup).

    From here on a connection that leaves this computer queues one flush job
    (`_schedule_flush`). `None` stops that (tests).
    """
    global _ledger_path
    with _lock:
        _ledger_path = path
        # A previous app's pool may have dropped its queued job at shutdown.
        _flush["queued"] = False


def _schedule_flush() -> None:
    """Ask the pool for one flush, at most one job per burst. Never raises.

    Called from the audit hook, so it does no I/O of its own: a queue put and
    a flag. The job waits `FLUSH_DELAY` before it reads what is pending, so
    the connections that follow the first are in the same write, and clears
    the flag *before* flushing, so one that lands during the write queues the
    next job rather than waiting for shutdown.
    """
    if _ledger_path is None or _flush["queued"]:
        return
    _flush["queued"] = True
    try:
        from tessellate.core import jobs

        if not jobs.enqueue("ledger", _flush_job, name="privacy ledger", dedupe_key="egress-ledger"):
            _flush["queued"] = False  # the pool is shutting down; the quit flushes
    except Exception:  # noqa: BLE001 - the hook must never raise (module docstring)
        _flush["queued"] = False


def _flush_job() -> None:
    time.sleep(FLUSH_DELAY)
    _flush["queued"] = False
    path = _ledger_path
    if path is not None:
        flush(path, create=False)


def flush(path: Path, *, create: bool = True) -> dict:
    """Add what this launch saw since the last flush to the ledger on disk.

    Only the difference is added, so flushing on every receipt read, from the
    flush job and again at shutdown never counts a connection twice.
    Returns the ledger written. `create=False` (the flush job's) writes
    only when there is something to add, never an empty first ledger.
    """
    with _io_lock:
        return _flush_locked(path, create)


def _take_unflushed(path: Path):  # noqa: ANN202
    """What the counters hold that the ledger at `path` does not: the new
    counts by destination, their rows, and the totals added; also the flushed
    marks (to be rolled back) as they stood before."""
    with _lock:
        flushed, flushed_totals = _flush_state.setdefault(str(path), ({}, {scope: 0 for scope in SCOPES}))
        added = {
            key: row["count"] - flushed.get(key, 0)
            for key, row in _destinations.items()
            if row["count"] > flushed.get(key, 0)
        }
        rows = {key: dict(_destinations[key]) for key in added}
        before = (dict(flushed), dict(flushed_totals))
        added_totals = {scope: _totals[scope] - flushed_totals[scope] for scope in SCOPES}
        for key, row in _destinations.items():
            flushed[key] = row["count"]
        for scope in SCOPES:
            flushed_totals[scope] = _totals[scope]
    return flushed, flushed_totals, added, rows, before, added_totals


def _stored_rows(ledger: dict) -> dict:
    stored = {}
    for item in ledger.get("destinations", []) if isinstance(ledger.get("destinations"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("host"), str):
            stored[(item.get("kind", "connect"), item["host"], item.get("port"))] = item
    return stored


def _row_with_history(key, row: dict, count: int, previous: dict | None) -> dict:  # noqa: ANN001
    """The ledger row for a destination: this flush's `count` added to what
    the ledger already held (`previous`), its first time and purposes kept."""
    out = _row_out(key, row)
    if previous is None:
        out["count"] = count
        return out
    out["count"] = int(previous.get("count", 0) or 0) + count
    out["first"] = previous.get("first", out["first"])
    for words in reversed([w for w in previous.get("purposes") or [] if isinstance(w, str)]):
        if words not in out["purposes"]:
            out["purposes"].append(words)
    out["purposes"] = out["purposes"][:MAX_PURPOSES]
    return out


def _flush_locked(path: Path, create: bool) -> dict:
    from tessellate.core.atomic_io import atomic_write_json

    flushed, flushed_totals, added, rows, before, added_totals = _take_unflushed(path)
    ledger = _read_ledger(path)
    stored_totals = ledger.get("totals") if isinstance(ledger.get("totals"), dict) else {}
    out_totals = {scope: int(stored_totals.get(scope, 0) or 0) + added_totals[scope] for scope in SCOPES}
    stored = _stored_rows(ledger)
    for key, count in added.items():
        stored[key] = _row_with_history(key, rows[key], count, stored.get(key))
    kept = sorted(stored.values(), key=lambda r: str(r.get("last", "")), reverse=True)[:MAX_DESTINATIONS]
    result = {
        "since": ledger.get("since") or since(),
        "updated": _now_iso(time.time()),
        "totals": out_totals,
        "destinations": kept,
    }
    if added or any(added_totals.values()) or (create and not path.exists()):
        try:
            atomic_write_json(path, result)
        except OSError:
            # A full disk costs the ledger an update, never the receipt. What
            # was not written stays unflushed, so the next flush (the flush job
            # runs one per burst) carries it rather than losing it.
            with _lock:
                flushed.clear()
                flushed.update(before[0])
                flushed_totals.update(before[1])
    return result
