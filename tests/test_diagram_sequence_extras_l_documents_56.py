"""L-documents-56: sequence autonumber, box, create and destroy, and a rect's colour are the builder's own."""

from __future__ import annotations

from pathlib import Path

from tests.test_diagram_kinds import _run

ROOT = Path(__file__).resolve().parents[1]
SRC = (
    "sequenceDiagram\n  autonumber\n  box Aqua Backend\n    participant A\n    actor B\n  end\n  participant C\n"
    "  A->>B: hi\n  create participant D as Dee\n  B->>D: make\n  destroy D\n  D-->>B: bye\n"
    "  rect rgba(0, 128, 0, 0.3)\n    A->>C: tint\n  end\n"
)


def _go(src):
    return _run(
        f"""const A = diagramKinds.sequence;
const m = A.parse({src!r});
const once = m && A.print(m);
console.log(JSON.stringify({{ ok: Boolean(m), m, once, stable: Boolean(m) && A.print(A.parse(once)) === once }}));"""
    )


def test_box_create_destroy_and_autonumber_are_read_not_kept():
    got = _go(SRC)
    assert got["ok"] and got["m"]["autonumber"] is True
    boxes = {p["id"]: p.get("box") for p in got["m"]["participants"]}
    assert boxes["A"] == boxes["B"] == "Aqua Backend" and boxes["C"] is None
    steps = [s for s in got["m"]["steps"] if s["type"] == "m"]
    assert steps[1]["create"] == "D" and steps[2]["destroy"] == "D"


def test_they_print_back_in_order_and_are_stable():
    got = _go(SRC)
    lines = got["once"].splitlines()
    assert lines.index("  autonumber") < lines.index("  box Aqua Backend")
    assert "  create participant D as Dee" in lines and "  destroy D" in lines
    assert lines.index("  create participant D as Dee") == lines.index("  destroy D") - 2
    assert got["stable"]


def test_an_unplaceable_create_and_a_late_autonumber_stay_as_they_were():
    assert _go("sequenceDiagram\n  participant A\n  create participant B\n  Note over A: x\n")["ok"] is False
    late = _go("sequenceDiagram\n  A->>B: x\n  autonumber\n")
    assert "autonumber" not in late["m"] and late["once"].count("autonumber") == 1


def test_the_menus_offer_box_lifetime_numbering_and_a_rect_colour():
    js = (ROOT / "frontend/js/diagram-kinds.js").read_text(encoding="utf-8")
    for word in ("Box…", '"Lifetime"', "Number the messages", "Colour of the highlight"):
        assert word in js
