"""INBOX 1530 (d), audit 1031 ranked row 21: p5 loads and runs only when
background art is on. The dashboard's constellation was its one use; it moved
out of dashboard.js into the lazy dash-art.js with p5's loader, and with the
art off (the default) it draws one still sky over a plain canvas with p5's own
random generator, so the arrangement is the moving one's. Measured on the
dashboard by the 1530 sweep (`dash.js` in the session scratchpad): with the
art off p5 is not fetched at all."""

import re

from tests._app_js import INDEX_HTML, JS_DIR, frontend_text

BOOT = re.findall(r'<script src="/js/([A-Za-z0-9_.-]+\.js)', INDEX_HTML.read_text(encoding="utf-8"))


def test_no_boot_script_names_p5():
    assert "dash-art.js" not in BOOT
    for name in BOOT:
        text = (JS_DIR / name).read_text(encoding="utf-8")
        assert "/vendor/p5.min.js" not in text, name
        assert "function ensureP5" not in text, name


def test_the_constellation_is_a_lazy_bundle_behind_a_stand_in():
    entries = frontend_text("lazy-entries.js")
    assert 'dashArt: ["/js/dash-art.js"],' in entries
    assert 'dashArt: ["renderArtWidget"],' in entries
    art = frontend_text("dash-art.js")
    assert "Object.assign(window, { renderArtWidget, dashArtStop: stopArt, dashArtRefresh: refreshArtForTheme });" in art


def test_p5_is_fetched_only_with_background_art_on():
    art = frontend_text("dash-art.js")
    #: frontend_text unwraps dash-art.js's closure (13d130b11): the function's
    #: tail is at column 0 again and its body two spaces in.
    body = art[art.index("async function startArt(holder) {") :]
    body = body[: body.index("\n}\n")]
    assert body.index("const live = bgArtOn();") < body.index("ensureP5()")
    assert body.count("ensureP5()") == 2
    assert "if (live && typeof p5 === \"undefined\" && !(await ensureP5()))" in body
    assert "if (live && typeof p5 === \"undefined\") {" in body
    assert "artInstance = live ? new p5(sketch, holder) : artStill(sketch, holder);" in body
    # Off, the sky is the reduced-motion still: one frame, no loop.
    assert "    !live ||\n    reducedMotionWanted()" in body


def test_the_still_sky_uses_p5s_random_generator():
    art = frontend_text("dash-art.js")
    still = art[art.index("function artStill(sketch, holder) {") :]
    still = still[: still.index("\n}\n")]  # unwrapped, as above
    assert "seed = (1664525 * seed + 1013904223) % M;" in still and "const M = 4294967296;" in still
    assert "Math.ceil(window.devicePixelRatio) || 1" in still
    assert "new p5(" not in still


def test_turning_the_art_on_or_off_redraws_the_constellation():
    settings = frontend_text("settings.js")
    body = settings[settings.index("function toggleBgArt(on) {") :]
    assert "refreshArtForTheme();" in body[: body.index("\n}\n")]


def test_switching_the_art_on_starts_it_once():
    """Audit 1029 X15: `applyAppearance` reaches `applyPalette`, which restarts
    the art when it is wanted, so `toggleBgArt` starting it again built it
    twice per switch (a 125 ms click at 1x, 466 ms at 4x CPU). Only Off needs
    its own call."""
    settings = frontend_text("settings.js")
    body = settings[settings.index("function toggleBgArt(on) {") :]
    body = body[: body.index("\n}\n")]
    assert "startBgArt" not in body.replace("`startBgArt`", "")
    assert "if (!on) stopBgArt();" in body
    palette = frontend_text("ai-tools.js")
    palette = palette[palette.index("function applyPalette(") :]
    assert "if (bgArtOn()) startBgArt();" in palette[: palette.index("\n}\n")]
    applied = settings[settings.index("function applyAppearance() {") :]
    assert "applyPalette(activePalette(), false);" in applied[: applied.index("\n}\n")]
