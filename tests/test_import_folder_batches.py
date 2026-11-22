"""A folder of thousands of notes imports in batches (L979).

`/import/markdown` takes at most `MAX_IMPORT_FILES` files a request, and the
multipart reader refuses more than a thousand, so `importMarkdown` sent a
5,000-file folder as one request and was refused whole ("The import did not
work"). The browser now sends the chosen files in batches the server takes.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.api import routes_settings_transfer

ROOT = Path(__file__).resolve().parents[1]


def _body() -> str:
    text = (ROOT / "frontend" / "js" / "settings-data.js").read_text(encoding="utf-8")
    return text.split("async function importMarkdown", 1)[1].split("\n}\n", 1)[0]


def test_the_batch_size_is_the_servers_cap():
    text = (ROOT / "frontend" / "js" / "settings-data.js").read_text(encoding="utf-8")
    size = int(re.search(r"const IMPORT_MARKDOWN_BATCH = (\d+);", text).group(1))
    assert size == routes_settings_transfer.MAX_IMPORT_FILES


def test_the_files_are_sent_in_batches_and_the_counts_added_up():
    body = _body()
    assert "IMPORT_MARKDOWN_BATCH" in body
    # one FormData per batch, made inside the loop and not once for the folder
    assert body.index("for (let at = 0") < body.index("new FormData()") < body.index('form.append("files"')
    assert "total.imported +=" in body and "total.ids.push(" in body


def test_the_server_takes_a_full_batch(client):
    n = routes_settings_transfer.MAX_IMPORT_FILES
    files = [("files", (f"d{i % 5}/n{i}.md", f"# Note {i}\n\nbody {i}\n".encode(), "text/markdown")) for i in range(n)]
    reply = client.post("/import/markdown", files=files)
    assert reply.status_code == 201, reply.text
    assert reply.json()["imported"] == n
