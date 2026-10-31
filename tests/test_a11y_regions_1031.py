"""Audit 1031 N28: a hidden `role=status` with a fixed sentence is read out when it later shows.

The layout-editing hint and the forgot-password "reset on the computer" note were
live regions that sat at `display:none` and appeared with their words already in
them; 25 regions existed at once. They are plain text now, and the one status
region (`announce`) says that editing began. Other hidden regions carry text that
changes while they are hidden and are pinned by their own tests."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _tag(element_id: str) -> str:
    return re.search(rf"<[a-z]+ [^>]*id=\"{element_id}\"[^>]*>", HTML).group(0)


def test_a_fixed_hint_that_shows_later_is_not_a_live_region():
    for element_id in ("dash-hint", "lock-forgot-remote"):
        assert "role=" not in _tag(element_id), element_id


def test_beginning_to_edit_the_layout_is_said_once_by_the_status_region():
    dash = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert 'announce("Editing layout.' in dash

