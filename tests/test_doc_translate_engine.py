"""Source text: the behaviour is front-end script that pytest cannot run without a browser, so these pin the code's text.

L331: a document's "Translate this passage" goes to the offline translator when it is installed."""
from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents.js"


def _fn() -> str:
    text = JS.read_text(encoding="utf-8")
    return text.split("async function docTranslatePassage(")[1].split("let docLastTranslateLanguage")[0]


def test_translate_passage_tries_the_offline_engine_before_the_chat():
    body = _fn()
    assert 'apiJson("/translate/status"' in body
    assert 'ensureModule("translate")' in body and "translateCaught({ selection: text })" in body
    # The chat hand-off stays as the fallback when the package is not installed.
    assert body.index("translateCaught(") < body.index('switchTab("chat")')
