"""The local usage ledger and simple mode (WORLD_CLASS_PLAN H9, row 27).

The ledger counts feature names on this computer only; its gate is "a
feature unused for ninety days is listed, and the palette's top five are the
five most used". Simple mode hides what a new person does not need and
leaves every hidden place reachable from the palette.
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

from tessellate.core import clock, deps, usage

ROOT = Path(__file__).resolve().parents[1]


def test_counts_are_kept_and_most_used_come_first(client):
    for _ in range(3):
        client.post("/usage", json={"features": ["tab:notes", "cmd:new-note"]})
    client.post("/usage", json={"features": ["tab:chat"]})
    body = client.post("/usage/summary", json={"known": []}).json()
    assert [f["name"] for f in body["features"]][:3] == ["cmd:new-note", "tab:notes", "tab:chat"]
    assert body["features"][0]["count"] == 3


def test_a_feature_unused_for_ninety_days_is_listed(app_state):
    data = deps.get_config().data_dir
    old = clock.today() - timedelta(days=120)
    usage.record(data, ["tab:graph"], today=old)
    usage.record(data, ["tab:notes"])
    body = usage.summary(data, known=["tab:graph", "tab:notes", "tab:timeline"])
    assert body["unused"] == ["tab:graph", "tab:timeline"]


def test_nothing_typed_can_ride_in_a_name(client):
    sent = client.post("/usage", json={"features": ["tab:notes", "my password is hunter2", "x" * 80, "Cmd:Upper"]}).json()
    assert sent["counted"] == 1
    names = [f["name"] for f in client.post("/usage/summary", json={"known": []}).json()["features"]]
    assert names == ["tab:notes"]


def test_clear_forgets_every_count(client):
    client.post("/usage", json={"features": ["tab:notes"]})
    cleared = client.delete("/usage").json()
    assert cleared == {"cleared": True}
    summary = client.post("/usage/summary", json={"known": []}).json()
    assert summary["features"] == []


def test_the_ledger_is_never_sent_anywhere():
    """The page posts only to this app's own `/usage`; nothing else names it."""
    js = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend" / "js").glob("*.js"))
    assert re.findall(r"(?:fetch|api)\(\"(/usage[^\"]*)\"", js) == ["/usage"]
    assert "usage.json" not in (ROOT / "src" / "tessellate" / "core" / "privacy_http.py").read_text(encoding="utf-8")


def test_simple_mode_hides_three_tabs_and_keeps_four():
    css = (ROOT / "frontend" / "css" / "02-chat-graph.css").read_text(encoding="utf-8")
    rule = css.split(':root[data-simple="on"] #tab-bar button[role="tab"]', 1)[1].split("}", 1)[0]
    hidden = set(re.findall(r'\[data-tab="(\w+)"\]', rule))
    assert hidden == {"graph", "timeline", "reminders"}
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    tabs = re.findall(r'<button role="tab" id="tab-btn-(\w+)"', html)
    assert [t for t in tabs if t not in hidden] == ["dashboard", "notes", "chat", "library"]
    boot = (ROOT / "frontend" / "js" / "theme-boot.js").read_text(encoding="utf-8")
    assert 'localStorage.getItem("simpleMode") === "1"' in boot


def test_capture_from_anywhere_opens_the_running_app(monkeypatch):
    """`memorymap --capture` opens capture.html on the running copy, and says
    so plainly when nothing is running."""
    import tessellate.__main__ as entry

    class Lock:
        port = 8123

    opened = []
    monkeypatch.setattr(entry, "_existing_instance", lambda: ("live", Lock()))
    monkeypatch.setattr("webbrowser.open", lambda url, new=0: opened.append(url))
    assert entry._capture() == 0
    assert opened == ["http://127.0.0.1:8123/capture.html"]
    monkeypatch.setattr(entry, "_existing_instance", lambda: ("none", None))
    assert entry._capture() == 1


def test_the_capture_page_saves_one_line_and_names_its_command(client):
    from tessellate import __version__

    html = (ROOT / "frontend" / "capture.html").read_text(encoding="utf-8")
    assert set(re.findall(r'\?v=([^"]+)"', html)) == {__version__}
    assert "<script>" not in html and '<script src="/js/capture.js?v=' in html
    js = (ROOT / "frontend" / "js" / "capture.js").read_text(encoding="utf-8")
    assert 'call("/entries", "POST"' in js and '"X-Auth-Token"' in js
    command = client.get("/capture/command").json()["command"]
    assert command.endswith("--capture")
