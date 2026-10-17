"""INBOX 904 B26: opening a shape group must not throw the library list to the top.

The owner: "these dropdowns don't show anything" (Basic shapes, Flowchart more,
Arrows more, BPMN, Network and cloud). A draw.io group loads its file when it is
opened and the library redraws when it arrives; the redraw emptied the list and
its scroll went to 0, so a group opened low in the list (header at 1280px) was
rebuilt out of sight. Measured with `scratchpad/ui-sweeps/shapescroll904.js`:
scrollTop 1280 to 0, no tile of the opened group on screen.
"""

from __future__ import annotations

import re

from tests._app_js import with_pieces


def test_the_library_redraw_keeps_the_scroll_place():
    source = with_pieces("whiteboard-library.js")
    body = source[source.index("function wbRenderLibrary()") :]
    body = body[: body.index("\n}\n")]
    assert re.search(r"const top = query === wbLibState\.libQuery \? list\.scrollTop : 0;", body)
    assert "wbLibState.libQuery = query;" in body
    # restored after the tiles and the focus are placed, which can scroll it
    assert body.index("wbLibSetActive(keep") < body.index("list.scrollTop = top;")
