"""Other copies of Tessellate running on this computer (INBOX 1641).

The owner, after "Port 8000 is already in use by another program": "the user
should be able to shutdown running instances from the settings".

`instance.lock` (core/instance_lock.py) is per data folder, so it cannot show a
copy that serves a different notebook. This is the per-user side of it: each
server that claims its lock also writes one small record, `<pid>.json`, into a
folder only this user can read (`%LOCALAPPDATA%\\Tessellate\\run` on Windows,
`$XDG_STATE_HOME/tessellate/run` elsewhere; `TESSELLATE_RUN_DIR` overrides it,
which the tests use). The record holds the pid, port, data folder, start time
and the same random token the copy's `/instance/focus` already takes.

- **Listing** prunes as it reads, and only a copy that really runs stays. A
  record is live when the port answers `/health` naming the instance the
  record holds (`instance_lock.instance_id` of its token), or when its pid is
  alive and began when the record says it did (Windows reuses pids, so "alive"
  alone proves nothing). A port held by a different instance, or by an older
  build with several records on it, keeps one at most: the holder wins. A crash
  or a closed window skips `release`, so reading is where dead records go;
  start-up prunes too (`prune_now`).
- **Shut down** asks the other copy over its own loopback route
  (`POST /instance/shutdown`, carrying the token). Nothing a web page can send
  carries the token, and the folder is private to this user, so another user's
  copy is never reachable. A copy that does not answer is never killed: a
  dead copy's pid can be reused by another program, so it is reported as
  not answering instead. A record that is not live is removed and reported
  as "gone", which is not an error.

Pure functions with the probes passed in, so the rules are tested without a
second server (`tests/test_running_copies_1641.py`). Light imports only.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass

from tessellate.core import instance_lock, run_records
from tessellate.core.run_records import Record


@dataclass(frozen=True)
class Copy:
    pid: int
    port: int
    started: float
    data_dir: str
    this_copy: bool

    def public(self) -> dict:
        """What Settings sees. The token never leaves this module."""
        return asdict(self)


#: A record is written when the server claims its lock, a moment after the
#: process began. Further apart than this, the pid belongs to someone else.
START_SLACK_SECONDS = 300.0
#: The clock of the process table and the clock of the record may differ a little.
START_EARLY_SECONDS = 5.0


def _live(
    rec: Record,
    *,
    me: int,
    served: str | None,
    alive: bool,
    began: float | None,
    now: float,
) -> bool:
    """Whether the copy this record describes is really running."""
    if rec.pid == me:
        return True
    if served:  # a named instance holds the port: this record is it, or it is not
        return served == instance_lock.instance_id(rec.token)
    if not alive:
        return False
    if began is not None:
        return -START_EARLY_SECONDS <= rec.started - began <= START_SLACK_SECONDS
    # The platform will not say when the process began: the boot grace is all that is known.
    return now - rec.started < instance_lock.BOOT_GRACE_SECONDS or served == ""


def _probes(
    identity_fn: Callable[[int], str | None] | None,
    answers_fn: Callable[[int], bool] | None,
    alive_fn: Callable[[int], bool] | None,
    started_fn: Callable[[int], float | None] | None,
) -> tuple[Callable[[int], str | None], Callable[[int], bool], Callable[[int], float | None]]:
    """The probes, with the real ones looked up at call time. A caller that
    only says whether a port answers (`answers_fn`) is treated as an older
    build that answers without naming itself."""
    if identity_fn is None:
        if answers_fn is not None:
            identity_fn = lambda port: "" if answers_fn(port) else None  # noqa: E731
        else:
            identity_fn = instance_lock.served_instance
    return identity_fn, alive_fn or instance_lock.pid_alive, started_fn or instance_lock.process_started


def _records(
    *,
    me: int,
    identity_fn: Callable[[int], str | None] | None = None,
    answers_fn: Callable[[int], bool] | None = None,
    alive_fn: Callable[[int], bool] | None = None,
    started_fn: Callable[[int], float | None] | None = None,
    now: float | None = None,
) -> list[Record]:
    """The live records, with the stale ones deleted on the way."""
    identity, alive_of, started_of = _probes(identity_fn, answers_fn, alive_fn, started_fn)
    when = time.time() if now is None else now
    try:
        files = sorted(run_records.run_dir().glob("*.json"))
    except OSError:
        return []
    served_on: dict[int, str | None] = {}  # one probe per port per pass
    live: list[Record] = []
    for path in files:
        rec = run_records.read(path)
        if rec is None:
            continue  # not ours to delete: junk reads as no record
        if rec.port not in served_on:
            served_on[rec.port] = identity(rec.port)
        if _live(rec, me=me, served=served_on[rec.port], alive=alive_of(rec.pid), began=started_of(rec.pid), now=when):
            live.append(rec)
        else:
            _forget(path)
    # One port, one copy: records that cannot be told apart by an instance id
    # (older builds) keep the newest, since the port can only be held once.
    kept: list[Record] = []
    for rec in sorted(live, key=lambda r: r.started, reverse=True):
        unnamed = not served_on.get(rec.port) and rec.pid != me
        if unnamed and any(k.port == rec.port and (k.pid == me or not served_on.get(k.port)) for k in kept):
            _forget(run_records.path_for(rec.pid))
            continue
        kept.append(rec)
    return sorted(kept, key=lambda r: r.started)


def _forget(path) -> None:
    try:
        path.unlink()
    except OSError:
        pass  # another listing removed it first, or it is locked: tried again next time


def list_copies(
    *,
    own_pid: int | None = None,
    identity_fn: Callable[[int], str | None] | None = None,
    answers_fn: Callable[[int], bool] | None = None,
    alive_fn: Callable[[int], bool] | None = None,
    started_fn: Callable[[int], float | None] | None = None,
    now: float | None = None,
) -> list[Copy]:
    me = os.getpid() if own_pid is None else own_pid
    return [
        Copy(r.pid, r.port, r.started, r.data_dir, r.pid == me)
        for r in _records(
            me=me, identity_fn=identity_fn, answers_fn=answers_fn, alive_fn=alive_fn, started_fn=started_fn, now=now
        )
    ]


def prune_now() -> None:
    """Delete the records of copies that are gone."""
    list_copies()


def prune_in_background() -> None:
    """`prune_now` off the start-up path, called after a server claims its
    lock: a crash or a closed window skips `release`, so this is where the
    records of copies that died are dropped."""
    import logging

    from tessellate.core import jobs  # here, not at the top: this module keeps light imports

    def run() -> None:
        try:
            prune_now()
        except Exception:  # noqa: BLE001 - a tidy-up, never a reason to fail
            logging.getLogger(__name__).debug("running copies: start-up prune failed", exc_info=True)

    jobs.thread("running-copies-prune", run)


def ask_to_stop(port: int, token: str) -> bool:
    """Ask the copy on `port` to quit. True only when it said it is stopping."""
    return instance_lock.request_shutdown(port, token)


def shutdown(
    pid: int,
    *,
    own_pid: int | None = None,
    ask_fn: Callable[[int, str], bool] | None = None,
    identity_fn: Callable[[int], str | None] | None = None,
    alive_fn: Callable[[int], bool] | None = None,
    started_fn: Callable[[int], float | None] | None = None,
    now: float | None = None,
) -> str:
    """"stopping", "gone", "this-copy", "unknown" or "failed".

    Only ever asks: the copy is told to quit over its own route, with the
    token from its record, and nothing is killed. A kill fallback was built
    and taken out on review: a dead copy's pid can be reused by another
    program while a different copy holds its port, so no check from here
    ties a pid to the server answering (INBOX 1641). A record whose copy is
    no longer running is removed and reported as "gone" (it is not asked, and
    it is not an error); a copy that is running but cannot be asked is
    reported as not answering."""
    me = os.getpid() if own_pid is None else own_pid
    if pid == me:
        return "this-copy"
    rec = run_records.read(run_records.path_for(pid))
    if rec is None:
        return "unknown"
    identity, alive_of, started_of = _probes(identity_fn, None, alive_fn, started_fn)
    when = time.time() if now is None else now
    if not _live(rec, me=me, served=identity(rec.port), alive=alive_of(rec.pid), began=started_of(rec.pid), now=when):
        _forget(run_records.path_for(pid))
        return "gone"
    if (ask_fn or ask_to_stop)(rec.port, rec.token):
        return "stopping"
    return "failed"
