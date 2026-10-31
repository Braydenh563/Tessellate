"""The background art's styles: one list in three places, the cost rules,
and the seeded ones.

The style list lives in `BG_ART_STYLES` (settings.js, what a saved choice is
checked against), in `BG_ART_BUILDERS` (bg-art.js, what draws it) and in the
`#bg-art-style` picker (index.html, what a person can choose). They drifted
once already: the picker offered "constellations", "blobs" and "particles"
while the code drew "constellation", "bubbles" and "mesh", so every option
but Aurora failed the name check and silently fell back.

The microbes and mycelium styles grow their species from the display name,
through a genome adapted from helixlabs (MIT). The genome is exercised in
node, because "the same name always grows the same ecosystem" is the whole
promise of the feature and a regression would be invisible in a screenshot.

The frame costs themselves are measured, not tested here:
`scratchpad/ui-sweeps/bgartcost.js`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
BG_ART = FRONTEND / "js" / "bg-art.js"
SETTINGS = FRONTEND / "js" / "settings.js"
INDEX = FRONTEND / "index.html"
CSS = FRONTEND / "css" / "03-dashboard-widgets.css"

_HEAD = r"^  ([a-z]+)(?:\(p, ctx\) \{|: \{)$"


def _styles_const() -> list[str]:
    m = re.search(r"const BG_ART_STYLES = \[([^\]]*)\]", SETTINGS.read_text(encoding="utf-8"))
    assert m, "BG_ART_STYLES not found in settings.js"
    return re.findall(r'"([a-z]+)"', m.group(1))


def _builders_body() -> str:
    text = BG_ART.read_text(encoding="utf-8")
    return text[text.index("const BG_ART_BUILDERS = {") : text.index("// --- the runtime")]


def _builders() -> list[str]:
    return re.findall(_HEAD, _builders_body(), flags=re.M)


def _chunks() -> dict[str, str]:
    parts = re.split(_HEAD, _builders_body(), flags=re.M)
    # re.split with a group returns [pre, name, body, name, body, ...]
    return dict(zip(parts[1::2], parts[2::2]))


def _picker() -> list[str]:
    """The cards' names (Brief 95: the select became a grid of cards built
    from `BG_ART_INFO`, each with a preview and its measured cost)."""
    text = SETTINGS.read_text(encoding="utf-8")
    body = text[text.index("const BG_ART_INFO = {") :]
    body = body[: body.index("\n};")]
    return re.findall(r"^  ([a-z]+): \[", body, flags=re.M)


def _costs() -> dict[str, float]:
    text = BG_ART.read_text(encoding="utf-8")
    body = text[text.index("const BG_ART_COST = {") :]
    body = body[: body.index("};")]
    return {k: float(v) for k, v in re.findall(r"([a-z]+): ([\d.]+)", body)}


def test_the_three_lists_agree():
    styles = _styles_const()
    assert styles == _builders(), "BG_ART_STYLES and BG_ART_BUILDERS name different styles"
    assert styles == _picker(), "the background cards (BG_ART_INFO) offer a different list"
    assert {"microbes", "mycelium"} <= set(styles)
    html = INDEX.read_text(encoding="utf-8")
    assert 'id="bg-art-style" role="group"' in html


def test_every_style_has_a_measured_cost_under_two_milliseconds():
    """Brief 95: each card carries its measured frame cost and the tier read
    from it (Light under 0.5ms, Medium under 1.2ms, Heavy above), and no
    style may cost more than 2ms a frame (bgartcpu.js at 1440x900)."""
    costs = _costs()
    assert sorted(costs) == sorted(_styles_const())
    assert all(0 < ms <= 2 for ms in costs.values()), costs
    tiers = {"Light", "Medium", "Heavy"}
    text = BG_ART.read_text(encoding="utf-8")
    assert all(f'"{t}"' in text for t in tiers)
    assert any(ms < 0.5 for ms in costs.values()), "no Light style"


def test_every_style_says_how_its_frame_begins():
    """A canvas style washes, clears or keeps the last frame on its own word;
    one without a word would get none of the three and smear. A CSS style
    has no frames and says so instead."""
    chunks = _chunks()
    assert list(chunks) == _builders()
    for name, chunk in chunks.items():
        assert re.search(r'background: "(wash|clear|keep)"', chunk) or "dom: true" in chunk, name


def test_mesh_and_bubbles_are_cheap_canvases_not_css_animations():
    """The mesh and the bubbles were CSS animations: no page work, but the
    compositor redrew them at the display's full rate, and the whole browser
    spent about a core on them (1,000ms of CPU a second against 150 with the
    art off, bgartcost.js), more than any canvas style. Now the mesh is a
    fifth-density canvas at fifteen frames a second and the bubbles clear
    only their own boxes."""
    chunks = _chunks()
    for name in ("mesh", "bubbles"):
        assert "dom: true" not in chunks[name], name
        assert "frame(" in chunks[name], name
    assert "pixelDensity: 0.2" in chunks["mesh"] and "fps: 15" in chunks["mesh"]
    assert "g.clearRect(last[o]" in chunks["bubbles"]
    runtime = BG_ART.read_text(encoding="utf-8")
    assert "Math.min(style.fps || 30, bgArtFrameRate())" in runtime


def test_no_colour_or_gradient_is_built_per_frame():
    """A mark's fade is globalAlpha on a colour built once; a colour string
    per mark per frame was most of the old styles' garbage (the old
    constellation allocated about 140MB in ten seconds, measured)."""
    for name, chunk in _chunks().items():
        if "frame(" not in chunk:
            continue
        frame = chunk[chunk.index("      frame(") :]
        assert "bgHsla(" not in frame, f"{name} builds a colour string inside frame()"
        assert "createRadialGradient" not in frame, name
        assert "createLinearGradient" not in frame, name
        assert "new Map(" not in frame and "new Float32Array(" not in frame, name


def test_waves_keeps_its_wash_and_its_shape():
    """The owner likes the waves as they are: the trail wash and the five
    scrolling sine layers stay exactly as they were. Only the drawing moved
    from p5's vertex list to one canvas path per layer, with the colour p5
    itself would have set."""
    waves = _chunks()["waves"]
    assert 'background: "wash"' in waves
    for line in (
        "layers = Math.max(2, Math.round(5 * ctx.density));",
        "const hue = (ctx.baseHue + l * 12) % 360;",
        "fills.push(bgP5Rgba(hue, 62, ctx.dark ? 55 : 58, 0.16));",
        "const yBase = H * (0.35 + l * 0.13);",
        "const amp = 26 + l * 10;",
        "for (let x = 0; x <= W; x += 14) {",
        "const y = yBase + Math.sin(x * 0.006 + t * (0.6 + l * 0.18) + l) * amp",
        "+ Math.sin(x * 0.013 - t * 0.4) * (amp * 0.35);",
    ):
        assert line in waves, line
    runtime = BG_ART.read_text(encoding="utf-8")
    assert "bgP5Rgba(0, 0, o.dark ? 12 : 98, o.dark ? 0.1 : 0.12)" in runtime


def test_still_is_an_image_not_a_stopped_sketch():
    """Still captures one frame to an image and removes the sketch, so no
    loop and no canvas are left behind."""
    runtime = BG_ART.read_text(encoding="utf-8")
    run = runtime[runtime.index("function bgArtRun(") :]
    still = run[run.index("if (o.still) {\n    // One frame") :]
    still = still[: still.index("\n    return;\n  }\n")]
    # The capture is bgArtMountStill (shared with a long pause, INBOX 1436).
    assert "bgArtMountStill(canvas" in still
    mount = runtime[runtime.index("function bgArtMountStill(") :]
    mount = mount[: mount.index("\n}\n")]
    assert "toBlob(" in mount and "URL.createObjectURL" in mount
    # The still's canvas is never put in the page, and no loop is started.
    assert "appendChild(canvas)" not in still
    assert "requestAnimationFrame" not in still and "bgArtInstance =" not in still


def test_the_art_pauses_when_hidden_unfocused_or_covered():
    text = BG_ART.read_text(encoding="utf-8")
    assert 'document.addEventListener("visibilitychange"' in text
    assert 'window.addEventListener("blur"' in text
    assert "function bgArtCovered()" in text
    apply = text[text.index("function bgArtApplyPause()") :]
    apply = apply[: apply.index("\n}\n")]
    assert "noLoop()" in apply and "loop()" in apply and "is-paused" in apply


def test_bg_art_is_a_lazy_bundle_settings_fetches():
    """bg-art.js is 20 KB gzipped of boot code only a notebook with the art on
    needs: settings.js fetches the `bgArt` bundle in `startBgArt` and in the
    Appearance grid, and nothing at boot names its functions unguarded."""
    html = INDEX.read_text(encoding="utf-8")
    assert 'src="/js/bg-art.js' not in html
    entries = (FRONTEND / "js" / "lazy-entries.js").read_text(encoding="utf-8")
    assert 'bgArt: ["/js/bg-art.js"]' in entries
    settings = SETTINGS.read_text(encoding="utf-8")
    assert 'typeof bgArtRun !== "function"' in settings and 'ensureModule("bgArt")' in settings
    assert 'typeof BG_ART_COST === "undefined"' in settings


def test_helixlabs_is_credited():
    text = BG_ART.read_text(encoding="utf-8")
    assert "helixlabs" in text and "MIT" in text


_GENOME_SCRIPT = r"""
const fs = require("fs");
const vm = require("vm");
// bgLuma is boot code in settings.js; the lazy bg-art.js calls it.
const luma = fs.readFileSync(process.argv[3], "utf8").match(/function bgLuma[\s\S]*?\n}\n/)[0];
const src = luma + fs.readFileSync(process.argv[2], "utf8");
const noop = () => {};
const box = {
  document: { addEventListener: noop }, window: { addEventListener: noop },
  navigator: {}, performance: { now: () => 0 }, console,
};
vm.createContext(box);
vm.runInContext(src + `
this.out = { bgArtGenome, bgArtStrains, bgArtSpeciesName, bgArtStrainCount, bgColourHue, bgP5Rgba };
bgLumCap = 0.1; this.capped = [bgHsla(200, 85, 68, 1), bgHsla(120, 90, 60, 0.5)]; bgLumCap = 0;
bgLumFloor = 0.35; this.floored = [bgHsla(260, 72, 50, 1), bgHsla(300, 80, 30, 0.4)]; bgLumFloor = 0;
this.plain = bgHsla(200, 85, 68, 1);
`, box);
const { bgArtGenome, bgArtStrains, bgArtSpeciesName, bgArtStrainCount, bgColourHue, bgP5Rgba } = box.out;
const grow = (name) => bgArtStrains(name, bgArtStrainCount(name)).map((s) => ({
  name: bgArtSpeciesName(s), sum: bgArtGenome(s).sum,
}));
console.log(JSON.stringify({
  helixSum: bgArtGenome("AB").sum,
  a: grow("Brayden"),
  again: grow("Brayden"),
  b: grow("Ada"),
  repeat: grow("aaaa"),
  blank: grow("   "),
  fallback: grow("Tessellate"),
  capped: box.capped, floored: box.floored, plain: box.plain,
  p5: [bgP5Rgba(229.41176470588235, 62, 58, 0.16), bgP5Rgba(301.41176470588235, 62, 55, 0.16), bgP5Rgba(0, 0, 98, 0.12), bgP5Rgba(0, 0, 12, 0.1)],
  hues: [bgColourHue("#ff0000"), bgColourHue("#00ff00"), bgColourHue("#4664f0"), bgColourHue("rgb(0, 0, 255)"), bgColourHue("#fff")],
}));
"""


@pytest.fixture(scope="module")
def genome(tmp_path_factory):
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("bgart") / "genome.js"
    script.write_text(_GENOME_SCRIPT, encoding="utf-8")
    out = subprocess.run(
        [node, str(script), str(BG_ART), str(SETTINGS)], capture_output=True, text=True, timeout=60, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_genome_is_helixlabs_sum(genome):
    # helixlabs: sumCode += charCodeAt(i) * (i + 1). "AB" is 65*1 + 66*2.
    assert genome["helixSum"] == 65 + 66 * 2


def test_the_same_name_grows_the_same_ecosystem(genome):
    assert genome["a"] == genome["again"]
    assert 3 <= len(genome["a"]) <= 5


def test_a_different_name_grows_a_different_one(genome):
    assert [s["name"] for s in genome["a"]] != [s["name"] for s in genome["b"]]


def test_strains_of_one_name_differ_even_for_a_repeated_letter(genome):
    for key in ("a", "repeat"):
        sums = [s["sum"] for s in genome[key]]
        assert len(set(sums)) == len(sums), key


def test_a_blank_name_falls_back_to_the_app_name(genome):
    assert genome["blank"] == genome["fallback"]


def test_the_accent_hue_is_read_without_p5(genome):
    """The CSS styles run without p5, so the accent's hue is computed here;
    it must be the number p5's `hue()` gave (standard HSL hue)."""
    red, green, indigo, blue, white = genome["hues"]
    assert round(red) == 0 and round(green) == 120 and round(blue) == 240
    assert 228 <= indigo <= 230
    assert white == 0


