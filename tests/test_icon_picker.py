"""The one icon and emoji picker (MINDMAP_PLAN.md decisions 43 to 46; INBOX 642).

The owner: "an emoji and icon widget library which can be dragged and placed in
the whiteboard and mindmap and which are also available in text editors and
formatting toolbars". One lazy module, `icon-picker.js`, opened by every surface
that offers an icon or an emoji. What this holds:

- it is fetched with its own stylesheet on first use (`pickIconOrEmoji`), so
  the boot budget does not pay for it;
- every emoji it offers is one a map topic's icon slot accepts (the server's
  `_is_one_emoji`), so no pick is refused on save;
- it is the only new emoji table (the document editor's `:shortcode:` table
  predates it), and the surfaces that offer a glyph open it;
- the recipe index names it.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.api.routes_whiteboard import _is_one_emoji
from tests import _js_scope

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
PICKER = _js_scope.unwrapped((JS / "icon-picker.js").read_text(encoding="utf-8"))
APP = (JS / "app.js").read_text(encoding="utf-8")


def _emoji_source() -> list[tuple[str, str, str]]:
    block = PICKER[PICKER.index("const ICON_EMOJI_SOURCE = [") : PICKER.index("\n];", PICKER.index("const ICON_EMOJI_SOURCE"))]
    groups = re.findall(r'\["(\w+)", "([^"]+)",\s*((?:"[^"]*"(?:\s*\+\s*)?)+)\]', block)
    out = []
    for key, label, body in groups:
        joined = "".join(re.findall(r'"([^"]*)"', body))
        decoded = re.sub(r"\\u\{([0-9A-Fa-f]+)\}", lambda m: chr(int(m.group(1), 16)), joined)
        out.append((key, label, decoded))
    return out


def test_the_picker_is_fetched_on_first_use_with_its_own_styles():
    """Not at boot: `LAZY_MODULES.iconPicker` names the stylesheet and the
    script, `LAZY_ENTRY_POINTS` stands in for `openIconPicker`, and every
    caller goes through the one door in editor.js (a boot script every
    caller reaches) rather than calling `openIconPicker` itself."""
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert 'iconPicker: ["/css/icon-picker.css", "/js/icon-picker.js", "/js/icon-picker-icons.js"]' in app
    editor = (JS / "editor.js").read_text(encoding="utf-8")
    loader = editor[editor.index("function pickIconOrEmoji(") :][:400]
    assert 'iconPicker: ["openIconPicker"]' in app and "openIconPicker(options)" in loader
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "/js/icon-picker.js" not in index and "/css/icon-picker.css" not in index, "the picker must not load at boot"
    for path in JS.glob("*.js"):
        if path.name in ("icon-picker.js", "editor.js"):
            continue
        assert "openIconPicker(" not in path.read_text(encoding="utf-8"), f"{path.name} calls openIconPicker; use pickIconOrEmoji"


def test_every_emoji_offered_is_one_a_topic_icon_accepts():
    groups = _emoji_source()
    assert len(groups) == 9, [g[0] for g in groups]
    count = 0
    for key, _label, source in groups:
        for pair in filter(None, source.split(",")):
            name, glyph = pair.split("=", 1)
            assert re.fullmatch(r"[a-z0-9_]+", name), (key, name)
            assert _is_one_emoji(glyph), (key, name, [hex(ord(c)) for c in glyph])
            count += 1
    assert count >= 300, count


def test_the_surfaces_that_offer_a_glyph_open_the_one_picker():
    map_js = (JS / "whiteboard-map.js").read_text(encoding="utf-8")
    assert "pickIconOrEmoji(" in map_js[map_js.index("function wbMapOpenIconPicker") :][:800]


def test_no_third_emoji_table():
    """The picker's set and nothing else (the document editor's shortcodes are
    aliases of it now): a file with dozens of escaped pictographs is an emoji table."""
    tables = sorted(
        path.name
        for path in JS.glob("*.js")
        if len(re.findall(r"\\u\{1F[0-9A-Fa-f]{3}\}", path.read_text(encoding="utf-8"))) > 40
    )
    #: avatars.js holds emoji the companion recognises in what a person typed
    #: (matchers, not a table to pick from: test_no_ui_emoji.py says so).
    assert tables == ["avatars.js", "icon-picker.js"], tables


def test_the_recipe_index_names_it():
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "`openIconPicker(" in design


def test_every_shortcode_aliases_a_picker_emoji_and_the_old_248_survive():
    """The document editor's `:shortcode:` names are aliases of the picker's
    emoji (folded from `DOC_EMOJI_SOURCE`): each target must exist, so none
    resolves to nothing, and the table keeps its 248 names."""
    names = {pair.split("=")[0] for _, _, body in _emoji_source() for pair in body.split(",") if pair}
    block = PICKER[PICKER.index("const ICON_SHORTCODES =") :]
    block = block[: block.index(";\n")]
    codes = "".join(re.findall(r'"([^"]*)"', block))
    pairs = [pair.split("=") for pair in codes.split(",") if pair]
    assert len(pairs) == 248
    assert [code for code, target in pairs if target not in names] == []
    assert {"heart", "+1", "-1", "fire", "umbrella", "bug", "confounded"} <= {code for code, _ in pairs}
    # The completion asks the picker lazily, at call time, and says so to the loader.
    prose = (JS / "documents-prose.js").read_text(encoding="utf-8")
    assert "window.iconShortcodes?.()" in prose and 'ensureModule("iconPicker")' in prose
    assert "DOC_EMOJI_SOURCE" not in prose
