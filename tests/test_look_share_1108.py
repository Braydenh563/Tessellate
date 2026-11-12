"""Share a look as JSON, and Surprise me with a mix (BACKLOG Colours, More themes).

The pure half of settings.js (between `LOOK FILE BEGIN` and `LOOK FILE END`) is
run under node against the page's real lists, so what is checked is the shipped
code: an import takes only what it can prove (types, ranges, colour format) and
names what it skipped; a seeded pick is repeatable and stays inside the sets.
"""

from __future__ import annotations

from tests._help_text import help_more_text
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
SETTINGS = (JS / "settings.js").read_text(encoding="utf-8")
AI_TOOLS = (JS / "ai-tools.js").read_text(encoding="utf-8")
CONTROLS = unwrapped((JS / "settings-controls.js").read_text(encoding="utf-8"))
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _block(src: str, head: str, tail: str) -> str:
    start = src.index(head)
    return src[start : src.index(tail, start) + len(tail)]


def _run(body: str) -> object:
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    pure = _block(SETTINGS, "// LOOK FILE BEGIN", "// LOOK FILE END")
    script = "\n".join(
        [
            _block(AI_TOOLS, "const DEVICE_ONLY_KEYS", "];"),
            _block(AI_TOOLS, "const OVERRIDABLE_KEYS", "];"),
            _block(AI_TOOLS, "const LOOK_KEYS", ";"),
            _block(SETTINGS, "const ACCENTS = [", "\n];"),
            _block(SETTINGS, "const PALETTES = [", "\n];"),
            _block(SETTINGS, "const BG_ART_STYLES", ";"),
            "const THEME_PRESETS = { utilitarian: {}, ocean: {} };",
            "const settingsLook = {};",
            pure,
            body,
        ]
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _check(values: dict, **extra) -> dict:
    payload = {"kind": "tessellate-look", "version": 1, "values": values, **extra}
    return _run(f"console.log(JSON.stringify(settingsLook.lookFile.check(JSON.parse({json.dumps(json.dumps(payload))}))))")


def test_an_export_reads_back_whole():
    values = {"theme": "dark", "palette": "ocean", "accent": "teal", "radius": "10", "glass-opacity": "80", "bgArt": "on"}
    out = _check(values, preset="ocean")
    assert out["values"] == values and out["skipped"] == [] and out["preset"] == "ocean"
    assert "error" not in out


def test_the_payload_carries_only_look_keys():
    out = _run(
        'console.log(JSON.stringify(settingsLook.lookFile.payload({theme:"dark", zoom:"150", nope:"x", radius:"9"}, "ocean")))'
    )
    assert out == {"kind": "tessellate-look", "version": 1, "values": {"theme": "dark", "radius": "9"}, "preset": "ocean"}


def test_unknown_and_device_keys_are_skipped_by_name():
    out = _check({"theme": "light", "zoom": "150", "density": "compact", "nope": "1", "__proto__": "x"})
    assert out["values"] == {"theme": "light"}
    names = " ".join(out["skipped"])
    assert all(k in names for k in ("zoom", "density", "nope", "__proto__"))


@pytest.mark.parametrize(
    "key,value",
    [
        ("radius", "99"), ("radius", "-1"), ("radius", "4.5"), ("radius", ""), ("radius", True),
        ("glass-blur", "1"), ("glass-opacity", "4"), ("glass-sheen-strength", "101"), ("bg-intensity", "19"),
        ("accent", "nope"), ("palette", "nope"), ("theme", "purple"), ("font", "comic"), ("bg-style", "x"),
        ("bg-motion", "fast"), ("glass", "maybe"), ("bgArt", "yes"),
        ("accent-custom", "red"), ("accent-custom", "#12345"), ("accent-custom", "#12345g"),
        ("page-bg", "url(http://x/y.png)"), ("page-bg", "red"), ("page-bg", "linear-gradient(url(x))"),
        ("theme", 3), ("accent", ["teal"]), ("accent", None),
    ],
)
def test_a_value_it_cannot_prove_is_skipped(key, value):
    out = _check({key: value, "page-wash": "on"})
    assert out["values"] == {"page-wash": "on"}
    assert any(key in s for s in out["skipped"])


def test_colours_and_gradients_are_accepted_in_their_format():
    out = _check({"accent-custom": "#AABBCC", "page-bg": "linear-gradient(135deg,#f2f3f5,rgba(1,2,3,0.5) 45%)"})
    assert out["values"]["accent-custom"] == "#aabbcc" and "page-bg" in out["values"] and not out["skipped"]
    assert _check({"page-bg": "#fafafa"})["values"] == {"page-bg": "#fafafa"}


def test_numbers_may_arrive_as_numbers():
    assert _check({"radius": 12})["values"] == {"radius": "12"}


@pytest.mark.parametrize(
    "bad",
    [
        "[]", "3", "null",
        '{"kind":"other","version":1,"values":{}}',
        '{"kind":"tessellate-look","version":2,"values":{}}',
        '{"kind":"tessellate-look","version":1,"values":[]}',
    ],
)
def test_a_file_that_is_not_a_look_is_refused(bad):
    out = _run(f"console.log(JSON.stringify(settingsLook.lookFile.check(JSON.parse({json.dumps(bad)}))))")
    assert out["error"] and out["values"] == {}


def test_a_file_with_nothing_usable_is_an_error_naming_what_was_skipped():
    out = _check({"radius": "99"})
    assert "radius" in out["error"]


def test_an_unknown_preset_is_skipped():
    out = _check({"theme": "dark"}, preset="nope")
    assert out["preset"] == "" and any("preset" in s for s in out["skipped"])


def test_the_toast_names_at_most_four():
    out = _run('console.log(JSON.stringify(settingsLook.lookFile.skippedLine(["a","b","c","d","e","f"])))')
    assert out.count(",") == 3 and "2 more" in out and "a" in out


def test_the_controls_exist_are_wired_and_documented():
    for ident in ("look-export", "look-import", "look-import-file"):
        assert f'id="{ident}"' in INDEX
        assert f'"{ident}"' in CONTROLS
    assert "exportNow" in CONTROLS[CONTROLS.index('$("look-export")') :][:200]
    assert "downloadJson(" in SETTINGS[SETTINGS.index("function exportLook") :][:300]
    more = help_more_text()
    themes = more[more.index('"id": "themes"') :][:4000]
    assert "Export look" in themes and "Import look" in themes
