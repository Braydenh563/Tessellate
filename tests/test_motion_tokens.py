"""Every transition runs on the motion tokens, and no hover is a filter.

**Why this exists (INBOX 399 (4), INBOX 405).** The owner asked for the
component quality of motion.dev, Kokonut UI and bklit.ui: one timing and one
curve family for everything that answers the pointer, so a hover here and a
press there feel like one app. Measured before this lint: 125 transitions on
`ease`, three on `ease-out`, four hand-written `cubic-bezier`s, and eleven
durations written as numbers beside the three `--motion-*` tokens DESIGN.md
names (0.15s, 0.2s, 0.25s, 0.35s, 90ms, 220ms).

And `button:hover { filter: brightness(1.07) }` on every button in the app:
a filter on hover makes the browser give the element a compositing layer for
the length of the hover and re-rasterise its text, which the owner saw as a
flicker on the chat's floating "Jump to latest" pill in the desktop window,
and a 7% brightness shift is too small to read as a state change anyway.
A hover is a colour (`--accent-surface-hover`, `--hover-veil`).

What the rules allow:

- a duration from `--motion-fast`, `--motion-base` or `--motion-slow`, or an
  off switch below one millisecond (the reduced-motion blankets);
- a curve from `--ease-out`, `--ease-in-out` or `--ease-spring`, or `linear`
  and `steps()` for something that moves at a constant rate;
- never `transition: all`, which animates properties nobody chose, layout
  ones included.

`animation` timings are not covered, on purpose: DESIGN.md ("Motion") keeps a
keyframe's own timing as part of the effect it draws.
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_DIR

DECL = re.compile(
    r"(?<![-\w])(transition(?:-duration|-timing-function|-property)?)\s*:\s*([^;{}]*)[;}]"
)
DURATION = re.compile(r"(?<![\w.-])(\d*\.?\d+)(m?s)\b")
EASING = re.compile(r"\b(ease-in-out|ease-out|ease-in|ease)\b|cubic-bezier\(")


def _blank_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


def _declarations():
    for path in sorted(CSS_DIR.glob("*.css")):
        text = _blank_comments(path.read_text(encoding="utf-8"))
        for m in DECL.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            yield f"{path.name}:{line}", m.group(1), " ".join(m.group(2).split())


def _off_switch(number: str, unit: str) -> bool:
    ms = float(number) * (1000 if unit == "s" else 1)
    return ms < 1


def _bad_duration(value: str) -> list[str]:
    bare = re.sub(r"var\(--[\w-]+\)", "", value)
    return [n + u for n, u in DURATION.findall(bare) if not _off_switch(n, u)]


def _bad_easing(value: str) -> list[str]:
    bare = re.sub(r"var\(--[\w-]+\)", "", value)
    return [m.group(0) for m in EASING.finditer(bare)]


def test_the_rules_know_the_shapes():
    assert _bad_duration("opacity 0.15s ease") == ["0.15s"]
    assert _bad_duration("opacity var(--motion-fast) var(--ease-out)") == []
    assert _bad_duration("0.001ms !important") == []
    assert _bad_easing("opacity var(--motion-fast) ease") == ["ease"]
    assert _bad_easing("transform var(--motion-base) cubic-bezier(0.2, 0.8, 0.2, 1)") == ["cubic-bezier("]
    assert _bad_easing("transform var(--motion-fast) linear") == []


def test_no_transition_animates_everything():
    offenders = [
        f"{where}: {prop}: {value}"
        for where, prop, value in _declarations()
        if prop in ("transition", "transition-property") and re.search(r"(^|[\s,])all\b", value)
    ]
    assert not offenders, (
        "`transition: all` animates properties nobody chose, layout ones "
        "included. Name them:\n" + "\n".join(offenders)
    )


def test_every_transition_duration_is_a_token():
    offenders = [
        f"{where}: {prop}: {value}"
        for where, prop, value in _declarations()
        if prop in ("transition", "transition-duration") and _bad_duration(value)
    ]
    assert not offenders, (
        "A transition's duration is `--motion-fast`, `--motion-base` or "
        "`--motion-slow` (DESIGN.md, Motion):\n" + "\n".join(offenders)
    )


def _split_top(value: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in value:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
            continue
        cur += ch
    parts.append(cur)
    return parts


def _curveless(value: str) -> bool:
    """An item with a duration and no curve runs on `ease`, the untokened default."""
    for item in _split_top(value):
        timed = "var(--motion-" in item or DURATION.search(re.sub(r"var\(--[\w-]+\)", "", item))
        if timed and not re.search(r"var\(--ease-|\blinear\b|steps\(", item) and "!important" not in item:
            return True
    return False


def test_every_transition_curve_is_a_token():
    assert _curveless("background var(--motion-slow), color var(--motion-slow) var(--ease-out)")
    assert not _curveless("opacity var(--motion-fast) var(--ease-out), visibility var(--motion-fast) linear")
    offenders = [
        f"{where}: {prop}: {value}"
        for where, prop, value in _declarations()
        if (prop in ("transition", "transition-timing-function") and _bad_easing(value))
        or (prop == "transition" and _curveless(value))
    ]
    assert not offenders, (
        "A transition's curve is `--ease-out`, `--ease-in-out` or "
        "`--ease-spring` (00-tokens-shell.css), or `linear`:\n" + "\n".join(offenders)
    )


def _rules(text: str):
    """Yield (line, selector, body) for every innermost rule."""
    text = _blank_comments(text)
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        selector = m.group(1).strip()
        if selector.startswith("@"):
            continue
        yield text.count("\n", 0, m.start(1)) + 1, selector, m.group(2)


def test_no_hover_is_a_filter():
    offenders = []
    for path in sorted(CSS_DIR.glob("*.css")):
        for line, selector, body in _rules(path.read_text(encoding="utf-8")):
            if ":hover" not in selector:
                continue
            if re.search(r"(?<![-\w])filter\s*:", body):
                offenders.append(f"{path.name}:{line}: {selector.splitlines()[-1].strip()}")
    assert not offenders, (
        "A hover is a colour, never a `filter`: a filter gives the element a "
        "compositing layer for the hover and re-rasterises its text (INBOX "
        "405). Use `--accent-surface-hover` on a solid button, "
        "`--hover-veil` as a `background-image` over any other ground:\n"
        + "\n".join(offenders)
    )


def test_the_reduced_motion_blankets_stop_transitions_outright():
    """**An off switch is zero, not almost zero** (the companion's menu, the
    owner: "the right click companion popup still doesnt appear next to the
    companion and instead at the top of the screen", reported several times).

    `transition-property` is `all` on every element unless it says otherwise,
    so a blanket that sets `transition-duration: 0.01ms` does not remove
    transitions: it gives every element in the app a real one, on every
    property. A transition runs from the next frame, and until then a
    `getBoundingClientRect` after a style write reads where the element was:
    measured with the system's reduced-motion hint on, the escaped menu read
    at 0,904 straight after `left: 0; top: 0` was written, and the companion
    placed its menu from that rect, 276 to 565px from the companion, some of
    it off screen (`scratchpad/ui-sweeps/companionmenulow.js`, 12 of 12
    openings under the hint, 0 of 24 without). A zero duration and a zero
    delay start no transition at all, which is what the blanket means."""
    # Every rule that switches transitions off, in whichever blanket it sits
    # (the system hint's, Reduce motion's, Interface animations off).
    blankets = []
    for path in sorted(CSS_DIR.glob("*.css")):
        text = _blank_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"\{([^{}]*transition-duration:[^;]*!important[^{}]*)\}", text):
            blankets.append((path.name, m.group(1)))
    assert len(blankets) >= 3, "the motion blankets moved; point this lint at them"
    for name, body in blankets:
        duration = re.search(r"transition-duration:\s*([^;]+);", body)
        delay = re.search(r"transition-delay:\s*([^;]+);", body)
        assert duration and duration.group(1).strip() == "0s !important", f"{name}: {duration and duration.group(1)}"
        assert delay and delay.group(1).strip() == "0s !important", f"{name}: a delay starts a transition too"


# --- Interface animations: the polish set's own switch (the owner, 2026-10-05)
#
# "make them happen even with reduced motion but with a separate toggle in the
# appearance settings with it automatically on ... just make sure they are
# cheap". The polish set (press, menus, dialogs, tab indicators and panels,
# lists settling, toasts, focus rings, hovers) reads `--ui-*`, which resolves
# against `data-ui-motion` on the root and never against the media query; the
# decorative motion (Atlas, background art, graph, whiteboard) keeps reduced
# motion. These hold the shape; `scratchpad/ui-sweeps/motion1005.js` measures
# it in a browser.

UI_TOKENS = ("--ui-fast", "--ui-base", "--ui-slow", "--ui-exit", "--ui-step")
JS_DIR = CSS_DIR.parent / "js"
#: The recipes the switch governs. A reduced-motion block that names one of
#: them would be gating the polish by the media query again.
POLISH = (
    "button", ".chip", ".seg", ".tabs-line", "#tab-bar", "#settings-nav",
    ".ui-glide", ".action-menu", ".dock-menu", ".help-popover", ".modal-overlay",
    ".toast", ".tab-page", ".skeleton", ".ui-settle", ".scroll-top",
    "summary", "#sidebar", ".theme-card", ".start-step", "header#top-bar",
)
#: Not polish, though they sit on a polish recipe: an indicator that something
#: is happening (the recording pulse, the skeleton's shimmer) keeps its own
#: reduced-motion branch, which DESIGN.md asks of every indefinite animation.
INDICATORS = (".recording", ".skeleton")


def _reduced_motion_blocks():
    """(file, selector, body) of every rule inside a reduced-motion query."""
    for path in sorted(CSS_DIR.glob("*.css")):
        text = _blank_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"@media[^{]*prefers-reduced-motion[^{]*\{", text):
            depth, i = 1, m.end()
            while depth and i < len(text):
                depth += {"{": 1, "}": -1}.get(text[i], 0)
                i += 1
            for r in re.finditer(r"([^{};]+)\{([^{}]*)\}", text[m.end():i - 1]):
                yield path.name, " ".join(r.group(1).split()), r.group(2)


def test_the_interface_tokens_resolve_against_the_switch():
    text = _blank_comments((CSS_DIR / "00-tokens-shell.css").read_text(encoding="utf-8"))
    off = re.search(r':root\[data-ui-motion="off"\]\s*\{([^}]*)\}', text)
    assert off, "no `:root[data-ui-motion=\"off\"]` block: the switch resolves nothing"
    for token in UI_TOKENS:
        assert re.search(rf"{token}:\s*var\(--motion-[a-z]+\)", text), f"{token} is not a motion token when on"
        assert re.search(rf"{token}:\s*0s;", off.group(1)), f"{token} is not zero when off"


def test_the_motion_sections_run_on_the_switch():
    """Every duration in a `/* --- motion:` section is an `--ui-*` token: the
    polish set is what the switch turns off, so it may not read the plain
    scale, which nothing turns off."""
    offenders = []
    for path in sorted(CSS_DIR.glob("*.css")):
        raw = path.read_text(encoding="utf-8")
        heads = [m.start() for m in re.finditer(r"/\* ---", raw)]
        for n, start in enumerate(heads):
            if not raw.startswith("/* --- motion:", start):
                continue
            end = heads[n + 1] if n + 1 < len(heads) else len(raw)
            section = _blank_comments(raw[start:end])
            for m in re.finditer(r"(?<![-\w])(transition|animation)(?:-duration|-delay)?\s*:([^;{}]*)", section):
                if "var(--motion-" in m.group(2):
                    line = raw.count("\n", 0, start + m.start()) + 1
                    offenders.append(f"{path.name}:{line}: {' '.join(m.group(0).split())[:90]}")
    assert not offenders, "A motion section reads `--motion-*` rather than `--ui-*`:\n" + "\n".join(offenders)


def test_the_polish_is_never_gated_by_the_media_query_alone():
    offenders = [
        f"{name}: `{selector}`"
        for name, selector, body in _reduced_motion_blocks()
        if re.search(r"(?<![-\w])(transition|animation)(-[a-z]+)?\s*:", body)
        and any(re.search(rf"(^|[\s,>(]){re.escape(p)}(?![-\w])", selector) for p in POLISH)
        and not all(any(i in part for i in INDICATORS) for part in selector.split(","))
        # A blanket that names the polish only to exempt it while the switch is on.
        and 'data-ui-motion="on"' not in selector
    ]
    assert not offenders, (
        "A reduced-motion block stops part of the polish set, which the "
        "Interface animations switch governs (on plays it even under reduced "
        "motion; off makes it instant through `--ui-*`):\n" + "\n".join(offenders)
    )
    for path in sorted(CSS_DIR.glob("*.css")):
        text = _blank_comments(path.read_text(encoding="utf-8"))
        assert "prefers-reduced-motion: no-preference" not in text, (
            f"{path.name}: motion opted in by the media query; the switch decides"
        )


def test_the_blankets_leave_transitions_to_the_switch():
    """Both reduced-motion blankets still the animations; their transition half
    applies only while Interface animations is not on (or to the decorative
    surfaces), and an off blanket exists of its own."""
    # The manual and off blankets are motion-still.css (media on only while a switch is).
    text = _blank_comments("\n".join((CSS_DIR / n).read_text(encoding="utf-8") for n in ("02-chat-graph.css", "motion-still.css")))
    rules = [(" ".join(m.group(1).split()), m.group(2))
             for m in re.finditer(r"([^{};]+)\{([^{}]*transition-duration:\s*0s !important[^{}]*)\}", text)]
    assert rules, "no transition blanket found"
    decorative = ("#graph-svg", "#whiteboard-container", "#nm-buddy")
    for selector, _ in rules:
        for part in [p.strip() for p in re.split(r",(?![^()]*\))", selector)]:
            assert ('data-ui-motion="on"' in part and ":not(" in part) or 'data-ui-motion="off"' in part or any(
                d in part.split(")")[0] for d in decorative
            ), f"a transition blanket stops the polish without asking the switch: {part}"
    assert any('[data-ui-motion="off"]' in s for s, _ in rules), "no blanket for Interface animations off"


def test_the_switch_is_wired_from_boot_to_settings():
    boot = (JS_DIR / "theme-boot.js").read_text(encoding="utf-8")
    assert 'dataset.uiMotion = pref("ui-motion", "on")' in boot, "theme-boot.js does not set data-ui-motion before first paint"
    prefs = (JS_DIR / "prefs.js").read_text(encoding="utf-8")
    assert re.search(r'"ui-motion":\s*\{\s*default:\s*"on"', prefs), "prefs.js has no default for ui-motion"
    settings = (JS_DIR / "settings.js").read_text(encoding="utf-8")
    assert 'root.dataset.uiMotion = appearancePref("ui-motion")' in settings
    assert '$("ui-motion-toggle").addEventListener("change"' in settings
    html = (CSS_DIR.parents[0] / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<input type="checkbox" id="ui-motion-toggle" checked>', html), "the toggle is not on by default"
    assert 'data-help-for="motion-help"' in html, "the switch has no help popover"


#: Rules whose motion is not the interface's: the companion and Atlas, the
#: graph, the whiteboard, the boot splash, and the indicators that say work
#: is happening (their own `progress-motion` setting). Everything else is the
#: polish set and runs on the switch.
DECORATIVE = re.compile(
    r"#nm-buddy|\.nm-|\.nmb|\.nms|\.atl-|\.name-mark|\.graph-node|\.graph-edge|\.graph-label|"
    r"\.graph-minimap|\.graph-halo|\.graph-core|graph-orb|\.emblem|\.typing|\.progress-|\.ai-writing|"
    r"\.boot-splash|\.mic-bar|recording|\.wb-|\.sketch-color|\.onboarding-dot|theme-switching|"
    r"\.is-generating"
)


def test_every_interface_transition_runs_on_the_switch():
    """The motion tokens resolve against the attribute for the polish class:
    a transition outside the decorative and progress surfaces names `--ui-*`,
    so Interface animations off is zero for it whatever the blankets do."""
    offenders = []
    for path in sorted(CSS_DIR.glob("*.css")):
        for line, selector, body in _rules(path.read_text(encoding="utf-8")):
            flat = " ".join(selector.split())
            if flat.startswith("@") or DECORATIVE.search(flat):
                continue
            for m in re.finditer(r"(?<![-\w])transition(?:-duration|-delay)?\s*:([^;]*)", body):
                if "var(--motion-" in m.group(1):
                    offenders.append(f"{path.name}:{line}: {flat[:70]}")
    assert not offenders, (
        "An interface transition reads `--motion-*`, which Interface animations "
        "cannot turn off; use `--ui-fast`, `--ui-base`, `--ui-slow` or `--ui-exit`:\n"
        + "\n".join(offenders)
    )


def test_the_skeleton_shimmer_follows_the_os_unless_always_was_chosen():
    """The default "always" must not force the shimmer under the OS
    reduced-motion setting: only an explicit choice (data-progress-chosen,
    set by settings.js) or an OS that allows motion plays it."""
    css = _blank_comments((CSS_DIR / "02-chat-graph.css").read_text(encoding="utf-8"))
    forced = [m for m in re.finditer(r"([^{};]+)\{[^{}]*animation:\s*shimmer[^{}]*!important", css)]
    assert forced, "no forced shimmer rule found"
    for m in forced:
        before = css[: m.start()]
        in_media = before.rfind("@media") > before.rfind("}\n}") and "reduce)" in before[before.rfind("@media"):]
        assert "data-progress-chosen" in m.group(1) or in_media, (
            f"a forced shimmer ignores the OS reduced-motion setting: {' '.join(m.group(1).split())}"
        )
    settings = (JS_DIR / "settings.js").read_text(encoding="utf-8")
    assert 'toggleAttribute("data-progress-chosen"' in settings


# --- Phase 13 decision 14 (Brief 57): the slow token moves things -------------

#: A colour, a ground or an edge changing is feedback, not a move: it runs on
#: `--ui-fast` (a hover) or `--ui-base` (a state). `--motion-slow` is for a
#: surface entering, leaving or moving. The one exception is a label whose
#: colour follows the glide moving under it (`.has-glide`, 08-consistency.css).
COLOUR_PROPS = re.compile(r"^\s*(color|background(?:-color)?|border(?:-[a-z]+)?-color|outline-color|box-shadow|fill|stroke)\b")


def _rules_with_selectors():
    for path in sorted(CSS_DIR.glob("*.css")):
        text = _blank_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"([^{};]+)\{([^{}]*)\}", text):
            line = text.count("\n", 0, m.start(2)) + 1
            yield f"{path.name}:{line}", " ".join(m.group(1).split()), m.group(2)


def test_a_colour_change_never_runs_on_the_slow_token():
    offenders = []
    for where, selector, body in _rules_with_selectors():
        if ".has-glide" in selector:
            continue
        for value in re.findall(r"(?<![-\w])transition\s*:\s*([^;]+)", body):
            for item in _split_top(value):
                if COLOUR_PROPS.match(item) and re.search(r"var\(--(motion|ui)-slow\)", item):
                    offenders.append(f"{where}: {selector[:60]} -> {item.strip()[:60]}")
    assert not offenders, (
        "A colour, ground or edge change runs on --ui-fast (hover) or --ui-base (state); "
        "--motion-slow is for a surface that enters, leaves or moves (DESIGN.md, Motion):\n" + "\n".join(offenders)
    )


#: Keyframes whose timing is the drawing itself, as the docstring above keeps
#: for `animation`: the companion's body and the board's laser trail.
EFFECT_SELECTORS = re.compile(r"#nm-buddy|name-mark|\.nm-|\.atl-|nmb-|atlas|wb-laser")


def test_an_interface_animation_that_plays_once_runs_on_a_token():
    """A message arriving, a panel sliding in, a log row fading in: one-shot
    interface motion takes the motion tokens, so Interface animations and the
    reduced-motion switch reach it. Loops and the companion keep their own."""
    offenders = []
    for where, selector, body in _rules_with_selectors():
        if EFFECT_SELECTORS.search(selector):
            continue
        for value in re.findall(r"(?<![-\w])animation\s*:\s*([^;]+)", body):
            if "infinite" in value or "!important" in value:
                continue
            for item in _split_top(value):
                if re.search(r"var\(--(motion|ui)-", item):
                    continue
                bare = re.sub(r"var\(--[\w-]+\)", "", item)
                m = DURATION.search(bare)
                if m and not _off_switch(*m.groups()) and not re.search(r"\b\d+\s+(alternate|normal)\b|\s[2-9]\d*\s", item):
                    ms = float(m.group(1)) * (1000 if m.group(2) == "s" else 1)
                    if ms < 1000:
                        offenders.append(f"{where}: {selector[:60]} -> {item.strip()[:60]}")
    assert not offenders, "A one-shot interface animation's duration is a motion token:\n" + "\n".join(offenders)
