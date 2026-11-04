"""A write that fails says so (audit 2026-10-05, FE-12).

`.catch(() => {})` on a POST, PUT, PATCH or DELETE hides a person's own
action failing: Forget a memory, delete a backup, pin or delete a question,
clear the server log, the tension card's "Linked as contradicting." shown
when the POST had failed, a bulk reminder delete. Each named one now toasts
the reason and stops before any success message.

The rest are not all wrong (a beacon, a best-effort preference write, a
background mark-as-read), so this is a ratchet rather than a ban: the number
of writes with a silent catch can only go down. A new write that may fail
quietly on purpose says why in a comment and is counted here.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.api.asset_strip import strip_js

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"

SILENT = re.compile(r"\.catch\(\s*\(\s*\w?\s*\)\s*=>\s*(\{\s*\}|null|undefined|false)\s*\)")
WRITE = re.compile(r'method:\s*"(POST|PUT|PATCH|DELETE)"')

#: 2026-10-05: the count after the named ones were fixed. Only ever lowered.
SILENT_WRITES = 31


def _silent_writes() -> list[str]:
    found = []
    for path in sorted(JS.glob("*.js")):
        code = strip_js(path.read_text(encoding="utf-8"))
        for match in SILENT.finditer(code):
            # The statement the catch closes: back to the last `;`, `{` or `}`
            # at the start of a line, at most a few lines up.
            start = max(code.rfind(";\n", 0, match.start()), code.rfind("{\n", 0, match.start()))
            statement = code[max(start, match.start() - 600) : match.start()]
            if WRITE.search(statement):
                line = code.count("\n", 0, match.start()) + 1
                found.append(f"{path.name}:{line}")
    return found


def test_the_named_writes_say_when_they_fail():
    named = {
        "settings-controls.js": "/memory/${pref.id}",
        "settings-data.js": "/backups/${item.name}",
        "ask-history.js": "/ask-history/${id}`, { method: \"DELETE\" })",
        "suggestions-inbox.js": "/entries/tensions/accept",
        "shell-reminders.js": "/reminders/${r.id}`, { method: \"DELETE\" })",
    }
    for file, url in named.items():
        code = strip_js((JS / file).read_text(encoding="utf-8"))
        at = code.index(url)
        window = code[at : at + 260]
        assert not SILENT.search(window), f"{file}: {url} still fails silently"


def test_silent_writes_only_go_down():
    found = _silent_writes()
    assert len(found) <= SILENT_WRITES, (
        f"{len(found)} writes swallow their failure (cap {SILENT_WRITES}); "
        f"a person's action that fails must say so: {found[-10:]}"
    )
