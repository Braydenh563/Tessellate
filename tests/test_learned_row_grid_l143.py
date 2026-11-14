"""L-chat-143: a derived fact's row is one line (chip, text and meta, actions) on a
wide screen and stacks below 600px. Measured in the app: 142px a row before, 63px."""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")


def test_the_row_is_a_grid_of_head_text_actions_with_a_narrow_stack():
    row = re.search(r"\.learned-row \{([^}]*)\}", CSS).group(1)
    assert "display: grid" in row and '"head text acts" "head meta acts"' in row
    assert "acts" in re.search(r"\.learned-row > :last-child \{([^}]*)\}", CSS).group(1)
    narrow = re.search(r"@media \(max-width: 600px\) \{\s*\.learned-row \{([^}]*)\}", CSS).group(1)
    assert '"head" "text" "meta" "acts"' in narrow
    for name in ("text", "meta"):
        rule = re.search(r"\.learned-%s \{([^}]*)\}" % name, CSS).group(1)
        assert f"grid-area: {name}" in rule and "margin: 0;" in rule
