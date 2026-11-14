"""L-chat-184: skills do not activate or get suggested with no model; one test per state.

The owner: "I can still activate skills and the suggested skill popup still
appears when I have no model running". Runs the real nudge, menu and run
functions of skills.js under node with stubbed page globals.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._js_functions import function_spans

SRC = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "skills.js").read_text(encoding="utf-8")
WANTED = ("skillMatchingDraft", "renderChatNudge", "fillSkillSelect", "runSkill", "allSkills", "looksLikeAnAgentRequest")

SKILLS = [
    {"name": "Weekly review", "description": "summarise recent notes", "composer": True, "builtin": True},
    {"name": "Tidy categories", "description": "reorganise categories", "builtin": True},
]


def _fn(name: str) -> str:
    for start, end, n in function_spans(SRC):
        if n == name:
            head = SRC.rfind("\nfunction ", 0, start) + 1
            return SRC[head : end + 1]
    raise AssertionError(name)


def run(off: bool, tools: bool, draft: str, pick: str | None = None) -> dict:
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    consts = "\n".join(
        SRC[SRC.index(name) : SRC.index(";\n", SRC.index(name)) + 1]
        for name in ("const AGENT_INTENT_RE", "const AGENT_WEB_RE", "const AGENT_OBJECT_RE")
    )
    script = f"""
const off = {json.dumps(off)}, tools = {json.dumps(tools)};
const els = {{ "chat-nudge": {{ classList: {{ toggle(c, v) {{ this.hidden = v; }} }}, replaceChildren() {{ this.kids = []; }}, append(...k) {{ this.kids = k; }} }},
  "chat-input": {{ value: {json.dumps(draft)} }}, "tools-toggle": {{ checked: tools }} }};
const $ = (id) => els[id];
const aiIsOff = () => off;
const toasts = []; const toast = (m, k) => toasts.push([m, k]);
const mk = () => {{ const e = {{ kids: [], classList: {{ add() {{}}, toggle() {{}} }}, appendChild(c) {{ this.kids.push(c); }}, replaceChildren() {{ this.kids = []; }}, setAttribute() {{}}, closest: () => null }};
  Object.defineProperty(e, "options", {{ get() {{ return this.kids.flatMap((k) => (k.kids.length ? k.kids : [k])); }} }}); return e; }};
const document = {{ createElement: mk }};
const setLabel = () => {{}}; const smallButton = (l) => ({{ classList: {{ add() {{}} }}, label: l }});
const skillsCache = {json.dumps(SKILLS)}; const SKILL_MANAGE_VALUE = "__manage";
const skillSummary = (s) => s.name; const started = [];
const askSkillInputs = () => {{}}; const startSkill = (s) => started.push(s.name);
{consts}
const chatNudgeDismissed = new Set();
{"".join(_fn(n) + chr(10) for n in WANTED)}
renderChatNudge();
const nudge = els["chat-nudge"];
const select = document.createElement("select"); select.value = ""; fillSkillSelect(select);
const opts = select.options.filter((o) => o.value);
runSkill(skillsCache.find((s) => s.name === {json.dumps(pick)}) || skillsCache[0]);
console.log(JSON.stringify({{ offered: (nudge.kids || []).some((k) => /You have a skill/.test(k.textContent || "")), started, toasts: toasts.map((t) => t[1]),
  disabled: opts.filter((o) => o.disabled).map((o) => o.value) }}));
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


DRAFT = "please run the weekly review summarise recent notes"


def test_no_model_tools_on_offers_no_skill_and_runs_no_model_skill_never():
    got = run(off=True, tools=True, draft=DRAFT, pick="Tidy categories")
    assert got["offered"] is False
    assert got["started"] == [] and got["toasts"] == ["info"]
    assert got["disabled"] == ["Tidy categories"]


def test_no_model_tools_off_offers_no_skill():
    assert run(off=True, tools=False, draft=DRAFT)["offered"] is False


def test_model_up_tools_off_offers_no_skill():
    assert run(off=False, tools=False, draft=DRAFT)["offered"] is False


def test_model_up_tools_on_offers_the_skill_and_runs_any_skill():
    got = run(off=False, tools=True, draft=DRAFT, pick="Tidy categories")
    assert got["offered"] is True
    assert got["started"] == ["Tidy categories"] and got["toasts"] == [] and got["disabled"] == []


def test_no_model_still_runs_a_skill_the_composer_can_read_off_the_notes():
    got = run(off=True, tools=True, draft="", pick="Weekly review")
    assert got["started"] == ["Weekly review"] and got["toasts"] == []
