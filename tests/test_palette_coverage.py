"""Every feature has a Ctrl+K row, generated rather than typed (UI_MODERNISATION
"the command palette and Find anything", row 1, Brief 90; CHAT_PLAN decision 53).

Measured before (scratchpad/ui-sweeps/deepen72b.js, 2026-10-10): of 18 words a
person types into the palette, 11 found no command, among them "read text from
image", "statistics", "calculator", "timer", "word count" and "find anything",
while "Tools and features" (`featureCatalog`, dashboard.js) listed most of those
features by name. The palette was a second hand-written list that had drifted
from the first.

So typed text reaches three generated sets beside the hand-written rows
(app-palette.js): every catalogue feature no hand-written row already lands on
(`paletteFeatureRows`), every act in the act registry (`paletteActRows`, over
`GET /read/acts`, `act_registry.palette_rows`), and the Settings index
(`paletteSettingRows`, over `findSettings`). This file holds that:

* the generators read their sources, so a feature added there is a row here;
* the palette's matcher, simulated over the parsed tables, finds a row for each
  of deepen72b's 18 words, and for every feature in the catalogue (0 missing);
* every alias names a place that exists (a reveal target, a tab, a pane).

The Settings index is read from the live DOM, so its half is the sweep's.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.ai import act_registry
from tests.test_catalogue_reveal import _feature_rows, _list_literal, _palette_rows, _targets
from tests import _js_scope

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
PALETTE = _js_scope.unwrapped((JS / "app-palette.js").read_text(encoding="utf-8"))

#: deepen72b.js's palette words, the 11 that found nothing among them.
QUERIES = (
    "ocr", "read text from image", "reminder", "calendar", "timeline", "undo", "agent", "stop the model",
    "statistics", "guide", "backup", "calculator", "timer", "convert", "word count", "find anything",
    "activity", "health",
)


def _function(name: str) -> str:
    start = PALETTE.index(f"function {name}(")
    end = PALETTE.find("\nfunction ", start + 1)
    return PALETTE[start : end if end > 0 else len(PALETTE)]


def _aliases() -> dict[str, str]:
    body = re.search(r"const PALETTE_ALIASES = \{(.*?)\n\};", PALETTE, flags=re.S)
    assert body, "PALETTE_ALIASES is not declared in app-palette.js"
    return dict(re.findall(r'"([\w:-]+)":\s*"([^"]*)"', body.group(1)))


def _filler() -> set[str]:
    body = re.search(r"const PALETTE_FILLER = new Set\(\[(.*?)\]\)", PALETTE, flags=re.S)
    assert body, "PALETTE_FILLER is not declared in app-palette.js"
    return set(re.findall(r'"([^"]+)"', body.group(1)))


def _field(obj: str, key: str) -> str:
    match = re.search(rf'\b{key}:\s*"((?:[^"\\]|\\.)*)"', obj)
    return match.group(1) if match else ""


def _target(obj: str) -> str:
    reveal = _field(obj, "reveal")
    if reveal:
        return reveal
    tab = _field(obj, "tab")
    return f"tab:{tab}" if tab else ""


def _rows() -> list[dict]:
    """The rows typed text can reach, as the palette builds them."""
    hand = [{"label": name, "keywords": _field(obj, "keywords"), "about": _field(obj, "about"), "target": _target(obj)}
            for name, obj in _palette_rows()]
    covered = {row["target"] for row in hand if row["target"]}
    said = [row["label"].lower() for row in hand]
    items = [(name, obj) for name, obj in _feature_rows()]
    landings: dict[str, int] = {}
    for _name, obj in items:
        landings[_target(obj)] = landings.get(_target(obj), 0) + 1
    features = []
    for name, obj in items:
        target = _target(obj)
        named = any(name.lower() in label for label in said)
        if named or (target and target in covered and landings[target] == 1):
            continue
        features.append({"label": f"ph:compass {name}", "keywords": "", "about": _field(obj, "desc"), "target": target})
    acts = [{"label": f"ph:lightning {row['label']}", "keywords": row["example"], "about": row["help"], "target": ""}
            for row in act_registry.palette_rows()]
    return hand + features + acts


def _score(row: dict, phrase: str, words: list[str], aliases: dict[str, str]) -> int:
    """`paletteScore`, read the same way: name first, then its other words,
    then its line of what it does."""
    label = re.sub(r"(^|\s)ph:[\w-]+\s*", " ", row["label"].lower()).strip()
    if label.startswith(phrase) or f" {phrase}" in label:
        return 4
    if phrase in label:
        return 3
    named = f"{label} {row['keywords'].lower()} {aliases.get(row['target'], '')}"
    if phrase in named or all(w in named for w in words):
        return 2
    return 1 if all(w in f"{named} {row['about'].lower()}" for w in words) else 0


def _found(query: str, rows: list[dict]) -> list[str]:
    aliases, filler = _aliases(), _filler()
    phrase = query.lower().strip()
    words = phrase.split()
    words = [w for w in words if w not in filler] or words
    return [row["label"] for row in rows if _score(row, phrase, words, aliases)]


def test_the_generators_read_their_sources():
    assert "featureCatalog()" in _function("paletteFeatureRows")
    assert '"/read/acts"' in _function("paletteActRows")
    assert "findSettings(" in _function("paletteSettingRows")
    pool = _function("palettePool")
    for generator in ("paletteFeatureRows(", "paletteActRows(", "paletteSettingRows("):
        assert generator in pool, f"palettePool never calls {generator[:-1]}"
    assert "palettePool(" in _function("paletteMatches")


def test_every_word_the_sweep_typed_finds_a_command():
    rows = _rows()
    empty = [q for q in QUERIES if not _found(q, rows)]
    assert not empty, f"Ctrl+K finds no command for {empty}"


def test_every_feature_in_the_catalogue_has_a_row():
    rows = _rows()
    targets = {row["target"] for row in rows if row["target"]}
    labels = [row["label"].lower() for row in rows]
    missing = [name for name, obj in _feature_rows()
               if not (_target(obj) in targets or any(name.lower() in label for label in labels))]
    assert not missing, f"features with no palette row: {missing}"


def test_every_act_in_the_registry_has_a_row():
    assert len(act_registry.palette_rows()) == len(act_registry.ACTS)
    assert "paletteStartAct(" in _function("paletteActRows"), "an act row has to start the act in Chat"


def test_every_alias_names_a_place_that_exists():
    tabs = _list_literal("navigation.js", "TABS")
    sections = _list_literal("settings.js", "SETTINGS_SECTIONS")
    targets = set(_targets())
    wrong = []
    for key in _aliases():
        if key.startswith("tab:"):
            ok = key[4:] in tabs
        elif key.startswith("settings:"):
            ok = key[9:] in sections
        else:
            ok = key in targets
        if not ok:
            wrong.append(key)
    assert not wrong, f"aliases for places that do not exist: {wrong}"


def test_the_aliases_people_type_find_their_place():
    """Row 5's aliases: the to-do word finds the reminders, "whiteboard" a board."""
    rows = _rows()
    for query, wanted in (("todo", "Reminders"), ("whiteboard", "board"), ("hotkeys", "Keyboard shortcuts")):
        assert any(wanted in label for label in _found(query, rows)), f"Ctrl+K {query!r} does not find {wanted}"


def test_a_row_run_for_these_words_comes_first_next_time():
    """Row 5's learned ranking: what was run for a query is recorded when it
    runs, sorted ahead of the name's match, kept in the prefs module (never
    raw localStorage) and said in the row's title."""
    assert "palettePick(typed, name)" in _function("paletteRun")
    ranked = _function("paletteRanked")
    assert "b.picked - a.picked ||" in ranked.split("scored.sort(")[1].split(";")[0][:40]
    assert 'prefs.json("palette-picks"' in _function("palettePicks")
    assert 'prefs.setJSON("palette-picks"' in _function("palettePick")
    assert "localStorage" not in PALETTE
    assert "row.title = match.why" in _function("paletteDrawRows")
