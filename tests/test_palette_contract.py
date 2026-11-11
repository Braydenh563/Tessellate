"""The command palette's matching stays whole and stays commands and places.

**Why this file exists.** The palette's reminder filter once read `r.content`,
and a reminder has no `content`, its field is `text`. `undefined.toLowerCase()`
threw partway through `paletteMatches` and every group was lost with it. Since
INBOX 666 the palette no longer lists content (notes, documents, reminders,
conversations, files, boards: Find anything's), so the payload half of this
file is gone; what is left keeps the same failure class out (a field read goes
through `paletteText`) and pins the new split.
"""

from __future__ import annotations

import re
from tests._app_js import app_js_text

def _palette_matches_source() -> str:
    text = app_js_text()
    start = text.index("function paletteMatches(")
    #: app-palette.js is wrapped in one IIFE (W29 carve 7), so the function sits
    #: at two spaces and ends at the first two-space closing brace; ending at the
    #: next column-0 `function` read the whole rest of the file.
    end = text.index("\n  }\n", start) + 5
    return text[start:end]


def test_palette_field_reads_go_through_the_guard():
    """One malformed record must cost one missing group, not all of them.

    Every `.toLowerCase()` directly on a payload field inside `paletteMatches`
    is a chance for the whole function to throw, so they go through
    `paletteText`, which returns "" for anything that is not a string.
    """
    source = _palette_matches_source()
    raw = re.findall(r"\b[a-z]\.\w+\.toLowerCase\(\)", source)
    assert not raw, f"these bypass paletteText and can throw the palette away: {raw}"


def test_the_palette_is_commands_and_places_only():
    """INBOX 666 (the owner: "I thought [the palette] was just for quick
    commands and navigation, not for finding notes and documents"). Content
    groups are Find anything's; the palette keeps commands, places (tabs,
    sub-tabs, Settings pages, categories, tags) and one handoff row."""
    source = _palette_matches_source()
    for group in ("Notes", "Documents", "Files", "Boards & maps", "Reminders", "Conversations"):
        assert f'group: "{group}"' not in source, f"the palette lists {group} again"
    #: The hand-written rows are gathered in `paletteBase` since Brief 90.
    text = app_js_text()
    base = text[text.index("function paletteBase(") :]
    base = base[: base.index("\nfunction ")]
    assert "paletteBase(" in source
    assert "paletteCommands()" in base and "notesPaletteCommands(" in base


def test_the_palette_returns_every_group_it_builds():
    """A group that is built and then left out of the return is dead code that
    looks alive: the "never ran once" shape again. Every `*Matches` list the
    function builds has to appear in what it returns."""
    source = _palette_matches_source()
    built = set(re.findall(r"const (\w+Matches) =", source))
    returned = source[source.rindex("return ["):]
    missing = sorted(name for name in built if name not in returned)
    assert not missing, f"built but never returned: {missing}"