def test_the_waves_colours_are_the_ones_p5_set(genome):
    """The waves no longer go through p5, and must look as they did: these
    are p5 1.9.4's own `color(h, s, l, a).toString()` in `colorMode(HSL,
    360, 100, 100, 1)`, read from the vendored p5 in Chromium, for the
    default accent's first and last wave layers and the two trail washes."""
    assert genome["p5"] == [
        "rgba(81,105,214,0.16)",
        "rgba(211,69,208,0.16)",
        "rgba(250,250,250,0.12)",
        "rgba(31,31,31,0.1)",
    ]


def test_the_art_runs_at_30_or_20_frames_a_second():
    """A timestamp gate, not every display frame: 30 a second, 20 on a
    small machine (four cores or four gigabytes or fewer) or on battery."""
    text = BG_ART.read_text(encoding="utf-8")
    rate = text[text.index("function bgArtFrameRate()") :]
    rate = rate[: rate.index("\n}\n")]
    assert "? 20 : 30" in rate
    assert "hardwareConcurrency" in text and "deviceMemory" in text and "getBattery" in text
    assert "1000 / Math.min(style.fps || 30, bgArtFrameRate())" in text


def test_the_art_needs_no_p5():
    """The art draws on its own canvas; p5 stays for the dashboard's art
    widget only (the emblem is a 2D canvas since audit FE-07)."""
    text = BG_ART.read_text(encoding="utf-8")
    assert "new p5(" not in text
    start = SETTINGS.read_text(encoding="utf-8")
    body = start[start.index("function startBgArt()") :]
    body = body[: body.index("\n}\n")]
    assert "ensureP5" not in body


