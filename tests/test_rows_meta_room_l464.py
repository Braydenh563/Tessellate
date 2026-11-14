"""Source text: LEDGER L464, "uipolish leftovers: rows-view 28px meta button"
(uipolish: "a rows-view meta icon button is 28px in a 24px line").

Measured 2026-11-13 at 1440 in rows view: the meta line was 24px with
`overflow-y: hidden`, so its 28px (`--target-min`) icon buttons stood 2px out
at the top and bottom and their hover face and focus ring were cut. With
2px of block padding the line is 28px, the buttons sit 0px inside it, and the
row stays 45px.
"""

from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css" / "01-forms-settings.css"


def test_the_rows_meta_line_has_room_for_a_target_sized_button():
    css = CSS.read_text(encoding="utf-8")
    rule = css[css.index(".entry-list.is-rows .entry-meta {") :]
    rule = rule[: rule.index("}")]
    assert "padding-block: 2px;" in rule
    assert "overflow-y: hidden;" in rule
