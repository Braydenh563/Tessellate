"""The note list's clamp settle reads every card before it unclips any (owner-asks-audit 1643 b, 1667 m).

`noteClampFit` unclipped a card as it went, so the next card's `clientHeight`
read paid for a layout: 51 forced layouts and 58 ms in one callback at 4x.
Measured with 18 clamped cards at 4x: callback 41 to 62 ms with 33 to 55 ms
forced before, 6 to 15 ms with none after (numbers in
docs/roadmap/agent-remaining/w34-def1-1111.md). Run in node with fake cards
that log every read and write.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CARDS = (ROOT / "frontend" / "js" / "note-cards.js").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def test_no_card_is_read_after_another_was_unclipped() -> None:
    block = re.search(r"^const noteClampFit = new ResizeObserver\(.*?^\}\);", CARDS, re.S | re.M)
    assert block, "noteClampFit is gone from note-cards.js"
    script = f"""
const log = [];
let callback = null;
globalThis.ResizeObserver = class {{ constructor(fn) {{ callback = fn; }} unobserve(t) {{ log.push("unobserve " + t.name); }} observe() {{}} }};
const card = (name, {{ fits, connected = true }}) => ({{
  name, isConnected: connected,
  get clientHeight() {{ log.push("read " + name); return 100; }},
  get scrollHeight() {{ return fits ? 80 : 400; }},
  classList: {{ contains: () => true }},
  unclip() {{ log.push("write " + name); }},
}});
{block.group(0)}
callback([
  {{ target: card("a", {{ fits: true }}) }},
  {{ target: card("b", {{ fits: false }}) }},
  {{ target: card("c", {{ fits: true }}) }},
  {{ target: card("gone", {{ fits: true, connected: false }}) }},
  {{ target: card("d", {{ fits: true }}) }},
]);
process.stdout.write(JSON.stringify(log));
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    log = json.loads(out)
    writes = [i for i, line in enumerate(log) if line.startswith("write ")]
    reads = [i for i, line in enumerate(log) if line.startswith("read ")]
    assert [log[i] for i in writes] == ["write a", "write c", "write d"]
    assert reads and max(reads) < min(writes), log
    assert "unobserve gone" in log
