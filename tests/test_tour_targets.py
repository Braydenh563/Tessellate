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
