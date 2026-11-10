"""The Diagram builder's slow first open and the close that "did not work" (the owner, 2026-11-09: "I clicked the
diagram builder quick access button and it didt open for liek 10 seconds. also when I tried to close the diagram
builder panel after, I clicked it multiple times and it didnt close until like 15 seconds later").

Measured (agent dglag-1109, Playwright on a fresh start, CPU throttled 8x so a frame costs what the owner's log
shows): three presses while the first open was still fetching its code made three identical dialogs, and each X
closed one (262, 225 and 113 ms each), so the window looked as if it would not close. The open itself waits on the
Library bundle (33 files, 5 MB) and the builder's own files; no server request in it waits on the search model,
whose warm-up holds off while requests arrive (tests/test_embedding_warmup.py) and runs on its own thread.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from tessellate.ai import embeddings

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _embed_open(script: str):
    """Run diagram-embed.js in a bare context whose `ensureModule` is pending until the test settles it."""
    prog = (
        "const vm=require('vm');const calls=[];let settle=[];"
        "const ctx={diagramModel:{},console,calls,toast:()=>undefined,"
        "ensureModule:(n)=>(calls.push(n),new Promise((r)=>settle.push(r)))};"
        "ctx.settleAll=(v)=>{const s=settle;settle=[];s.forEach((r)=>r(v));};"
        "vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-embed.js'))},'utf8'),ctx);"
        f"(async()=>{{const out=await vm.runInContext({json.dumps(script)},ctx);process.stdout.write(JSON.stringify(out));}})();"
    )
    done = subprocess.run(["node", "-e", prog], capture_output=True, text=True, check=True, timeout=30)
    return json.loads(done.stdout)


@needs_node
def test_a_second_press_while_the_builder_is_opening_opens_no_second_dialog():
    got = _embed_open(
        "(async () => { const a = diagramModel.embed.open({}); const b = diagramModel.embed.open({});"
        " return { same: a === b, loads: calls.filter((n) => n === 'diagramBuilder').length }; })()"
    )
    assert got == {"same": True, "loads": 1}


@needs_node
def test_a_builder_that_failed_to_load_does_not_hold_the_door_shut():
    got = _embed_open(
        "(async () => { const a = diagramModel.embed.open({}); settleAll(false); await a;"
        " diagramModel.embed.open({}); return calls.filter((n) => n === 'diagramBuilder').length; })()"
    )
    assert got == 2


def test_closing_the_builder_frees_the_door_before_anything_awaits():
    """`leave` (every way out: X, Cancel, Done, Escape, Open an existing diagram) lets the next press open a new one."""
    text = (JS / "diagram-embed.js").read_text(encoding="utf-8")
    leave = re.search(r"const leave = \(\) => \{(.*?)\n    \};", text, re.S)
    assert leave and "current = null" in leave.group(1)
    # The X is the dialog head's, wired as the dialog is built: no await sits between building it and putting it up.
    build = text[text.index("const head = dialogHead(title, () => finish(false));") : text.index("document.body.append(overlay);")]
    assert "await" not in build


def test_a_quick_access_tile_says_it_is_working_and_takes_no_second_press():
    text = (JS / "dashboard.js").read_text(encoding="utf-8")
    body = text[text.index("function quickLinkButton(") : text.index("async function saveQuickAccess(")]
    assert re.search(r"setBusy\(button, true\)", body)
    assert re.search(r"setBusy\(button, false\)", body)


def test_the_builder_script_is_served_while_the_search_model_is_loading(client, monkeypatch):
    """The leading theory (the open waits on a request queued behind the model load) is pinned false: with the warm-up's
    load held open, the builder's script and the health probe still answer."""
    monkeypatch.setattr(embeddings, "_warmup", {"running": False, "started": False, "error": False})
    monkeypatch.setattr(embeddings, "WARMUP_DELAY_SECONDS", 0)
    monkeypatch.setattr(embeddings, "_pulse", {"at": 0.0})
    monkeypatch.setattr(embeddings, "_notebook_has_notes", lambda _f: True)
    monkeypatch.setattr(embeddings, "backfill_missing", lambda *_a, **_k: None)
    loading, release = threading.Event(), threading.Event()

    class SlowLoad:
        def embed_text(self, _text):
            loading.set()
            release.wait(10)

    embeddings.start_warmup(SlowLoad(), session_factory=lambda: None)
    try:
        assert loading.wait(5), "the warm-up never started its load"
        assert client.get("/js/diagram-embed.js").status_code == 200
        assert client.get("/health").status_code == 200
        assert embeddings.warmup_running()
    finally:
        release.set()
