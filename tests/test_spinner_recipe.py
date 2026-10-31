"""One recipe for "the app is working on it" (INBOX 441 (2)).

The owner, over a screenshot of a note reading "Atlas is reading..." beside a
small blue ring: "make sure all these loading spinners are consistent across
the app". Measured before this recipe (`scratchpad/ui-sweeps/spinners.js`),
the same state was drawn six different ways:

- the `.spinner` ring, 2px stroke, 0.7s;
- the Phosphor `circle-notch` glyph, 1.1s, under two keyframe names
  (`chip-spin`, `chip-filing-spin`), in three colours depending on the host;
- a status line that was only a pulsing word, whose animation
  (`pulse-fade`) had **no `@keyframes` at all**, so it never moved;
- the chat reply dots standing in for a loading line in a toast and in the
  Library (`typingDots` is the *reply* indicator, a different thing);
- a busy button that was `disabled` plus `aria-busy` and showed nothing;
- a dozen "Working..." lines that carried a decorative, motionless icon.

The recipe is DESIGN.md's row "Something is working on it": **`.spinner`**
(one element, drawn by `spinnerEl()` or the `ph:spin` marker in `setLabel`),
sized in `em` of the text beside it, one stroke, one colour, one speed, a slow
opacity pulse under reduced motion; **`setBusy(button, busy, label)`** for a
button. These tests are the ratchet: a second spin keyframe, a re-introduced
glyph spinner, an ASCII "..." in the copy, or a hand-built `.spinner` all fail
here, not in a screenshot.

Like the other frontend lints this cannot see the DOM; what runs in a browser
is `scratchpad/ui-sweeps/spinners.js`, which measures every indicator it can
trigger and prints the distinct signatures (one, plus the filled-button
colour).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
CSS_FILES = sorted((FRONTEND / "css").glob("*.css"))
JS_FILES = sorted([*FRONTEND.glob("*.js"), *(FRONTEND / "js").glob("*.js")])
DESIGN = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")


def _strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _all_css() -> str:
    return "\n".join(_strip_css_comments(p.read_text(encoding="utf-8")) for p in CSS_FILES)


def _keyframes(css: str) -> dict[str, str]:
    """Every `@keyframes name { ... }` body, braces balanced (a keyframes block
    nests one level, so a flat regex cuts it at the first inner `}`)."""
    found: dict[str, str] = {}
    for match in re.finditer(r"@keyframes\s+([A-Za-z0-9_-]+)\s*\{", css):
        depth, i = 1, match.end()
        while depth and i < len(css):
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        found[match.group(1)] = css[match.end() : i - 1]
    return found


def _rules(css: str):
    """(selector, body) of each flat rule, at any media depth."""
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        yield match.group(1).strip(), match.group(2)


def _js_code_lines(path: Path):
    """(lineno, line) with whole-line comments removed: prose in a comment is
    not copy."""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith(("//", "*", "/*")):
            continue
        yield number, line


# --- the definition ---------------------------------------------------------


def test_the_ring_has_one_turn_and_one_pulse_keyframe() -> None:
    frames = _keyframes(_all_css())
    assert "spinner-turn" in frames, "the recipe's rotation is @keyframes spinner-turn"
    assert "360deg" in frames["spinner-turn"]
    assert "spinner-pulse" in frames, "the reduced-motion branch is @keyframes spinner-pulse"
    pulse = frames["spinner-pulse"]
    assert "opacity" in pulse, "a slow opacity pulse, per DESIGN.md's Motion section"
    assert "transform" not in pulse and "rotate" not in pulse


#: Companion characters (`nm-*`, `nmb-*`, `atl-*`) are poses and plays, not
#: progress, and the owner's brief leaves them alone. `emblem-spin` turns the
#: dashboard's emblem canvas, a decoration with its own pause switch.
COMPANION_PREFIXES = ("nm-", "nmb-", "atl-")
DECORATIVE_TURNS = {"emblem-spin"}


def test_no_second_rotation_keyframe_outside_the_allowlist() -> None:
    """Every keyframes block that turns a full circle is the ring, the emblem,
    or a companion pose. A new one is a second spinner."""
    frames = _keyframes(_all_css())
    turning = {name for name, body in frames.items() if "360deg" in body}
    stray = {
        name
        for name in turning
        if name != "spinner-turn"
        and name not in DECORATIVE_TURNS
        and not name.startswith(COMPANION_PREFIXES)
    }
    assert not stray, (
        f"{sorted(stray)} turn a full circle outside the spinner recipe: use "
        "`.spinner` (DESIGN.md, 'Something is working on it'), or, for a "
        "decoration, add the name to DECORATIVE_TURNS with a reason"
    )
    named_spin = {
        name
        for name in frames
        if "spin" in name and name not in {"spinner-turn", "spinner-pulse", *DECORATIVE_TURNS}
        and not name.startswith(COMPANION_PREFIXES)
    }
    assert not named_spin, f"{sorted(named_spin)}: a spin keyframe that is not the recipe's"


#: Names found by this lint on its first run that are not progress indicators
#: and so are not this recipe's to fix: the companion's aura and core glow
#: (`atl-*`, left alone by the brief) and the monitor log's row fade. Each
#: animates nothing today. May only shrink: define the block, delete the name.
KNOWN_UNDEFINED = {"fade-in", "atl-glow", "atl-core"}


def test_every_animation_names_a_keyframes_block_that_exists() -> None:
    """`pulse-fade` named a keyframes block nobody wrote, so the tension
    review's 'working' line never moved and no test noticed. A name with no
    block is a no-op that reads as correct."""
    css = _all_css()
    defined = set(_keyframes(css))
    keywords = {
        "none", "infinite", "normal", "reverse", "alternate", "alternate-reverse",
        "forwards", "backwards", "both", "running", "paused", "linear", "ease",
        "ease-in", "ease-out", "ease-in-out", "step-start", "step-end", "initial",
        "inherit", "unset", "revert",
    }
    missing: dict[str, set[str]] = {}
    for selector, body in _rules(css):
        for decl in re.finditer(r"(?<![\w-])animation(-name)?\s*:\s*([^;}]+)", body):
            value = decl.group(2)
            if "var(" in value:
                continue
            for token in re.split(r"[\s,]+", re.sub(r"(cubic-bezier|steps)\([^)]*\)", "", value)):
                token = token.strip()
                if (
                    not token
                    or token in keywords
                    or re.fullmatch(r"-?[\d.]+(m?s)?|!important", token)
                    or token.startswith(("var(", "calc("))
                ):
                    continue
                if token not in defined:
                    missing.setdefault(token, set()).add(selector.split(",")[0].strip()[:60])
    missing = {name: where for name, where in missing.items() if name not in KNOWN_UNDEFINED}
    assert not missing, f"animation names with no @keyframes: {missing}"
    stale = KNOWN_UNDEFINED & defined
    assert not stale, f"{sorted(stale)} are defined now: delete them from KNOWN_UNDEFINED"


def test_the_ring_is_one_rule_with_one_stroke_one_colour_one_speed() -> None:
    css = _all_css()
    base = [body for sel, body in _rules(css) if sel.strip() == ".spinner"]
    assert len(base) == 1, "`.spinner` is defined in exactly one rule"
    body = base[0]
    assert "aspect-ratio: 1" in body and "flex: none" in body, "a ring that cannot become an ellipse"
    assert re.search(r"(block-size|height):\s*[\d.]+em", body), "sized in em of the text beside it"
    assert "var(--spinner-stroke)" in body, "one stroke weight, a token"
    assert "var(--accent-text)" in body, "one colour, the accent's text colour"
    assert "var(--spinner-turn)" in body, "one speed, a token"
    root_tokens = "".join(b for sel, b in _rules(css) if sel.strip() == ":root")
    for token in ("--spinner-stroke", "--spinner-turn", "--spinner-pulse"):
        assert len(re.findall(rf"{token}\s*:", css)) == 1, f"{token} is declared once"
        assert token in root_tokens, f"{token} lives on :root with the other tokens"


def test_reduced_motion_pulses_the_ring_and_progress_motion_always_still_turns_it() -> None:
    raw = "\n".join(p.read_text(encoding="utf-8") for p in CSS_FILES)
    css = _strip_css_comments(raw)
    reduce_blocks = re.findall(r"@media \(prefers-reduced-motion: reduce\)\s*\{", css)
    assert reduce_blocks
    # The pulse is reachable from both reduced-motion gates the app has.
    assert re.search(
        r"@media \(prefers-reduced-motion: reduce\)\s*\{[^@]*?\.spinner\s*\{[^}]*spinner-pulse", css, re.S
    ), "the OS setting gives the ring a pulse"
    assert re.search(
        r'\[data-motion="reduced"\][^{]*\.spinner\s*\{[^}]*spinner-pulse', css
    ), "the app's own Reduce motion gives the ring a pulse too"
    # And the owner's 'always' setting (progress motion) keeps it turning.
    assert re.search(
        r'\[data-progress-motion="always"\]\s*\.spinner\s*\{[^}]*spinner-turn', css
    ), "progress motion 'always' keeps the rotation, as it does for every progress indicator"
    # The old behaviour swapped the ring for a dead ellipsis glyph.
    assert '.spinner::before' not in css


def test_a_busy_button_shows_the_ring_in_its_own_text_colour_when_filled() -> None:
    css = _all_css()
    assert re.search(r"button:not\(\.ghost\)\s*>\s*\.spinner\s*\{[^}]*currentColor", css), (
        "on a filled button the accent-text ring would vanish into the fill"
    )


# --- the builders -----------------------------------------------------------


def test_the_ring_is_built_in_one_place_and_the_label_grammar_knows_it() -> None:
    app = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
    assert len(re.findall(r"function spinnerEl\(", app)) == 1
    assert 'className = "spinner"' in app
    # `ph:spin` is the marker: a spinner, not an icon called "spin".
    assert re.search(r'match\[1\]\s*===\s*"spin"', app), "setLabel turns ph:spin into the ring"
    assert "function setBusy(" in app, "a button's busy state is one helper"
    for path in JS_FILES:
        if path.name == "app.js":
            continue
        for number, line in _js_code_lines(path):
            assert 'className = "spinner"' not in line and "class=\"spinner\"" not in line, (
                f"{path.name}:{number} builds a spinner by hand: use spinnerEl() or ph:spin"
            )


def test_the_html_never_hand_builds_a_ring() -> None:
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'class="spinner"' not in html and "circle-notch" not in html


def test_the_icon_lint_knows_spin_is_a_marker_not_a_glyph() -> None:
    lint = (ROOT / "tests" / "test_icon_names.py").read_text(encoding="utf-8")
    assert '"spin"' in lint.split("NOT_ICONS", 1)[1].split("\n\n", 1)[0]


# --- the recipe is written down ---------------------------------------------


def test_the_recipe_row_is_in_the_recipe_index() -> None:
    index = DESIGN.split("## The recipe index", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in index.splitlines() if "`.spinner`" in line]
    assert rows, "DESIGN.md's recipe index has a row for the spinner"
    row = rows[0]
    for needle in ("setBusy", "ph:spin", "test_spinner_recipe", "spinners.js"):
        assert needle in row, f"the row names {needle}"


# --- the migration ----------------------------------------------------------


def test_the_glyph_spinner_is_gone() -> None:
    offenders = []
    for path in [*JS_FILES, *CSS_FILES, FRONTEND / "index.html"]:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith(("//", "*", "/*")):
                continue
            if "circle-notch" in line:
                offenders.append(f"{path.name}:{number}")
    assert not offenders, f"circle-notch is the old glyph spinner, use ph:spin: {offenders}"


def test_the_old_spin_keyframes_and_classes_are_gone() -> None:
    css = _all_css()
    frames = set(_keyframes(css))
    assert not {"chip-spin", "chip-filing-spin", "pulse-fade"} & frames
    for dead in ("chip-spin", "chip-filing-spin", "pulse-fade"):
        assert dead not in css, f"{dead} is still referenced"


# Labels shaped "ph:<icon> <Verb>ing...": a status that says the app is
# working, drawn with a motionless decorative icon. They use `ph:spin`.
IN_PROGRESS_ICON_LABEL = re.compile(r"ph:(?!spin\b)[a-z0-9-]+ [A-Z][a-z]+ing\b[^\"'`]*…")


def test_an_in_progress_label_carries_the_ring_not_a_decorative_icon() -> None:
    offenders = []
    for path in JS_FILES:
        for number, line in _js_code_lines(path):
            if IN_PROGRESS_ICON_LABEL.search(line):
                offenders.append(f"{path.name}:{number}: {line.strip()[:90]}")
    assert not offenders, "\n".join(offenders)


# --- the phrasing rule ------------------------------------------------------

#: A companion's silent line is a speech bubble, not progress copy.
THREE_DOTS_OK = {("avatars.js", '"..."')}


def test_in_progress_copy_uses_a_real_ellipsis_never_three_dots() -> None:
    """Sentence case, `…` (U+2026) or nothing, never `...`, no em-dashes (the
    em-dash lint is test_no_em_dashes.py). Looks for a string or template
    literal that ENDS in three dots, which is how every 'Loading...' is
    written."""
    pattern = re.compile(r"\.\.\.[\"'`]")
    offenders = []
    for path in JS_FILES:
        for number, line in _js_code_lines(path):
            for match in pattern.finditer(line):
                start = match.start()
                opener = line[start - 1] if start else ""
                if opener in "\"'`" and (path.name, f'{opener}...{opener}') in THREE_DOTS_OK:
                    continue
                offenders.append(f"{path.name}:{number}: {line.strip()[:90]}")
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for number, line in enumerate(html.splitlines(), 1):
        if re.search(r"""(placeholder|title|aria-label|aria-description)="[^"]*\.\.\."|>[^<>]*[A-Za-z]\.\.\.<""", line):
            offenders.append(f"index.html:{number}: {line.strip()[:90]}")
    assert not offenders, "use the real ellipsis:\n" + "\n".join(offenders)


