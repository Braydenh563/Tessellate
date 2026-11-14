"""A wrapped board file's own names stay its own: a name declared inside a file's
`(() => { ... })()` wrapper and read by another file has to be on that file's
`Object.assign(window, {...})` list, or the other file throws when it runs.

Found 2026-11-14 by the E2E "New mind map: Tab adds a branch": the base's map add
(`wbMapCache.renderAdd`, whiteboard-map.js) read `wbBoardSearch`, which the L286 carve
had made private to whiteboard-search.js, so Tab threw and added nothing. No load-order
lint sees it, because the read only runs on a key press."""

from __future__ import annotations

import re
import sys
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
WRAPPER = re.compile(r"(?m)^\((?:async )?(?:\(\) =>|function \(\)) \{")
OWN = re.compile(r"(?m)^  (?:const|let|function|async function|class) (wb\w+)")
DECLARED = re.compile(r"(?m)^\s*(?:const|let|var|function|async function|class) (wb\w+)")
READ = re.compile(r"(?<![\w.$])(wb\w+)\b(?!\s*:)")


def _code(text: str) -> str:
    # Whole-line comments only: names in prose are not reads.
    return re.sub(r"(?m)^\s*//.*$", "", text)


def _exported(text: str) -> set[str]:
    names = set(re.findall(r"window\.(\w+) =", text))
    for block in re.findall(r"Object\.assign\(window, \{([^}]*)\}", text):
        names |= set(re.findall(r"\w+", block))
    return names


def leaks() -> list[tuple[str, str, str]]:
    files = {p.name: p.read_text(encoding="utf-8") for p in sorted(JS.glob("*.js"))}
    reads = {n: set(READ.findall(_code(t))) - set(DECLARED.findall(t)) for n, t in files.items()}
    found = []
    for name, text in files.items():
        if not WRAPPER.search(text):
            continue
        private = set(OWN.findall(text)) - _exported(text)
        for other, used in reads.items():
            if other != name:
                found += [(name, n, other) for n in sorted(private & used)]
    return found


def test_no_file_reads_a_name_another_file_keeps_private():
    assert leaks() == []


def test_the_check_sees_the_bug_it_was_written_for(tmp_path, monkeypatch):
    (tmp_path / "a.js").write_text("(() => {\n  const wbSecret = {};\n  Object.assign(window, { wbOther });\n})();\n")
    (tmp_path / "b.js").write_text("function wbUse() {\n  return wbSecret.x;\n}\n")
    monkeypatch.setattr(sys.modules[__name__], "JS", tmp_path)
    assert leaks() == [("a.js", "wbSecret", "b.js")]
