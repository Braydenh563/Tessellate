"""Private spaces in the window (INBOX 1727): the switch, the lock, the questions.

The server's half is `tests/test_private_spaces.py`; this holds the wiring a
person meets: the Private switch in New space and Edit space (the
`.setting-check` recipe), the lock glyph in the switcher, the lazy file that
unlocks and asks, the note menu's locked Private row, the move-out question
and the help that says all of it.
"""

from __future__ import annotations

from pathlib import Path

from tessellate.ai import help_topics_more
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
LAZY = (JS / "private-spaces.js").read_text(encoding="utf-8")


def _dialog(dialog_id: str) -> str:
    start = INDEX.index(f'<dialog id="{dialog_id}"')
    return INDEX[start : INDEX.index("</dialog>", start)]


def test_new_space_and_edit_space_carry_a_private_switch_with_help():
    """Built on first open (the boot document's element cap), from the recipes."""
    assert 'row.className = "setting-check space-private-row";' in LAZY
    assert 'input.setAttribute("role", "switch");' in LAZY
    assert 'help.setAttribute("data-help-for", `${prefix}-help`);' in LAZY and "initHelpToggles(head);" in LAZY
    finder = (JS / "spaces-find.js").read_text(encoding="utf-8")
    assert 'privateSpaces("mount", "space-create");' in finder and 'mount("space-edit");' in LAZY
    for dialog_id in ("space-create-dialog", "space-edit-dialog"):
        assert '<p id="' + dialog_id.replace("-dialog", "-error") + '"' in _dialog(dialog_id)


def test_the_create_request_sends_the_switch_and_the_switcher_draws_a_lock():
    finder = (JS / "spaces-find.js").read_text(encoding="utf-8")
    assert 'is_private: $("space-create-private")?.checked === true' in finder
    assert "space-option-lock" in finder and "isPrivate: Boolean(space.is_private)" in finder
    assert 'privateSpaces("enter", activeSpaceId())' in finder


def test_the_lazy_file_is_registered_and_exports_one_name():
    lazy = (JS / "lazy-entries.js").read_text(encoding="utf-8")
    #: hello-unlock.js rides in the same bundle (INBOX 1727's Windows Hello), after it.
    assert 'privateSpaces: ["/js/private-spaces.js", "/js/hello-unlock.js"]' in lazy
    assert 'privateSpaces: ["privateSpaces"]' in lazy
    assert "Object.assign(window, { privateSpaces });" in LAZY


def test_it_unlocks_with_the_password_or_pin_and_locks_on_close():
    assert '"/private-spaces/unlock"' in LAZY and "Password or PIN" in LAZY
    assert 'window.addEventListener("pagehide"' in LAZY and '"/private-spaces/lock"' in LAZY
    assert '"/private-spaces/touch"' in LAZY


def test_leaving_asks_keep_private_first():
    assert 'cancelLabel: "Keep it private"' in LAZY and 'confirmLabel: "Make it ordinary"' in LAZY
    batch = (JS / "batch-space.js").read_text(encoding="utf-8")
    assert 'privateSpaces("askKeep"' in batch and "keep_private: keepPrivate" in batch


def test_a_notes_private_row_is_locked_on_inside():
    menu = (JS / "entry-menu.js").read_text(encoding="utf-8")
    assert '"Move it out of this space to share it"' in menu and "disabled: true" in menu


def test_the_idle_minutes_are_in_settings():
    assert 'id="account-private-idle"' in INDEX
    assert 'setPreference("private_space_idle_minutes"' in unwrapped((JS / "settings-controls.js").read_text(encoding="utf-8"))


def test_the_guide_explains_private_spaces():
    topic = next(t for t in help_topics_more.MORE_TOPICS if t["id"] == "private-spaces")
    for words in ("Keep it private", "Make it ordinary", "Move it out of this space to share it", "A private reminder", "PIN"):
        assert words in topic["body"]


def test_a_private_reminder_is_announced_by_its_notice():
    """Round 2: the browser's notification, toast and centre say "A private
    reminder" (the server's `notice`), never the words."""
    status = (JS / "status.js").read_text(encoding="utf-8")
    assert ".map((r) => ({ ...r, ...r.notice }))" in status


def test_the_graph_draws_a_sealed_link_end_as_a_muted_dashed_node():
    canvas = (JS / "graph-canvas.js").read_text(encoding="utf-8")
    assert "private: [1, 2]" in canvas
    assert 'node.type === "private") return `${node.preview}\\nIn a locked private space`' in canvas
    assert 'node.type === "unresolved" || node.type === "private") return gcTokens.muted' in canvas


def test_a_locked_backlink_carries_no_sentence():
    """The server's row for a sealed source is not a "note" row, the only
    kind whose sentence the Connections sheet borrows."""
    connections = (JS / "connections.js").read_text(encoding="utf-8")
    assert 'if (row.kind === "note" && !context.has(row.id))' in connections


def test_the_idle_lock_is_noticed_from_an_open_state():
    """The touch's answer is read against the state the unlock just set."""
    assert "state.status = { ...(state.status || {}), open: true };" in LAZY
    assert 'toastAction("Private spaces locked.", "Unlock", unlock)' in LAZY
    assert "setInterval" not in LAZY


def test_deleting_a_locked_space_asks_for_the_password_and_sends_again():
    """L697: the 423 used to land as a bare message with no way to unlock."""
    text = (JS / "batch-space.js").read_text(encoding="utf-8")
    start = text.index("async function spaceDeleteSubmit")
    body = text[start : text.index("\n}\n", start)]
    assert "answered.status === 423" in body
    assert 'privateSpaces("unlock")' in body
    assert '(await privateSpaces("unlock"))) answered = await send();' in body
