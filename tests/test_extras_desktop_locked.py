"""INBOX 904 B27: the packaged app cannot remove its own window.

The owner: "I shouldn't be able to uninstall the desktop view in the packaged
windows app". Settings, Packages offered Reinstall and a red Remove on "Desktop
window (pywebview)", and the packaged build is that window: removing it leaves an
app that cannot open. A packaged (frozen) build refuses it in the row, the
single route and the bulk walk; a source install still may.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.core import extras

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _clean_extras():
    extras.reset_for_tests()
    yield
    extras.reset_for_tests()


def _row(client, extra_id="desktop"):
    return next(e for e in client.get("/extras").json()["extras"] if e["id"] == extra_id)


def test_a_source_install_may_remove_the_desktop_window(client, monkeypatch):
    monkeypatch.setattr(extras.sys, "frozen", False, raising=False)
    row = _row(client)
    assert row["removable"] is True and row["locked"] == ""


def test_a_packaged_build_marks_the_desktop_window_not_removable(client, monkeypatch):
    monkeypatch.setattr(extras.sys, "frozen", True, raising=False)
    row = _row(client)
    assert row["removable"] is False
    assert "desktop window" in row["locked"].lower()
    assert _row(client, "voice")["removable"] is True


def test_a_packaged_build_refuses_the_removal_route(client, monkeypatch):
    monkeypatch.setattr(extras.sys, "frozen", True, raising=False)
    body = client.post("/extras/desktop/uninstall").json()
    assert body["started"] is False and "desktop window" in body["message"].lower()
    assert not extras.current().running


def test_a_packaged_build_skips_it_in_a_bulk_removal(client, monkeypatch):
    monkeypatch.setattr(extras.sys, "frozen", True, raising=False)
    monkeypatch.setattr(extras, "is_installed", lambda extra: True)
    # inline, as tests/test_extras_bundles.py does, so the outcome is there on the next line
    monkeypatch.setattr(extras, "_dispatch", lambda func, *args, name="": func(*args))

    def _unexpected(*args, **kwargs):
        raise AssertionError("nothing may be removed")

    monkeypatch.setattr(extras.subprocess, "Popen", _unexpected)
    extras.start_bulk("uninstall", ["desktop"])
    item = extras.bulk_status()["items"][0]
    assert item["outcome"] == "skipped" and "desktop window" in item["message"].lower()


def test_the_row_menu_and_the_bars_leave_remove_out():
    source = (ROOT / "frontend" / "js" / "settings-packages.js").read_text(encoding="utf-8")
    can = source[source.index("function packagesCan(") :]
    can = can[: can.index("\n}\n")]
    assert "removable !== false" in can
    menu = source[source.index("function packagesRowMenu(") :]
    menu = menu[: menu.index("\n}\n")]
    assert "removable !== false" in menu and menu.index("removable !== false") < menu.index("ph:trash Remove")
