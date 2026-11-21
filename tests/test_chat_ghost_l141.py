"""L-chat-141 (CHAT_PLAN decision 69): ghost-text completions in the chat box,
from the person's own tags, titles and recent searches. No model, one switch."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
SRC = (JS / "chat-ghost.js").read_text(encoding="utf-8")


def _rest(text, pool):
    script = (
        "const w={__chatGhostTest:{}};global.window=w;global.document={addEventListener(){},activeElement:null};global.prefs={set(){},get:()=>'on'};"
        + SRC
        + f";console.log(JSON.stringify(w.__chatGhostTest.rest({json.dumps(text)},{json.dumps(pool)})))"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_completes_the_last_word_from_a_tag_or_title():
    pool = ["sourdough", "Weekly review"]
    assert _rest("how is my sour", pool) == "dough"
    assert _rest("show the weekly rev", pool) == "iew"


def test_nothing_for_short_words_code_multiline_or_a_finished_word():
    pool = ["sourdough"]
    assert _rest("so", pool) == ""
    assert _rest("`sour", pool) == ""
    assert _rest("line one\nsour", pool) == ""
    assert _rest("sourdough", pool) == ""
    assert _rest("sour ", pool) == ""


def test_it_is_lazy_one_switch_and_accept_rate_kept():
    #: Preloaded with the quickNote bundle three seconds after boot (the boot scripts are at
    #: their gzip cap); it wires its own focus listener, and catches a box already focused.
    app = (JS / "app.js").read_text(encoding="utf-8")
    #: The bundle's list, not its last entry: composer-lint.js joined it (L-chat-227).
    assert '"/js/router-overlays.js", "/js/chat-ghost.js"' in re.search(r"quickNote: \[[^\]]*\]", app).group(0)
    assert "document.activeElement?.matches?.(CHAT_GHOST_BOXES)" in SRC
    assert 'prefs.get("searchSuggest", "on") !== "off"' in SRC
    assert "chatGhostTally" in SRC and '"Tab"' in SRC and '"Escape"' in SRC


def test_the_quick_note_and_capture_card_complete_inside_their_own_surface():
    """L-chat-156: a modal's top layer hides a span on the body, so the ghost is appended inside the dialog
    or the capture card (measured 2026-11-14: quick note ghost at 625,395 inside #quick-note, card body
    ghost inside #capture-card, both under the box and not covered; Tab took the word in both)."""
    for box in ("#chat-input", "#quick-note-text", "#capture-card-body", ".capture-bar-input"):
        assert box in SRC.split("CHAT_GHOST_BOXES =", 1)[1].split(";", 1)[0]
    assert 'input.closest("dialog, .capture-card") || document.body' in SRC
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="quick-note-text"' in html and html.index("<dialog id=\"quick-note\"") < html.index('id="quick-note-text"')
