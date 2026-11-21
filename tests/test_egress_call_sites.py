"""A new outbound call site names its purpose (OPEN ledger 1512).

`egress.purpose` / `egress.labelled` make the "where your data went" list say
what each connection was for. The files below reach out without naming one
(local model servers, loopback checks, the user's own endpoint); the list may
only shrink. A file that makes an outbound call and is on neither side fails.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._repo_files import repo_files

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"

_CALL = re.compile(
    r"requests\.(get|post|put|delete|head|request|Session)|httpx\.|urlopen|urllib\.request"
    r"|http\.client|socket\.create_connection|hf_hub_download|snapshot_download"
)
_NAMED = re.compile(r"egress\.(purpose|labelled)")

#: Outbound code that does not name a purpose today. Remove a line when its
#: file gains one; never add a line for new code.
UNNAMED = {
    "ai/ollama_client.py",
    "ai/captions.py",
    "ai/openai_client.py",
    "api/routes_tasks.py",
    "api/routes_bench.py",
    "__main__.py",
    "core/instance_lock.py",
}


def _outbound_files() -> dict[str, str]:
    found = {}
    for path in repo_files(SRC, suffixes=(".py",)):
        text = path.read_text(encoding="utf-8", errors="replace")
        if _CALL.search(text):
            found[path.relative_to(SRC).as_posix()] = text
    return found


def test_every_outbound_file_names_a_purpose_or_is_listed():
    bad = [f for f, text in _outbound_files().items() if not _NAMED.search(text) and f not in UNNAMED]
    assert not bad, f"outbound call without egress.purpose or egress.labelled: {bad}"


def test_the_unnamed_list_has_no_stale_lines():
    files = _outbound_files()
    stale = [f for f in UNNAMED if f not in files or _NAMED.search(files[f])]
    assert not stale, f"remove from UNNAMED: {stale}"
