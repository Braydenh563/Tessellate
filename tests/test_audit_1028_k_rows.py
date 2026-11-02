"""Audit 1028 K rows settled 2026-10-31: K28 one loopback list, K38 the once ticket kept out of the log."""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.core import logbuffer, security

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"


def test_one_loopback_host_list():
    """K28: routes_auth kept its own copy of the list; a fix to one would miss the other."""
    defined = [p for p in SRC.rglob("*.py") if re.search(r"^_?LOOPBACK_HOSTS\s*=", p.read_text(encoding="utf-8"), re.M)]
    assert [p.name for p in defined] == ["security.py"]
    assert {"localhost", "127.0.0.1", "::1"} <= security.LOOPBACK_HOSTS


def test_a_media_link_ticket_never_reaches_the_log():
    """K38: the `once` ticket rides in the query; the access line shows the key, not the ticket."""
    line = '127.0.0.1:5000 - "GET /media/a.pdf?once=Zk3s9QxY HTTP/1.1" 200'
    scrubbed = logbuffer.scrub_query_strings(line)
    assert "Zk3s9QxY" not in scrubbed and "once=[redacted]" in scrubbed