def test_the_emblem_moves_by_css_not_by_redrawing():
    """Drawn once (SVG layers since the tessellation mark, brief "logo"),
    moved by CSS animations of its layers: no p5 instance, no frame loop."""
    app = app_js_text()
    for name in ("function renderEmblem(", "function emblemArt("):
        body = app[app.index(name) :]
        body = body[: body.index("\n}\n")]
        assert "frameRate(" not in body, "the emblem must draw once, not loop"
        assert "new p5(" not in body and "requestAnimationFrame" not in body
    css = CSS.read_text(encoding="utf-8")
    for frames in ("emblem-arrive", "emblem-breathe", "emblem-lift"):
        assert f"@keyframes {frames}" in css


def _luma(rgba: str) -> float:
    r, g, b = (int(v) for v in re.findall(r"[\d.]+", rgba)[:3])

    def lin(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def test_the_contrast_guards_bound_every_colour_a_style_builds(genome):
    """While a style builds its colours, the dark theme's cap and the light
    theme's floor hold every colour's luminance on the side the text needs
    (measured need: scratchpad/ui-sweeps/bgartcontrast.js), and the rest of
    the time colours are untouched."""
    for colour in genome["capped"]:
        assert colour.startswith("rgba(") and _luma(colour) <= 0.1 + 0.005, colour
    for colour in genome["floored"]:
        assert colour.startswith("rgba(") and _luma(colour) >= 0.35 - 0.005, colour
    assert genome["plain"].startswith("hsla(")
    styles = BG_ART.read_text(encoding="utf-8")
    for name in ("aurora", "constellation", "mycelium", "mesh"):
        assert "darkCap:" in _chunks()[name], name
    assert "bgLumCap = 0;" in styles and "bgLumFloor = 0;" in styles


def test_mycelium_cross_fades_its_generations():
    """The owner: the hand-over "needs to be smoother and maybe faded". A
    generation fades out on its own canvas while the next grows on the twin
    the runtime gives it, instead of a window-wide `destination-out` and a
    hard clear; and its spores are scattered, never a ring of even angles."""
    body = _chunks()["mycelium"]
    assert "twin: true" in body
    assert "destination-out" not in body
    assert "canvas.style.opacity = fadeOpacity[" in body
    # Uneven angles and staggered starts.
    assert "p.random(-0.38, 0.38)" in body and "TD[n] =" in body
    runtime = BG_ART.read_text(encoding="utf-8")
    run = runtime[runtime.index("function bgArtRun(") :]
    assert 'id = "bg-art-twin"' in run and "style.twin && !o.still" in run
    # Removed with the canvas, and handed over with it.
    assert "twin.canvas.remove()" in run
    halt = runtime[runtime.index("function bgArtHalt(") :]
    assert 'getElementById("bg-art-twin")' in halt[: halt.index("\n}\n")]


def test_microbes_copy_prerendered_bodies_and_glows():
    """The owner: "optimise the microbes animation as well". Bodies are
    painted once into an atlas per species and copied a cell per organism;
    glows are painted at the size they are drawn and copied unscaled, both
    on whole pixels, so neither is resampled a frame."""
    body = _chunks()["microbes"]
    frame = body[body.index("      frame() {") :]
    assert "atlasOf(sp)" in body and "bgSprite(cell * angles, cell * phases" in body
    assert "g.drawImage(at.img, sx, sy, cell, cell, (X[i] - at.half) | 0" in frame
    assert "g.drawImage(sp.glowSprite, (X[i] - sp.glowHalf) | 0, (Y[i] - sp.glowHalf) | 0);" in frame
    # The outlines are no longer built a frame, only the flagella.
    assert "bodies(g, si, q, 0)" not in frame and "bodies(g, si, q, 2)" in frame


def test_constellation_stars_are_copied_unscaled():
    """Stars are painted at the sizes they are drawn and copied on whole
    pixels; the far layer, the most numerous, is squares batched per
    twinkle step rather than an image copy each."""
    body = _chunks()["constellation"]
    frame = body[body.index("      frame(t) {") :]
    assert "g.drawImage(spr, (sx[i] - spr.width / 2) | 0, (sy[i] - spr.width / 2) | 0);" in frame
    assert "g.drawImage(halo, (sx[i] - hh) | 0, (sy[i] - hh) | 0);" in frame
    assert "g.rect((sx[i] - 1) | 0, (sy[i] - 1) | 0, 2, 2)" in frame
    # No scaled copies of a star left in the frame.
    assert ", ds, ds)" not in frame and ", hs, hs)" not in frame


def test_the_art_drops_to_12_frames_after_30_seconds_without_a_pointer():
    """audit 1031 Z18: nobody is watching it, so it costs less (a style's own
    per-frame step already scales with the rate it asks for)."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    text = BG_ART.read_text(encoding="utf-8")
    pick = lambda name: text[text.index(name) :].split("\n}\n")[0] + "\n}\n"  # noqa: E731
    source = (
        "let bgArtOnBattery = false, bgArtLastPointer = 0, NOW = 0;\n"
        "const performance = { now: () => NOW };\n"
        "const BG_ART_SMALL_MACHINE = false;\n"
        + re.search(r"const BG_ART_CALM_MS = \d+;", text).group(0) + "\n"
        + re.search(r"const BG_ART_CALM_FPS = \d+;", text).group(0) + "\n"
        + pick("function bgArtCalm(")
        + pick("function bgArtFrameRate(")
        + "const at = (t) => { NOW = t; return bgArtFrameRate(); };\n"
        "bgArtLastPointer = 1000;\n"
        "console.log(JSON.stringify([at(1000), at(30999), at(31001), (bgArtLastPointer = 40000, at(40001))]));\n"
    )
    result = subprocess.run([node, "-e", source], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == [30, 30, 12, 30]
    assert 'type !== "keydown"' in text and "bgArtLastPointer = performance.now()" in text
