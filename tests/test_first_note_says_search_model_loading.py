"""L-world-class-6: while the built-in search model loads, the first note's
card and its activity row say so, not "Filing", which read as an AI filing a
note no AI could file yet (scratchpad/first-run-472.md row 12)."""

from __future__ import annotations

from types import SimpleNamespace

from tessellate.api import routes_entries
from tessellate.core import jobs
from tests._app_js import app_js_text


def test_the_filing_row_says_the_search_model_is_loading(monkeypatch):
    ready = SimpleNamespace(is_ready=lambda: True)
    cold = SimpleNamespace(is_ready=lambda: False)
    monkeypatch.setattr(routes_entries.deps, "get_embeddings", lambda: cold)
    assert jobs.label_for("file-entry") == "Loading the search model"
    monkeypatch.setattr(routes_entries.deps, "get_embeddings", lambda: ready)
    assert jobs.label_for("file-entry") == "Filing a note"
    assert jobs.label_for("ocr") == jobs.LABELS["ocr"]


def test_the_card_chip_says_the_search_model_is_loading():
    js = app_js_text()
    at = js.index('const warming = modelStatus && modelStatus.embedding_ready === false;')
    assert '"ph:spin Search model loading…"' in js[at : at + 400]
