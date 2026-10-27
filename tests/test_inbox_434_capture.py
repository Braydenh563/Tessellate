"""INBOX 434: making a note is the fastest, safest thing in the app.

Measured with `scratchpad/ui-sweeps/captureaudit.js`; each test names the
number it holds."""

from __future__ import annotations

import re

from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def test_a_paste_or_drop_on_the_mounted_editor_reaches_its_note_box():
    """An image pasted into Capture and a file dropped on it both vanished
    (0 attachment cards) because the listeners only answered a bare
    textarea; the live editor is mounted over it. After: 1 and 2 cards."""
    code = app_js_text()
    assert "function fileDropBox(el)" in code
    assert '?.closest?.(".note-surface")?.noteSurfaceHost' in code
    assert "await handleFileUpload(box, files);\n}, true);" in code


def test_a_save_with_the_server_gone_is_held_and_sent_later():
    """Before: "Failed to fetch", the text kept, nothing ever sent it. After:
    held in the outbox, the box cleared, sent 174 ms after the server came
    back (captureaudit.js `offline`)."""
    code = app_js_text()
    assert 'quickNote: ["/js/quick-note.js",' in code
    assert '"noteOutboxAdd", "flushNoteOutbox"' in code
    # Loaded on the boot timer with the Clear controls (INBOX 466).
    timer = re.search(r"setTimeout\(\(\) => \[([^\]]*)\]\.forEach\((?:\(name\) => ensureModule\(name\)|ensureModule)\), 3000\);", code)
    assert timer and '"quickNote"' in timer.group(1) and '"fieldClear"' in timer.group(1)
    assert "if (await heldOffline(error, body, contentBox, titleBox)) return;" in code
    assert "flushNoteOutbox(); // notes kept on this device" in code
    quick = (JS / "quick-note.js").read_text(encoding="utf-8")
    assert "payload.client_key = payload.client_key || newNoteClientKey();" in quick
    assert 'window.addEventListener("online", () => flushNoteOutbox());' in quick


def test_quick_note_is_a_shortcut_and_a_palette_row():
    """Alt+N from any tab: caret in 28 to 70 ms, saved without leaving the
    tab, in the list 100 to 310 ms after Ctrl+Enter; Escape keeps the words."""
    code = app_js_text()
    assert 'quickNote: { keys: "Alt+N"' in code
    assert "quickNote: () => openQuickNote()," in code
    assert 'chord: "quickNote", act: () => openQuickNote()' in code
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<dialog id="quick-note" class="card space-dialog quick-note-dialog"' in html
    assert 'id="note-outbox-notice"' in html
    # A modal dialog sits above the lock screen: a lock closes it (measured,
    # open=false after lockNow, the words back on the next open).
    quick = (JS / "quick-note.js").read_text(encoding="utf-8")
    assert 'else $("quick-note").close();' in quick


def test_a_pasted_link_offers_the_page_only_with_the_web_allowed():
    """The web clipper (POST /links/clip) had no door in the interface. A bare
    link pasted into Capture or Quick note now offers it, and only while the
    web is allowed: measured, no toast with it off, one with it on."""
    quick = (JS / "quick-note.js").read_text(encoding="utf-8")
    assert 'apiJson("/links/clip"' in quick
    assert "if (!(prefsCache && prefsCache.web_search_enabled)) return;" in quick
    assert 'event.target.closest?.("#quick-note, #capture")' in quick


def test_the_palettes_enter_does_not_reach_the_box_it_opens():
    """New note from the palette began every note with a blank line ("\\n"
    in the box before the first keystroke); after: ""."""
    code = app_js_text()
    assert 'event.key === "Enter" && matches[paletteIndex]) {' in code
    at = code.index('event.key === "Enter" && matches[paletteIndex]) {')
    assert "event.preventDefault();" in code[at : at + 300]


def test_inline_tags_are_read_from_the_text():
    from tessellate.entry.tagnames import inline_tags

    text = (
        "Recipe #cooking and #soup\n# Heading\n#42 https://a.com/p#sec &#39; ##x "
        "#ff0000 #cafe [#link](u) `#code`\n```\n#include\n```\n#project/garden- #Cooking"
    )
    assert inline_tags(text) == ["cooking", "soup", "cafe", "link", "project/garden"]
    assert inline_tags("") == []


def test_a_note_written_with_hashtags_is_tagged_when_asked(client):
    """Before: `#cooking #soup` in Capture saved with tags []."""
    asked = client.post(
        "/entries", json={"content": "Soup tonight #cooking #soup", "tags": ["Cooking", "x"], "inline_tags": True}
    ).json()
    assert asked["tags"] == ["Cooking", "x", "soup"]
    # Off unless asked: an import's or the AI's text is not a person's labels.
    plain = client.post("/entries", json={"content": "Soup #cooking"}).json()
    assert plain["tags"] == []


def test_the_same_note_sent_twice_by_the_outbox_is_saved_once(client):
    body = {"content": "Queued while the server was down", "client_key": "k-434-a", "defer_filing": True}
    first = client.post("/entries", json=body).json()
    again = client.post("/entries", json=body).json()
    assert again["id"] == first["id"]
    other = client.post("/entries", json={**body, "client_key": "k-434-b"}).json()
    assert other["id"] != first["id"]
