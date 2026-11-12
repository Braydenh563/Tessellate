"""Sh1 P16 and X6: the Notes filter box reads day names, not only ISO dates.

`before:tuesday` and `after:yesterday` worked in Find anything (the server,
`search/query.py`) and were a plain word in the Notes list's own box, which
read `before:` and `after:` as `YYYY-MM[-DD]` only. The box now reads the same
words. The clock is fixed: Wednesday 2026-06-03, local time, so no run reads
the real date.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import with_pieces

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

NOW = "2026-06-03T12:00:00"  # a Wednesday


def _source() -> str:
    text = with_pieces("notes-list.js")
    out = []
    for name in ("LIVE_QUERY_RE", "ENGINE_QUERY_RE", "TAG_COUNT_RE"):
        m = re.search(rf"^const {name} =.*?;\n", text, re.M | re.S)
        assert m, name
        out.append(m.group(0))
    for name in ("parseNoteQuery", "noteQueryIsEmpty", "matchesSearch"):
        m = re.search(rf"^function {name}\(.*?^\}}\n", text, re.M | re.S)
        assert m, name
        out.append(m.group(0))
    day = re.search(r"^parseNoteQuery\.day = function .*?^\};\n", text, re.M | re.S)
    assert day, "parseNoteQuery.day"
    out.append(day.group(0))
    return "\n".join(out)


def _kept(q: str, days: dict[int, str]) -> list[int]:
    rows = [{"id": i, "content": "note", "tags": [], "created_at": f"{d}T09:00:00"} for i, d in days.items()]
    script = f"""
const FIXED = new Date({json.dumps(NOW)}).getTime();
const RealDate = Date;
globalThis.Date = class extends RealDate {{
  constructor(...a) {{ if (a.length) super(...a); else super(FIXED); }}
  static now() {{ return FIXED; }}
}};
let noteSearch = {json.dumps(q)};
const NOTE_FLAGS = [];
const noteEngine = {{ bodyIds: () => null }};
const noteSemanticLoaded = () => false;
const noteSortName = (e) => e.title || "";
{_source()}
process.stdout.write(JSON.stringify({json.dumps(rows)}.filter(matchesSearch).map((e) => e.id)));
"""
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


DAYS = {
    1: "2026-05-20",
    2: "2026-05-31",
    3: "2026-06-01",  # Monday
    4: "2026-06-02",  # Tuesday
    5: "2026-06-03",  # today
    6: "2026-02-10",
}


@needs_node
@pytest.mark.parametrize(
    ("query", "kept"),
    [
        ("before:2026-06-02", [1, 2, 3, 6]),  # the old ISO form still reads
        ("before:tuesday", [1, 2, 3, 6]),  # leaves Tuesday out, as Find anything does
        ("after:tuesday", [5]),
        ("before:tue", [1, 2, 3, 6]),
        ("before:today", [1, 2, 3, 4, 6]),
        ("after:yesterday", [5]),
        ("after:today", []),
        ("before:wednesday", [1, 2, 3, 4, 6]),  # today is that Wednesday
        ("after:3d", [3, 4, 5]),  # 3 days ago is 2026-05-31, left out
        ("before:2w", [6]),  # 2 weeks ago is 2026-05-20, left out
        ("before:march", [6]),  # the span's first day, 2026-03-01
        ("after:may", [3, 4, 5]),  # the span's last day, 2026-05-31
        ("before:2026-03", [6]),
    ],
)
def test_a_day_word_is_a_day_in_the_filter_box(query, kept):
    assert _kept(query, DAYS) == kept


@needs_node
def test_a_word_that_names_no_day_stays_a_word():
    rows = {1: "2026-06-01"}
    assert _kept("before:zebra", rows) == []  # a plain word, matching no note's text
    assert _kept("before:constructor", rows) == []
