"""The motion pass stays a recipe, and stays cheap (INBOX 459 (2)).

The owner asked for "cheap css animations to things like the horizontal pill
selectors and sidebars ... but dont over do it in a vibecoded way". DESIGN.md's
recipe index has one "Motion" row for what came of it; this holds the row:

- **One indicator.** A selection that moves between options (a `.seg`, the top
  bar's tabs, the sub-tab strips, the Settings sections and a pane's groups)
  is drawn by one shared recipe: the strip's `::before`, placed on the chosen
  option by `glideStrip` (shell-reminders.js) through `--glide-x/y/w/h`, and
  moved from where it was drawn by a `transform` animation on that
  pseudo-element (the owner, 2026-10-05: "Also like the smooth slide across
  tabs"). A second indicator, per control, is how ten strips end up moving
  ten ways. It replaced a CSS-anchored `::before` whose four insets were the
  one layout property in motion in the app, so no inset moves anywhere now.
- **Only the compositor's properties move.** Every rule in a section headed
  `/* --- motion:` transitions or starts from `opacity`, `transform`,
  `translate`, `scale` or a colour, and nothing else.

Reduced motion is not a rule here: the polish follows Interface animations
(`data-ui-motion`, the `--ui-*` tokens; `tests/test_motion_tokens.py`), and
`scratchpad/ui-sweeps/motion1005.js` measures the indicator gliding with the
switch on under reduced motion and landing at once with it off. Like the other frontend lints this cannot see the
DOM; the sweep is what runs against a browser.
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_DIR

ROOT = CSS_DIR.parents[1]
JS_DIR = ROOT / "frontend" / "js"

#: What a motion rule may move. Colours change paint, not layout, and a label
#: that changes colour as the fill arrives under it is part of the glide.
COMPOSITOR = {
    "opacity", "transform", "translate", "scale", "rotate",
    "color", "background-color", "border-color", "outline-color", "box-shadow",
    # `display` and `overlay` with `allow-discrete` only hold an element
    # in the tree for an exit fade; they animate nothing themselves.
    "display", "overlay",
}
INSETS = {"top", "right", "bottom", "left"}
NOT_PROPERTIES = {
    "ease", "ease-in", "ease-out", "ease-in-out", "linear", "allow-discrete",
    "none", "normal",
}


def _blank_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


def _sheets() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(CSS_DIR.glob("*.css"))}


def _motion_sections() -> list[tuple[str, int, str]]:
    """Every `/* --- motion: ...` section: (file, first line, its CSS with
    comments blanked), running to the next `/* ---` head or the file's end."""
    out = []
    for name, text in _sheets().items():
        heads = [m.start() for m in re.finditer(r"/\* ---", text)]
        for i, start in enumerate(heads):
            if not text.startswith("/* --- motion:", start):
                continue
            end = heads[i + 1] if i + 1 < len(heads) else len(text)
            out.append((name, text.count("\n", 0, start) + 1, _blank_comments(text[start:end])))
    return out


def _rules(css: str):
    """(selector, body) for every innermost rule, at-rules unwrapped."""
    for m in re.finditer(r"([^{};]+)\{([^{}]*)\}", css):
        yield " ".join(m.group(1).split()), m.group(2)


def _transitioned(body: str) -> set[str]:
    found: set[str] = set()
    for m in re.finditer(r"(?<![-\w])transition(?:-property)?\s*:([^;]*)", body):
        value = re.sub(r"var\([^)]*\)", " ", m.group(1))
        for part in value.split(","):
            for token in part.split():
                token = token.lower()
                if token in NOT_PROPERTIES or re.match(r"^[\d.]+m?s$", token):
                    continue
                found.add(token)
    return found


def test_there_are_motion_sections_to_check():
    names = {name for name, _, _ in _motion_sections()}
    assert names, "no `/* --- motion:` section found: the lint below would pass on nothing"


