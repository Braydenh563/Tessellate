"""Windows Hello in the window (INBOX 1727): where its UI comes from and what
it must never do. The ceremony itself was driven in Chromium with the CDP
virtual authenticator (hasPrf); these hold the wiring in place."""

from __future__ import annotations

from pathlib import Path

from tessellate.ai import help_chat

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
HELLO = (JS / "hello-unlock.js").read_text(encoding="utf-8")


def test_it_is_lazy_in_the_private_spaces_bundle_not_a_boot_script():
    assert '"/js/hello-unlock.js"' in (JS / "lazy-entries.js").read_text(encoding="utf-8")
    assert "hello-unlock.js" not in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "Object.assign(privateSpaces.actions, { hello })" in HELLO
    assert "Object.assign(window" not in HELLO


def test_the_lock_screen_asks_for_it_only_when_this_computer_has_it():
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert 'if (status?.hello_here || $("lock-hello")) privateSpaces("hello", "lock", status?.hello_here);' in app


def test_the_private_space_card_offers_it_while_it_asks():
    spaces = (JS / "private-spaces.js").read_text(encoding="utf-8")
    assert 'if (known?.hello) ACTIONS.hello?.("space", asked);' in spaces
    #: An ordinary password prompt never shows it: only the lock or a space card,
    #: by the card's mode in CSS, with no watcher (the wake-source lint).
    css = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    assert '.lock-overlay[data-mode="unlock"] #lock-hello.for-lock' in css
    assert '.lock-overlay[data-mode="prompt"] #lock-hello.for-space' in css
    assert "MutationObserver" not in HELLO


def test_prf_is_feature_detected_and_an_ip_address_page_never_offers_it():
    assert "isUserVerifyingPlatformAuthenticatorAvailable" in HELLO
    assert '"extension:prf"' in HELLO
    assert "location.hostname" in HELLO
    #: The PRF output wraps the key: no output, no unlock (never a yes/no gate).
    assert "if (!prfOf(cred)) throw new Error(NO_PRF);" in HELLO


def test_settings_has_the_switch_with_its_help_beside_the_pin():
    for needle in (
        'title.textContent = "Unlock with Windows Hello";',
        'help.setAttribute("data-help-for", "hello-help");',
        'input.setAttribute("role", "switch");',
        '$("account-pin-group").after(group);',
        "initHelpToggles(head);",
    ):
        assert needle in HELLO, needle
    controls = (JS / "settings-controls.js").read_text(encoding="utf-8")
    assert 'privateSpaces("hello", "settings", info.hello)' in controls


def test_the_guide_says_where_it_is_and_what_turns_it_off():
    lock = next(t for t in help_chat.HELP_TOPICS if "windows hello" in t["keywords"])
    for words in ("Unlock with Windows Hello", "on this computer only", "password change", "restore"):
        assert words in lock["body"], words
    spaces = next(t for t in help_chat.HELP_TOPICS if t["id"] == "private-spaces")
    assert "Windows Hello" in spaces["body"]
