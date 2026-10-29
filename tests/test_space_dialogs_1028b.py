"""Sweep 1028b W11: the space dialogs submit on Enter and name their icon group.

The inputs belong to an (empty) form by `form=`; the radiogroup is labelled by
a visible label, not by the hidden input (which has no accessible name).
"""

from __future__ import annotations

import re
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")


def test_each_space_dialog_has_a_form_its_fields_and_button_belong_to():
    for kind in ("create", "edit"):
        assert f'<form id="space-{kind}-form"' in HTML
        assert re.search(rf'<input[^>]*id="space-{kind}-name"[^>]*form="space-{kind}-form"', HTML)
        assert re.search(rf'<button[^>]*type="submit"[^>]*form="space-{kind}-form"[^>]*id="space-{kind}-submit"', HTML)


def test_the_icon_group_is_named_by_a_visible_label():
    for kind in ("create", "edit"):
        assert f'aria-labelledby="space-{kind}-icon-label"' in HTML
        assert f'id="space-{kind}-icon-label"' in HTML
        assert f'aria-labelledby="space-{kind}-icon"' not in HTML
