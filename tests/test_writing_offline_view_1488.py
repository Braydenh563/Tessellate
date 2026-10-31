"""The Writing room's no-model view (INBOX 1488): what the page offers.

The owner: "if certain features are useless or not available with no ai they
shouldnt be an option". The passes are tested in `test_writing_nomodel_1488.py`;
this holds the page half: model-only entries carry `data-gate="model"`, the
rule-only ones `data-gate="rule"` (and start hidden), the gate puts the select
back whole when a model connects, and one line says what the writer does.
Measured in the app on a no-model server and with the status poll patched to
a model: 7 chips both ways, 9 and 25 menu rows.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
DESK = (ROOT / "frontend" / "js" / "writing-desk.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _select(select_id: str) -> str:
    start = HTML.index(f'<select id="{select_id}"')
    return HTML[start : HTML.index("</select>", start)]


def test_the_kind_menu_gates_what_needs_a_model_and_what_the_rule_does():
    kind = _select("draft-kind")
    assert re.findall(r'<option value="(\w+)" data-gate="model"', kind) == ["continue", "rewrite"]
    assert re.findall(r'<option value="(\w+)" data-gate="rule" hidden', kind) == ["tidy", "plain", "formal"]
    assert '<optgroup label="Translate into" data-gate="model">' in kind


def test_tone_and_length_offer_only_what_a_rule_can_honour_with_no_model():
    assert re.findall(r'<option value="(\w+)" data-gate="model"', _select("draft-tone")) == ["friendly", "punchy"]
    assert re.findall(r'<option value="(\w+)" data-gate="model"', _select("draft-length")) == ["long"]


def test_one_line_under_the_controls_and_the_refine_field_say_what_works_with_no_model():
    line = re.search(r'<p id="draft-rule-line" class="muted draft-rule-line hidden">(.*?)</p>', HTML, re.S).group(1)
    assert "no model" in line.lower() and "by rule" in line and "!" not in line and chr(0x2014) not in line
    refine = HTML[HTML.index('<input id="draft-instruction"') :][:500]
    assert 'data-offline-placeholder="Refine: “shorter”, “add a summary”, “as bullets”, “formal”, “tidy it up”"' in refine
    badge = HTML[HTML.index('id="draft-by"') :][:400]
    assert "by plain rule with no model" in badge and ">From your words<" in badge


def test_the_gate_runs_at_load_and_on_every_change_of_model():
    assert 'document.addEventListener("mm-model-gate", syncDraftGate);\nsyncDraftGate();' in DESK
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert '"saveDraftAsNote", "draftSaveMenuInit"]' in app and '"writingDesk", navigator' in app


def test_a_note_menu_offers_translate_only_with_a_model():
    menu = (ROOT / "frontend" / "js" / "menus.js").read_text(encoding="utf-8")
    assert re.search(r"\.\.\.\(aiIsOff\(\) \? \[\] : \[\{\n\s+label: \"ph:translate Translate\"", menu)


def _gated(off: bool, value: str) -> dict:
    gate = DESK[DESK.index("function gateDraftSelect") : DESK.index("function syncDraftGate")]
    script = f"""
    const draftGate = {{ kept: new WeakMap(), off: null }};
    const node = (value, gate, hidden) => ({{ value, dataset: gate ? {{ gate }} : {{}}, hidden: !!hidden }});
    const children = [node("note"), node("tidy", "rule", true), node("continue", "model"), node("plain", "rule", true), node("expand")];
    const events = [];
    const select = {{
      value: {json.dumps(value)}, children,
      get options() {{ return this.children; }},
      replaceChildren(...nodes) {{ this.children = nodes; }},
      dispatchEvent(e) {{ events.push(e.type); }},
    }};
    const $ = () => select;
    globalThis.Event = class {{ constructor(type) {{ this.type = type; }} }};
    {gate}
    gateDraftSelect(select, {str(off).lower()});
    console.log(JSON.stringify({{ values: select.children.map((n) => n.value), value: select.value, events, hidden: select.children.some((n) => n.hidden) }}));
    """
    run = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


@needs_node
def test_with_no_model_the_select_loses_model_entries_and_moves_off_one_it_was_on():
    done = _gated(True, "continue")
    assert done["values"] == ["note", "tidy", "plain", "expand"] and done["value"] == "note"
    assert done["events"] == ["change"] and not done["hidden"]
    assert _gated(True, "tidy")["events"] == []  # a kept choice stays, and says nothing


@needs_node
def test_a_model_connecting_puts_the_select_back_whole_without_the_rule_entries():
    done = _gated(False, "tidy")
    assert done["values"] == ["note", "continue", "expand"] and done["value"] == "note" and done["events"] == ["change"]
