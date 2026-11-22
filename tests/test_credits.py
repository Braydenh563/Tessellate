"""Settings, Help, Credits (the owner: "we should reference all the vendored
repos and libraries somewhere to give them credit"; WORLD_CLASS_PLAN, the
recommendation: a credits list in Help generated from docs/THIRD_PARTY.md).

frontend/credits.json is written by scripts/build_credits.py; this fails when
THIRD_PARTY.md gains a library the page does not list."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parents[1]
HTML = index_html_text()
FIND = (ROOT / "frontend/js/settings-find.js").read_text(encoding="utf-8")


def _builder():
    spec = importlib.util.spec_from_file_location("build_credits", ROOT / "scripts/build_credits.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_page_list_matches_third_party_md():
    built = _builder().render()
    on_disk = (ROOT / "frontend/credits.json").read_text(encoding="utf-8")
    assert on_disk == built, "run python scripts/build_credits.py"


def test_every_vendored_library_is_credited_with_a_licence_and_a_source():
    rows = [row for group in json.loads((ROOT / "frontend/credits.json").read_text(encoding="utf-8"))["groups"] for row in group["rows"]]
    names = {row["name"] for row in rows}
    for expected in ("D3", "CodeMirror 6", "Phosphor Icons", "Harper", "FlashText", "draw.io stencils"):
        assert expected in names
    for row in rows:
        assert row["licence"] and row["source"].startswith("https://"), row


def test_credits_are_a_fold_in_settings_help_drawn_when_opened():
    help_section = HTML.split('id="settings-help"')[1].split("</section>")[0]
    assert 'details class="settings-group settings-fold" data-fold-key="help-credits" id="credits-fold"' in help_section
    assert 'id="credits-list"' in help_section
    assert 'api("/credits.json"' in FIND
    assert 'fold.addEventListener("toggle", draw)' in FIND
    assert 'name.rel = "noopener noreferrer"' in FIND
