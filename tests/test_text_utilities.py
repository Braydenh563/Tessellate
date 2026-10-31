"""A text's counts and outline from one utilities module (CHAT_PLAN section
2, the documents row): words, characters and lines equal `wc` on the
fixture, the browser's `textCounts` equals the server's `utilities.counts`,
and the editor's outline (`docScanHeadings`) equals `utilities.outline`.
Also "find" with the same windows: a documents search reads "last week" as
the notes search does."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tessellate.ai import utilities

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/utilities/counts_1010.md"
JS = ROOT / "frontend/js"


def _wc() -> dict:
    env = {**os.environ, "LC_ALL": "C.UTF-8"}
    out = subprocess.run(["wc", "-w", "-m", "-l", str(FIXTURE)], capture_output=True, text=True, env=env, check=True)
    lines, words, chars = (int(n) for n in out.stdout.split()[:3])
    return {"lines": lines, "words": words, "chars": chars}


def _function(path: Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    start = src.index(f"function {name}(")
    end = src.index("\n}\n", start) + 3
    return src[start:end]


def _node(script: str):
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout)


@pytest.mark.skipif(shutil.which("wc") is None, reason="wc is not installed")
def test_the_counts_equal_wc_on_the_fixture():
    got = utilities.counts(FIXTURE.read_text(encoding="utf-8"))
    assert {k: got[k] for k in ("words", "chars", "lines")} == _wc()
    assert got["read"] == "under a min"


@pytest.mark.skipif(shutil.which("node") is None or shutil.which("wc") is None, reason="node or wc missing")
def test_the_browser_counts_the_same():
    text = FIXTURE.read_text(encoding="utf-8")
    source = (JS / "settings-wiring.js").read_text(encoding="utf-8")
    shared = source[source.index("const WORD_PER_CHARACTER") : source.index("function textCounts(")]
    fn = "const TEXT_READING_WPM = 220;\n" + shared + _function(JS / "settings-wiring.js", "textCounts")
    got = _node(fn + f"\nconsole.log(JSON.stringify(textCounts({json.dumps(text)})));")
    assert {k: got[k] for k in ("words", "chars", "lines")} == _wc()
    assert got["read"] == utilities.counts(text)["read"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_editor_outline_is_the_servers():
    text = FIXTURE.read_text(encoding="utf-8")
    fn = _function(JS / "documents.js", "docScanHeadings")
    got = _node(fn + f"\nconsole.log(JSON.stringify(docScanHeadings({json.dumps(text)})));")
    assert got == utilities.outline(text, max_level=4)
    assert [h["text"] for h in got] == ["Harbor plan", "Costs", "Notes for Sam", "Second part", "Open questions"]


def test_reading_time_wording():
    assert [utilities.reading_time(n) for n in (0, 100, 440, 220 * 90)] == ["", "under a min", "2 min read", "1.5h read"]


def test_no_count_of_its_own_in_the_documents_bundle():
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    assert "READING_WPM" not in re.sub(r"//.*", "", docs)
    assert docs.count("textCounts(") >= 3


def test_a_window_in_the_documents_search_is_a_window(client, session):
    from tessellate.core.database import Document

    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    headers = {"X-Auth-Token": token}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add_all([
        Document(title="Harbor roof", content="the harbor roof", updated_at=now - timedelta(days=2)),
        Document(title="Harbor crane", content="the harbor crane", updated_at=now - timedelta(days=60)),
        Document(title="Garden", content="beds", updated_at=now - timedelta(days=1)),
    ])
    session.commit()
    titles = lambda q: sorted(d["title"] for d in client.get("/documents", params={"q": q}, headers=headers).json())  # noqa: E731
    assert titles("harbor") == ["Harbor crane", "Harbor roof"]
    assert titles("harbor in the last week") == ["Harbor roof"]
    assert titles("last week") == ["Garden", "Harbor roof"]


def test_the_document_status_bar_shows_lines_not_only_counts_them():
    """OPEN ledger 299: `textCounts` returned `lines` and nothing showed it.
    The bar now reads characters, words, lines and the reading time."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend"
    source = (root / "js" / "documents.js").read_text(encoding="utf-8")
    block = source[source.index("function renderDocCounts") : source.index("function renderDocStatusBar")]
    assert "docLineCount(" in block
    assert "line${" in block or "line\"" in block
    assert "lines" in (root / "index.html").read_text(encoding="utf-8").split('id="doc-counts"')[1][:200]
    helper = source[source.index("function docLineCount") :][:400]
    assert 'endsWith("\\n")' in helper


def test_the_palette_has_a_help_button_that_takes_its_own_escape():
    """OPEN ledger 289: the timer, stopwatch and Count words are palette rows
    with no surface of their own, so the palette's foot carries a `?`
    (`data-help-for`). The first Escape closes that help only; the palette
    closes on the next (menus.js marks the press as spent)."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend"
    html = (root / "index.html").read_text(encoding="utf-8")
    card = html[html.index('id="palette-card"') : html.index('id="history-overlay"')]
    assert 'data-help-for="palette-help"' in card and 'aria-controls="palette-help"' in card
    assert 'id="palette-help"' in card
    for word in ("Timer", "Stopwatch", "Count words"):
        assert word in card
    wiring = (root / "js" / "settings-wiring.js").read_text(encoding="utf-8")
    assert "if (!e.helpPopoverSpent) closePalette();" in wiring
