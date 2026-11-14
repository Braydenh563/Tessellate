"""L747, the owner's call (2026-11-12): two copies of the mind count as one. A test keeps their decisions in step.

The copies are `behaviour.Mind` (the desk) and `nameMarkBuddyDecide` with `nmb.cat` (the app). What they share is the
catalogue (`frontend/companion-catalogue.json`): the part of the day, the mood's energy and the factor an act's mood,
energy and day weights make. This runs the JS functions in node and the Python ones over every act, mood and hour, and
asks for the same number. A change to one side's rule that is not made on the other fails here."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import catalogue
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")
MOODS = ("happy", "curious", "sleepy", "startled", "proud", "bored", "content", "focus")


def _js_rows() -> list[list]:
    start = AV.index("phase(hour) {")
    methods = AV[start : AV.index("weigh(act, now, hour", start)]
    doc = catalogue.load()
    acts = sorted(bh.CATALOGUED)
    script = (
        "const doc = %s; const pick = () => ''; const nmb = {};\n" % json.dumps(doc)
        + "const st = { doc, entry: {} };\n"
        + "for (const e of doc.entries) { if (e.kind !== 'idle_act' || e.desk?.s !== 'built') continue;"
        + " for (const n of e.desk.names || []) if (n.startsWith('acts:')) st.entry[n.slice(5)] = e; }\n"
        + "nmb.cat = {\n" + methods + "};\n"
        + "const out = [];\n"
        + "for (const act of %s) for (const mood of %s) for (let h = 0; h < 24; h++)\n" % (json.dumps(acts), json.dumps(MOODS))
        + "  out.push([act, mood, h, nmb.cat.phase(h), nmb.cat.factor(act, mood, nmb.cat.phase(h))]);\n"
        + "process.stdout.write(JSON.stringify(out));"
    )
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


@needs_node
def test_the_app_and_the_desk_weigh_every_act_alike() -> None:
    rows = _js_rows()
    assert len(rows) > 24 * len(MOODS) * 3, "the desk's catalogued acts were found"
    for act, mood, hour, phase, factor in rows:
        assert phase == bh.phase_of(hour), (hour, phase)
        assert factor == pytest.approx(bh.catalogue_factor(act, mood, hour)), (act, mood, hour)


@needs_node
def test_the_calm_hours_agree() -> None:
    # The app's night (`hour >= 22 || hour < 6`) is the catalogue's night phase the desk uses.
    assert re.search(r"const night = hour >= 22 \|\| hour < 6;", AV)
    assert catalogue.load()["phases"]["night"] == [22, 6]
