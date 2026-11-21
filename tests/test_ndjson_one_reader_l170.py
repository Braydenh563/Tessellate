"""L170: one NDJSON reader (`api.ndjson`, ndjson-read.js, loaded on first use) for Ask, Chat, the Guide, the digest and the writing desk.

The real helper runs in node against a stream that splits a line across two
chunks, carries a bad line and ends without a newline, and against one that
never answers. The consumers are read as text: none keeps its own reader."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")
CONSUMERS = ["answer-kit.js", "dashboard.js", "writing-desk.js", "help-chat.js"]

HARNESS = r"""
const src = process.argv[1];
const logs = [];
const recordBrowserLog = (level, parts) => logs.push(parts.join(" "));
const api = () => {};
eval(src);
const stream = (chunks, hang = false) => {
  const enc = new TextEncoder();
  let i = 0;
  return { body: { getReader: () => ({
    read: () => (i < chunks.length ? Promise.resolve({ done: false, value: enc.encode(chunks[i++]) }) : hang ? new Promise(() => {}) : Promise.resolve({ done: true })),
    cancel: () => { logs.push("cancelled"); return Promise.resolve(); },
  }) } };
};
(async () => {
  const seen = [];
  await api.ndjson(stream(['{"a":1}\n{"b"', ':2}\nnot json\n{"c":3}']), (e) => seen.push(e));
  let idle = null;
  await api.ndjson(stream(['{"a":1}\n'], true), () => {}, { idleMs: 20, idleMessage: "stalled" }).catch((e) => { idle = e.message; });
  console.log(JSON.stringify({ seen, logs, idle }));
})();
"""


def _helper() -> str:
    text = (JS / "ndjson-read.js").read_text(encoding="utf-8")
    start = text.index("api.ndjson = async")
    return text[start : text.index("\n};\n", start) + 4]


@node
def test_the_reader_joins_split_lines_skips_a_bad_one_and_gives_up_on_silence():
    out = subprocess.run(["node", "-e", HARNESS, _helper()], capture_output=True, text=True, timeout=30, check=True).stdout
    said = json.loads(out)
    assert said["seen"] == [{"a": 1}, {"b": 2}, {"c": 3}]
    assert any("Unparseable line" in line and "Stream" in line for line in said["logs"])
    assert said["idle"] == "stalled" and "cancelled" in said["logs"]


@pytest.mark.parametrize("name", CONSUMERS)
def test_a_consumer_has_no_reader_of_its_own(name):
    text = (JS / name).read_text(encoding="utf-8")
    assert 'await ensureModule("ndjson");' in text and "api.ndjson(" in text and "getReader()" not in text and not re.search(r"decoder\.decode\(", text)
