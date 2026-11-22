"""The Suggest links rows put the note icon on the words' cap-height centre.

Owner: the note icon sits higher than the title in each option row. An icon
beside words takes `.ph-lead` (DESIGN.md, "An icon beside words"): in a font
whose ascent is tall (Segoe UI) the flex row's box centre is above the
capitals, and `.ph-lead` moves the icon by the measured gap. Measured with
`scratchpad/ui-sweeps/graph-theme-suggest.js` (FONT metrics of Segoe UI):
cap-centre offset 0.63 px before, 0.03 px after.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_suggestion_rows_put_the_note_icon_on_the_words() -> None:
    js = (ROOT / "frontend" / "js" / "suggestions-inbox.js").read_text(encoding="utf-8")
    assert 'inboxEl("i", "ph ph-note ph-lead")' in js
