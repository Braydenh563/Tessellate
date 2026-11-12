"""VC6: Harper's own dictionary, kept-dismissed findings and all five dialects.

The real worker, run in node on the vendored binary (the driver of
`test_prose_tools.py`, with the person's own words and ignored list added).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
NAMES = ["Zorblax", "Quillfeather", "Mandrovia", "Pelikanto", "Thrumbold", "Vexilar", "Oskerwin", "Dunmarrow", "Kelpiston", "Yarrowick"]

DRIVER = r"""
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
const plan = JSON.parse(process.argv[3]);
const out = {};
let n = 0;
const ask = async (message) => { const id = ++n; await handler({ data: { id, dialect: "us", ...message } }); return replies.find((r) => r.id === id); };
const spelling = (r) => r.lints.filter((l) => l.kind === "Spelling").length;
out.namesBefore = spelling(await ask({ text: plan.names.join(", ") + " met." }));
await handler({ data: { type: "own", words: plan.names } });
out.namesAfter = spelling(await ask({ text: plan.names.join(", ") + " met." }));
const dup = "The the cat sat.";
out.dupPlain = (await ask({ text: dup })).lints.filter((l) => l.problem === "The the").length;
out.dupIgnored = (await ask({ text: dup, ignored: ["the the"] })).lints.filter((l) => l.problem === "The the").length;
out.dupEdited = (await ask({ text: "Intro line.\n\n" + dup, ignored: ["the the"] })).lints.filter((l) => l.problem === "The the").length;
out.dupRestored = (await ask({ text: dup, ignored: [] })).lints.filter((l) => l.problem === "The the").length;
out.dialects = {};
for (const d of ["us", "uk", "au", "ca", "in"]) {
  const r = await ask({ dialect: d, text: "The colour and the color. The centre and the center." });
  out.dialects[d] = r.lints.filter((l) => l.kind === "Spelling" || l.kind === "Regionalism").map((l) => l.problem).sort();
}
process.stdout.write(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("harper") / "driver.mjs"
    script.write_text(DRIVER, encoding="utf-8")
    done = subprocess.run(
        [node, str(script), (JS / "harper-worker.js").as_uri(), json.dumps({"names": NAMES})],
        capture_output=True, text=True, timeout=200, check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


def test_ten_names_stop_being_findings_once_the_dictionary_is_loaded(run) -> None:
    assert run["namesBefore"] == 10, run
    assert run["namesAfter"] == 0, run


def test_a_dismissed_finding_stays_dismissed_inside_harper_and_a_restore_shows_it(run) -> None:
    assert run["dupPlain"] == 1
    assert run["dupIgnored"] == 0
    assert run["dupEdited"] == 0
    assert run["dupRestored"] == 1


def test_each_dialect_flags_its_own_variant(run) -> None:
    d = run["dialects"]
    assert d["us"] and all(w.lower() in ("colour", "centre") for w in d["us"]), d
    #: Canada writes colour and centre, so it flags the American pair, as the others do.
    for key in ("uk", "au", "ca", "in"):
        assert d[key] and all(w.lower() in ("color", "center") for w in d[key]), (key, d)


def test_the_page_sends_the_dismissed_list_and_the_setting_lists_five_dialects() -> None:
    prose = (JS / "documents-prose.js").read_text(encoding="utf-8")
    assert 'ignored: docProseDismissed().filter((row) => row.rule === "grammar")' in prose
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    block = html[html.index('id="doc-spelling-variant"') :].split("</select>")[0]
    assert len(re.findall(r"<option value=", block)) == 6  # five dialects and no preference


def test_the_guide_says_names_are_known() -> None:
    from tests._help_text import help_chat_text

    assert "(names are known)" in help_chat_text()
