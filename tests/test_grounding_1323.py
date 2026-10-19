"""INBOX 1323: "Grounded in" as a source list, and no raw front matter.

The owner's screenshot showed chip 1 as "--- type: Meeting date: ...": a
note's front matter printed as its title. `flattenNoteMarkdown` feeds every
note-label chip, so the strip lives there.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"


def test_note_labels_skip_front_matter():
    text = (JS / "chat-attach.js").read_text(encoding="utf-8")
    body = text[text.index("function flattenNoteMarkdown(md) {"):][:400]
    assert "stripFrontmatter(md)" in body


def test_grounding_is_a_source_list_in_the_reply_kit_css():
    lazy = (CSS / "reply-kit-lazy.css").read_text(encoding="utf-8")
    for rule in (".answer-grounding-label {", ".answer-grounding-chip .note-label-prefix {",
                 ".answer-grounding-thumbs {", "button.answer-grounding-thumb {"):
        assert rule in lazy, rule
    boot = (CSS / "03-dashboard-widgets.css").read_text(encoding="utf-8")
    assert ".answer-grounding-thumbs {" not in boot, "the thumbnails' rules moved, not copied"


def test_grounded_in_is_one_native_fold_shared_by_ask_and_chat():
    # 2026-10-19: the heading is the toggle (native details, keyboard operable),
    # remembered per browser; the one builder serves Ask and Chat, which loads
    # the lazy sheet that holds the fold's look.
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    src = (root / "frontend" / "js" / "capture-ask.js").read_text(encoding="utf-8")
    start = src.index("function renderAnswerGrounding(")
    body = src[start : start + 5000]
    assert 'fold.className = "agent-step grounding-fold"' in body
    assert 'prefs.get("grounding-fold", "open")' in body
    assert 'ensureModule("replyKit")' in body
    css = (root / "frontend" / "css" / "reply-kit-lazy.css").read_text(encoding="utf-8")
    assert ".grounding-fold > .fold-summary::before {" in css
    # the badge is the bare digit, centred by the grid
    assert "`ph:file-text ${n}`" in src and "`ph:file-text ${n}.`" not in src
