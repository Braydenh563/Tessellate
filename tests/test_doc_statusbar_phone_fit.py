"""The document status strip fits a phone in every font.

The strip clips (`overflow: hidden`) and holds one row. Its goal and findings
buttons kept their full words, so in the mono font at 390px the file type
picker ended at 397, past the screen edge and cut off by the strip
(scratchpad/ui-sweeps/fontmatrix-*.js, `#doc-type-button` off-screen). The two
buttons whose words can be shortened give way, with an ellipsis and their full
words in the title; the type picker keeps its box.
"""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "frontend" / "css" / "10-responsive.css"


def _phone_block() -> str:
    text = CSS.read_text(encoding="utf-8")
    start = text.index("@media (max-width: 599.98px) {")
    return text[start:]


def test_goal_and_findings_buttons_shrink_with_an_ellipsis_on_a_phone():
    block = _phone_block()
    shrink = re.search(r"#tab-documents \.doc-statusbar > :is\(#doc-word-goal, #doc-prose\) \{([^}]*)\}", block)
    assert shrink and "flex: 0 1 auto" in shrink.group(1) and "min-width: 0" in shrink.group(1)
    words = re.search(r"#tab-documents :is\(#doc-goal-label, #doc-prose-count\) \{([^}]*)\}", block)
    assert words and "text-overflow: ellipsis" in words.group(1) and "overflow: hidden" in words.group(1)
