"""JSON Schema lint and key completion for a .json document (L-documents-42), run in node.

`documents-json-schema.js` is the browser's text, over the vendored CodeMirror's own JSON parser: here the
library list and the API are a fake, so every keyword of the validator, the pointer-to-range mapping and the
completion list are checked without a browser. The browser half is measured by the agent sweep named in the ledger row.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CM_JS = ROOT / "frontend" / "vendor" / "codemirror" / "codemirror.min.js"
PIECE = ROOT / "frontend" / "js" / "documents-json-schema.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name"],
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "description": "The person's name."},
        "age": {"type": "integer", "minimum": 0, "maximum": 150},
        "role": {"enum": ["admin", "user"]},
        "tags": {"type": "array", "items": {"type": "string"}},
        "home": {"$ref": "#/definitions/place"},
    },
    "definitions": {
        "place": {"type": "object", "required": ["city"], "properties": {"city": {"type": "string", "description": "A city."}, "zip": {"type": "string"}}},
    },
}

_HARNESS = """
const window = globalThis;
globalThis.navigator = globalThis.navigator || { userAgent: "node", platform: "" };
%(cm)s
const DOC_LINT_CONFIG = {};
%(piece)s
const CM = window.CM6;
const S = DOC_LINT_CONFIG.jsonSchema;
const state = (doc) => CM.state.EditorState.create({ doc, extensions: [CM.json.json()] });
const env = { docs: () => [{ id: 1, title: "person.schema.json", file_type: "json" }, { id: 2, title: "notes", file_type: "md" }], api: async () => ({ content: JSON.stringify(SCHEMA) }) };
(async () => {
  const out = {};
  for (const [key, call] of Object.entries(CALLS)) {
    const text = call.text;
    if (call.op === "lint") out[key] = (await S.diagnostics(CM, state(text), env)).map((d) => ({ ...d, at: text.slice(d.from, d.to) }));
    if (call.op === "complete") {
      const at = text.indexOf("|");
      const doc = text.replace("|", "");
      const st = state(doc);
      const context = { state: st, pos: at, explicit: Boolean(call.explicit), matchBefore(re) { const line = st.doc.lineAt(at); const m = re.exec(st.sliceDoc(line.from, at)); return m ? { from: line.from + m.index, to: at, text: m[0] } : null; } };
      const got = await S.complete(CM, context, env);
      out[key] = got && { from: got.from, doc, options: got.options.map((o) => ({ label: o.label, detail: o.detail, info: o.info })) };
    }
  }
  console.log(JSON.stringify(out));
})();
"""


def _node(calls: dict) -> dict:
    script = f"const SCHEMA = {json.dumps(SCHEMA)};\nconst CALLS = {json.dumps(calls)};\n" + _HARNESS % {
        "cm": CM_JS.read_text(encoding="utf-8"),
        "piece": PIECE.read_text(encoding="utf-8"),
    }
    done = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


def _lint(text: str) -> list[dict]:
    return _node({"a": {"op": "lint", "text": text}})["a"]


def _complete(text: str, explicit: bool = False):
    return _node({"a": {"op": "complete", "text": text, "explicit": explicit}})["a"]


HEAD = '{"$schema": "person.schema.json", '


def test_a_valid_file_has_no_findings():
    assert _lint(HEAD + '"name": "Ada", "age": 36, "role": "admin", "tags": ["a"], "home": {"city": "Leeds"}}') == []


def test_type_names_the_value_and_underlines_it():
    (d,) = _lint(HEAD + '"name": 5}')
    assert d["at"] == "5" and d["message"] == "Expected a string, found an integer." and d["severity"] == "warning"
    (d,) = _lint(HEAD + '"name": "x", "age": 1.5}')
    assert d["at"] == "1.5" and "an integer" in d["message"]


def test_required_underlines_the_opening_brace():
    (d,) = _lint('{"$schema": "person.schema.json"}')
    assert d["message"] == 'Missing required property "name".' and d["at"] == "{"


def test_additional_properties_false_underlines_the_key():
    (d,) = _lint(HEAD + '"name": "x", "nick": 1}')
    assert d["at"] == '"nick"' and d["message"] == '"nick" is not allowed here.'


def test_enum_minimum_and_maximum():
    (d,) = _lint(HEAD + '"name": "x", "role": "root"}')
    assert d["at"] == '"root"' and d["message"] == 'Not one of "admin", "user".'
    (d,) = _lint(HEAD + '"name": "x", "age": -1}')
    assert d["message"] == "Below the minimum of 0."
    (d,) = _lint(HEAD + '"name": "x", "age": 200}')
    assert d["message"] == "Above the maximum of 150."


def test_items_and_ref_are_followed_to_the_deep_range():
    (d,) = _lint(HEAD + '"name": "x", "tags": ["a", 2]}')
    assert d["at"] == "2" and "found an integer" in d["message"]
    found = _lint(HEAD + '"name": "x", "home": {"zip": 1}}')
    assert sorted(d["message"] for d in found) == ["Expected a string, found an integer.", 'Missing required property "city".']
    assert {d["at"] for d in found} == {"1", "{"}


def test_a_schema_not_in_the_library_is_one_note_and_not_a_check():
    (d,) = _lint('{"$schema": "https://example.com/other.json", "name": 1}')
    assert d["severity"] == "info" and d["at"] == '"https://example.com/other.json"'


def test_no_schema_key_no_findings():
    assert _lint('{"name": 1}') == []


def test_a_path_and_a_title_without_the_extension_both_find_the_document():
    assert _lint('{"$schema": "./schemas/person.schema.json", "name": 1}')[0]["message"].startswith("Expected a string")
    assert _lint('{"$schema": "person.schema", "name": 1}')[0]["message"].startswith("Expected a string")


def test_completion_lists_keys_with_descriptions_and_skips_present_ones():
    got = _complete('{"$schema": "person.schema.json", "name": "x", "|')
    assert [o["label"] for o in got["options"]] == ["age", "role", "tags", "home"]
    got = _complete('{"$schema": "person.schema.json", "|')
    name = next(o for o in got["options"] if o["label"] == "name")
    assert name["info"] == "The person's name." and name["detail"] == "required, string"


def test_completion_follows_the_pointer_into_a_ref():
    got = _complete('{"$schema": "person.schema.json", "home": {"|')
    assert [(o["label"], o.get("info")) for o in got["options"]] == [("city", "A city."), ("zip", None)]


def test_completion_is_silent_in_a_value_and_with_no_schema():
    assert _complete('{"$schema": "person.schema.json", "name": "|') is None
    assert _complete('{"name": "|') is None
