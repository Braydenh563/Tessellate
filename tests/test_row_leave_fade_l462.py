"""Source text: LEDGER L462, "Fade rows added or removed after first render
(needs keyed rendering)" (motion-1005: "A row added or removed after a list's
first render does not fade; the lists redraw whole").

The added half is ledger 1538 (`rowEnterIds`, `.row-enter`). The removed half:
measured 2026-11-13 at 1440, a note moved to the bin from the Notes list ran a
240ms opacity fade (`--ui-slow`) and then the list redrew from 18 rows to 17.
"""

from tests._app_js import frontend_text


def test_a_binned_row_fades_out_before_the_redraw():
    js = frontend_text("note-cards.js")
    body = js[js.index("async function binNoteWithUndo(entry)") :]
    body = body[: body.index("\n}\n")]
    fade = body.index("leaving.animate([{ opacity: 1 }, { opacity: 0 }]")
    assert 'getPropertyValue("--ui-slow")' in body
    assert fade < body.index("await faded;") < body.index("await refreshEntries([entry.id]);")


def test_an_arriving_row_still_fades_in():
    js = frontend_text("notes-list.js")
    assert "rowEnterIds = new Set(" in js
