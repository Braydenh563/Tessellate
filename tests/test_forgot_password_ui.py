"""The lock screen's "Forgot your password?" and the recovery key dialog (INBOX 663).

The routes are held by tests/test_forgot_password.py; this holds the page:
the link is where it was asked for and only where it makes sense, the card
offers both paths, the code is lazy, and the key the dialog shows is taken
out of the page when it closes and put nowhere the Guide reads.
The flows themselves are measured in a browser by
scratchpad/ui-sweeps/forgotpw.js.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
RECOVERY_JS = (ROOT / "frontend" / "js" / "account-recovery.js").read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = re.search(rf"^(?:async )?function {name}\(", source, re.M).start()
    return source[start : source.index("\n}\n", start)]


def test_the_link_is_under_the_field_on_the_lock_card():
    card = INDEX[INDEX.index('id="lock-card"') : INDEX.index('id="lock-forgot-card"')]
    # Under Unlock since the owner's "a small hyperlink below the unlock button".
    assert card.index('id="lock-password"') < card.index('id="lock-submit"') < card.index('id="lock-forgot"')
    assert 'id="lock-forgot" type="button" class="link-button lock-forgot"' in card
    assert "Forgot your password?" in card


def test_the_link_shows_on_the_unlock_only():
    """By the overlay's mode, in CSS (app.js is at its gzip ratchet), and the
    open card takes the lock card's place."""
    css = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    assert '#lock-overlay:not([data-mode="unlock"]) :is(#lock-forgot, #lock-forgot-card),' in css
    assert "#lock-overlay:has(#lock-forgot-card:not(.hidden)) #lock-card {\n  display: none;" in css


def test_the_card_offers_both_paths_and_the_command():
    card = INDEX[INDEX.index('id="lock-forgot-card"') : INDEX.index('id="recovery-key-dialog"')]
    for needle in (
        "I have my recovery key",
        "I don't have it",
        'id="lock-recovery-key"',
        'id="lock-recovery-new"',
        'id="lock-recovery-confirm"',
        "python -m tessellate --reset-password",
        'id="lock-reset-copy"',
        "Type RESET to confirm",
        'id="lock-reset-send"',
        'id="lock-reset-code"',
        'id="lock-reset-submit" type="button" class="danger lock-forgot-action" disabled',
        "sealed backup still opens",
        'data-help-for="lock-forgot-help"',
        'id="lock-forgot-remote"',
    ):
        assert needle in card, needle


def test_the_code_is_lazy():
    source = app_js_text()
    assert 'accountRecovery: ["/css/recovery-lazy.css", "/js/account-recovery.js"]' in source
    assert 'accountRecovery: ["openForgotPassword", "offerRecoveryKey", "showRecoveryKey", "makeRecoveryKey", "recoveryAccountRow"]' in source
    assert "account-recovery.js" not in re.sub(r"<!--.*?-->", "", INDEX, flags=re.S)
    assert "recovery-lazy.css" not in INDEX


def test_setup_offers_a_key_and_the_reset_goes_to_setup():
    assert 'if (mode === "setup") offerRecoveryKey(password);' in _function(app_js_text(), "submitLockForm")
    reset = _function(RECOVERY_JS, "submitPasswordReset")
    assert 'prefs.remove("token")' in reset and "showLockScreen(true)" in reset
    assert '"/auth/reset"' in reset and 'code }' in reset
    assert '"/auth/reset-code"' in _function(RECOVERY_JS, "requestResetCode")
    recover = _function(RECOVERY_JS, "submitRecovery")
    assert '"/auth/recover"' in recover and "ownsAuthErrors: true" in recover
    assert "showRecoveryKey(body.recovery_key" in recover


def test_the_key_leaves_the_page_when_the_dialog_closes():
    wire = _function(RECOVERY_JS, "wireRecoveryDialog")
    assert 'dialog.addEventListener("close"' in wire
    assert '$("recovery-key-value").textContent = ""' in wire


def test_the_key_is_put_nowhere_else():
    """Not stored, not logged, not in an attribute the Guide reads (help-chat.js
    reads `title`, `aria-label` and `.help-body`, inside a tab only)."""
    from tessellate.api.asset_strip import strip_js

    code = strip_js(RECOVERY_JS)
    for forbidden in ("localStorage.setItem(\"recovery", "prefs.set(\"recovery", "sessionStorage", "console.", "setAttribute(\"title\"", ".title =", "aria-label"):
        assert forbidden not in code, forbidden
    dialog = INDEX[INDEX.index('<dialog id="recovery-key-dialog"') : INDEX.index("</dialog>", INDEX.index('<dialog id="recovery-key-dialog"'))]
    value = re.search(r'<p class="recovery-key-value" id="recovery-key-value"[^>]*></p>', dialog)
    assert value, "the key's element starts empty"
    # Outside every tab, so the Guide's on-screen context never reaches it.
    assert INDEX.index('class="tab-page') > INDEX.index('<dialog id="recovery-key-dialog"')
    help_chat = (ROOT / "frontend" / "js" / "help-chat.js").read_text(encoding="utf-8")
    assert "document.getElementById(`tab-${tab}`)" in help_chat


def test_settings_names_the_button_for_what_it_does():
    # The row and its button are drawn by account-recovery.js since the boot
    # scripts' total cap (2026-10-06); the pane awaits it through the stand-in.
    account = _function(app_js_text(), "renderAccount")
    assert "await recoveryAccountRow(info)" in account
    lazy = (ROOT / "frontend" / "js" / "account-recovery.js").read_text(encoding="utf-8")
    assert '"Replace it" : "Make a recovery key"' in _function(lazy, "recoveryAccountRow")
    controls = (ROOT / "frontend" / "js" / "settings-controls.js").read_text(encoding="utf-8")
    assert '$("account-recovery-make").addEventListener("click", () => makeRecoveryKey())' in controls
    assert "showRecoveryKey(result.recovery_key" in controls  # after a re-key


def test_the_key_file_never_goes_through_save_file():
    """INBOX 671: `saveFile` writes into the data dir's exports in the desktop
    window; the key goes to a native Save dialog there, a download elsewhere."""
    from tessellate.api.asset_strip import strip_js

    assert "saveFile(" not in strip_js(RECOVERY_JS)
    saver = _function(RECOVERY_JS, "saveRecoveryKeyFile")
    assert "await desktopShell()" in saver
    assert '"/auth/recovery-key/save"' in saver
    assert "downloadBlob(" in saver


def test_a_wrong_password_on_the_lock_form_says_so_under_the_field():
    # The server answers 401 "That password is wrong."; apiJson turns an
    # unclaimed 401 into Error("Locked") for the expired-session case, which is
    # what the lock form showed under the field until the call owned it
    # (measured in a browser, scratchpad/ui-sweeps/verify1011.js, 2026-10-11).
    form = _function(app_js_text(), "lockRequest")
    call = form[form.index('apiJson(`/auth/${mode'):]
    call = call[: call.index("});")]
    assert "ownsAuthErrors: true" in call and "silent: true" in call
