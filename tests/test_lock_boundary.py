"""The lock screen is this app's only privacy boundary.

ROADMAP.md ranks auditing it first, and says why: shortcuts once ran behind
the lock screen and were found by a user pressing keys, not by a test.

The audit that produced this file drove the running app locked and checked
each avenue the roadmap named. **The server side already held**, `/entries`,
`/media`, `/documents` and `/reminders` all answer 401 while locked, and the
keyboard gate gave nothing away (the command palette, the agent palette, `/`
to focus search and the `g`-then-letter tab jumps were all refused, and a
`#hash` route did not unlock anything).

**The client side did not.** The overlay was a visual cover, not a purge:
with the notebook locked, `#entry-list` still held 61 notes and 3,431
characters of their text, `#library-grid` 5,089, and the documents list
6,422: one devtools click, one screen reader or one browser extension away
from being read. `purgeLockedContent()` closes that, and unlocking restores
everything because `startApp()` re-renders it.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import app_js_text

APP_JS = Path(__file__).resolve().parent.parent / "frontend" / "js" / "app.js"

#: Containers that hold the user's own words rather than the app's chrome.
USER_CONTENT_IDS = [
    "entry-list",
    "chat-messages",
    "library-grid",
    "library-docs-list",
    "timeline-feed",
    "timeline-table-body",
    "reminder-groups",
    "timeline-calendar",
    "palette-list",
    "palette-preview",
]


def test_locking_purges_the_rendered_content():
    """`lockNow` must clear the DOM, not merely cover it."""
    source = app_js_text()
    start = source.index("async function lockNow(")
    body = source[start : source.index("\n}", start)]
    assert "purgeLockedContent()" in body, (
        "lockNow must purge rendered content, the overlay alone is a cover, not a boundary"
    )


def test_every_user_content_container_is_purged():
    source = app_js_text()
    start = source.index("const LOCK_PURGE_IDS")
    listed = source[start : source.index("];", start)]
    missing = [name for name in USER_CONTENT_IDS if f'"{name}"' not in listed]
    assert not missing, f"these still hold the user's words while locked: {missing}"


def test_a_purged_container_holds_no_static_ui():
    """INBOX 492: `replaceChildren()` on a container deletes everything in
    it, not only the user's words. `#timeline-scroll` and `#reminder-list-card`
    were listed, and both hold static markup (the feed, the table and its head,
    the reminders' dock and filters) that `startApp()` never rebuilds: after one
    lock the Notes select button threw `Cannot read properties of null` from
    `paintTimeline`, and the Reminders tab lost its controls. A purged
    container may hold only what the app renders into it, so no element in
    `index.html` with an id may sit inside one."""
    from html.parser import HTMLParser

    source = app_js_text()
    start = source.index("const LOCK_PURGE_IDS")
    listed = re.findall(r'"([a-z0-9-]+)"', source[start : source.index("];", start)])
    assert listed

    class Walk(HTMLParser):
        VOID = {"input", "br", "img", "hr", "meta", "link", "source", "col", "wbr"}

        def __init__(self):
            super().__init__()
            self.stack: list[tuple[str, str | None]] = []
            self.bad: list[tuple[str, str]] = []

        def handle_starttag(self, tag, attrs):
            ident = dict(attrs).get("id")
            if ident:
                for _tag, outer in self.stack:
                    if outer in listed:
                        self.bad.append((outer, ident))
            if tag not in self.VOID:
                self.stack.append((tag, ident))

        def handle_endtag(self, tag):
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break

    walk = Walk()
    walk.feed((APP_JS.parent.parent / "index.html").read_text(encoding="utf-8"))
    assert not walk.bad, f"purging these deletes static UI: {sorted(set(walk.bad))}"


def test_text_fields_are_cleared_too():
    """A textarea keeps its text in `.value`, which `replaceChildren()` never
    touches: the document editor would otherwise stay fully readable behind
    the lock screen."""
    source = app_js_text()
    start = source.index("function purgeLockedContent(")
    body = source[start : source.index("\n}\n", start)]
    assert '"value" in field' in body or ".value = \"\"" in body
    for field in ("doc-content", "doc-title"):
        assert field in body, f"{field} keeps its text in .value and must be cleared"


def _lock_storage_handler(source: str) -> str:
    """The `storage` listener that watches the token. There are two: the look
    mirror (ai-tools.js, `lookFromOtherWindow`) loads first, so the first one
    found is not the lock's; the lock's is the one that reads the "token" key."""
    start = 0
    while True:
        start = source.index('addEventListener("storage"', start)
        handler = source[start : source.index("\n});", start)]
        if '"token"' in handler:
            return handler
        start += 1


def test_locking_reaches_every_open_tab():
    """Locking in one tab must lock the others.

    The audit found this by opening a second tab, which ROADMAP.md had named
    as an unchecked avenue. Locking in tab A cleared tab A and dropped the
    shared token, so the API correctly refused tab B, but tab B kept showing
    all 61 notes with no lock screen, indefinitely. Lock the notebook, walk
    away from a shared machine, and everything is still on screen in the
    window behind.

    `storage` is the right signal because it fires in *other* tabs of the same
    origin only: the tab that locked has already handled itself, and nothing
    has to poll.
    """
    source = app_js_text()
    assert 'addEventListener("storage"' in source, (
        "no cross-tab lock listener, a second open tab keeps showing everything"
    )
    handler = _lock_storage_handler(source)
    assert "purgeLockedContent()" in handler
    assert "showLockScreen(false)" in handler
    # A sign-in elsewhere must not be mistaken for a lock.
    assert 'prefs.get("token", null)' in handler


def test_the_password_free_boot_is_taken_only_when_the_server_offers_it():
    """Optional sign-in (INBOX 426 aa): the boot path asks for a session
    without a password only when `/auth/status` says this caller may have
    one, and falls back to the lock screen when it is refused."""
    source = app_js_text()
    start = source.index("async function initAuth(")
    body = source[start : source.index("\n}\n", start)]
    assert "status.auto_session" in body
    assert "/auth/auto-session" in source
    assert "showLockScreen(false)" in body


def test_private_notes_ask_through_the_same_lock_screen():
    """With sign-in off the vault stays locked, and it is opened by the
    existing unlock UI in a prompt mode, not by a second password form."""
    source = app_js_text()
    assert "Unlock private notes" in source
    assert "/auth/unlock-vault" in source
    start = source.index("async function submitLockForm(")
    body = source[start : source.index("\n}\n", start)]
    assert '"prompt"' in body, "the lock form must know its prompt mode"


def test_a_prompt_is_not_mistaken_for_the_lock_screen():
    """The prompt borrows the overlay. A lock in another tab while it is up
    must still purge this one, so "the overlay is showing" cannot be read as
    "already locked" while it is in prompt mode."""
    source = app_js_text()
    handler = _lock_storage_handler(source)
    assert 'dataset.mode !== "prompt"' in handler


def test_no_second_password_form():
    """DESIGN.md's recipe for asking the password for one action is the lock
    card in prompt mode. A password field built anywhere else is a second
    form to keep in step with the throttle, the error line and the purge."""
    html = (APP_JS.parent.parent / "index.html").read_text(encoding="utf-8")
    #: Two more, named: the sealed full backup's own passphrase, typed when it
    #: is made and when it is restored (BACKLOG 115 row 10). It is a secret for
    #: that one file, not the account password, so the lock card (which checks
    #: the account password) is the wrong recipe for it.
    sealed = ('id="export-backup-password" type="password"', 'id="restore-bundle-password" type="password"')
    assert all(field in html for field in sealed)
    #: And two more, named (INBOX 663): the new password and its confirmation
    #: on the "Forgot your password?" card, which sets a password without the
    #: old one, so the prompt (which checks the old one) cannot be its recipe;
    #: they are Change password's new and confirm fields, on the lock screen.
    recovery = ('id="lock-recovery-new" type="password"', 'id="lock-recovery-confirm" type="password"')
    assert all(field in html for field in recovery)
    #: And two more, named: the quick-unlock PIN and its confirmation (Settings,
    #: Account, 018448017). A PIN is a second secret for this computer only, set
    #: while signed in, so the lock card (which checks the account password)
    #: cannot be its recipe either.
    pin = ('id="account-pin-new" type="password"', 'id="account-pin-confirm" type="password"')
    assert all(field in html for field in pin)
    #: And one more, named: the other computer's password in Settings, Sync
    #: over the home network. It is a secret for a different machine, typed
    #: once to pair and never stored, so the lock card (which checks this
    #: account's password) cannot be its recipe.
    assert 'id="sync-password" type="password"' in html
    #: And one more, named: the sync passphrase on the folder sheet, kept in a
    #: template here (sync-folder.js clones it) because no script may build a
    #: password field. It seals the shared folder's files, not this account.
    assert '<template id="sync-folder-passphrase">' in html
    assert html.count('type="password"') == 12, (
        "lock card, Change password's three, the sealed backup's two, the forgot card's two, the PIN's two, "
        "the other computer's password when pairing, the folder sync passphrase"
    )
    for path in sorted(APP_JS.parent.glob("*.js")):
        source = path.read_text(encoding="utf-8")
        assert 'type = "password"' not in source, path.name
        assert "type=\"password\"" not in source, path.name
