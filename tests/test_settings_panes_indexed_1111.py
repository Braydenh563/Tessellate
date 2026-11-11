"""Every Settings pane has a row the Settings search can land on (OPEN.md F6, "Settings panes indexed").

`settingRowsScan` (settings-find.js) reads a pane's rows by `SETTING_ROW_SELECTOR`
and skips the pane title. A pane whose only words are its title, a muted line and
a field named by `aria-label` has no row at all, so no query finds it: measured
in the app, 20 of 21 panes gave rows and "What it remembers" (Memory) gave none, so
"remember", "standing instructions" and "memory" found nothing in that pane.

This reads the Settings markup, so it holds for the panes the page ships; the
panes whose rows the script draws are listed with the measured row count.
"""

from __future__ import annotations

import re
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "frontend" / "index.html"

#: Panes whose rows are drawn by script after the page loads (so the markup has
#: none), with the row count the live scan gave on an empty notebook.
DRAWN_BY_SCRIPT = {
    "templates": 1,
}

def _panes() -> dict[str, str]:
    html = INDEX.read_text(encoding="utf-8")
    start = html.index('id="settings-body-template"')
    body = html[start : html.index("</script>", start)]
    parts = re.split(r'<section class="settings-section[^"]*" id="settings-', body)[1:]
    return {part.split('"', 1)[0]: part for part in parts}


def _rows(markup: str) -> int:
    # The pane title's own h3 is skipped by the scan, and so are help popovers.
    markup = re.sub(r'<div class="dock settings-pane-title".*?</div>\s*</div>', "", markup, flags=re.S)
    markup = re.sub(r'<div class="help-body.*?</div>', "", markup, flags=re.S)
    return len(re.findall(r"<(?:label|h4|legend|h3)\b|class=\"[^\"]*\b(?:setting-label|setting-check|check-row|checkbox-label)\b", markup))


def test_every_settings_pane_has_a_row_the_search_can_find():
    panes = _panes()
    assert len(panes) >= 20, "the Settings panes were not found: has the template moved?"
    bare = [name for name, markup in panes.items() if name not in DRAWN_BY_SCRIPT and _rows(markup) == 0]
    assert not bare, f"no findable row in: {bare} (give the field a visible or visually-hidden <label>, settings-find.js)"
