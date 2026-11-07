"""The value field's second Escape hands the focus back to its slider, never to the page (agent-remaining/value-field-1107.md:
"after the second Escape leaves a field inside a panel, focus lands on the page (BODY) instead of the slider")."""

from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "value-field.js").read_text(encoding="utf-8")


def test_second_escape_focuses_the_fields_home():
    assert "if (!input.vfRevert()) leave();" in SRC
    leave = SRC[SRC.index("const leave = () =>"):]
    leave = leave[: leave.index("};")]
    assert "home.focus()" in leave and "isConnected" in leave and "input.blur()" in leave


def test_a_slider_field_names_its_slider_as_home():
    assert "home: () => slider," in SRC
