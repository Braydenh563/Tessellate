"""One phase vocabulary for every chat surface (INBOX 649).

The owner: the "thinking..." text "should change based on the state like for if
it is waiting for the first token, thinking, or writing etc. maybe the wording
can be more atlas themed". The words are decided (the INBOX entry), the table
is `PROGRESS_PHASES` in chat.js, and the one place the stream's events meet it
is `streamChat` in capture-ask.js. The table is run in node here; the callers
are held as source ratchets, and `scratchpad/ui-sweeps/phases.js` drives the
real app against a fake server.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import with_pieces

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CHAT = with_pieces("chat.js")
ASK = with_pieces("capture-ask.js")
ATTACH = with_pieces("chat-attach.js")
#: The turn's own code (chat-attach.js and chat-turn.js), without answer-kit.js,
#: which holds the client that legitimately says `phase("writing")`.
ATTACH_OWN = (JS / "chat-attach.js").read_text(encoding="utf-8") + (JS / "chat-turn.js").read_text(encoding="utf-8")
KIT = (JS / "answer-kit.js").read_text(encoding="utf-8")
PALETTE = (JS / "palette.js").read_text(encoding="utf-8")
HELP = (JS / "help-chat.js").read_text(encoding="utf-8")
DOCS = (JS / "documents.js").read_text(encoding="utf-8")


def _table_in_node(names: list[str]) -> dict:
    """Run the table's own source, not a copy of it."""
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    start = CHAT.index("const PROGRESS_PHASES = {")
    end = CHAT.index("function typingDots(")
    script = (
        "const personaDisplayName = (n) => (!n || n === 'Librarian' ? 'Atlas' : n);\n"
        + CHAT[start:end]
        + KIT[KIT.index("function toolPhaseVerb(") : KIT.index("\n}\n", KIT.index("function toolPhaseVerb(")) + 3]
        + f"\nconsole.log(JSON.stringify({{{', '.join(names)}}}));\n"
    )
    run = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_the_decided_words_for_every_phase():
    out = _table_in_node(
        [
            'reaching: progressPhaseText("reaching")',
            'loading: progressPhaseText("loading")',
            'engine: progressPhaseText("engine")',
            'reading: progressPhaseText("reading")',
            'thinking: progressPhaseText("thinking")',
            'writing: progressPhaseText("writing")',
            'tool: progressPhaseText("tool", null, "searching notes for “x”")',
            'toolBare: progressPhaseText("tool")',
            'unknown: progressPhaseText("nonsense")',
        ]
    )
    assert out == {
        "reaching": "Reaching Atlas…",
        "loading": "Waking the model…",
        "engine": "Working it out without a model…",
        "reading": "Reading your notes…",
        "thinking": "Atlas is thinking…",
        "writing": "Atlas is writing…",
        "tool": "Atlas is searching notes for “x”…",
        "toolBare": "Atlas is using a tool…",
        "unknown": None,
    }


def test_a_persona_name_replaces_atlas_and_the_old_librarian_name_does_not():
    out = _table_in_node(
        [
            'coach: progressPhaseText("writing", "Coach")',
            'old: progressPhaseText("thinking", "Librarian")',
            'reach: progressPhaseText("reaching", "Analyst")',
            'load: progressPhaseText("loading", "Coach")',
        ]
    )
    assert out["coach"] == "Coach is writing…"
    assert out["old"] == "Atlas is thinking…"
    assert out["reach"] == "Reaching Analyst…"
    # The two phases that name no one stay the same for everyone.
    assert out["load"] == "Waking the model…"


def test_the_indicator_has_two_shapes_and_only_writing_gets_the_trace():
    body = CHAT[CHAT.index("function typingDots(") : CHAT.index("\n}\n", CHAT.index("function typingDots("))]
    # Both branches (dots and the stepped word) derive the shape the same way.
    assert body.count('const next = phase === "writing" ? "writing" : "thinking";') == 2
    assert "PROGRESS_PHASES[phase]?.visual" not in body


