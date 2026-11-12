"""L-documents-14: the code-keys.js sweep closed the keybindings sheet with
docIdeCloseKeys, which is private to documents-ide.js; it presses the
sheet's own Close button instead."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_sweep_closes_the_sheet_by_its_button():
    sweep = (ROOT / "scratchpad/ui-sweeps/code-keys.js").read_text(encoding="utf-8")
    assert "docIdeCloseKeys" not in sweep
    assert '#doc-keys-overlay button[aria-label=\\"Close\\"]' in sweep
