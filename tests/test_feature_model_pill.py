"""The model pill in the writing desk's and the documents assistant's dock.

The owner, 2026-11-12: "Yes, a dock pill". Each pill is a `.chat-model-button`
(the `#chat-active-model` recipe) marked `data-feature-pill="<feature key>"`,
filled from that feature's resolved row and opening the one picker sheet.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

PILLS = {"draft-model-pill": "writing", "doc-ai-model-pill": "documents"}


def _tag(ident: str) -> str:
    match = re.search(rf'<button\b[^>]*\bid="{ident}"[^>]*>', HTML)
    assert match, ident
    return match.group(0)


def test_each_dock_has_a_pill_of_the_chat_pill_recipe_for_its_feature():
    for ident, key in PILLS.items():
        tag = _tag(ident)
        assert "chat-model-button" in tag
        assert f'data-feature-pill="{key}"' in tag


def test_the_pill_is_inside_the_dock_not_the_menu():
    desk = HTML[HTML.index('data-dock-name="writing-room"'):HTML.index('id="draft-help-body"')]
    assert 'id="draft-model-pill"' in desk
    assert desk.index('id="draft-model-pill"') < desk.index('id="draft-more-menu"')
    docs = HTML[HTML.index('id="doc-ai-model-pill"'):]
    assert docs.index('id="doc-ai-model-pill"') < docs.index('id="doc-ai-model"')


def test_the_pill_reads_the_resolved_row_and_opens_the_shared_sheet():
    js = app_js_text()
    body = js[js.index("function syncFeatureModelPills("):]
    body = body[: body.index("\nfunction ", 10)]
    assert "featureModelRow(" in body and "row.model" in body
    assert "openFeatureModelSheet(" in js[js.index("[data-feature-pill]"):]
    assert "syncFeatureModelSelects.pills()" in js[js.index("function syncFeatureModelSelects"):]
