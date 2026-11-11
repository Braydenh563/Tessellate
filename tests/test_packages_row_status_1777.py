"""INBOX 1777, the owner's screenshot of Settings, Packages.

Two things were wrong on the Live captions row: an empty tick on a row that
cannot be installed, and the Speaker labels install's "installed" line and
"What pip is doing" sitting under the Live captions row (the last in the
list), which they were not about. The structure is read from the source; the
measured numbers are in the CHANGELOG line.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend/js/settings-packages.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = JS.index(f"function {name}(")
    return JS[start : JS.index("\n  }\n", start)]


def test_a_row_that_cannot_be_installed_has_no_tick():
    pick = _fn("packagesPick")
    assert "if (extra.unavailable && !extra.installed) return null;" in pick
    row = _fn("packagesRow")
    assert "const pick = packagesPick(extra);" in row and "if (pick) named.append(pick);" in row
    # The old rule drew a disabled tick instead.
    assert "(extra.unavailable && !extra.installed));" not in pick


def test_a_computer_with_no_build_says_so_not_ready_yet():
    row = _fn("packagesRow")
    assert 'extra.no_build ? "ph:prohibit Not for this computer" : "ph:hourglass Not ready yet"' in row


def test_status_and_log_are_placed_under_the_row_they_are_about():
    show = _fn("packagesShowStatus")
    assert "document.getElementById(`extra-row-${packagesStatusRow(body)}`)" in show
    assert "host.append(line, wrap)" in show and "list.after(line, wrap)" in show
    # Held, because getElementById cannot find a node a repaint detached.
    assert "ui.status ||=" in show
    render = JS[JS.index("async function renderExtras") : JS.index("// --- dictation model sizes")]
    assert "packagesShowStatus(list, body)" in render
    assert '$("extras-status").textContent' not in render


def test_the_row_in_hand_comes_from_the_install_then_from_the_last_one():
    which = _fn("packagesStatusRow")
    assert 'item.outcome === "running"' in which
    assert "body.installing || body.last" in which


def test_the_server_names_the_row_the_step_is_about_once_it_has_ended(client):
    body = client.get("/extras").json()
    assert "last" in body and "installing" in body
    assert all("no_build" in row for row in body["extras"])
