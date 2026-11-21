"""L-chat-17 (CHAT_PLAN item 11): "Lines written from your notes" off makes the
three surfaces that speak about the notes say nothing personal: the greeting is
a plain hello, the today line falls back to the page's counts, the companion
has no remark. On (the default) they are unchanged."""

from __future__ import annotations

from datetime import datetime, timedelta

from tessellate.api import routes_insights
from tessellate.core import deps
from tessellate.core.database import Reminder
from tessellate.entry import manager
from tests._clock import pin_clock

NOW = datetime(2026, 11, 10, 9, 0)


def _seed(monkeypatch) -> None:
    pin_clock(monkeypatch, NOW)
    with deps.get_db().session() as session:
        for _ in range(2):
            manager.create_entry(session, "# Harbor launch date\n\nThe launch is set for the first week of December.")
        session.add(Reminder(text="Collect the parcel", due_at=NOW + timedelta(minutes=30)))
        session.commit()


def test_the_switch_is_on_by_default_and_the_surfaces_speak_about_the_notes(client, monkeypatch):
    _seed(monkeypatch)
    assert client.get("/preferences").json()["personal_wording"] is True
    texts = {client.get(f"/insights/today-line?seed={s}").json()["text"] for s in range(12)}
    assert any("Harbor launch date" in t for t in texts)
    assert any("Collect the parcel" in r["text"] for r in client.get("/insights/remarks").json()["remarks"])


def test_off_the_greeting_today_line_and_remarks_say_nothing_about_the_notes(client, monkeypatch):
    _seed(monkeypatch)
    saved = client.put("/preferences", json={"personal_wording": False})
    assert saved.status_code == 200
    assert client.get("/preferences").json()["personal_wording"] is False
    greet = client.get("/insights/greeting?block=morning").json()
    assert greet["source"] == "plain"
    assert greet["greeting"] in routes_insights.GREETING_FALLBACKS["morning"]
    for s in range(6):
        assert client.get(f"/insights/today-line?seed={s}").json() == {"text": "", "kind": "none", "sources": []}
    assert client.get("/insights/remarks").json() == {"remarks": []}


def test_the_settings_row_and_its_help_are_in_the_page_and_the_guide():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend/index.html").read_text(encoding="utf-8")
    assert 'id="pref-personal-wording"' in html and 'data-help-for="personal-wording-help"' in html
    import re

    from tests._help_text import help_more_text

    guide = re.sub(r'"\s*\n\s*"', "", help_more_text())
    assert "Lines written from your notes (on by default)" in guide
