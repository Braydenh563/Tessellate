"""The Word-style equation field (math-field.js; INBOX 1473 a).

MathLive (vendored, MIT) draws and edits the equation; what is tested here is
the app's side of it. The pure core (`MATH-FIELD-CORE-BEGIN` to `-END`) runs
in node: boxes in and out of the stored TeX, the one-line rule, and the change
that replaces exactly the equation's source range and nothing else. The
wiring is read from the files: the library is vendored with its licence, loads
only on the first equation edit (never at boot), comes from no CDN, and the
page's policy needs no loosening for it. The click, the box, Enter, Escape and
undo run in a browser in `tests-e2e/specs/math-field.spec.js`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
FIELD = (JS / "math-field.js").read_text(encoding="utf-8")
VENDOR = ROOT / "frontend" / "vendor" / "mathlive"

DRIVER = r"""
const results = [];
const check = (name, ok, detail) => results.push({ name, ok: !!ok, detail: detail == null ? null : String(detail) });
const eq = (name, got, want) => check(name, got === want, JSON.stringify(got));

// An empty box in, a box out: the stored text keeps `{}`.
eq("boxes in", mathFieldBoxes("\\frac{67}{}"), "\\frac{67}{\\placeholder{}}");
eq("every empty group", mathFieldBoxes("{} & { }"), "{\\placeholder{}} & {\\placeholder{}}");
eq("filled groups stay", mathFieldBoxes("\\frac{a}{b}"), "\\frac{a}{b}");
eq("boxes out, braced", mathFieldUnplace("\\frac{67}{\\placeholder{}}"), "\\frac{67}{}");
// MathLive writes a whole-argument box without its braces; the braces come back.
eq("bare box is braced", mathFieldUnplace("\\frac{67}\\placeholder{}"), "\\frac{67}{}");
eq("bare filled box", mathFieldUnplace("x^\\placeholder{2}"), "x^{2}");
eq("box with an id", mathFieldUnplace("\\frac{\\placeholder[a]{}}{\\placeholder[b]{3}}"), "\\frac{}{3}");
eq("nested", mathFieldUnplace("\\sqrt{\\placeholder{\\frac{1}{\\placeholder{}}}}"), "\\sqrt{\\frac{1}{}}");
eq("no placeholder word is touched", mathFieldUnplace("\\placeholders"), "\\placeholders");
eq("round trip", mathFieldUnplace(mathFieldBoxes("\\begin{pmatrix} {} & {} \\\\ {} & {} \\end{pmatrix}")), "\\begin{pmatrix} {} & {} \\\\ {} & {} \\end{pmatrix}");
eq("escaped braces are not groups", mathFieldGroupEnd("{\\}}", 0), 3);

// The stored form: one line, trimmed, a bare dollar escaped.
eq("one line", mathFieldStored(" a\n  + b "), "a + b");
eq("dollar escaped", mathFieldStored("a$b"), "a\\$b");
eq("escaped dollar kept", mathFieldStored("a\\$b"), "a\\$b");
eq("boxes unwrapped when stored", mathFieldStored("\\frac{1}{\\placeholder{}}"), "\\frac{1}{}");

