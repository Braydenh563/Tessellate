"""Source text: the design tokens sit in a cascade layer (L-ui-modernisation-1), from the row "Adopt CSS cascade layers (@layer tokens, base, components,
surfaces, overrides) so 08-consistency.css stops winning by specificity."
08-consistency.css has since been dissolved into the components; what is left
of the ask is the token layer. Every unlayered rule beats a layered one
whatever its specificity, so a theme, a palette or a component that sets a
token wins by being unlayered, not by out-scoring `:root[data-mode="dark"]`.

Measured before the wrap (`scratchpad`-free, a static pass over every sheet):
one token was set by a later unlayered rule of lower specificity than its
layered one, `--muted` in 02-chat-graph.css's `:root`, and that sheet sets the
dark value too, so the painted value is the same in both modes (and Classic's
pinned literals, `tests/test_theme_pins.py`, are untouched).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "frontend" / "css"
TOKENS = (CSS / "00-tokens-shell.css").read_text(encoding="utf-8")


def _strip(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _layer_bodies(css: str) -> list[str]:
    out, i = [], 0
    while (j := css.find("@layer tokens {", i)) >= 0:
        k = css.index("{", j)
        depth, m = 1, k + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(css[m], 0)
            m += 1
        out.append(css[k + 1 : m - 1])
        i = m
    return out


def test_the_layer_order_is_declared_first() -> None:
    """Source text: "@layer tokens". The order statement comes before any rule,
    so a later layer name lands after it, never ahead by accident."""
    text = _strip(TOKENS)
    first_rule = re.search(r"[^\s@][^{};]*\{", text).start()
    assert text.index("@layer tokens;") < first_rule


def test_the_palette_tokens_are_layered() -> None:
    """Source text: "so 08-consistency.css stops winning by specificity". The
    base and dark palettes are inside the layer."""
    bodies = "".join(_layer_bodies(_strip(TOKENS)))
    for token in ("--card:", "--ink:", "--muted:", "--space-1:", "--target-min", "--modal-bg-opaque"):
        if token in _strip(TOKENS):
            assert token in bodies, token
    assert ':root[data-mode="dark"]' in bodies


def test_the_token_layer_holds_tokens_only() -> None:
    """Source text: "@layer tokens". A rule that styles an element is not a
    token: in a layer its `!important` would outrank every unlayered one."""
    for body in _layer_bodies(_strip(TOKENS)):
        assert "!important" not in body
        for prop in re.findall(r"(?:[{;]|^)\s*([a-z-][\w-]*)\s*:(?!:)", body, flags=re.M):
            if prop.startswith("--"):
                continue
            assert prop == "color-scheme", prop


def test_only_the_token_sheet_opens_a_layer() -> None:
    """Source text: "@layer tokens, base, components, surfaces, overrides".
    One layer is built; another is added by name in the order statement first."""
    for sheet in sorted(CSS.glob("*.css")):
        if sheet.name == "00-tokens-shell.css":
            continue
        assert "@layer" not in _strip(sheet.read_text(encoding="utf-8")), sheet.name
