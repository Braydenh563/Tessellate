"""L593: the image viewer hands the focus back on close, and Back closes the
graph's note panel (it stayed open on the hidden map, 1440 and 390).

Driven in Chromium before the fix: Escape closed the viewer with the focus on
<body> (the opener lost); Back from the graph tab with the panel open went to
the Reminders tab and the panel was still open on return (width 448 at 390).
These are the shapes the suite can see.
"""

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_the_viewer_remembers_its_opener_and_gives_the_focus_back_on_close():
    src = _read("lightbox-view.js")
    open_at = src.index("function openLightbox(")
    assert "const opener = document.activeElement;" in src[open_at : open_at + 600]
    close = src[src.index("  const close = () => {") :][:600]
    assert "opener.focus(" in close and "opener?.isConnected" in close


def test_back_closes_the_graph_note_panel_before_walking_the_tab_history():
    src = _read("router-overlays.js")
    top = src[src.index("function routerCloseTopOverlay") : src.index("function routerBackHook")]
    assert 'getElementById("graph-popup")' in top and 'call("closeGraphPopup")' in top
    # Only a shown panel: one on a hidden tab has no layout box.
    assert "popup.offsetParent !== null" in top
