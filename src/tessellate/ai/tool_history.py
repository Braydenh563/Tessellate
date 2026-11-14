"""The agent's recent tool calls and what came back (O10, L163, INBOX 1842).

A small in-memory ring, newest kept: the tool, what it was asked (cut), whether
it worked and the words of its result (cut). It is read by `/tools` in the chat
and never written to disk, so a restart starts it empty and a private chat
leaves nothing behind. Recorded at the one door every call comes through
(`tools/tool_door.py` wraps `tool_run.execute_tool`), refusals and failures included.
"""

from __future__ import annotations

import functools
import json
import threading
from collections import deque
from datetime import datetime, timezone

from sqlalchemy.orm import Session

#: How many calls are kept; the oldest fall off.
KEPT = 50
_ARGS_CUT, _RESULT_CUT = 90, 160
_LOG: deque[dict] = deque(maxlen=KEPT)
_LOCK = threading.Lock()


def _cut(text: str, size: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= size else text[: size - 1].rstrip() + "…"


def _arguments(arguments: dict | None) -> str:
    parts = []
    for key, value in (arguments or {}).items():
        if str(key).startswith("__"):
            continue
        shown = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (str, list, dict)) else str(value)
        parts.append(f"{key}={_cut(shown, 40)}")
    return _cut(", ".join(parts), _ARGS_CUT)


def record(name: str, arguments: dict | None, result: object, *, now: datetime | None = None) -> None:
    """Keep one call. `result` is what the tool returned (an `error` key is a failure)."""
    failed = isinstance(result, dict) and "error" in result
    said = result["error"] if failed else json.dumps(result, ensure_ascii=False, default=str) if result is not None else ""
    row = {
        "at": (now or datetime.now(timezone.utc)).isoformat(),
        "tool": str(name)[:80],
        "arguments": _arguments(arguments),
        "ok": not failed,
        "result": _cut(said, _RESULT_CUT),
    }
    with _LOCK:
        _LOG.append(row)


def recorded(run):
    """Wrap the tool door: run the call, keep it, hand back its result."""

    @functools.wraps(run)
    def door(session, name, arguments, *rest, **more):
        result = run(session, name, arguments, *rest, **more)
        record(name, arguments, result)
        return result

    return door


def recent(limit: int = 10) -> list[dict]:
    """The newest `limit` calls, newest first."""
    with _LOCK:
        return list(reversed(_LOG))[: max(0, limit)]


def clear() -> None:
    with _LOCK:
        _LOG.clear()


def slash(session: Session, arg: str, now: datetime) -> str:
    """`/tools [n]`: the newest calls, one line each."""
    from tessellate.ai import slash_more

    rows = recent(slash_more.count_arg(arg))
    if not rows:
        return "No tool calls yet. When the assistant uses a tool, it is listed here with what came back."
    lines = []
    for row in rows:
        asked = f" ({row['arguments']})" if row["arguments"] else ""
        came = f"failed: {row['result']}" if not row["ok"] else (row["result"] or "done")
        lines.append(f"- **{row['tool']}**{asked}: {came}")
    lead = "The last tool call:" if len(rows) == 1 else f"The last {len(rows)} tool calls, newest first:"
    return f"{lead}\n\n" + "\n".join(lines)
