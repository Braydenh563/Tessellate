"""The notes sidebar keeps its own render debt (owner bug 4 on #257) and peeks to its open width (bug 5).

`renderSidebar` skipped while Notes was hidden marked only the list's `data-stale`, which the tab
bar's press clears and which does not exist before the notes surface is built, so the categories
showed empty with no fold caret on the first Notes open."""
import re
from pathlib import Path

from tests._app_js import app_js_text


def _body(js, name):
    start = js.index(f"function {name}(")
    return js[start:js.index("\nfunction ", start + 1)]


def test_hidden_skip_records_the_sidebar_debt():
    body = _body(app_js_text(), "renderSidebar")
    hidden = body[:body.index("return;")]
    assert "renderSidebar.owed = true" in hidden
    assert "renderSidebar.owed = false" in body


def test_every_notes_reveal_pays_the_sidebar_debt():
    js = app_js_text()
    assert re.search(r"dataset\.stale \|\| renderSidebar\.owed\)\) renderSidebar\(\)", _body(js, "renderEntries"))
    assert js.count("dataset.stale || renderSidebar.owed)) renderEntries()") >= 1
    assert js.count("dataset.stale || renderSidebar.owed)) {") >= 1


# Owner bug 5: the collapsed rail's hover peek stayed 48px. Measured in the running app by
# scratchpad/ui-sweeps/notessidebar257.js (open 260, rail 48, peek 260, content x unmoved, 0 clipped).
_ROOT = Path(__file__).resolve().parent.parent


def _css():
    return "".join(p.read_text(encoding="utf-8") for p in sorted((_ROOT / "frontend" / "css").glob("*.css")))


def test_notes_peek_outranks_the_notes_rail_rules():
    css = _css()
    rule = re.search(r"#tab-notes \.layout-sidebar-collapsed > #sidebar\.sidebar-collapsed:is\(:hover[^{]*\{([^}]*)\}", css)
    assert rule, "the notes peek needs its own (2,3,0) rule: #tab-notes #sidebar(.sidebar-collapsed) is (2,1,0)"
    assert "position: sticky" in rule.group(1)
    assert "width: var(--peek-width" in rule.group(1)


def test_peek_width_is_the_fitted_open_width():
    js = (_ROOT / "frontend" / "js" / "sheets-selects.js").read_text(encoding="utf-8")
    body = js[js.index("function applySidebarWidth("):js.index("\n}\n", js.index("function applySidebarWidth("))]
    assert 'setProperty("--peek-width", fitted)' in body


def test_notes_sidebar_is_wired_when_its_surface_is_built():
    js = (_ROOT / "frontend" / "js" / "sheets-selects.js").read_text(encoding="utf-8")
    assert re.search(r'for \(const name of \[[^\]]*"notes"[^\]]*\]\) onSurface\(name, wire\)', js)
