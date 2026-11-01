"""Trust contract rule 1, the static half (WORLD_CLASS_PLAN 28.4): per surface,
how many top-level functions in frontend/js write to the server (a POST, PUT,
PATCH or DELETE in the body) and how many of those name an undo path
(pushUndo, wbPushUndo, a toast Undo action, or a function with 'undo' in its
own name). undo.js measures the same thing by pressing the buttons; this reads
the code, so it also counts handlers no button in the seeded notebook reaches.

    python scratchpad/ui-sweeps/measure-writes.py [--list SURFACE]

A function that calls another function which pushes the undo is counted as
having no undo path here (the reading is one body deep), so the number is a
floor for "undoable" and a ceiling for "not undoable": undo.js is the check.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SURFACES = {
    "notes list": ["notes-list.js", "note-cards.js", "selection.js", "tag-manager.js", "tidy.js", "batch-space.js"],
    "note editor": ["editor.js", "note-edit-panels.js", "note-panels.js", "note-properties.js", "note-history.js", "note-templates.js", "quick-note.js"],
    "documents": ["documents.js", "documents-code.js", "documents-prose.js", "documents-cm.js"],
    "whiteboard": ["whiteboard.js", "whiteboard-library.js", "whiteboard-templates.js", "whiteboard-commands.js", "whiteboard-format.js", "whiteboard-history.js", "whiteboard-interchange.js"],
    "mind map": ["whiteboard-map.js"],
    "graph": ["graph.js", "graph-canvas.js", "link-types.js"],
    "timeline": ["timeline.js", "meetings.js"],
    "library": ["library.js", "media.js", "lightbox.js", "web-clip.js", "skills.js"],
    "settings": ["settings.js", "settings-controls.js", "settings-data.js", "settings-models.js", "settings-packages.js", "settings-panes.js", "settings-wiring.js", "prefs.js"],
    "dashboard": ["dashboard.js", "dash-boards.js", "quick-access.js"],
    "chat": ["chat.js", "chat-agent.js", "chat-attach.js", "ask-history.js", "ask-compose.js"],
    "reminders": ["shell-reminders.js"],
}
WRITE = re.compile(r"""method:\s*["'](POST|PUT|PATCH|DELETE)["']""")
UNDO = re.compile(r"pushUndo\(|wbPushUndo\(|pushEntryPutUndo\(|[Uu]ndo")
FUNC = re.compile(r"^(\s*)(?:async\s+)?function\s+(\w+)\s*\(|^(\s*)(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?(?:function\b|\()")


def functions(path: Path):
    lines = path.read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        m = FUNC.match(line)
        if not m:
            continue
        indent = len(m.group(1) if m.group(2) else m.group(3))
        if indent > 0:
            continue
        j = i + 1
        while j < len(lines) and not (lines[j].startswith("}") or lines[j].startswith(");")):
            j += 1
        yield (m.group(2) or m.group(4)), i + 1, "\n".join(lines[i:j + 1])


def main() -> None:
    want = sys.argv[sys.argv.index("--list") + 1] if "--list" in sys.argv else None
    total_w = total_u = 0
    for surface, files in SURFACES.items():
        writes = undone = 0
        gaps = []
        for name in files:
            path = ROOT / "frontend" / "js" / name
            if not path.exists():
                continue
            for fn, line, body in functions(path):
                if not WRITE.search(body):
                    continue
                writes += 1
                if UNDO.search(body):
                    undone += 1
                else:
                    gaps.append(f"{name}:{line} {fn}")
        total_w += writes
        total_u += undone
        print(f"{surface}: write functions {writes}, with an undo path {undone}")
        if want == surface:
            for g in gaps:
                print("   no undo path:", g)
    print(f"TOTAL: write functions {total_w}, with an undo path {total_u}")


if __name__ == "__main__":
    main()
