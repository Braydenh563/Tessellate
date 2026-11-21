"""L585: a note written in one window shows in another within about a second.

The writing window posts a tick on a BroadcastChannel once the server has
answered; the other asks /entries/changes at once. Lock, theme and the space
switch already ride `storage` events, so the channel carries notes only."""

from _app_js import frontend_text

SYNC = frontend_text("notes-sync.js")
APP = frontend_text("app.js")


def test_api_announces_a_landed_write():
    assert 'document.dispatchEvent(new Event("notebook-written"))' in APP
    line = next(row for row in APP.splitlines() if "notebook-written" in row)
    assert "response.ok" in line and "readOnly" in line


def test_sync_channel_posts_on_write_and_pulls_on_tick():
    assert 'new BroadcastChannel("memorymap-notes")' in SYNC
    assert 'addEventListener("notebook-written"' in SYNC
    assert "noteChannel.onmessage" in SYNC
    assert "followNoteChanges()" in SYNC.split("noteChannel.onmessage")[1]


def test_other_space_writes_and_busy_ticks_are_handled():
    tail = SYNC.split("noteChannel.onmessage")[1]
    assert "activeSpaceId()" in tail
    assert "noteChanges.again" in tail and "noteChanges.again" in SYNC.split("finally")[1]


def test_open_note_still_left_to_the_edit_conflict_path():
    assert 'id !== appState.get("note")' in SYNC


def test_lock_and_look_stay_on_storage_events():
    assert 'event.key !== "token"' in frontend_text("settings-wiring.js")
    assert 'addEventListener("storage", lookFromOtherWindow)' in frontend_text("ai-tools.js")
