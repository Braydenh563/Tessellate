"""The IDE shell sweep drives the run panel through public names only.

`docIdeRunApply` became private to documents-ide.js's wrapper when the file
was split, so the sweep's direct call threw and the script exited 1 with no
failed check. It now resizes the panel by dragging `.doc-run-resize`, the grip
a person drags."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_ide_shell_sweep_resizes_through_the_grip():
    sweep = (ROOT / "scratchpad" / "ui-sweeps" / "ide-shell.js").read_text(encoding="utf-8")
    code = "\n".join(line for line in sweep.splitlines() if not line.strip().startswith("//"))
    assert "docIdeRunApply" not in code
    assert ".doc-run-resize" in code and "page.mouse.down()" in code
    ide = (ROOT / "frontend" / "js" / "documents-ide.js").read_text(encoding="utf-8")
    exported = ide[ide.rindex("Object.assign(window"):]
    assert "docIdeRunApply" not in exported, "if it is public again, the sweep may call it"
    assert "doc-run-resize" in ide
