"""L-documents-14: scratchpad/ui-sweeps/code-keys.js closes the keybindings
sheet with docIdeCloseKeys, so documents-ide.js puts it on window."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_close_keys_is_on_window():
    src = (ROOT / "frontend/js/documents-ide.js").read_text(encoding="utf-8")
    line = next(l for l in src.splitlines() if l.strip().startswith("Object.assign(window, { docIde"))
    assert "docIdeCloseKeys" in line
    assert "docIdeCloseKeys" in (ROOT / "scratchpad/ui-sweeps/code-keys.js").read_text(encoding="utf-8")
