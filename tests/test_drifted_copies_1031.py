"""One copy of each helper, and one shape for a refused id (audit 1031 AR8, BK9)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from tessellate.core import clock, paths, usage

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"


def _sources():
    for path in SRC.rglob("*.py"):
        yield path, path.read_text(encoding="utf-8")


def test_contained_accepts_a_name_and_refuses_the_ways_out(tmp_path):
    base = tmp_path / "uploads"
    base.mkdir()
    (tmp_path / "uploads2").mkdir()
    assert paths.contained(base, "a.txt") == (base / "a.txt").resolve()
    for bad in ("../x", "..", "", "../uploads2/x", "/etc/passwd"):
        with pytest.raises(paths.OutsideFolder):
            paths.contained(base, bad)
    (base / "link").symlink_to(tmp_path / "uploads2")
    with pytest.raises(paths.OutsideFolder):
        paths.contained(base, "link/x")


def test_slug_forms():
    assert paths.slug("# My plan: v2!\nsecond line") == "My-plan-v2"
    assert paths.slug("", fallback="note") == "note"
    assert paths.slug("Work & Play 2", 49, ascii_only=True, fallback="space") == "work-play-2"
    assert paths.slug("!!!", 49, ascii_only=True, fallback="space") == "space"
    assert len(paths.slug("x" * 200, 30)) == 30


def test_no_second_copy_of_containment_slug_or_today():
    offenders = []
    for path, text in _sources():
        rel = path.relative_to(SRC).as_posix()
        if rel not in ("core/paths.py",) and re.search(r"os\.path\.realpath\(os\.path\.join\(", text):
            offenders.append(f"{rel}: containment")
        if re.search(r"^\s*def _(?:slug|slugify|within_dir|within_exports)\(", text, re.M):
            offenders.append(f"{rel}: helper")
        if rel != "core/clock.py" and re.search(r"\bdate\.today\(\)", text.replace("`date.today()`", "")):
            offenders.append(f"{rel}: date.today()")
    assert not offenders, offenders


def test_a_test_pins_the_day_in_one_place(tmp_path, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2026, 8, 1))
    usage.record(tmp_path, ["note"])
    assert "2026-08-01" in str(usage.read(tmp_path))


def test_an_id_no_row_can_have_is_a_404_like_any_unknown_one(client):
    small = client.get("/entries/-1")
    huge = client.get("/entries/99999999999999999999")
    assert (small.status_code, huge.status_code) == (404, 404)
    assert huge.json()["code"] == small.json()["code"] == "not_found"
    doc = client.get("/documents/99999999999999999999")
    assert doc.status_code == 404


def test_a_number_typed_into_a_field_is_still_a_422(client):
    reply = client.get("/entries?offset=99999999999999999999")
    assert reply.status_code == 422


def test_an_unknown_backup_is_a_404_on_every_spelling(client):
    for name in ("nope.db", "..%2f..%2fx", "%2e%2e%2fx"):
        reply = client.delete(f"/backups/{name}")
        assert reply.status_code == 404, name


def test_every_offset_and_limit_has_a_floor(client):
    app = client.app
    bare = []
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for param in dependant.query_params:
            if param.name not in ("offset", "limit", "skip"):
                continue
            meta = " ".join(repr(m) for m in getattr(param.field_info, "metadata", []))
            if "Ge(" not in meta and "Gt(" not in meta:
                bare.append(f"{route.path}:{param.name}")
    assert not bare, bare
