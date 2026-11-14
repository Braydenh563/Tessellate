"""Live captions tap the microphone in an AudioWorklet (L580).

ScriptProcessorNode is deprecated and ran on the page's main thread. The tap
is now a module served from the app's own origin, which `script-src 'self'`
allows with no blob: or data: URL, so the policy stays as it was (measured in
Chromium: addModule resolved in 99 ms and a 4096-sample Float32Array arrived,
no violation logged). A real microphone is a device check.
"""

from __future__ import annotations

from pathlib import Path

from tessellate.core.security import build_csp
from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]


def test_the_page_no_longer_uses_the_deprecated_node():
    for path in (ROOT / "frontend" / "js").glob("*.js"):
        text = path.read_text(encoding="utf-8")
        assert "createScriptProcessor" not in text, path.name
        assert "onaudioprocess" not in text, path.name


def test_the_tap_is_a_module_from_the_apps_own_origin():
    captions = frontend_text("captions.js")
    assert 'audioWorklet.addModule("/js/caption-tap-worker.js")' in captions
    assert 'new AudioWorkletNode(ctx, "caption-tap"' in captions
    assert "createObjectURL" not in captions
    worker = (ROOT / "frontend" / "js" / "caption-tap-worker.js").read_text(encoding="utf-8")
    assert 'registerProcessor("caption-tap"' in worker
    assert "CAPTION_TAP_BLOCK = 4096" in worker


def test_the_policy_needed_no_change_for_it():
    csp = build_csp([])
    script = next(part for part in csp.split(";") if part.strip().startswith("script-src"))
    assert "'self'" in script and "blob:" not in script and "data:" not in script


def test_a_failed_tap_ends_the_started_run_and_says_so():
    captions = frontend_text("captions.js")
    start = captions.index("await ctx.audioWorklet.addModule")
    block = captions[start : start + 900]
    assert "/stop" in block and "save: false" in block and "toast(why, \"info\")" in block