def test_motion_rules_move_only_what_the_compositor_moves():
    offenders = []
    for name, line, css in _motion_sections():
        for selector, body in _rules(css):
            moved = _transitioned(body)
            allowed = COMPOSITOR
            bad = sorted(moved - allowed)
            if bad:
                offenders.append(f"{name} (section from line {line}): `{selector}` transitions {', '.join(bad)}")
    assert not offenders, "\n".join(offenders) + (
        "\n\nA motion rule moves opacity, transform, translate, scale or a colour "
        "(DESIGN.md, the recipe index's Motion row). The selection indicator's "
        "insets are the one exception and live in its own rule."
    )


def test_starting_styles_in_motion_sections_set_only_compositor_properties():
    offenders = []
    for name, line, css in _motion_sections():
        for m in re.finditer(r"@starting-style\s*\{", css):
            depth, i = 1, m.end()
            while depth and i < len(css):
                depth += {"{": 1, "}": -1}.get(css[i], 0)
                i += 1
            for selector, body in _rules(css[m.end():i - 1]):
                props = {p.group(1).lower() for p in re.finditer(r"(?<![-\w])([a-z-]+)\s*:", body)}
                bad = sorted(props - COMPOSITOR)
                if bad:
                    offenders.append(f"{name} (section from line {line}): @starting-style `{selector}` sets {', '.join(bad)}")
    assert not offenders, "\n".join(offenders)


def test_the_selection_indicator_is_one_recipe():
    css = "".join(_blank_comments(t) for t in _sheets().values())
    flat = " ".join(css.split())
    assert "anchor-name: --glide" not in flat and "position-anchor: --glide" not in flat, (
        "the anchored indicator is back beside the measured one: one recipe draws every strip"
    )
    boxes = re.findall(r"(?:(?<=[{}])|\A)([^{}]*::before)\s*\{([^{}]*var\(--glide-x\)[^{}]*)\}", css)
    assert len(boxes) == 1, f"{len(boxes)} rules draw a sliding indicator; one does"
    selector, body = boxes[0]
    assert ".has-glide::before" in selector and "translate: var(--glide-x) var(--glide-y)" in body
    assert "transition" not in body, "the indicator moves by its transform animation, not a transition"
    for selector, body in _rules(css):
        assert not (_transitioned(body) & INSETS), f"`{selector}` transitions an inset"


def test_no_script_names_an_anchor():
    offenders = [
        p.name for p in sorted(JS_DIR.glob("*.js"))
        if re.search(r"anchorName|anchor-name|positionAnchor|position-anchor", p.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        f"{offenders} set an anchor in script: the glide is CSS alone, moved by the `.active` class "
        "every strip already sets"
    )


def test_every_strip_glides_on_the_compositor_in_every_engine():
    """The owner, 2026-10-04 and 2026-10-05: "a slight css sliding animation
    for the active tab ... cheap but looks professional", "Also like the
    smooth slide across tabs". One function wires every strip; it animates
    `transform` alone, on the `::before`, for `--ui-slow`, so Interface
    animations governs it and reduced motion does not."""
    js = (JS_DIR / "shell-reminders.js").read_text(encoding="utf-8")
    init = js[js.index("function glideStrip(strip)") :]
    init = init[: init.index("\n}\n")]
    assert "strip.animate(" in init and 'pseudoElement: "::before"' in init
    assert re.findall(r"\{ (\w+): `", init) == ["transform"], "the glide animates something other than transform"
    assert '"--ui-slow"' in init, "the glide does not read the Interface animations token"
    assert "prefers-reduced-motion" not in init and "dataset.motion" not in init, (
        "the glide asks reduced motion; Interface animations decides it"
    )
    strips = re.search(r'const GLIDE_STRIPS = "([^"]+)"', js).group(1)
    for strip in ("#tab-bar", "#settings-nav", ".settings-nav-groups", ".tabs-line", ".seg"):
        assert strip in strips, f"{strip} has no sliding indicator"
    assert 'glideStrip($("tab-bar"));' in js
