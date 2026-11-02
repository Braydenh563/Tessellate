"""A "?" inside a modal dialog opens its popover inside that dialog (INBOX 667).

The owner: "the quick note popup tooltip button doesnt work or show a popup".
`wireHelpPopover` moved every panel to `<body>`, and a `showModal()` dialog is
in the browser's top layer, above the whole document and inert outside, so a
"?" in the Quick note opened its help underneath the dialog. Measured by
`scratchpad/ui-sweeps/quicknotehelp.js`: topmost-at-centre false before, true
after; the first Escape now closes only the help.
"""

import re
from pathlib import Path

from tests._app_js import app_js_text, frontend_text

ROOT = Path(__file__).resolve().parent.parent


def _open_body() -> str:
    text = app_js_text()
    start = text.index("function wireHelpPopover(")
    return text[start : text.index("placeHelpPopover(panel, trigger);", start)]


def test_the_popover_escapes_into_the_open_dialog_not_body():
    body = _open_body()
    assert 'trigger.closest("dialog[open]") || document.body' in body
    assert not re.search(r"^\s*document\.body\.appendChild\(panel\)", body, re.M)


def test_the_first_escape_in_a_dialog_closes_only_the_help():
    text = app_js_text()
    handler = text[text.index("event.helpPopoverSpent = true") :][:600]
    assert 'closest("dialog[open]")' in handler and "event.preventDefault()" in handler


def test_the_dialogs_with_a_help_button_exist():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    dialogs = [
        m.group(1)
        for m in re.finditer(r'<dialog\b[^>]*id="([^"]+)"(.*?)</dialog>', html, re.S)
        if "data-help-for" in m.group(2)
    ]
    assert "quick-note" in dialogs


# A help popover fades out before it goes home (OPEN ledger 1419).

def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_1419_a_help_popover_fades_out_before_it_goes_home():
    body = _fn(frontend_text("menus.js"), "wireHelpPopover")
    assert "afterMenuExit(panel, () => {" in body
    assert "clearTimeout(panel._exitTimer);" in body
    assert re.search(r"\.help-popover\.hidden,\s*\.action-menu\.hidden \{", (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8"))


# Escape closes the popover and nothing else (dashcls-1031).

def test_escape_in_a_popover_is_spent_there_and_focus_goes_back_to_its_button():
    text = frontend_text("menus.js")
    handler = text[text.index("event.helpPopoverSpent = true") - 400 :][:1600]
    # Later document listeners (Settings' overlay close among them) never see
    # this press: they used to close the whole dialog with the popover.
    assert "event.stopImmediatePropagation();" in handler
    # The press ends with focus back on the "?" that opened the popover.
    assert "opener.focus(" in handler
    assert handler.index("closeHelpPopovers()") < handler.index("opener.focus(")
