"""The manual's few pictures (L-world-class-785; the owner, 2026-11-12: "add a few pictures").

A picture only where words alone leave the layout unclear: the Graph, the Timeline and a
board. One entry per topic id, read by `help_chat.help_listing` (the manual and Settings,
Help draw an `<img>` from it) and by `scratchpad/ui-sweeps/help-images.py`, which writes the
WebP files. `tests/test_manual_parity.py` holds the list to the files on disk, their size and
the topics that exist, so a picture cannot go missing or grow unnoticed.
"""

from __future__ import annotations

#: Every file is this many CSS pixels wide, so the page reserves its box before it loads.
WIDTH = 720
HEIGHT = 450

#: topic id -> the file under `frontend/img/help/`, the README shot it is made from
#: (`scratchpad/ui-sweeps/readmeshots.js`'s `file`), and the alt text.
HELP_IMAGES: dict[str, dict[str, str]] = {
    "graph": {
        "file": "graph.webp",
        "shot": "graph",
        "alt": "The Graph tab: notes as dots, joined by lines, grouped into coloured clusters.",
    },
    "timeline": {
        "file": "timeline.webp",
        "shot": "timeline",
        "alt": "The Timeline tab: notes in date order down a line, newest first.",
    },
    "whiteboard": {
        "file": "whiteboard.webp",
        "shot": "whiteboard",
        "alt": "A board: sticky notes, a flow chart and a toolbar along the bottom.",
    },
}


def image_for(topic_id: str) -> dict | None:
    """The picture for a topic as the manual's JSON carries it, or None."""
    entry = HELP_IMAGES.get(topic_id)
    if entry is None:
        return None
    return {"src": f"/img/help/{entry['file']}", "alt": entry["alt"], "width": WIDTH, "height": HEIGHT}
