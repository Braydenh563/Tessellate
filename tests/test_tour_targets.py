"""Every id a tour step points at exists in the page (UI_MODERNISATION_PLAN 12z, row 2).

A step whose `target` or `or` selector names an id that index.html does not
carry has nothing to point at: the card floats with no arrow. This is the
static half of "tour steps whose target is visible and non-empty"; the
visible half needs a browser (scratchpad/ui-sweeps/tour*.js).
"""

from __future__ import annotations

import re
from pathlib import Path
from tests import _js_scope

ROOT = Path(__file__).resolve().parent.parent
TOUR = _js_scope.unwrapped((ROOT / "frontend" / "js" / "tour.js").read_text(encoding="utf-8"))
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
JS_TEXT = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend" / "js").glob("*.js"))

_SELECTOR = re.compile(r"""^\s*(?:target|or)\s*:\s*["']([^"']+)["']""", re.M)
_ID = re.compile(r"#([A-Za-z][\w-]*)")


def _ids() -> set[str]:
    found = set()
    for selector in _SELECTOR.findall(TOUR):
        found.update(_ID.findall(selector))
    return found


def test_the_tour_names_some_targets():
    assert len(_ids()) >= 10


def test_every_tour_id_is_in_the_page_or_made_by_a_script():
    missing = sorted(
        i for i in _ids()
        if f'id="{i}"' not in HTML and f"'{i}'" not in JS_TEXT and f'"{i}"' not in JS_TEXT
    )
    assert not missing, f"tour targets with no element: {missing}"


def _step_block(target: str) -> str:
    """The text of the first tour step naming `target`, up to the next step."""
    start = TOUR.index(f'target: "{target}"')
    end = TOUR.find("target:", start + 10)
    return TOUR[start:end]


def test_a_step_on_a_control_a_phone_hides_is_left_out_by_media_not_dropped_mid_run():
    """Source text: ui-modernisation 60. At 390 wide `#wb-add-note` is
    display:none (07-whiteboard-misc.css, max-width 599.98px), so the step
    was planned, counted 4, then dropped mid-run and the counter read 4/4/3.
    The step names the breakpoint instead, as the map's Add a topic step does,
    and its words use the button's own name, Sidebar."""
    block = _step_block("#wb-add-note")
    assert 'media: "(min-width: 600px)"' in block
    assert "Sidebar" in block and "Notes opens" not in block


def test_the_make_something_new_step_follows_the_create_button_into_the_empty_state():
    """Source text: ui-modernisation 60. On a notebook with nothing in it
    library.js hides the dock's `#library-new-doc` and shows
    `#library-empty-create` in its place, so the step lost its target and was
    dropped mid-run (1440 Library counter 4/4/3). It carries the other button
    as `or`, with the words for it."""
    block = _step_block("#library-new-doc")
    assert 'or: "#library-empty-create"' in block
    assert "orText:" in block