def test_a_tool_label_becomes_a_verb_phrase():
    out = _table_in_node(
        [
            'listed: toolPhaseVerb("ph:books Listed notes (3)")',
            'searched: toolPhaseVerb("ph:magnifying-glass Searched notes for “x”")',
            'tagged: toolPhaseVerb("Tagged note #4")',
            'saved: toolPhaseVerb("ph:floppy-disk Saved note #9")',
            'read: toolPhaseVerb("Read note #3 in full")',
            'found: toolPhaseVerb("ph:brain Found 4 similar notes to #2")',
            'took: toolPhaseVerb("Took a snapshot")',
            'noVerb: toolPhaseVerb("No path between #1 and #2")',
            'empty: toolPhaseVerb("")',
            'nothing: toolPhaseVerb(null)',
        ]
    )
    assert out["listed"] == "listing notes (3)"
    assert out["searched"] == "searching notes for “x”"
    assert out["tagged"] == "tagging note #4"
    assert out["saved"] == "saving note #9"
    assert out["read"] == "reading note #3 in full"
    assert out["found"] == "finding 4 similar notes to #2"
    assert out["took"] == "taking a snapshot"
    assert out["noVerb"] is None and out["empty"] is None and out["nothing"] is None


def test_the_label_is_a_node_of_its_own_and_the_stepped_word_does_not_repeat_it():
    # Readable with motion off: `progressLine` always draws the label, and under
    # the stepped indicator it clips that indicator's word instead of doubling.
    line = CHAT[CHAT.index("function progressLine(") :]
    assert 'label.className = "progress-line-label"' in line
    assert 'indicator.classList.contains("typing-dots-stepped")' in line
    assert 'wrap.classList.add("progress-line-still")' in line
    css = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))
    assert ".progress-line-still > .progress-line-label {" in css


def test_set_phase_drives_the_words_and_the_shape_together():
    line = CHAT[CHAT.index("function progressLine(") :]
    set_phase = line[line.index("wrap.setPhase = (phase, detail) => {") :]
    set_phase = set_phase[: set_phase.index("\n  };") + 5]
    assert "indicator.setPhase?.(phase, detail)" in set_phase
    assert "progressPhaseText(phase, opts.persona, detail)" in set_phase
    assert "wrap.setStatus(text)" in set_phase


def test_the_stream_client_maps_each_event_to_a_phase():
    wrapper = ASK[ASK.index("function streamChat(options)") : ASK.index("async function streamChatEvents(")]
    assert 'phase("reaching")' in wrapper  # the request leaving
    assert 'phase("reading")' in wrapper  # status: searching, and meta with notes
    assert 'phase("loading")' in wrapper  # quiet after meta
    #: INBOX 801: with no model connected nothing is woken.
    assert 'if (meta?.ollama_running === false) {\n        phase("engine");' in wrapper
    assert 'phase("thinking")' in wrapper  # reasoning deltas
    assert 'phase("writing")' in wrapper  # answer deltas
    assert 'phase("tool", event.ok ? toolPhaseVerb(event.label) : null)' in wrapper
    assert "MODEL_LOAD_HINT_MS" in wrapper
    # The timer cannot outlive the turn.
    assert ".finally(() => clearTimeout(timer))" in wrapper
    # And the raw reader hands over the server's first byte instead of dropping it.
    assert 'event.type === "status" && onStatus' in ASK


def test_every_streaming_caller_hands_its_line_to_the_client():
    assert "progress: pendingLine," in ATTACH
    assert "progress: askLine," in PALETTE
    assert "streamChat({\n      progress,\n" in ASK
    # None of them keeps a vocabulary of its own any more.
    for src in (ATTACH, ASK):
        assert 'say("Writing the answer…")' not in src
        assert 'say("The model is' not in src
        assert "const say = " not in src
    assert 'phase("writing")' not in ATTACH_OWN


def test_no_surface_opens_on_the_old_word():
    for name, src in {"attach": ATTACH, "palette": PALETTE, "help": HELP, "documents": DOCS}.items():
        assert not re.search(r'(progressLine|typingDots)\("Thinking…"', src), name
    assert 'setLabel(status, "ph:spin Thinking…")' not in DOCS
    assert 'progressPhaseText("reaching")' in DOCS
    assert "progressLine(null, { persona: sentPersona, words: true })" in ATTACH
    assert "progressLine(null, { persona: askedPersona, words: true })" in PALETTE
    assert "progressLine(null, { persona: GUIDE_NAME })" in HELP


def test_the_guide_drives_its_own_stream_through_the_same_line():
    turn = HELP[HELP.index("async function helpChatStreamTurn(") :]
    assert 'line?.setPhase("thinking")' in turn
    assert 'line?.setPhase("writing")' in turn
    assert "line?.remove()" in turn
