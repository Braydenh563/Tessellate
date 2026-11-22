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
# scratchpad/ui-sweeps/owner257.js (open 260, rail 48, peek 260, content x unmoved, 0 clipped).
_ROOT = Path(__file__).resolve().parent.parent


def _css():
    return "".join(p.read_text(encoding="utf-8") for p in sorted((_ROOT / "frontend" / "css").glob("*.css")))


def test_notes_peek_outranks_the_notes_rail_rules():
    css = _css()
    rule = re.search(r"#tab-notes \.layout-sidebar-collapsed > #sidebar\.sidebar-collapsed:is\(:hover[^{]*\{([^}]*)\}", css)
    assert rule, "the notes peek needs its own (2,3,0) rule: #tab-notes #sidebar(.sidebar-collapsed) is (2,1,0)"
    assert "position: sticky" in rule.group(1)
    assert "width: var(--saved-width)" in rule.group(1)


def test_peek_width_is_the_fitted_open_width():
    js = (_ROOT / "frontend" / "js" / "sheets-selects.js").read_text(encoding="utf-8")
    body = js[js.index("function applySidebarWidth("):js.index("\n}\n", js.index("function applySidebarWidth("))]
    assert 'setProperty("--saved-width", fitted)' in body


def test_notes_sidebar_is_wired_when_its_surface_is_built():
    js = (_ROOT / "frontend" / "js" / "sheets-selects.js").read_text(encoding="utf-8")
    assert re.search(r'for \(const name of \[[^\]]*"notes"[^\]]*\]\) onSurface\(name, wire\)', js)


def test_local_map_caret_leads_like_the_other_folds():
    """Owner bug 7: the Local map's caret sat at the end, after the count chip and the expand icon."""
    html = (_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    head = html[html.index('class="panel-head graph-pane-head"'):html.index("</h3>", html.index('class="panel-head graph-pane-head"'))]
    assert head.index('id="graph-pane-toggle"') < head.index('class="graph-pane-title"')
    assert "ph-caret-down" in head and "ph-caret-up" not in head
    js = (_ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
    assert '"ph ph-caret-down" : "ph ph-caret-right"' in js
    css = _css()
    assert re.search(r"\.graph-pane-actions \{\s*gap: var\(--space-2\)", css)
    assert re.search(r"\.graph-pane-toggle \{[^}]*margin-inline-end: var\(--space-2\)", css)


def test_a_settings_group_keeps_a_gap_above_it():
    """Owner bug on #257: Confirmed patterns sat flush (0px) under What it remembers' list; Skills,
    Tasks and What it learned had the same. Measured 16px after; owner257.js checks every page."""
    assert re.search(r"\.settings-section > :not\(\.settings-group\) \+ \.settings-group \{\s*margin-top: var\(--space-6\)", _css())


# The Documents sidebar (owner 2026-11-22 on #257), measured by owner257.js at 1440, the 136px
# floor and 2560: New had a blank 26px face, the list scrolled sideways (176 in 144), card meta
# wrapped (55 to 73px) and All in Library had no icon gap.
def test_doc_new_keeps_its_icon_at_every_width():
    lazy = (_ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert not re.search(r"\.doc-new-split #doc-new \.ph-lead\s*\{\s*display:\s*none", lazy)


def test_doc_head_wraps_only_below_its_one_row_width():
    css = _css()
    block = css[css.index("@container doc-sidebar (width < 11rem)"):]
    assert re.search(r"#doc-sidebar-list > \.sidebar-head \{\s*flex-wrap: wrap;", block[:300])


def test_doc_card_meta_keeps_one_line():
    lazy = (_ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    rule = lazy[lazy.index(".doc-item-meta {"):]
    rule = rule[:rule.index("}")]
    assert "white-space: nowrap" in rule and "max-width: 100%" in rule and "text-overflow: ellipsis" in rule


def test_browse_all_links_use_the_token_gap():
    css = _css()
    assert re.search(r"\.conv-browse-all \{[^}]*align-items: center;[^}]*gap: var\(--space-2\)", css)
