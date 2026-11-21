"""Every dialog, popover and sheet closes on Escape (WORLD_CLASS_PLAN, the
Escape lint). Three kinds of surface, three static checks:

- an overlay a script builds and gives `wireBackdropClose` has an Escape
  handler in the same file (or, for a fixed id, one beside that id);
- an overlay written in index.html (`class="... overlay"`) is named in the
  router's overlay table (router-overlays.js, which closes it on Escape) or
  beside an Escape handler;
- a native `<dialog>` closes on Escape by itself, so it must not opt out
  (`closedby="none"`) or swallow `cancel`.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = {p.name: p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend/js").glob("*.js"))}
HTML = (ROOT / "frontend/index.html").read_text(encoding="utf-8")

#: The lock screen is the one overlay Escape must not close: it is the gate.
GATE = {"lock-overlay"}


def _escape_beside(literal: str) -> bool:
    for text in JS.values():
        for match in re.finditer(re.escape(literal), text):
            if "Escape" in text[max(0, match.start() - 400):match.start() + 400]:
                return True
    return False


def test_every_built_overlay_handles_escape():
    sites = 0
    unhandled = []
    for name, text in JS.items():
        for match in re.finditer(r"wireBackdropClose\(", text):
            if text[max(0, match.start() - 9):match.start()] == "function ":
                continue
            sites += 1
            fixed = re.match(r'\$\("([\w-]+)"\)', text[match.end():])
            if fixed:
                ok = _escape_beside(f'"{fixed.group(1)}"') or f'"{fixed.group(1)}"' in JS["router-overlays.js"]
            else:
                start = max(text.rfind("\nfunction ", 0, match.start()), text.rfind("\nasync function ", 0, match.start()), 0)
                ok = "Escape" in text[start:match.start() + 3000]
            if not ok:
                unhandled.append(f"{name}:{text.count(chr(10), 0, match.start()) + 1}")
    assert sites >= 25, sites
    assert not unhandled, f"an overlay with a backdrop close and no Escape handler: {unhandled}"


def test_every_overlay_in_the_page_closes_on_escape():
    ids = re.findall(r'<div id="([\w-]+)" class="[^"]*\boverlay\b[^"]*"', HTML)
    ids += re.findall(r'<div class="[^"]*\boverlay\b[^"]*" id="([\w-]+)"', HTML)
    assert len(ids) >= 12, ids
    table = JS["router-overlays.js"]
    unhandled = [i for i in ids if i not in GATE and f'"{i}"' not in table and not _escape_beside(f'"{i}"')]
    assert not unhandled, f"an overlay in index.html that Escape leaves open: {unhandled}"


def test_a_native_dialog_is_not_made_to_ignore_escape():
    assert len(re.findall(r"<dialog\b", HTML)) >= 5
    assert 'closedby="none"' not in HTML
    for name, text in JS.items():
        assert not re.search(r'addEventListener\("cancel",[^)]*preventDefault', text), name
