"""Five spelling dialects, not two (DOCUMENTS_PLAN, Brief 75's VC6).

Harper ships American, British, Australian, Canadian and Indian rules; the
writing panel offered two. The worker passes all five through, the select
lists them, the preference accepts them, and the editor's own pair table
(`DOC_SPELLING_PAIRS`) reads each one in the right direction. What it does in
the page is `scratchpad/ui-sweeps/spellingdialects1018.js`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
HTML = (FRONTEND / "index.html").read_text(encoding="utf-8")
DOCS = (FRONTEND / "js" / "documents.js").read_text(encoding="utf-8")

DIALECTS = ["us", "uk", "au", "ca", "in"]

HARPER_DRIVER = r"""
import { readFile } from "node:fs/promises";
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, init) => {
  const href = String(url && url.href ? url.href : url);
  if (href.startsWith("file:")) {
    return new Response(await readFile(new URL(href)), { headers: { "Content-Type": "application/wasm" } });
  }
  return realFetch(url, init);
};
let handler = null;
const replies = [];
globalThis.self = {
  addEventListener: (type, fn) => { if (type === "message") handler = fn; },
  postMessage: (message) => replies.push(message),
};
await import(process.argv[2]);
for (const dialect of JSON.parse(process.argv[4])) {
  await handler({ data: { id: dialect, dialect, text: process.argv[3] } });
}
process.stdout.write(JSON.stringify(replies));
"""


def test_the_worker_answers_in_each_of_the_five_dialects(tmp_path) -> None:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path / "harper.mjs"
    script.write_text(HARPER_DRIVER, encoding="utf-8")
    text = "The colour of the centre, and the color of the center: we organise and organize it."
    out = subprocess.run(
        [node, str(script), (FRONTEND / "js" / "harper-worker.js").as_uri(), text, json.dumps(DIALECTS)],
        capture_output=True, text=True, timeout=180, check=False,
    )
    assert out.returncode == 0, out.stderr
    found = {r["id"]: {lint["problem"] for lint in r["lints"]} for r in json.loads(out.stdout)}
    assert list(found) == DIALECTS
    # American flags the -our and -re forms; every other dialect flags the American ones.
    assert {"colour", "centre"} <= found["us"]
    for dialect in ("uk", "au", "in"):
        assert {"color", "center"} <= found[dialect] and not {"colour", "centre"} & found[dialect], dialect
    # Canadian keeps -our and -re but not -ise: the one dialect that differs from both neighbours.
    assert {"color", "center", "organise"} <= found["ca"] and "colour" not in found["ca"]
    assert "organise" not in found["uk"]


def test_the_select_lists_the_five_in_order() -> None:
    select = re.search(r'<select id="doc-spelling-variant">(.*?)</select>', HTML, re.S).group(1)
    assert re.findall(r'value="(\w+)"', select) == ["off", *["uk", "us", "au", "ca", "in"]]


def test_the_preference_takes_every_dialect() -> None:
    from tessellate.api.routes_settings import PreferencesBody

    for value in ["off", *DIALECTS]:
        assert PreferencesBody(spelling_variant=value).spelling_variant == value
    with pytest.raises(ValueError):
        PreferencesBody(spelling_variant="fr")


NODE_PAIRS = r"""
const source = process.argv[2];
let prefsCache = { spelling_variant: process.argv[3] };
const fn = new Function("prefsCache", source + "; return docVariantLookup();");
const map = fn(prefsCache);
process.stdout.write(JSON.stringify(Object.fromEntries(map)));
"""


def _lookup(tmp_path, variant: str) -> dict[str, str]:
    node = shutil.which("node")
    if not node:  # pragma: no cover
        pytest.skip("node is not available")
    start = DOCS.index("const DOC_SPELLING_PAIRS = [")
    end = DOCS.index("\n}\n", DOCS.index("function docVariantLookup(")) + 3
    script = tmp_path / "pairs.js"
    script.write_text(NODE_PAIRS, encoding="utf-8")
    out = subprocess.run(
        [node, str(script), DOCS[start:end], variant], capture_output=True, text=True, timeout=60, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_pair_table_reads_each_dialect_the_right_way(tmp_path) -> None:
    us = _lookup(tmp_path, "us")
    assert us["colour"] == "color" and us["organise"] == "organize"
    for variant in ("uk", "au", "in"):
        british = _lookup(tmp_path, variant)
        assert british["color"] == "colour" and british["organize"] == "organise", variant
        assert "colour" not in british
    ca = _lookup(tmp_path, "ca")
    # Canadian: -our, -re and the doubled l stay; -ize, program and tire are American.
    assert ca["color"] == "colour" and ca["center"] == "centre" and ca["traveled"] == "travelled"
    assert ca["organise"] == "organize" and ca["programme"] == "program" and ca["tyre"] == "tire"
    assert "colour" not in ca and "organize" not in ca
    assert _lookup(tmp_path, "off") == {}


def test_the_finding_names_the_dialect() -> None:
    assert '"UK" : "US"' not in DOCS, "the finding's label was a two-way ternary"
    assert "DOC_VARIANT_LABEL" in DOCS
