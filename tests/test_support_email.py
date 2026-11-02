"""One support address, on both sides, and every door that leads to it.

INBOX 256 (the owner): an error should suggest saving the support bundle
and emailing it, open the mail dialogue, and Atlas should say the same when
asked about an error.
"""

import re
from pathlib import Path

import tessellate
from tessellate.ai import help_chat
from tests._app_js import app_js_text, with_pieces

ROOT = Path(__file__).resolve().parents[1]
APP = app_js_text()
SETTINGS = with_pieces("settings.js")  # the body listeners are in settings-controls.js since INBOX 1501
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_the_frontend_and_backend_agree_on_the_address():
    match = re.search(r'^const SUPPORT_EMAIL = "([^"]+)";', APP, re.M)
    assert match and match.group(1) == tessellate.SUPPORT_EMAIL


def test_atlas_points_an_error_at_the_bundle_and_the_address():
    assert tessellate.SUPPORT_EMAIL in help_chat.SYSTEM_PROMPT
    assert "Logs" in help_chat.SYSTEM_PROMPT and "support bundle" in help_chat.SYSTEM_PROMPT


def test_an_error_toast_carries_the_report_button():
    toast = APP[APP.index("function toast(message, isError = false"):]
    toast = toast[: toast.index("\n}\n")]
    assert "emailSupportReport(message)" in toast
    assert 'help.textContent = "Report this"' in toast


def test_the_logs_menu_has_the_email_row_and_it_is_wired():
    """In the kebab, not the bar: a fourth control beside Support bundle
    wrapped the actions row to two lines at the settings width."""
    row = HTML[HTML.index('id="logs-email-bundle"') - 200 : HTML.index('id="logs-email-bundle"') + 60]
    assert 'class="doc-dock-menu-item"' in row
    assert '$("logs-email-bundle").addEventListener("click"' in SETTINGS


def test_the_mail_door_saves_the_bundle_first_and_opens_mailto():
    body = APP[APP.index("async function emailSupportReport(about)"):]
    body = body[: body.index("\n}\n")]
    assert "downloadSupportBundle()" in body
    assert "mailto:${SUPPORT_EMAIL}" in body
    assert body.index("downloadSupportBundle()") < body.index("mailto:")
