"""L499 retake, measured 2026-11-22 (1440x900, showcase seed, Notes tab):
typing "new" in the palette put four Settings rows ("Finding new versions",
"Check GitHub for a newer version", "Follow the newest changes...", "Last
backup") above New note.

A Settings row carried its whole search haystack (the row's text, its
element's full text, title, aria label, keys, find words, synonyms) as
`keywords`, so the body text counted as another word for the row: "Last
backup" scored 2 because its paragraph says "newest", and the tie-break
`near` counted "new" twice for "Finding new versions" (label and haystack).
Now a Settings row's other words are its keys, find words and synonyms; its
body text still finds it, at the loose score (1).

This runs the real `paletteSettingRows` and `paletteRanked` with a
`findSettings` stub and a `meaningCloseness` that counts held words.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests import _js_scope

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
PALETTE = _js_scope.unwrapped((JS / "app-palette.js").read_text(encoding="utf-8"))

SETTINGS = [
    {"text": "Finding new versions", "section": "about", "sectionLabel": "About", "where": "",
     "haystack": "finding new versions how the app looks for a new version", "keys": "", "find": "", "synonyms": []},
    {"text": "Last backup", "section": "about", "sectionLabel": "About", "where": "Health",
     "haystack": "last backup when the newest backup was written", "keys": "", "find": "", "synonyms": []},
    {"text": "Updates", "section": "about", "sectionLabel": "About", "where": "",
     "haystack": "updates", "keys": "", "find": "upgrade", "synonyms": ["release"]},
]


def _function(name: str) -> str:
    start = PALETTE.index(f"function {name}(")
    return PALETTE[start : PALETTE.index("\n}\n", start) + 3]


def _ranked(query: str) -> list[str]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const PALETTE_ALIASES = {}; const PALETTE_FILLER = new Set();\n"
        "const paletteUsage = new Map(); const PALETTE_WHY = [];\n"
        "const meaningAlts = (q) => q.split(/\\s+/).map((w) => [w]);\n"
        "const meaningHolds = () => false, meaningMissing = () => 0,"
        " meaningWords = (t) => String(t).split(/\\s+/).filter(Boolean);\n"
        "const meaningCloseness = (things, text) => things.filter((g) => new RegExp(`\\\\b${g[0]}\\\\b`).test(String(text).toLowerCase())).length;\n"
        "const palettePrefixPicks = () => ({}); const paletteFeature = (r) => r.label;\n"
        "const paletteGen = { settingsAsked: true, settings: true };\n"
        f"const findSettings = () => {json.dumps(SETTINGS)};\n"
        "const settingRowIsTopic = () => false; const paletteLater = (f) => f;\n"
        + "".join(_function(f) for f in ("paletteText", "paletteTarget", "paletteWords", "paletteScore", "paletteVocab",
                                          "paletteTier", "paletteWhy", "paletteRanked", "paletteSettingRows"))
        + "\nconst base = [{ group: 'Everywhere', label: 'ph:pencil New note', about: 'Save anything' }];\n"
        f"const rows = [...base, ...paletteSettingRows({json.dumps(query)})];\n"
        f"console.log(JSON.stringify(paletteRanked(rows, {json.dumps(query)}).map((r) => r.label)));\n"
    )
    out = subprocess.run([node, "-"], input=script, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-600:]
    return json.loads(out.stdout.strip())


def test_new_note_leads_a_setting_that_holds_new_in_its_body() -> None:
    labels = _ranked("new")
    assert labels[0] == "ph:pencil New note", labels


def test_a_setting_found_only_by_its_body_text_ranks_after_name_matches() -> None:
    labels = _ranked("new")
    assert labels.index("ph:gear Last backup") > labels.index("ph:gear Finding new versions"), labels


def test_a_settings_find_words_and_synonyms_still_count_as_its_other_words() -> None:
    assert _ranked("upgrade")[0] == "ph:gear Updates"
    assert _ranked("release")[0] == "ph:gear Updates"
