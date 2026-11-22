"""The document properties panel reads a note type (GRAPH_PLAN, the item listed
after KG1 to KG9, built).

A document whose frontmatter says `type: Meeting` shows the Meeting type's
fields it has not written yet as empty rows, each with the control its kind
needs, so the panel and the note's own Properties sheet agree. The decision
of *which* fields are still missing is pure string work and runs in node here;
the panel only draws what it answers and writes through `docFrontmatterAddEdits`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_doc_frontmatter import model_source

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_JS = ROOT / "frontend" / "js" / "documents-props.js"  # the panel moved out of documents.js (DC13 remainder, doc22-1102)

TYPES = [
    {"name": "Meeting", "fields": [
        {"name": "attendees", "kind": "list"},
        {"name": "date", "kind": "date"},
        {"name": "done", "kind": "checkbox"},
    ]},
    {"name": "Person", "fields": [{"name": "company", "kind": "note"}]},
]

DRIVER = r"""
const types = JSON.parse(process.argv[2]);
const out = [];
const check = (name, ok, detail = "") => out.push({ name, ok: Boolean(ok), detail });
const names = (r) => r.fields.map((f) => f.name).join(",");

let fm = docFrontmatterParse("---\ntype: Meeting\ndate: 2026-10-04\n---\nBody");
let r = docFrontmatterTypeFields(fm, types);
check("type-name", r.type === "Meeting", r.type);
check("skips-written", names(r) === "attendees,done", names(r));

fm = docFrontmatterParse('---\ntype: "person"\n---\nBody');
r = docFrontmatterTypeFields(fm, types);
check("case-and-quotes", r.type === "Person" && names(r) === "company", JSON.stringify(r));

fm = docFrontmatterParse("---\ntitle: x\n---\nBody");
r = docFrontmatterTypeFields(fm, types);
check("no-type", r.type === null && r.fields.length === 0, JSON.stringify(r));

fm = docFrontmatterParse("---\ntype: Nonsense\n---\nBody");
r = docFrontmatterTypeFields(fm, types);
check("unknown-type", r.type === null && r.fields.length === 0, JSON.stringify(r));

fm = docFrontmatterParse("---\ntype: Meeting\n---\nBody");
check("no-types-loaded", docFrontmatterTypeFields(fm, null).fields.length === 0);
check("no-block", docFrontmatterTypeFields(null, types).fields.length === 0);

fm = docFrontmatterParse("---\ntype:\n  - Meeting\n---\nBody");
r = docFrontmatterTypeFields(fm, types);
check("list-type-not-read", r.type === null, JSON.stringify(r));

fm = docFrontmatterParse("---\nType: Meeting\nATTENDEES: [a]\n---\nBody");
r = docFrontmatterTypeFields(fm, types);
check("key-case", r.type === "Meeting" && names(r) === "date,done", JSON.stringify(r));

// Adding a field is the model's own add: the other lines keep their bytes.
fm = docFrontmatterParse("---\ntype: Meeting\n---\nBody");
const added = docTableApplyEdits("---\ntype: Meeting\n---\nBody", docFrontmatterAddEdits(fm, "attendees", "[Sam, Ada]"));
check("add-list", added === "---\ntype: Meeting\nattendees: [Sam, Ada]\n---\nBody", JSON.stringify(added));
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def checks(tmp_path_factory) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("doctype") / "run.js"
    script.write_text(model_source() + DRIVER, encoding="utf-8")
    out = subprocess.run(
        [node, str(script), json.dumps(TYPES)], capture_output=True, text=True, timeout=60, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_missing_fields_of_the_documents_type(checks: list[dict]) -> None:
    failed = [c for c in checks if not c["ok"]]
    assert not failed, "\n".join(f"{c['name']}: {c['detail']}" for c in failed)
    assert len(checks) >= 9


def test_the_panel_draws_them_and_asks_for_the_types() -> None:
    """The call sites exist (a function nothing calls never ran once)."""
    text = DOCUMENTS_JS.read_text(encoding="utf-8")
    assert "docFrontmatterTypeFields(" in text.split("// DOC-FRONTMATTER-END", 1)[1]
    assert "/note-types" in text
    assert "docPropsTypeRows(" in text.split("function renderDocProperties", 1)[1].split("function docInsertProperties", 1)[0]