# --- one place sets a button busy -------------------------------------------

#: Containers (a list, a pane, the tour card) mark themselves busy for a
#: screen reader; that is not a button. A button goes through `setBusy`.
#: statistics.js: the Statistics dialog's body (a div) while it counts.
#: reply-kit.js: the answer panel's statistics grid while it loads (C06), a region, not a button.
#: mermaid-draw.js marks a diagram's figure busy while it draws, a container like the others.
#: graph-canvas.js: the map's count line (a status region) during a slow reload (audit 1029 G30).
CONTAINER_BUSY_FILES = {"app.js", "chat.js", "notes-list.js", "tour.js", "statistics.js", "reply-kit.js", "mermaid-draw.js", "graph-canvas.js"}


def test_a_button_is_marked_busy_only_through_setbusy() -> None:
    offenders = []
    for path in JS_FILES:
        if path.name in CONTAINER_BUSY_FILES:
            continue
        for number, line in _js_code_lines(path):
            if 'setAttribute("aria-busy"' in line:
                offenders.append(f"{path.name}:{number}: {line.strip()[:90]}")
    assert not offenders, "use setBusy(button, true, label):\n" + "\n".join(offenders)


@pytest.mark.parametrize("name", ["categories-panel.js", "chat.js", "graph.js", "editor.js"])
def test_the_buttons_that_used_to_hand_roll_it_use_setbusy(name: str) -> None:
    assert "setBusy(" in (FRONTEND / "js" / name).read_text(encoding="utf-8")
