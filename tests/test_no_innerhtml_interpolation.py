"""No innerHTML built from an interpolated template (WORLD_CLASS_PLAN 10, F8).

Both sites that did this interpolated app-controlled strings, but the shape
is the XSS shape and the next author will interpolate a title. setLabel()
builds the same icon-plus-text with DOM nodes. Static, because the suite
cannot run the DOM.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
#: Across lines (SEC-16, security audit 2026-10-05): the single-line pattern
#: this used to be missed a multi-line template in chat-agent.js that put a
#: note's text into innerHTML. And every HTML sink, not only innerHTML.
PATTERN = re.compile(
    r"(?:innerHTML|outerHTML)\s*\+?=\s*`[^`]*\$\{"
    r"|insertAdjacentHTML\s*\([^,)]*,\s*`[^`]*\$\{",
    re.S,
)
WRITE = re.compile(r"document\.write(?:ln)?\s*\(")
#: `document.write` into a print window the app opened itself, with nothing
#: in it but a `blob:` URL the app made (whiteboard.js, `wbExportPdf`).
ALLOWED_WRITES: dict[str, int] = {}


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def test_no_innerhtml_assignment_interpolates():
    hits = []
    for path in (FRONTEND / "js").glob("*.js"):
        text = path.read_text(encoding="utf-8")
        hits += [f"{path.name}:{_line(text, m.start())}" for m in PATTERN.finditer(text)]
    assert not hits, "HTML built from a template with ${...}; use setLabel() or DOM nodes:\n" + "\n".join(hits)


def test_document_write_stays_where_it_is_known_safe():
    found = {}
    for path in (FRONTEND / "js").glob("*.js"):
        count = len(WRITE.findall(path.read_text(encoding="utf-8")))
        if count:
            found[path.name] = count
    assert found == ALLOWED_WRITES, found
