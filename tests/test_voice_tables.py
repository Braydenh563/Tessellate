"""The app speaks in one voice (CHAT_PLAN decision 55, section 2's toasts
row): system copy moves onto the realiser's voice table surface by surface.
First the three surfaces with the most toasts (library.js 119, whiteboard.js
104, whiteboard-map.js 72): every failure is `voiceLine("failed", ...)`,
"Couldn't ..." in one register. The copy lint: no toast says "!" or "Oops"
anywhere in the app."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.ai import realise

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend/js"
MOVED = (
    "activity-panel.js",
    "ai-tools.js",
    "answer-kit.js",
    "app-import.js",
    "app.js",
    "ask-compose.js",
    "ask-history.js",
    "attachment-actions.js",
    "captions.js",
    "capture-ask.js",
    "chat-agent.js",
    "chat-attach.js",
    "chat-docs.js",
    "chat-edit.js",
    "chat-turn.js",
    "chat.js",
    "dash-night.js",
    "dashboard.js",
    "diag-report.js",
    "diagram-suggest.js",
    "documents-history.js",
    "documents-ide.js",
    "documents-prose.js",
    "documents-replace.js",
    "documents-word.js",
    "documents.js",
    "editor.js",
    "entity-page.js",
    "entry-card.js",
    "entry-menu.js",
    "file-drop.js",
    "gesture-kit.js",
    "graph-canvas.js",
    "graph.js",
    "image-layout.js",
    "library.js",
    "lightbox-actions.js",
    "lightbox-view.js",
    "margin-reader.js",
    "math-editor.js",
    "media.js",
    "meetings.js",
    "mermaid-draw.js",
    "model-bench.js",
    "note-history.js",
    "note-panels.js",
    "note-properties.js",
    "notes-list.js",
    "notifications.js",
    "onboarding.js",
    "phone-shell.js",
    "questions-view.js",
    "quick-note.js",
    "quickadd.js",
    "reminder-edit.js",
    "reply-kit.js",
    "selection.js",
    "semantic-notice.js",
    "settings-controls.js",
    "settings-data.js",
    "settings-health.js",
    "settings-models.js",
    "settings-packages.js",
    "settings-panes.js",
    "settings-wiring.js",
    "settings.js",
    "shell-reminders.js",
    "skills.js",
    "space-swap.js",
    "spaces-find.js",
    "statistics.js",
    "studio.js",
    "suggestions-inbox.js",
    "tag-manager.js",
    "tag-suggest.js",
    "update-dialogs.js",
    "usage-ledger.js",
    "web-clip.js",
    "web-results.js",
    "whiteboard-history.js",
    "whiteboard-library.js",
    "whiteboard-map-more.js",
    "whiteboard-map.js",
    "whiteboard.js",
    "wiring.js",
)


def _js_voice() -> dict:
    src = (JS / "status.js").read_text(encoding="utf-8")
    body = src[src.index("const VOICE = {"):src.index("};", src.index("const VOICE = {"))]
    return dict(re.findall(r'^\s*(\w+): "((?:[^"\\]|\\.)*)",', body, re.M))


def test_the_browsers_voice_is_the_realisers():
    assert _js_voice() == realise.VOICE


def test_the_realiser_says_a_failure_in_one_register():
    assert realise.say("failed", what="open that document") == "Couldn't open that document."
    assert realise.say("failed", what="save", why="the disk is full") == "Couldn't save: the disk is full"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_browser_says_it_the_same():
    src = (JS / "status.js").read_text(encoding="utf-8")
    table = src[src.index("const VOICE = {"):src.index("};", src.index("const VOICE = {")) + 2]
    start = src.index("function voiceLine(")
    fn = src[start:src.index("\n}\n", start) + 2]
    script = table + "\n" + fn + '\nconsole.log(JSON.stringify([voiceLine("failed", {what: "open that document"}), voiceLine("failed", {what: "save", why: "the disk is full"})]));'
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60, check=True)
    assert json.loads(out.stdout) == ["Couldn't open that document.", "Couldn't save: the disk is full"]


def test_the_moved_surfaces_fail_in_the_voice():
    calls = 0
    for name in MOVED:
        src = (JS / name).read_text(encoding="utf-8")
        calls += src.count('voiceLine("failed", ')
        for line in src.split("\n"):
            if "toast(" in line:
                assert not re.search(r'["`]Could not ', line), f"{name}: {line.strip()}"
                assert not re.search(r'["`]Couldn\'t ', line), f"{name}: a failure not through the voice: {line.strip()}"
    assert calls >= 281  # 262 before L-world-class-140, which moved the last literal template toasts


def test_no_toast_in_the_app_says_oops_or_shouts():
    found = []
    for path in sorted(JS.glob("*.js")):
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            for said in re.findall(r'toast(?:Action)?\(\s*["\'`]([^"\'`]*)', line):
                if "Oops" in said or re.search(r"!(?=\s|$)", said):
                    found.append(f"{path.name}:{number}: {said}")
    assert not found, found
