"""One sync story for the person (WORLD_CLASS_PLAN B6 decision 14): one Settings group, two ways in, one line.

Settings, Import & export, Sync between computers offers Sync over the home network (pairing, Sync now) and Sync
through a folder (the button opens sync-folder.js's sheet), under one last-synced line that names the way; the
palette and the Tools and features row open that group; the Guide's two topics point at each other and the group.
"""

from __future__ import annotations

from pathlib import Path

from tessellate.ai import help_chat
from tessellate.ai.help_topics_more import TOPIC_META
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def _group() -> str:
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    start = html.index('<div class="settings-group" id="sync-group">')
    return html[start:html.index('<div class="settings-group">', start + 10)]


def test_the_group_offers_both_ways_in_under_one_status_line():
    group = _group()
    home = group.index('<h4 class="setting-subhead">Sync over the home network</h4>')
    folder = group.index('<h4 class="setting-subhead">Sync through a folder</h4>')
    assert home < group.index('id="sync-pair-row"') < group.index('id="sync-now"') < folder
    assert folder < group.index('id="sync-folder-open"') < group.index('id="sync-status"')
    assert group.count('role="status"') == 1, "one last-synced line for both ways"
    help_text = group.split('id="sync-help"', 1)[1].split("</div>", 1)[0]
    assert "Over the home network" in help_text and "through a folder" in help_text and "never kept" in help_text


def test_the_line_names_the_way_and_the_folder_sheet_refreshes_it():
    text = app_js_text() + (FRONTEND / "js" / "settings-rows.js").read_text(encoding="utf-8")
    assert 'const way = s.via === "folder" ? "through a folder" : "over the home network";' in text
    assert 'document.addEventListener("sync-folder-done"' in text
    assert 'document.dispatchEvent(new CustomEvent("sync-folder-done"));' in text
    # The sheet no longer keeps a last-synced line of its own.
    sheet = (FRONTEND / "js" / "sync-folder.js").read_text(encoding="utf-8")
    assert "Last synced" not in sheet and 'label: "Sync through a folder"' in sheet


def test_the_palette_and_the_feature_row_open_the_group():
    features = (FRONTEND / "js" / "app-features.js").read_text(encoding="utf-8")
    rows = [line for line in features.splitlines() if "Sync between computers" in line]
    assert len(rows) == 2 and all('reveal: "sync-group"' in row for row in rows)


def test_the_guide_tells_one_story_in_two_topics():
    topics = {t["id"]: t["body"] for t in help_chat.HELP_TOPICS}
    home, folder = topics["two-computers"], topics["folder-sync"]
    for body in (home, folder):
        assert "Sync between computers (Settings, Import & export" in body and "two ways in with one result" in body.lower()
    assert "see Sync through a folder" in home and "Sync over the home network (Two computers)" in folder
    assert TOPIC_META["folder-sync"]["target"] == TOPIC_META["two-computers"]["target"] == "sync-group"
