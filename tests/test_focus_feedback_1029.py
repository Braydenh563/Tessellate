"""Audit 1029 row 56 (N14, N22, N19, G19, X21, X23): a cancel says it
cancelled, a dead link offers to be made, a picked title stays whole, and a
close or a failure never leaves the keyboard on <body>.

Source-shape checks plus one node run of the real `linkCancel`."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap

import pytest

from tests._app_js import frontend_text

NODE = shutil.which("node")


def _body(js: str, head: str) -> str:
    start = js.index(head)
    return js[start : js.index("\n}\n", start) + 2]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_escape_in_link_mode_takes_the_instruction_toast_down_with_it():
    """N14: Esc cleared `linkSource` but "Now click Link on the entry you want
    to connect it to (Esc cancels)" stayed up its full 5.5 seconds."""
    body = _body(frontend_text("note-panels.js"), "function linkCancel(")
    script = textwrap.dedent(
        """
        let linkSource = 7, rendered = 0;
        const gone = [];
        const mk = (text) => ({ textContent: text });
        const document = { querySelectorAll: () => [mk("Linked."), mk("Now click Link on the entry you want to connect it to (Esc cancels).")] };
        const dismissToast = (n) => gone.push(n.textContent);
        const renderEntries = () => { rendered++; };
        %s
        linkCancel();
        console.log(JSON.stringify({ linkSource, rendered, gone }));
        """
    ) % body
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got["linkSource"] is None and got["rendered"] == 1
    assert got["gone"] == ["Now click Link on the entry you want to connect it to (Esc cancels)."]


def test_every_way_out_of_link_mode_goes_through_the_one_cancel():
    panels = frontend_text("note-panels.js")
    begin = _body(panels, "function beginOrCompleteLink(")
    assert begin.count("linkCancel()") >= 2
    wiring = frontend_text("settings-wiring.js")
    assert 'e.key === "Escape" && linkSource !== null' in wiring
    esc = wiring[wiring.index('e.key === "Escape" && linkSource !== null'):][:120]
    assert "linkCancel()" in esc and "linkSource = null" not in esc


def test_a_wiki_link_with_no_target_offers_to_create_it_in_the_card():
    """N22: the card drew the link as plain text with nothing saying it was
    unresolved; clicking it did open the dialog, nothing led there."""
    src = frontend_text("notes-list.js")
    inline = _body(src, "function renderNoteInline(")
    assert "!mapTarget" in inline
    assert 'chip("Create' in inline
    assert "offerToCreateWikiTarget(name)" in inline
    assert "stopPropagation()" in inline[inline.index('chip("Create'):][:260]


def test_the_picker_inserts_the_whole_title_up_to_what_a_link_can_hold():
    """N19: the value was cut at 60, so the note held `[[Atlas project line 183:
    remember to follow up about Atlas pr]]`, a name that no longer matched its
    note. A link holds 120 (the card's and the document's pattern)."""
    editor = frontend_text("editor.js")
    body = _body(editor, "function editorLinkMatches(")
    assert body.count(".slice(0, 120)") == 3
    assert ".slice(0, 60)" in body, "the display labels may stay short"
    for line in body.splitlines():
        if "value:" in line or ".trim()" in line:
            assert ".slice(0, 60)" not in line


def test_closing_the_graph_popup_keeps_the_keyboard_on_the_map():
    """G19: Esc from the popup left focus on <body>."""
    graph = frontend_text("graph.js")
    close = _body(graph, "function closeGraphPopup(")
    assert "returnFocus" in close
    assert '$("graph-box")?.focus(' in close
    wiring = frontend_text("settings-wiring.js")
    esc = wiring[wiring.index('!$("graph-popup").classList.contains("hidden")'):][:120]
    assert "closeGraphPopup(true)" in esc
    assert 'addEventListener("click", closeGraphPopup)' not in frontend_text("wiring.js"), (
        "a click handler would pass the event as the argument"
    )


def test_the_ocr_workspace_opens_with_focus_inside_and_says_why_read_is_off():
    """X21: it opened on <body>, and the off Read button explained itself in a
    tooltip only."""
    lib = frontend_text("library.js")
    opener = _body(lib, "function openOcrWorkspace(")
    assert opener.index('overlay.classList.remove("hidden")') < opener.index('$("ocr-close")?.focus(')
    can = _body(lib, "function ocrSyncCanRead(")
    assert "ocr-empty-line" in can and "? ocrEmptyLine() : why" in can
    assert "ocrReadersLoading.then(ocrSyncCanRead)" in _body(lib, "function ocrPaintEmpty(")


def test_one_failure_helper_marks_links_and_returns_focus():
    """X23: the lock form's wrong password was fixed in sweep 1028b W9; the
    same helper now serves the unlock prompt, the recovery key and the reset."""
    wiring = frontend_text("settings-wiring.js")
    helper = _body(wiring, "function lockFail(")
    for part in ('"aria-invalid", "true"', "aria-describedby", ".focus()", ".select("):
        assert part in helper
    submit = _body(wiring, "async function submitLockForm(")
    assert "errorLine.textContent = error.message" not in submit
    recovery = frontend_text("account-recovery.js")
    assert "lockFail(" in _body(recovery, "function forgotError(")
    # Two failures are about a button (print a code, open the logs): nothing to mark, the press stays focused.
    assert recovery.count("forgotError(error.message)") == 2
    assert "forgotError(error.message, fields.key)" in recovery, "a wrong key is about the key field"


def test_escape_in_the_space_menu_never_leaves_the_keyboard_on_body():
    """X23: after a delete the menu was rebuilt under the focus, so the Esc
    that followed found nothing held and left <body> focused."""
    close = _body(frontend_text("spaces-find.js"), "function closeSpaceMenu(")
    assert "document.body" in close
