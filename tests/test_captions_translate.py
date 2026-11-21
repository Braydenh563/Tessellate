"""Translate under the live captions (ledger libr-1011 row 1222, live
translated captions, built here).

The dock translates each *finished* line through the offline translator's
worker, in order, one at a time, and shows the last two under the running
line. The pump is run here in node against a stand-in `translateAsk` (the real
one needs the downloaded model: needs a device). A line the translator fails
on keeps its place, so the lines after it stay in step."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests import _js_scope

ROOT = Path(__file__).resolve().parents[1]
JS = _js_scope.unwrapped((ROOT / "frontend" / "js" / "captions.js").read_text(encoding="utf-8"))
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _block(start: str, end: str) -> str:
    begin = JS.index(start)
    return JS[begin : JS.index(end, begin) + len(end)]


def _run(lines: list[str], answers: dict[str, object], on: bool = True) -> dict:
    node = shutil.which("node")
    if not node:  # pragma: no cover
        pytest.skip("node is not available")
    script = (
        _block("const captionTranslate = {", "};\n")
        + _block("function captionTranslatedText()", "\n}\n")
        + _block("async function captionTranslatePump()", "\n}\n")
        + """
const captionRun = { id: "run", lines: JSON.parse(process.argv[1]) };
const answers = JSON.parse(process.argv[2]);
const asked = [];
let inflight = 0, overlap = 0;
async function translateAsk(pair, text) {
  asked.push([pair.to, text]);
  inflight++; overlap = Math.max(overlap, inflight);
  await new Promise((r) => setTimeout(r, 5));
  inflight--;
  const a = answers[text];
  if (a === "throw") throw new Error("worker gone");
  return a === undefined ? { ok: true, text: "ES " + text } : a;
}
let paints = 0;
function captionPaint() { paints++; }
captionTranslate.on = process.argv[3] === "on";
captionTranslate.pair = { to: "es" };
(async () => {
  captionTranslate.out = [];
  await captionTranslatePump();
  await new Promise((r) => setTimeout(r, 200));
  process.stdout.write(JSON.stringify({ asked, out: captionTranslate.out, shown: captionTranslatedText(), overlap, paints }));
})();
"""
    )
    out = subprocess.run(
        [node, "-e", script, json.dumps(lines), json.dumps(answers), "on" if on else "off"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_every_finished_line_is_translated_in_order_one_at_a_time():
    got = _run(["hello there", "how are you", "fine thanks"], {})
    assert [text for _to, text in got["asked"]] == ["hello there", "how are you", "fine thanks"]
    assert got["out"] == ["ES hello there", "ES how are you", "ES fine thanks"]
    assert got["overlap"] == 1
    assert got["shown"] == "ES how are you\nES fine thanks"  # the last two


def test_a_failed_line_keeps_its_place_and_the_rest_carry_on():
    got = _run(["one", "two", "three"], {"two": {"ok": False, "error": "no"}})
    assert got["out"] == ["ES one", "", "ES three"]
    assert got["shown"] == "ES one\nES three"
    got = _run(["one", "two"], {"one": "throw"})
    assert got["out"] == ["", "ES two"]


def test_off_asks_nothing():
    got = _run(["one", "two"], {}, on=False)
    assert got["asked"] == [] and got["out"] == []


def test_the_dock_has_the_button_the_paragraph_and_the_help():
    assert re.search(r'<button type="button" id="captions-translate" class="ghost small hidden" aria-pressed="false"', HTML)
    assert 'id="captions-translated"' in HTML and 'lang="es"' in HTML
    help_text = HTML[HTML.index('id="captions-help"') :].split("</div>", 1)[0]
    assert "Translate" in help_text and "Settings, Packages" in help_text
    #: Shown only when the translator is installed, so a press never dead-ends.
    offer = _block("function captionOfferTranslate()", "\n}\n")
    assert '"/translate/status"' in offer and "status?.installed && status.pairs?.length" in offer
    assert 'addEventListener("click", captionToggleTranslate)' in JS


def test_the_note_keeps_what_was_said():
    stop = _block("async function stopLiveCaptions()", "\n}\n")
    assert "translat" not in stop.lower().replace("captiontranslate.on = false", "")
