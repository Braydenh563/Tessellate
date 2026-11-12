"""Status lines in BACKLOG.md that name code must agree with the code.

A row that reads "Next:" while its feature is on the page sends the next
session to rebuild it (CLAUDE.md section 1: three sessions have). Each test
here pins one such row to the evidence that closed it, so the row cannot
drift back to "Next" and the evidence cannot be deleted while the row says
"Built".
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _row(number: int) -> str:
    """The text of one numbered table row in BACKLOG 115's refinement table."""
    text = (ROOT / "docs" / "roadmap" / "BACKLOG.md").read_text(encoding="utf-8")
    match = re.search(rf"^\| {number} \| (.*)$", text.split("\n| # | Refinement", 1)[1], re.M)
    assert match, f"BACKLOG 115 row {number} not found"
    return match.group(1)


def test_saved_searches_row_is_marked_built_with_its_evidence():
    row = _row(8)
    assert not row.startswith("**Next:**"), "saved searches are built; the row still says Next"
    assert "Built" in row.split("|")[0]
    # The evidence the row cites must still exist in the frontend.
    wiring = (ROOT / "frontend" / "js" / "settings-wiring.js").read_text(encoding="utf-8")
    for name in re.findall(r"`(renderSavedSearches|persistSavedSearches|saveCurrentSearch)`", row):
        assert f"function {name}(" in wiring
    assert "settings-wiring.js" in row
    assert 'id="saved-searches"' in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


#: Names the textarea-era document editor owned, none of which exist in the
#: frontend any more. A sweep that reads one throws inside the page and
#: reports nothing (the editor.js sweep did, for weeks, until it was
#: re-pointed at `docSurface()` on 2026-10-05).
_RETIRED_EDITOR_NAMES = (
    "docUndoStack",
    "docUndoReset",
    "DOC_UNDO_LIMIT",
    "focusDocLiveBlock",
    "#doc-live .lp-src",
)


def test_no_sweep_reads_the_retired_textarea_editor():
    js = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "js").glob("*.js")
    )
    revived = {name for name in _RETIRED_EDITOR_NAMES if name in js}
    assert not revived, f"the frontend defines {revived} again; retire the list or the names"
    offenders = []
    for sweep in sorted((ROOT / "scratchpad" / "ui-sweeps").glob("*.js")):
        code = "\n".join(
            line
            for line in sweep.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("//")
        )
        hits = [name for name in _RETIRED_EDITOR_NAMES if name in code]
        if hits:
            offenders.append(f"{sweep.name}: {hits}")
    assert not offenders, "sweeps reading retired editor names: " + "; ".join(offenders)


def test_quickaccess_sweep_uses_the_dashboard_docks_customise_menu():
    """INBOX 488 moved Quick access's row menu to the dock's Customise; INBOX
    524 made adding a checklist dialog. The sweep must not drive the old ones."""
    code = (ROOT / "scratchpad" / "ui-sweeps" / "quickaccess.js").read_text(encoding="utf-8")
    assert "#dash-quicklinks .launch-head', '" not in code
    assert "#dash-customise" in code
    assert "rich-picker-row" not in code
    dashboard = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    # The two menu rows the sweep presses exist under those words.
    for row in ("Edit quick access", "Reset quick access"):
        assert row in code and row in dashboard


def test_mappan_sketch_fixture_is_a_path_the_board_can_draw():
    """The rect fixture stored `{type: "rect", x, y, width, height}`, which is
    not a path, so the board set it as `d` and the browser logged "Expected
    moveto path command" on every draw. A shape sketch is `{d, shape, ...}`."""
    code = (ROOT / "scratchpad" / "ui-sweeps" / "mappan.js").read_text(encoding="utf-8")
    assert 'stringify({ type: "rect"' not in code
    match = re.search(r'd: "(M [^"]+)", shape: "rect"', code)
    assert match, "the rect sketch fixture no longer carries a path"
    assert match.group(1).startswith("M ") and match.group(1).rstrip().endswith("Z")
    assert "no console errors" in code, "the sweep must assert on what the page logs"


def test_skeletons_sweep_names_the_views_that_are_right_to_read_blank():
    code = (ROOT / "scratchpad" / "ui-sweeps" / "skeletons.js").read_text(encoding="utf-8")
    block = code.split("const EXPECTED_BLANK = [", 1)[1].split("];", 1)[0]
    for view in ("chat/conversations", "documents/list", "graph"):
        assert f"name: '{view}'" in block
    # The phone-only exemption is bounded: documents/list is a drawer below 600.
    assert re.search(r"documents/list.*maxWidth: 599", block)
    assert "process.exit(failed ? 1 : 0)" in code
