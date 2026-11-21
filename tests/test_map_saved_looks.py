"""Source text: the behaviour is front-end script that pytest cannot run without a browser, so these pin the code's text.

Saving a mind map's look for reuse (L-mindmap-1): the theme dialog's
Saved looks row. The look is the whole theme under a name in prefs
(a preference of this device, like the rest of how a board is looked at);
applying one is a single theme patch (one Undo step) that clears every key the
saved look never set, so the map ends up exactly as saved. Driven in
Chromium on 2026-11-12: save, change, apply, forget."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_JS = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")


def _dialog() -> str:
    start = MAP_JS.index("function wbMapThemeDialog() {")
    return MAP_JS[start : MAP_JS.index("\n}\n", start)]


def test_the_dialog_has_a_saved_looks_row_with_save_and_forget() -> None:
    body = _dialog()
    for words in ("Saved looks", "Save this look", "Forget", "wb-map-saved-looks"):
        assert words in body, words


def test_applying_clears_keys_the_saved_look_never_set_in_one_patch() -> None:
    body = _dialog()
    at = body.index("looksSelect.addEventListener")
    apply = body[at : at + 700]
    assert "Object.keys(wbMapTheme()).map((key) => [key, null])" in apply
    assert "await wbMapSetTheme({ ...patch, ...look })" in apply


def test_the_list_is_capped_and_a_bad_blob_reads_as_empty() -> None:
    body = _dialog()
    assert ">= 20" in body and ".slice(0, 40)" in body
    assert "prefs.json(looksKey, {})" in body


def test_no_new_global_name_was_added() -> None:
    assert "const wbMapSavedLooks" not in MAP_JS and "function wbMapSaveLook" not in MAP_JS
