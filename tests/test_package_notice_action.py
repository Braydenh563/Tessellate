"""INBOX 1300 C35: a notice that says a package is not installed ("Settings,
Packages") carries an Open action that opens Settings, Packages at that
package's row, instead of leaving the person to find it."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")
REVEAL = (ROOT / "frontend" / "js" / "reveal-targets.js").read_text(encoding="utf-8")


def _body(name: str, text: str = STATUS) -> str:
    return text[text.index(f"function {name}(") :].split("\n}\n", 1)[0]


def test_toast_adds_an_open_action_to_a_packages_notice() -> None:
    body = _body("toast")
    assert "Packages/.test(" in body and "packagesNoticeOpen(" in body and "toastAction(" in body
    # After the muted gate, so a muted notebook stays quiet for the plain ones.
    assert body.index("notificationsMuted()") < body.index("Packages/.test(")


def test_every_package_the_server_names_has_a_row_to_scroll_to() -> None:
    table = _body("packagesNoticeTarget", REVEAL)
    extras = (ROOT / "src" / "tessellate" / "core" / "extras.py").read_text(encoding="utf-8")
    ids = set(re.findall(r'id="([a-z]+)",\n\s+label=', extras))
    named = set(re.findall(r'return "([a-z]+)"', table))
    assert named and named <= ids, named - ids


def test_the_open_action_reveals_the_package_row() -> None:
    body = _body("packagesNoticeOpen", REVEAL)
    assert 'revealFeature("extra-row", id)' in body and 'revealFeature("settings:extras")' in body


def test_the_lazy_reveal_stub_names_the_open_function() -> None:
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    #: The reveal list has grown (openShortcuts, flashRevealed, renderShortcutList);
    #: the intent is that the stub names packagesNoticeOpen, wherever it sits.
    reveal = app.split("const LAZY_ENTRY_POINTS", 1)[1].split("reveal:", 1)[1].split("]", 1)[0]
    assert '"revealFeature"' in reveal and '"packagesNoticeOpen"' in reveal
