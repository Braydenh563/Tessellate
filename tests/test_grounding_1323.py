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
