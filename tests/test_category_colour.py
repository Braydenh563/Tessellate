"""A category's own colour, chosen by the person (INBOX 441 (4)).

The owner: "there is no way to customise the colour of categories." Until now
every category's colour was a hash of its name (a dot) or its place in the
sorted list (the graph). A category now stores an optional `colour`: one of
the palette keys the swatch picker offers, or a `#rrggbb` hex, or nothing
(automatic). The stored value rides on the categories list, so every surface
that draws a category reads it from the one place.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from tessellate.api.routes_categories import CATEGORY_PALETTE_KEYS
from tessellate.core.database_manager import DatabaseManager


def _note(client, text, category):
    entry = client.post("/entries", json={"content": text}).json()
    client.put(f"/entries/{entry['id']}", json={"category": category})
    return entry["id"]


def _cats(client):
    return {c["name"]: c for c in client.get("/categories").json()}


def test_a_category_has_no_colour_until_one_is_chosen(client):
    _note(client, "a", "Work")
    assert _cats(client)["Work"]["colour"] is None


def test_set_a_palette_key_and_read_it_back(client):
    _note(client, "a", "Work")
    cid = _cats(client)["Work"]["id"]
    done = client.put(f"/categories/{cid}/colour", json={"colour": "teal"})
    assert done.status_code == 200
    assert done.json() == {"id": cid, "name": "Work", "colour": "teal"}
    assert _cats(client)["Work"]["colour"] == "teal"


def test_a_hex_is_accepted_and_lowercased(client):
    _note(client, "a", "Work")
    cid = _cats(client)["Work"]["id"]
    done = client.put(f"/categories/{cid}/colour", json={"colour": "#AB12cD"})
    assert done.status_code == 200
    assert _cats(client)["Work"]["colour"] == "#ab12cd"


def test_null_clears_it_back_to_automatic(client):
    _note(client, "a", "Work")
    cid = _cats(client)["Work"]["id"]
    client.put(f"/categories/{cid}/colour", json={"colour": "red"})
    cleared = client.put(f"/categories/{cid}/colour", json={"colour": None})
    assert cleared.status_code == 200 and cleared.json()["colour"] is None
    assert _cats(client)["Work"]["colour"] is None


@pytest.mark.parametrize(
    "bad",
    ["chartreuse", "#abc", "#12345g", "ff0000", "red; background: url(x)", "", " teal", "#1234567", 7, ["red"]],
)
def test_anything_else_is_refused_and_nothing_is_stored(client, bad):
    _note(client, "a", "Work")
    cid = _cats(client)["Work"]["id"]
    refused = client.put(f"/categories/{cid}/colour", json={"colour": bad})
    assert refused.status_code == 422
    assert _cats(client)["Work"]["colour"] is None


def test_a_missing_field_is_refused(client):
    _note(client, "a", "Work")
    cid = _cats(client)["Work"]["id"]
    assert client.put(f"/categories/{cid}/colour", json={}).status_code == 422


def test_an_unknown_category_is_a_400_like_its_siblings(client):
    assert client.put("/categories/99999/colour", json={"colour": "red"}).status_code == 400


def test_rename_keeps_the_colour_and_a_merge_keeps_the_targets(client):
    _note(client, "a", "Wrok")
    _note(client, "b", "Work")
    cats = _cats(client)
    client.put(f"/categories/{cats['Wrok']['id']}/colour", json={"colour": "pink"})
    client.put(f"/categories/{cats['Work']['id']}/colour", json={"colour": "green"})
    # A plain rename carries the colour with the row.
    client.put(f"/categories/{cats['Wrok']['id']}", json={"name": "Scratch"})
    assert _cats(client)["Scratch"]["colour"] == "pink"
    # Renaming onto an existing name merges; the survivor keeps its own.
    client.put(f"/categories/{_cats(client)['Scratch']['id']}", json={"name": "Work"})
    cats = _cats(client)
    assert "Scratch" not in cats and cats["Work"]["colour"] == "green"


def test_the_agent_created_category_starts_automatic(client):
    client.post("/categories", json={"name": "Garden"})
    assert _cats(client)["Garden"]["colour"] is None


def test_a_database_that_needs_the_per_space_rebuild_keeps_its_colours(tmp_path):
    """`_rebuild_categories_unique_constraint` copies a fixed column list into
    a new table. A column it does not name is gone after the rebuild, and a
    `colour` the person chose would silently disappear on the one start that
    rebuilds, so the copy names it."""
    path = tmp_path / "old.db"
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE categories (id INTEGER NOT NULL PRIMARY KEY,"
            " name VARCHAR(100) NOT NULL UNIQUE, description TEXT, created_at DATETIME,"
            " colour VARCHAR(16))"
        )
        conn.execute("INSERT INTO categories (id, name, colour) VALUES (1, 'Work', 'teal')")
        conn.execute("INSERT INTO categories (id, name, colour) VALUES (2, 'Home', NULL)")
        conn.commit()
    finally:
        conn.close()
    DatabaseManager(path)
    conn = sqlite3.connect(str(path))
    try:
        rows = dict(conn.execute("SELECT name, colour FROM categories"))
    finally:
        conn.close()
    assert rows == {"Work": "teal", "Home": None}


def test_the_column_arrives_on_a_database_that_never_had_it(tmp_path):
    path = tmp_path / "older.db"
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE categories (id INTEGER NOT NULL PRIMARY KEY,"
            " name VARCHAR(100) NOT NULL UNIQUE, description TEXT, created_at DATETIME)"
        )
        conn.execute("INSERT INTO categories (id, name) VALUES (1, 'Work')")
        conn.commit()
    finally:
        conn.close()
    DatabaseManager(path)
    conn = sqlite3.connect(str(path))
    try:
        assert dict(conn.execute("SELECT name, colour FROM categories")) == {"Work": None}
    finally:
        conn.close()


def test_the_migration_alone_adds_the_column(tmp_path):
    """The Alembic step, not the startup auto-migrator, is what is checked: a
    database stood at the revision before this one, with `categories` lacking
    the column, gains it from `upgrade` and keeps its rows."""
    from tessellate.core.database_manager import _ensure_alembic_baseline

    path = tmp_path / "migrate.db"
    DatabaseManager(path)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("ALTER TABLE categories DROP COLUMN colour")
        conn.execute("INSERT INTO categories (id, name, workspace_id, created_at) VALUES (7, 'Work', 'default', '2026-01-01 00:00:00')")
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("INSERT INTO alembic_version VALUES ('d3b7c2a91e45')")
        conn.commit()
    finally:
        conn.close()
    _ensure_alembic_baseline(path)
    conn = sqlite3.connect(str(path))
    try:
        assert conn.execute("SELECT name, colour FROM categories").fetchall() == [("Work", None)]
        assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [(_alembic_head(),)]
    finally:
        conn.close()


# ---- the frontend: one function, twelve swatches that read in both themes ----

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

#: The lightest and darkest grounds a dot is drawn on, from the tokens in
#: 00-tokens-shell.css: the light page's gradient stops and white, the dark
#: page's stops and the dark modal ground.
LIGHT_GROUNDS = ("#ffffff", "#e9edfb", "#f6f2ec", "#e6f1f2")
DARK_GROUNDS = ("#0e1017", "#171a26", "#0f1720", "#181b25", "#2a2f40")


def _palette() -> dict[str, str]:
    source = (FRONTEND / "js" / "notes-list.js").read_text(encoding="utf-8")
    block = re.search(r"const CATEGORY_PALETTE = \{(.*?)\};", source, re.S)
    assert block, "notes-list.js has no CATEGORY_PALETTE"
    return dict(re.findall(r'([a-z]+):\s*"(#[0-9a-f]{6})"', block.group(1)))


def _luminance(hex_colour: str) -> float:
    def channel(i: int) -> float:
        c = int(hex_colour[i : i + 2], 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5)


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_the_palette_keys_are_the_ones_the_picker_draws():
    """The server's list and the swatches in notes-list.js are one list. A key the
    picker offers that the server refuses would be a swatch that does
    nothing, so the two are compared here rather than trusted."""
    palette = _palette()
    assert tuple(palette) == CATEGORY_PALETTE_KEYS
    assert 10 <= len(palette) <= 12


def test_every_swatch_reads_as_a_dot_in_both_themes():
    """WCAG 1.4.11: a graphical mark needs 3:1 against what it sits on. One
    hex per swatch serves light and dark, so each must clear every ground."""
    for key, hex_colour in _palette().items():
        for ground in LIGHT_GROUNDS + DARK_GROUNDS:
            ratio = _contrast(hex_colour, ground)
            assert ratio >= 3.0, f"{key} {hex_colour} on {ground} is {ratio:.2f}:1"


def test_swatches_are_distinct_hues():
    colours = list(_palette().values())
    assert len(set(colours)) == len(colours)


def test_every_surface_asks_the_one_function():
    """A dot, chip, node or legend swatch that computes its own colour would
    ignore the person's choice. Dots go through `paintCategoryDot`, the graph
    through `graphCategoryScale`, the dashboard through `categoryColour`."""
    for name in ("categories-panel.js", "library.js", "note-cards.js", "timeline.js"):
        text = (FRONTEND / "js" / name).read_text(encoding="utf-8")
        assert "categoryDotColour(" not in text, name
        #: The picker's own preview shows a colour not yet chosen, so it
        #: sets the property itself; every other dot is `paintCategoryDot`.
        if name != "categories-panel.js":
            assert '"--category-dot"' not in text, f"{name} sets the dot itself"
    for name in ("graph.js", "graph-canvas.js"):
        text = (FRONTEND / "js" / name).read_text(encoding="utf-8")
        assert not re.search(r"scaleOrdinal\(\s*data\.categories", text), name
    dash = (FRONTEND / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert "hsl(${hueFor(cat.name)}" not in dash.replace("categoryColour(cat.name, `hsl(${hueFor(cat.name)}", "")
    assert "hueFor(group.name)" not in dash


def _alembic_head() -> str:
    """The migrations' head, read rather than written here: a pinned id goes
    stale the moment the next migration lands (two did, the same day)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return ScriptDirectory.from_config(config).get_current_head()
