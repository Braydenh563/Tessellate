"""L304: the diagram builder's Source view can fold long lines.

The field stays unwrapped by default (a line number sits on its own line); the dialog's menu has a
Wrap long lines row that turns the field's `wrap` to soft, hides the numbers while lines fold (they
would no longer sit beside their lines), is kept on the device, and says so in the Guide.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMBED = (ROOT / "frontend" / "js" / "diagram-embed.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def test_menu_has_a_wrap_row_that_flips_the_fields_wrap():
    assert '"ph:text-align-left Wrap long lines"' in EMBED
    assert '"ph:arrows-out-line-horizontal Stop wrapping"' in EMBED
    assert re.search(r'field\.setAttribute\("wrap", on \? "soft" : "off"\)', EMBED)
    assert 'srcwrap.classList.toggle("is-wrapped", on)' in EMBED
    assert 'prefs.set("dgm-source-wrap"' in EMBED


def test_wrapped_source_hides_the_numbers_it_no_longer_aligns():
    rule = re.search(r"\.dgm-srcwrap\.is-wrapped \.dgm-gutter \{([^}]*)\}", CSS)
    assert rule and "display: none" in rule.group(1)


def test_the_guide_names_the_row():
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-lines"))
    assert "Wrap long lines, in the ... menu" in body
