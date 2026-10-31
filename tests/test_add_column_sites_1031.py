"""New columns arrive as alembic revisions only (audit 1031 AR4).

`Database._add_missing_columns` adds any model column an old database lacks, so
a model edit alone "works" and the true shape of a table exists nowhere but a
running database. A column on a table the migrations already know has to be
named in a revision under `migrations/versions`; the ones that predate that rule
are frozen below (they reach old databases through the in-place path), and the
list may only shrink.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.core.database import Base

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "migrations" / "versions"

#: Columns on tracked tables that no revision names. Remove a row the day a revision covers it;
#: never add one: write the revision (copy a recent `add_column` one, which is idempotent).
FROZEN: frozenset[str] = frozenset(
    {
        "attachments.caption",
        "attachments.caption_edited",
        "attachments.caption_model",
        "attachments.vision_ocr_model",
        "attachments.vision_ocr_text",
        "documents.file_type",
        "documents.graph_pin_x",
        "documents.graph_pin_y",
        "entries.board_settings",
        "entries.colour",
        "entries.discarded_tags",
        "entries.filing_similar_id",
        "entries.filing_state",
        "entries.graph_pin_x",
        "entries.graph_pin_y",
        "entries.is_board",
        "entries.last_opened_at",
        "entries.source_path",
        "entries.source_title",
        "entries.source_url",
        "entries.suggested_tags",
        "entries.tag_suggest_off",
        "media_uploads.caption",
        "media_uploads.caption_edited",
        "media_uploads.caption_model",
        "media_uploads.size_bytes",
        "media_uploads.vision_ocr_model",
        "media_uploads.vision_ocr_text",
        "reminders.alert_minutes",
        "reminders.done_at",
        "reminders.repeat_day",
        "spaces.hidden_from_all",
        "user_preferences.proposed",
    }
)


def _revisions() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(VERSIONS.glob("*.py"))}


def _tracked_tables(revisions: dict[str, str]) -> dict[str, str]:
    """Table name to the text that creates it (the baseline, or a revision's `create_table`)."""
    tracked: dict[str, str] = {}
    for text in revisions.values():
        for match in re.finditer(r"op\.create_table\(\s*['\"](\w+)['\"]", text):
            start = match.start()
            tracked[match.group(1)] = tracked.get(match.group(1), "") + text[start : start + 6000]
    return tracked


def uncovered() -> set[str]:
    revisions = _revisions()
    created = _tracked_tables(revisions)
    out = set()
    for table in Base.metadata.tables.values():
        if table.name not in created:
            continue  # a table `create_all` made whole
        for column in table.columns:
            quoted = re.compile(rf"""['"]{re.escape(column.name)}['"]""")
            in_create = created[table.name].split("op.create_table(", 2)
            own = "op.create_table(" + in_create[1] if len(in_create) > 1 else ""
            if quoted.search(own):
                continue  # in the table's own create_table
            named = re.compile(rf"""['"]{re.escape(table.name)}['"]""")
            if any(named.search(t) and quoted.search(t) for t in revisions.values()):
                continue  # a revision names the table and the column
            out.add(f"{table.name}.{column.name}")
    return out


def test_a_new_column_has_a_revision():
    new = uncovered() - FROZEN
    assert not new, f"write an alembic revision for: {sorted(new)}"


def test_the_frozen_list_only_shrinks():
    stale = FROZEN - uncovered()
    assert not stale, f"a revision covers these now, remove them from FROZEN: {sorted(stale)}"


def test_the_in_place_path_has_one_ddl_site():
    # The one place a column is added without a revision, so a second never appears quietly.
    source = (ROOT / "src" / "tessellate" / "core" / "database.py").read_text(encoding="utf-8")
    assert len(re.findall(r'ADD COLUMN "', source)) == 1
