"""Owner reports, 2026-10-27: the popup agent's Send button, the graph fold
chevron touching its "?"."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_popup_agent_has_a_send_button_that_takes_enters_path():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    bar = html[html.index('class="command-palette-bar"'):]
    bar = bar[: bar.index("</div>")]
    assert re.search(r'<button[^>]*id="command-palette-send"[^>]*aria-label="Send"', bar)
    js = (ROOT / "frontend/js/palette.js").read_text(encoding="utf-8")
    assert '$("command-palette-send").addEventListener("click", cmdPaletteSend)' in js
    keydown = js[js.index('cmdPaletteInput.addEventListener("keydown"'):]
    assert "cmdPaletteSend();" in keydown[: keydown.index("});")]


def test_the_graph_fold_chevron_stops_a_gap_short_of_the_help_button():
    css = (ROOT / "frontend/css/graph-lazy.css").read_text(encoding="utf-8")
    rule = css[css.index("#graph-options .graph-fold-wrap > details > summary"):]
    rule = rule[: rule.index("}")]
    assert "max(var(--control-h), var(--target-min)) + var(--space-" in rule


def test_the_first_answer_ticks_get_started_even_after_leaving_for_the_dashboard():
    """E2E first-run, 2026-10-27: the answer took 2.4 s in CI, the dashboard
    was opened at 0.8 s and drew "1 of 3 done" for good. The badge refresh
    that follows every saved answer redraws the steps on the first one."""
    js = (ROOT / "frontend/js/capture-ask.js").read_text(encoding="utf-8")
    body = js[js.index("async function loadAskHistoryBadge()"):]
    body = body[: body.index("\n}\n")]
    assert "if (stats.total === 1) renderFirstStepsLazy();" in body
