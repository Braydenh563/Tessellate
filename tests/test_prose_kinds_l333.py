"""L333: the person can turn Harper's lint kinds off, by group, in the Checks sheet.

The preference is `prose_kinds_off`; the page sends it as `groupsOff` with every
grammar ask and the worker (run here in node on the vendored binary) drops the
lints of those kinds before the page sees them.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_prose_tools import HARPER_DRIVER

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "frontend" / "js" / "harper-worker.js"

DRIVER = HARPER_DRIVER.replace(
    'for (const dialect of ["uk", "us"]) {\n  await handler({ data: { id: dialect, dialect, text } });\n}',
    'for (const off of [[], ["capitalization", "style", "punctuation", "wording"]]) {\n'
    '  await handler({ data: { id: off.length ? "off" : "on", dialect: "us", text, groupsOff: off } });\n}',
)


def test_a_kind_group_turned_off_is_not_returned(tmp_path) -> None:
    node = shutil.which("node")
    if not node:  # pragma: no cover
        pytest.skip("node is not available")
    script = tmp_path / "kinds.mjs"
    script.write_text(DRIVER, encoding="utf-8")
    text = "the notebook is here. The the index moved,and it is fine.\n"
    out = subprocess.run(
        [node, str(script), WORKER.as_uri(), text], capture_output=True, text=True, timeout=120, check=False
    )
    assert out.returncode == 0, out.stderr
    on, off = json.loads(out.stdout)
    kinds_on = {lint["kind"] for lint in on["lints"]}
    kinds_off = {lint["kind"] for lint in off["lints"]}
    assert "Capitalization" in kinds_on or "Punctuation" in kinds_on, kinds_on
    assert not kinds_off & {"Capitalization", "Punctuation", "Style", "Readability", "WordChoice", "Usage"}, kinds_off
    assert any(lint["problem"] == "The the" for lint in off["lints"]), "grammar proper stays on"


def test_the_preference_round_trips_and_the_sheet_has_the_boxes(client) -> None:
    before = client.get("/preferences").json()
    assert before["prose_kinds_off"] == []
    put = client.put("/preferences", json={"prose_kinds_off": ["style", "punctuation"]}).json()
    assert put["prose_kinds_off"] == ["style", "punctuation"]
    bogus = client.put("/preferences", json={"prose_kinds_off": ["bogus"]})
    assert bogus.status_code == 422
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for group in ("style", "punctuation", "capitalization", "wording"):
        assert f'data-prose-group="{group}"' in html
    page = (ROOT / "frontend" / "js" / "documents-prose.js").read_text(encoding="utf-8")
    assert "groupsOff: (prefsCache && prefsCache.prose_kinds_off)" in page


def test_the_browser_voice_is_picked_in_settings_and_used_by_both_readers() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="pref-read-aloud-voice-name"' in html
    js = ROOT / "frontend" / "js"
    assert 'prefs.set("read-aloud-voice-name"' in (js / "settings-controls.js").read_text(encoding="utf-8")
    assert 'prefs.get("read-aloud-voice-name"' in (js / "media.js").read_text(encoding="utf-8")
    assert 'prefs.get("read-aloud-voice-name"' in (js / "documents-prose.js").read_text(encoding="utf-8")
