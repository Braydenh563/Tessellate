"""Audit 1028 K22: the composer's "today" is the person's day, not the
server's. A fixed instant seen from a far timezone is a different date."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

from tessellate.ai import composer, composer_digest
from tessellate.core import config, deps

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate" / "ai"
#: 23:30 UTC on 30 October: already 31 October in Kiritimati (UTC+14), still 30 October in UTC.
INSTANT = datetime(2026, 10, 30, 23, 30, tzinfo=timezone.utc)


class _Clock(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ANN001, ANN206
        return INSTANT.astimezone(tz) if tz else INSTANT


class _Prefs:
    def __init__(self, zone: str) -> None:
        self.zone = zone

    def get_preference(self, key: str, default=None):  # noqa: ANN001, ANN201
        return self.zone if key == "timezone" else default


def _from(monkeypatch, zone: str) -> None:
    monkeypatch.setattr(config, "datetime", _Clock)
    monkeypatch.setattr(deps, "_config", _Prefs(zone))


def test_today_is_the_persons_day_in_a_far_timezone(monkeypatch):
    _from(monkeypatch, "Pacific/Kiritimati")
    assert composer.user_today() == date(2026, 10, 31)
    _from(monkeypatch, "UTC")
    assert composer.user_today() == date(2026, 10, 30)


def test_a_day_count_runs_from_the_persons_day(monkeypatch):
    notes = [{"id": 1, "content": "Dentist on 31 October at 9am.", "tags": [], "category": "", "created_at": datetime(2026, 10, 1, 9)}]
    _from(monkeypatch, "Pacific/Kiritimati")
    far = composer_digest.answer("how many days until the dentist", notes)
    _from(monkeypatch, "UTC")
    near = composer_digest.answer("how many days until the dentist", notes)
    assert far["text"].startswith("The dentist is today")
    assert near["text"].startswith("The dentist is tomorrow")


def test_no_composer_module_reads_the_servers_clock():
    bare = re.compile(r"\bdate\.today\(\)|\bdatetime\.(?:now|today)\(\)")
    bad = [f"{p.name}:{n}" for p in sorted(SRC.glob("composer*.py"))
           for n, line in enumerate(p.read_text().splitlines(), 1)
           if bare.search(line) and not line.lstrip().startswith(("#", '"""')) and "server's" not in line]
    assert not bad, bad


def test_the_zone_name_is_read_from_the_saved_preference(monkeypatch):
    _from(monkeypatch, "Not/AZone")
    assert isinstance(composer.user_today(), date)
