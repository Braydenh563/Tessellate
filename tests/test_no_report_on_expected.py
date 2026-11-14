"""A condition the app expects is said plainly, never as an error with Report
this (INBOX 648, learnability; found by the no-model crawl,
scratchpad/ui-sweeps/e2e648-crawl.js).

An error toast carries "Report this", which mails the owner a support bundle.
Three presses on a plain install raised one for something that is not a fault:
Dictate with the voice add-on not installed (the hint already says to install
it in Settings, Packages), Compress on a chat with nothing to compress, and
Add on an empty reminder.
"""

from __future__ import annotations

from pathlib import Path

from tests import _js_scope
from tests._app_js import with_pieces

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def _function(source: str, head: str) -> str:
    start = source.index(head)
    return source[start : source.index("\n}\n", start) + 3]


def test_dictation_without_the_add_on_says_where_to_get_it_not_report_this():
    # The hint is the server's (ai/voice.py): it names Settings, Packages.
    body = _function((JS / "gesture-kit.js").read_text(encoding="utf-8"), "async function toggleDictation(")
    branch = body[body.index("if (!voiceStatus.available) {") :]
    branch = branch[: branch.index("return;")]
    assert "toast(voiceStatus.hint || \"Voice capture isn't available.\");" in branch


def test_nothing_to_compress_is_not_an_error():
    body = _function(with_pieces("chat.js"), "async function compressChatContext(")
    assert 'toast("There isn\'t enough conversation to compress yet.")' in body


def test_a_reminder_with_a_field_left_empty_is_not_an_error():
    # Found by the same crawl: Add on the empty Reminders form.
    body = _function((JS / "shell-reminders.js").read_text(encoding="utf-8"), "async function addReminder(")
    assert '"A reminder needs text and a due time."' in body
    assert '"Write what to be reminded of."' in body and '"Pick a due time for this reminder."' in body
    assert "toast(!text && !dueValue" in body and ", true)" not in body.split("toast(!text")[1].split("\n")[0]


def test_a_package_action_the_server_refuses_is_a_notice_and_a_failed_request_is_red():
    # OPEN.md: "Another install is already running." and "... is already
    # installed." came back as started: false and were shown as errors.
    text = (JS / "settings-packages.js").read_text(encoding="utf-8")
    assert "toast(result.message, !result." not in text
    #: One place (`packagesPost`) answers all four actions.
    assert text.count('result.failed ? true : result.') == 1
    assert text.count("failed: true, message: e.message") == 1


def test_a_held_quick_note_says_what_happens_to_its_reminder():
    # OPEN.md: a reminder chip on a note saved while the server is away was
    # dropped without a word. L497 moved the intent on: the reminder is now
    # held with the note and set when it goes in, and the toast says that.
    body = _function(_js_scope.unwrapped((JS / "quick-note.js").read_text(encoding="utf-8")), "async function saveQuickNote(")
    queued = body[body.index("if (result.queued) {") :]
    queued = queued[: queued.index("return;")]
    assert "heldReminder ?" in queued and "Its reminder is set then too." in queued


def test_a_silent_write_refused_by_a_restarted_server_shows_the_lock_screen():
    # OPEN.md (scan-1011): changing a setting after the server restarted toasted
    # "Locked" with Open the logs and drew no lock screen, because the PUT is
    # silent. A silent read stays quiet; a silent write now draws it.
    api = (JS / "app.js").read_text(encoding="utf-8")
    assert "if (!silent || fetchOptions.method) showLockScreen(false);" in api


def test_the_model_sheets_missing_models_notice_has_a_button_to_settings():
    # OPEN.md: "Open Settings, Models" was words in a toast, none a link.
    text = with_pieces("ai-tools.js")
    assert 'toastAction("Models aren\'t available yet.", "Open Settings, Models", () => openSettingsModal("models"));' in text
