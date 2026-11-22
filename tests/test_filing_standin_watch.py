"""A stand-in filing is followed to the model's answer (found driving a real
model, Qwen2.5 1.5B on llama-server, 2026-10-05).

With a slow model the note is filed by its words first (`standin`) and the
model's answer replaces it when it lands (entry/filing_background.py, `_LateFiling`).
`watchFiling` stopped at the first answer that was not `pending`, so the
composer's line and the toast said the stand-in ("Filed under “Health” (69%
sure)") and nothing ever said the model then moved it: measured, a note about
shin splints was moved from Health to Work at "100%" and the line still read
Health. Now the line says the stand-in is for now, the watch keeps going, and
a move is said with a way to put it back.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js" / "capture-ask.js"


def _function(source: str, head: str) -> str:
    start = source.index(head)
    end = source.index("\n}\n", start) + 3
    return source[start:end]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_watch_follows_a_stand_in_to_the_models_answer():
    source = JS.read_text(encoding="utf-8")
    parts = [
        _function(source, "async function watchFiling(entry, { quiet = false } = {}) {"),
        _function(source, "function settleCaptureStatus("),
        _function(source, "function filingOutcomeText(status) {"),
        _function(source, "function filedByText(saved) {"),
    ]
    script = (
        """
const Node = { TEXT_NODE: 3 };
const REVIEW_THRESHOLD = 50;
const FILING_POLL_STEPS = [1];
const FILING_WATCH_LIMIT_MS = 5000;
const filingWatches = new Set();
const modelStatus = { ollama_running: true };
const toasts = [];
const moved = [];
const answers = [
  { id: 7, filing_state: "pending", category: "Uncategorised" },
  { id: 7, filing_state: "standin", category: "Health", filed_by: "words", ai_confidence: 69 },
  { id: 7, filing_state: "standin", category: "Health", filed_by: "words", ai_confidence: 69 },
  { id: 7, filing_state: "auto", category: "Work", filed_by: "llm", ai_confidence: 100 },
];
let polls = 0;
async function apiJson() { return answers[Math.min(polls++, answers.length - 1)]; }
const text = { nodeType: 3, nodeValue: "" };
const line = { firstChild: text, dataset: { entryId: "7" }, offsetParent: {}, querySelector: () => null, querySelectorAll: () => [], appendChild() {} };
function $(id) { return id === "save-status" ? line : null; }
function aiNameNow() { return "Atlas"; }
function aiIsOff() { return false; }
function toastAction(message, label, run) { toasts.push([message, label]); run && moved.push(run); }
function flashEntry() {}
function chooseNoteCategory() {}
async function moveNotesToCategory(ids, name) { moved.push([ids, name]); return true; }
async function refreshEntries() {}
function setLabel() {}
function smallButton() { return { classList: { add() {} } }; }
"""
        + "\n".join(parts)
        + """
text.nodeValue = filedByText({ filing_state: "pending" });
(async () => {
  await watchFiling({ id: 7 });
  const lines = { line: text.nodeValue, toasts, polls };
  // The toast's action puts it back where the stand-in had it.
  const undo = toasts.find((t) => /moved it/.test(t[0]));
  if (undo) { const run = moved.find((m) => typeof m === "function"); if (run) await run(); }
  lines.moved = moved.filter((m) => Array.isArray(m));
  console.log(JSON.stringify(lines));
})();
"""
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout.strip().splitlines()[-1])
    assert out["polls"] == 4, f"the watch stopped at the stand-in: {out}"
    assert "Work" in out["line"], f"the line still says the stand-in: {out}"
    assert any("moved it" in t[0] and "Health" in t[0] and "Work" in t[0] for t in out["toasts"]), out
    assert out["moved"] == [[[7], "Health"]], out
