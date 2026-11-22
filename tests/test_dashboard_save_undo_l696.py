"""L696: the dashboard's layout, quick access and quick colours are steps on the undo stack.

Each save keeps the value it replaced and hands the pair to `pushRequestUndo`,
so Ctrl+Z puts the layout, the row or the colours back (a plain `PUT /preferences`).
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR

SOURCE = (JS_DIR / "dashboard.js").read_text(encoding="utf-8")


def _body(name: str) -> str:
    match = re.search(rf"^async function {name}\(.*?^\}}", SOURCE, re.S | re.M)
    assert match, name
    return match.group(0)


def test_each_dashboard_save_pushes_the_value_it_replaced():
    for name, key in (
        ("saveDashLayout", "dashboard_layout"),
        ("saveQuickAccess", "dashboard_quick_access"),
        ("saveQuickTints", "dashboard_quick_tints"),
    ):
        body = _body(name)
        assert "pushRequestUndo(" in body, name
        assert f"{{ {key}: before }}" in body, name
        assert "JSON.stringify(before) !==" in body, "an unchanged save adds no step"
