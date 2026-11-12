"""L310: a TypeScript file's Problems list carries sucrase's own parse errors.

The Lezer tree check (`docTreeDiagnostics`) decides first. When it finds nothing in a `.ts`
document, the pass a Run would use (sucrase, `run-core.js`) is asked too, so a file the editor
calls clean can no longer fail on Run with a sentence Problems never showed. The reply's
"(line:col)" becomes the underline, and the source is named in the row.
"""

from __future__ import annotations

import re
from pathlib import Path

CODE_JS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents-code.js"


def _lint_source() -> str:
    text = CODE_JS.read_text(encoding="utf-8")
    start = text.index("function docCodeLintSource(CM)")
    return text[start : text.index("\n}\n", start)]


def test_ts_lint_asks_sucrase_when_the_tree_is_clean():
    body = _lint_source()
    assert re.search(r'ext === "ts"', body)
    assert 'runVendorScript("/vendor/sucrase/sucrase.min.js", "SUCRASE")' in body
    assert "docDiagnosticRange(state.doc" in body
    assert 'source: "TypeScript"' in body


def test_sucrase_is_asked_only_after_the_tree_found_nothing():
    body = _lint_source()
    assert re.search(r"if \(!found\.length && ext === \"ts\"\) found = await sucraseFound\(\)", body)
