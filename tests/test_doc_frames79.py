"""L-documents-79: the frame sweep for the document editor."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_editor_frame_sweep_counts_every_kind_of_wake_site():
    sweep = (ROOT / "scratchpad" / "ui-sweeps" / "docframes79.js").read_text()
    for kind in ("requestAnimationFrame", "addEventListener", "ResizeObserver", "MutationObserver", "longtask", "setCPUThrottlingRate"):
        assert kind in sweep
