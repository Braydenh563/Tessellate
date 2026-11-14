"""Source text: L-ui-modernisation-82, deepflows settings: "Let that app add and change
notes" went back to off after a reload. Measured: `/preferences` said
`mcp_writes_enabled: true` and the box in Tools read false, because only
`renderAutonomousSettings` (Background tasks, Web search) filled it. Tools now
fills it from the read it already makes when it opens.

Also the dictation "Skip silence" box: its markup said unchecked over a
preference that ships on, so a read before the extras paint saw it off."""

import re
from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]


def test_tools_reads_the_mcp_writes_preference_when_it_opens() -> None:
    js = frontend_text("settings-controls.js")
    start = js.index("async function renderToolSettings()")
    block = js[start : start + 1200]
    assert 'apiJson("/preferences")' in block
    assert '$("pref-mcp-writes").checked = Boolean(prefs.mcp_writes_enabled)' in block


def test_skip_silence_markup_matches_its_shipped_default() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    tag = re.search(r'<input[^>]*id="voice-skip-silence"[^>]*>', html).group(0)
    assert " checked" in tag


def test_the_dictation_rows_read_the_preferences_fresh() -> None:
    js = frontend_text("settings-packages.js")
    start = js.index('$("voice-skip-silence").checked')
    assert 'prefsCache = (await apiJson("/preferences")' in js[start - 700 : start]
    assert "if (!prefsCache) prefsCache" not in js[start - 700 : start]
    # Painted whether or not the voice extra is installed: its row always shows.
    assert "if (voiceExtra?.installed)" not in js[start - 700 : start]
