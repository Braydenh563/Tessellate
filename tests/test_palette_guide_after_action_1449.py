"""INBOX 1449: "when I used the find everything search to open the ocr workspace,
the help guide section came up before the actual link to open it".

Find anything's action rows are the palette's (`paletteFind`), and the palette
ranked a Guide topic ("The OCR workspace", from Settings, Help) and the row that
opens the feature ("OCR workspace: read a document or image") by score alone.
Both scored 4 for "ocr workspace", so the tie went to list position, which put
the Guide first once Settings, Help had been opened. Measured before in the
running app (1440x900, Settings, Help opened once, Find anything): "ocr
workspace" gave the Guide topic first, then "Tesseract and the reading
language", then the feature at row 5; "whiteboard", "graph" and "calculator"
gave a Guide topic first too. After: the opening row is first for each.

A Guide topic is now its own group, marked `help`, and `paletteTier` ranks it
after every row that names the thing, for every feature. This runs the real
`paletteRanked` over feature names, with the Guide topic listed first so a
position tie cannot hide a missing rule.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
PALETTE = (JS / "app-palette.js").read_text(encoding="utf-8")

FEATURES = (
    "ocr workspace", "whiteboard", "calculator", "timer", "statistics", "graph", "backups",
    "reminders", "mind maps", "quick sketch", "find anything", "timeline",
)


def _function(name: str) -> str:
    start = PALETTE.index(f"function {name}(")
    return PALETTE[start : PALETTE.index("\n}\n", start) + 3]


def _ranked(query: str, rows: list[dict]) -> list[str]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const PALETTE_ALIASES = {}; const PALETTE_FILLER = new Set();\n"
        "const paletteUsage = new Map(); const PALETTE_WHY = [];\n"
        "const meaningAlts = () => null, meaningHolds = () => false, meaningCloseness = () => 0,"
        " meaningMissing = () => 0, meaningWords = (t) => String(t).split(/\\s+/).filter(Boolean);\n"
        "const palettePrefixPicks = () => ({}); const paletteFeature = (r) => r.label;\n"
        + "".join(_function(f) for f in ("paletteText", "paletteTarget", "paletteWords", "paletteScore", "paletteVocab",
                                          "paletteTier", "paletteWhy", "paletteRanked"))
        + f"\nconst rows = {json.dumps(rows)};\n"
        f"console.log(JSON.stringify(paletteRanked(rows, {json.dumps(query)}).map((r) => r.label)));\n"
    )
    out = subprocess.run([node, "-"], input=script, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-600:]
    return json.loads(out.stdout.strip())


def _rows(feature: str, *, action_keywords: str = "", guide_label: str | None = None) -> list[dict]:
    guide = {"group": "Guide", "help": True, "label": f"ph:book-open-text {guide_label or 'The ' + feature}"}
    action = {"group": "Features", "label": f"ph:compass {feature.capitalize()}: open it", "keywords": action_keywords}
    other = {"group": "Settings", "label": f"ph:gear {feature} setting"}
    return [guide, other, action]  # the Guide topic first: a position tie must not win


@pytest.mark.parametrize("feature", FEATURES)
def test_the_row_that_opens_a_feature_ranks_above_its_guide_topic(feature: str) -> None:
    labels = _ranked(feature, _rows(feature))
    action = next(i for i, label in enumerate(labels) if label.startswith("ph:compass"))
    guide = next(i for i, label in enumerate(labels) if label.startswith("ph:book-open-text"))
    assert action < guide, labels


def test_a_row_found_by_another_word_for_it_still_beats_the_guide_topic() -> None:
    """"scan" is a keyword of the OCR row and the first word of a Guide topic."""
    rows = [
        {"group": "Guide", "help": True, "label": "ph:book-open-text Scan a page"},
        {"group": "Features", "label": "ph:compass OCR workspace", "keywords": "scan image"},
    ]
    assert _ranked("scan", rows)[0] == "ph:compass OCR workspace"


def test_a_guide_topic_is_still_found_when_nothing_opens_the_feature() -> None:
    rows = [{"group": "Guide", "help": True, "label": "ph:book-open-text The calculator"}]
    assert _ranked("calculator", rows) == ["ph:book-open-text The calculator"]


def test_settings_help_rows_are_marked_as_guide_topics() -> None:
    body = _function("paletteSettingRows")
    assert 'group: settingRowIsTopic(row) ? "Guide" : "Settings"' in body
    assert "help: settingRowIsTopic(row)" in body
    settings_find = (JS / "settings-find.js").read_text(encoding="utf-8")
    assert 'row.section === "help"' in settings_find[settings_find.index("function settingRowIsTopic(") :][:200]
