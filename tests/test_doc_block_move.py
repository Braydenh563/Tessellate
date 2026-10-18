"""Alt+Up and Alt+Down move a block of a markdown document (INBOX 904 B20).

The owner asked for a manage mode for lined documents: rearrange by line or
element. The default line move already exists, but in prose it welds two
paragraphs together (`alpha`, blank, `beta`: Alt+Up on beta swaps it with the
blank line, not with alpha). The block move treats a paragraph, a list item
with its children, a fenced block or a heading's whole section as the unit, and
swaps it with its neighbour of the same kind, leaving the blank lines where they
were. The model is pure string work, run here in node; the key in the editor is
`scratchpad/ui-sweeps/docblockmove1018.js`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    i = DOCS.index(f"function {name}(")
    return DOCS[i : DOCS.index("\n}\n", i) + 3]


DRIVER = r"""
const out = [];
const eq = (name, got, want) => out.push({ name, ok: JSON.stringify(got) === JSON.stringify(want), got });
// Apply a move at the caret marked by `|`; the result carries the caret too.
function move(marked, delta, mark = "|") {
  const offset = marked.indexOf(mark);
  const text = marked.replace(mark, "");
  const edit = docBlockMoveEdit(text, offset, delta);
  if (!edit) return null;
  if (edit.noop) return { noop: true };
  const next = text.slice(0, edit.from) + edit.insert + text.slice(edit.to);
  return next.slice(0, edit.caret) + mark + next.slice(edit.caret);
}

// Paragraphs: the blank lines stay where they were.
eq("paragraph up", move("alpha\n\nbe|ta\n\ngamma\n", -1), "be|ta\n\nalpha\n\ngamma\n");
eq("paragraph down", move("al|pha\n\nbeta\n\ngamma\n", 1), "beta\n\nal|pha\n\ngamma\n");
eq("a multi-line paragraph is one block", move("one\ntwo\n\nth|ree\nfour\n", -1), "th|ree\nfour\n\none\ntwo\n");
eq("first block cannot go up", move("al|pha\n\nbeta\n", -1), { noop: true });
eq("last block cannot go down", move("alpha\n\nbe|ta\n", 1), { noop: true });
eq("a blank line is left to the default move", move("alpha\n|\nbeta\n", 1), null);
eq("the gap is untouched", move("a|\n\n\n\nb\n", 1), "b\n\n\n\na|\n");

// Lists: an item with its children swaps with the item beside it.
eq("item up", move("- a\n- b|\n- c\n", -1), "- b|\n- a\n- c\n");
eq("item down", move("- a|\n- b\n- c\n", 1), "- b\n- a|\n- c\n");
eq("children go with the item", move("- a|\n  - a1\n  - a2\n- b\n", 1), "- b\n- a|\n  - a1\n  - a2\n");
eq("a nested item moves among its siblings", move("- a\n  - x\n  - y|\n- b\n", -1), "- a\n  - y|\n  - x\n- b\n");
eq("a nested item stops at its parent", move("- a\n  - x|\n- b\n", -1), { noop: true });
eq("numbers stay in order", move("1. one\n2. tw|o\n3. three\n", -1), "1. tw|o\n2. one\n3. three\n");
eq("numbers stay in order, down", move("1. o|ne\n2. two\n", 1), "1. two\n2. o|ne\n");
eq("a loose list keeps its blank lines", move("- a\n\n- b|\n\n- c\n", -1), "- b|\n\n- a\n\n- c\n");
eq("a task item", move("- [ ] a\n- [x] b|\n", -1), "- [x] b|\n- [ ] a\n");

// Headings move as sections among the siblings of their own level.
const doc = "# Top\n\n## One\n\nbody one\n\n### Deep\n\ndeep\n\n## Two\n\nbody two\n\n## Three\n\nbody three\n";
eq("section down", move("# Top\n\n## O|ne\n\nbody one\n\n### Deep\n\ndeep\n\n## Two\n\nbody two\n\n## Three\n\nbody three\n", 1),
  "# Top\n\n## Two\n\nbody two\n\n## O|ne\n\nbody one\n\n### Deep\n\ndeep\n\n## Three\n\nbody three\n");
eq("section up takes its children", move("# Top\n\n## One\n\nbody one\n\n### Deep\n\ndeep\n\n## Tw|o\n\nbody two\n\n## Three\n\nbody three\n", -1),
  "# Top\n\n## Tw|o\n\nbody two\n\n## One\n\nbody one\n\n### Deep\n\ndeep\n\n## Three\n\nbody three\n");
eq("the last section moves up without welding", move("## A\n\nbody a\n\n## B|\n\nbody b", -1), "## B|\n\nbody b\n\n## A\n\nbody a");
eq("a section with no sibling stays put", move("# To|p\n\ntext\n", 1), { noop: true });
eq("a section does not leave its parent", move("# Top\n\n## On|e\n\nx\n\n# Next\n\n## Other\n", 1), { noop: true });

// Fenced code is one block, blank lines inside it included.
eq("a fence is one block", move("intro\n\n```\na\n\nb\n```\n\nou|tro\n", -1), "intro\n\nou|tro\n\n```\na\n\nb\n```\n");
eq("inside a fence moves the fence", move("intro\n\n```\na\n|\nb\n```\n", -1), "```\na\n|\nb\n```\n\nintro\n");
eq("a hash inside a fence is not a heading", move("para\n\n```\n# not a heading|\n```\n", -1), "```\n# not a heading|\n```\n\npara\n");

// A table, a quote and a callout are blocks like any other paragraph.
eq("a table is one block", move("text\n\n| a | b |\n| - | - |\n| 1 | ^2 |\n\nend\n", -1, "^"), "| a | b |\n| - | - |\n| 1 | ^2 |\n\ntext\n\nend\n");

// Frontmatter is never moved and nothing moves past it.
eq("frontmatter stays first", move("---\ntitle: x\n---\n\nal|pha\n\nbeta\n", -1), { noop: true });
eq("the caret in frontmatter is the default move's", move("---\ntit|le: x\n---\n\nalpha\n", 1), null);

// One step each way is a round trip, byte for byte.
const there = move("alpha\n\nbe|ta\n\ngamma\n", -1).replace("|", "");
eq("round trip", move(there.replace("beta", "be|ta"), 1).replace("|", ""), "alpha\n\nbeta\n\ngamma\n");
eq("a section round trip", (() => {
  const a = move("## A\n\nbody a\n\n## B|\n\nbody b", -1).replace("|", "");
  return move(a.replace("## B", "## B|"), 1).replace("|", "");
})(), "## A\n\nbody a\n\n## B\n\nbody b");
process.stdout.write(JSON.stringify(out));
"""


def _run() -> list:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    source = "\n".join(_fn(name) for name in ("docScanHeadings", "docSectionRange", "docBlockMoveEdit"))
    out = subprocess.run([node, "-e", source + DRIVER], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_block_move_model() -> None:
    bad = [row for row in _run() if not row["ok"]]
    assert not bad, bad


def test_the_keys_and_the_palette_are_wired() -> None:
    keymap = _fn("docCmKeymap")
    assert 'key: "Alt-ArrowUp"' in keymap and 'key: "Alt-ArrowDown"' in keymap
    run = _fn("docBlockMoveRun")
    assert "previewable" in run and "docBlockMoveEdit(" in run
    # A code file keeps the editor's own line move.
    assert "return false" in run
    assert 'id: "move-block-up"' in DOCS and 'id: "move-block-down"' in DOCS