// The change replaces the source range exactly.
const text = "before $a$ middle $$\\frac{1}{2}$$ after";
const inline = { from: 7, to: 10, delim: "$" };
const block = { from: 18, to: 33, delim: "$$" };
check("inline range is the equation", text.slice(inline.from, inline.to) === "$a$", text.slice(inline.from, inline.to));
check("block range is the equation", text.slice(block.from, block.to) === "$$\\frac{1}{2}$$", text.slice(block.from, block.to));
const apply = (src, c) => src.slice(0, c.from) + c.insert + src.slice(c.to);
eq("inline replaced", apply(text, mathFieldChange(text, inline, "a+b")), "before $a+b$ middle $$\\frac{1}{2}$$ after");
eq("block replaced", apply(text, mathFieldChange(text, block, "\\frac{1}{3}")), "before $a$ middle $$\\frac{1}{3}$$ after");
eq("nothing changed is no change", mathFieldChange(text, inline, "a"), null);
eq("emptied is removed", apply(text, mathFieldChange(text, inline, "")), "before  middle $$\\frac{1}{2}$$ after");
eq("a moved equation is refused", mathFieldChange("x" + text, inline, "q"), null);
eq("a deleted equation is refused", mathFieldChange("before", inline, "q"), null);
eq("neighbours byte-identical", apply(text, mathFieldChange(text, inline, "z")).replace("$z$", "$a$"), text);
process.stdout.write(JSON.stringify(results));
"""


def _region(text: str, begin: str, end: str) -> str:
    start, stop = text.find(begin), text.find(end)
    assert start != -1 and stop > start, f"{begin} / {end} markers are missing"
    return text[start + len(begin) : stop]


@pytest.fixture(scope="module")
def core_checks(tmp_path_factory) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("mathfield") / "run.js"
    script.write_text(_region(FIELD, "// MATH-FIELD-CORE-BEGIN", "// MATH-FIELD-CORE-END") + DRIVER, encoding="utf-8")
    out = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_core_round_trips_boxes_and_replaces_the_exact_range(core_checks: list[dict]) -> None:
    assert len(core_checks) >= 24
    failed = [c for c in core_checks if not c["ok"]]
    assert not failed, "\n".join(f"{c['name']}: {c['detail']}" for c in failed[:20])


def test_the_library_is_vendored_with_its_licence_and_loaded_only_on_use() -> None:
    assert (VENDOR / "mathlive.min.js").is_file()
    assert "Arno Gourdol" in (VENDOR / "LICENSE").read_text(encoding="utf-8")
    assert (VENDOR / "VERSION.txt").is_file()
    assert (VENDOR / "fonts" / "KaTeX_Main-Regular.woff2").is_file()
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "mathlive" not in index and "math-field" not in index
    entries = (JS / "lazy-entries.js").read_text(encoding="utf-8")
    assert 'mathField: ["/css/math-field-lazy.css", "/vendor/mathlive/mathlive.min.js", "/js/math-field.js"]' in entries
    assert 'mathField: ["openMathInPlace"]' in entries
    for boot in ("app.js", "app-boot.js"):
        path = JS / boot
        if path.is_file():
            assert "mathlive" not in path.read_text(encoding="utf-8").lower()


def test_nothing_comes_from_a_cdn_and_the_policy_is_not_loosened() -> None:
    assert not re.search(r"https?://", FIELD.replace("http://www.w3.org", ""))
    assert 'MathfieldElement.fontsDirectory = "/vendor/mathlive/fonts"' in FIELD
    assert "MathfieldElement.soundsDirectory = null" in FIELD
    from tessellate.core import security

    policy = security.build_csp([])
    assert "unsafe-eval" not in policy.replace("wasm-unsafe-eval", "")
    assert "style-src 'self'" in policy and "'unsafe-inline'" not in policy.split("style-src")[1].split(";")[0]
    # The library's markup carries style attributes the policy refuses; they are
    # applied through CSSOM instead (mathFieldAllowStyles), never by a looser policy.
    assert "el.style.cssText" in FIELD and "data-ml-style" in FIELD


def test_the_widget_click_goes_through_the_one_in_place_door() -> None:
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    assert 'ensureModule("mathField")' in docs and "openMathInPlace({ view, host, from, to, delim, tex: this.tex })" in docs
    assert "view.posAtDOM(host)" in docs


def test_the_keyboard_is_offered_on_touch_only() -> None:
    assert 'mathFieldTouch() ? "auto" : "manual"' in FIELD
    css = (ROOT / "frontend" / "css" / "math-field-lazy.css").read_text(encoding="utf-8")
    assert "@media (pointer: fine)" in css and "virtual-keyboard-toggle" in css
