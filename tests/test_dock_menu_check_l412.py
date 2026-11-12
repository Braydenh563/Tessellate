"""L412: a tick row in a dock menu matches the menu's items.

Measured in Settings, Logs, More at 1440 (probe logsm.js): ticks were 8px in,
14.72px type, 2.4px corners against the items' 12.8px, 13.6px and 4.8px,
because `.settings-section label` outranked `.dock-menu-check`. After: all
three equal."""

from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css" / "07-whiteboard-misc.css"


def test_tick_rows_wear_the_menu_items_padding_corner_and_size():
    """Source text: label.dock-menu-check sets the item's padding, radius and size."""
    block = CSS.read_text(encoding="utf-8").split("\nlabel.dock-menu-check {", 1)[1].split("}", 1)[0]
    assert "padding: var(--space-2) var(--space-5);" in block
    assert "border-radius: var(--radius-md);" in block
    assert "font-size: var(--text-md);" in block
