"""Every optional package's feature carries the one notice (INBOX 1748, Q27).

`extraNoticeMount(host, id)` is called where each registry package's feature
opens; the host is an empty slot in index.html or the surface's own element.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.core import extras

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_every_remaining_feature_mounts_its_notice() -> None:
    # documents, semantic and searxng moved with loadPrefs into settings-prefs.js (Sh1 P12, fc806ad6d).
    where = {
        "voice": "navigation.js",
        "translate": "translate.js",
        "languagetool": "documents-dictionary.js",  # the sheet moved out of documents.js (L327)
        "pyodide": "documents-code.js",
        "documents": "settings-prefs.js",
        "semantic": "settings-prefs.js",
        "needle": "status.js",
        "localllm": "status.js",
        "searxng": "settings-prefs.js",
    }
    for ident, name in where.items():
        text = _read(name)
        assert re.search(r'extraNoticeMount\([^;]*["`]' + ident + r'["`]', text) or (
            ident in ("needle", "localllm") and "extraNoticeMount($(`xn-${id}`), id)" in text
        ), (ident, name)


def test_the_slots_exist_once() -> None:
    for slot in ("voice", "languagetool", "documents", "semantic", "needle", "localllm"):
        assert HTML.count(f'id="xn-{slot}"') == 1, slot


def test_the_rapidocr_card_says_what_was_measured() -> None:
    row = next(e for e in extras.EXTRAS if e.id == "rapidocr")
    assert "140 MB" in row.size and "113 MB" in row.size
    assert "140 MB" in _read("ocr-engine.js") and "60 MB" not in _read("ocr-engine.js").split("rapidocr:")[1][:400]
