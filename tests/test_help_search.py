"""Settings, Help is searchable and its text carries emphasis (INBOX 520).

The owner: "the text in the help settings page needs to be like keyword
searchable and key things like key characters or hotkeys or item/location names
should be in like inline codeblocks or bolded/italicised". The pure parts (which
topics a query keeps, which words get a kbd, a strong or a code chip) run in
node; the DOM parts are held by shape, and measured in a browser by
`scratchpad/ui-sweeps/helpsearch.js`.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from tests._js_scope import unwrapped, unwrapped_copy

ROOT = Path(__file__).resolve().parents[1]
JS = unwrapped((ROOT / "frontend" / "js" / "settings-find.js").read_text(encoding="utf-8"))
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")

#: meaning.js first: the Settings bundle loads the two together (Brief 94).
HARNESS = """
const vm = require("vm"), fs = require("fs"), path = require("path");
const ctx = vm.createContext({ document: { addEventListener() {} }, apiJson: () => new Promise(() => {}) });
//: meaning.js is one closure and puts its exports on `window` (ranked row 37a); the context is the window, so they are the globals settings-find.js calls.
ctx.window = ctx;
vm.runInContext(fs.readFileSync(path.join(path.dirname(process.argv[1]), "meaning.js"), "utf8"), ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const call = (src) => JSON.stringify(vm.runInContext(src, ctx));
console.log(call(process.argv[2]));
"""


def _node(expr: str):
    unwrapped_copy(ROOT / "frontend" / "js" / "meaning.js")  # the harness reads it from beside the copy of settings-find.js
    out = subprocess.run(
        ["node", "-e", HARNESS, str(unwrapped_copy(ROOT / "frontend" / "js" / "settings-find.js")), expr],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def test_every_term_of_the_query_must_match() -> None:
    assert _node('helpQueryTerms("  Dark  mode ")') == ["dark", "mode"]
    assert _node('helpQueryTerms("")') == []
    #: A tier now (Brief 94): above 1 held by name, 1 by the body only, 0 not.
    assert _node('helpMatches(["dark", "mode"], "switch to dark theme mode")') > 1
    assert _node('helpMatches(["dark", "mode"], "switch to dark theme")') == 0
    assert _node('helpMatches(["dark", "mode"], "switch to dark theme mode", null, "themes")') == 1
    assert _node('helpMatches([], "anything")') > 0


def test_the_field_is_the_search_field_recipe_under_the_welcome_and_tours() -> None:
    pane = HTML[HTML.index('id="settings-help"') :]
    pane = pane[: pane.index('id="settings-about"')]
    field = re.search(r'<div class="search-field[ "][^>]*>(.*?)</div>', pane, re.S)
    assert field, "Help opens with a .search-field"
    assert 'class="ph ph-magnifying-glass search-field-icon"' in field.group(1)
    assert 'id="help-search"' in field.group(1) and "search-field-input" in field.group(1)
    assert 'aria-label="Search help"' in field.group(1)
    # INBOX 871: under the Welcome and tours group, above the topics it filters
    # (so the keyboard's Tab order follows the picture).
    assert pane.index("tour-replay") < pane.index('id="help-search"') < pane.index('id="help-topics"')
    assert 'id="help-empty"' in pane and "Nothing in Help matches" in pane
    assert 'id="help-search-status"' in pane and 'aria-live="polite"' in pane


def test_the_filter_builds_marks_from_nodes_and_escape_clears() -> None:
    body = JS[JS.index("function helpApplySearch") :]
    body = body[: body.index("\nfunction renderHelpTopics")]
    assert 'createElement("mark")' in JS
    assert "innerHTML" not in JS and "insertAdjacentHTML" not in JS
    assert '"Escape"' in JS and "classList.toggle" in body
    assert "details.open" in body or ".open =" in body
