"""Writes frontend/board-library/callouts.json (WHITEBOARD_PLAN 1355: callouts,
study boxes and notes) and its row in index.json. Run from the repo root."""

import json
from pathlib import Path

LIB = Path("frontend/board-library")


def shape(d, label=None, area=None, colour="ink", opacity=0.12, width=2, extra=None):
    data = {
        "d": d,
        "shape": "custom",
        "color": colour,
        "width": width,
        "fill": colour,
        "fillOpacity": opacity,
    }
    if label:
        data["label"] = label
    if area:
        data["label_area"] = dict(zip("xywh", area))
    data.update(extra or {})
    return {"key": "s", "kind": "sketch", "data": data, "z": 5}


def element(key, name, tags, w, h, items):
    for i, item in enumerate(items):
        item["key"] = f"p{i}"
    return {
        "key": key,
        "kind": "element",
        "name": name,
        "tags": tags,
        "payload": {"box": {"w": w, "h": h}, "items": items, "links": []},
    }


def rrect(x, y, w, h, r):
    return (
        f"M {x + r} {y} L {x + w - r} {y} A {r} {r} 0 0 1 {x + w} {y + r} L {x + w} {y + h - r} "
        f"A {r} {r} 0 0 1 {x + w - r} {y + h} L {x + r} {y + h} A {r} {r} 0 0 1 {x} {y + h - r} "
        f"L {x} {y + r} A {r} {r} 0 0 1 {x + r} {y} Z"
    )


def circle(cx, cy, r):
    return f"M {cx - r} {cy} A {r} {r} 0 1 1 {cx + r} {cy} A {r} {r} 0 1 1 {cx - r} {cy} Z"


def box(key, name, tags, colour, word):
    d = rrect(0, 0, 220, 110, 10)
    bar = "M 0 10 A 10 10 0 0 1 10 0 L 22 0 L 22 110 L 10 110 A 10 10 0 0 1 0 100 Z"
    return element(
        key,
        name,
        tags,
        220,
        110,
        [
            shape(d, f"{word}\nWrite it here", (0.14, 0.08, 0.82, 0.84), colour, 0.14),
            shape(bar, None, None, colour, 0.9, 1),
        ],
    )


ITEMS = [
    element(
        "speech-round",
        "Speech bubble",
        ["speech", "bubble", "say", "callout", "comment"],
        200,
        130,
        [
            shape(
                rrect(0, 0, 200, 100, 22) + " M 50 100 L 38 130 L 84 100 Z",
                None,
                (0.04, 0.04, 0.92, 0.7),
                "ink",
                0.12,
            )
        ],
    ),
    element(
        "speech-right",
        "Speech bubble, tail right",
        ["speech", "bubble", "say", "callout", "reply"],
        200,
        130,
        [
            shape(
                rrect(0, 0, 200, 100, 22) + " M 150 100 L 168 130 L 116 100 Z",
                None,
                (0.04, 0.04, 0.92, 0.7),
                "ink",
                0.12,
            )
        ],
    ),
    element(
        "rounded-callout",
        "Callout with a pointer",
        ["callout", "pointer", "label", "annotation", "point"],
        200,
        130,
        [
            shape(
                "M 0 0 L 200 0 L 200 90 L 120 90 L 100 130 L 80 90 L 0 90 Z",
                None,
                (0.03, 0.03, 0.94, 0.66),
                "ink",
                0.12,
            )
        ],
    ),
    element(
        "thought",
        "Thought bubble",
        ["thought", "think", "bubble", "idea", "cloud"],
        200,
        150,
        [
            shape(
                "M 40 20 C 40 -4 90 -8 100 14 C 120 -6 176 2 168 38 C 200 46 196 96 160 96 "
                "C 150 112 112 116 100 98 C 84 114 40 110 36 86 C 4 84 -4 40 40 20 Z",
                None,
                (0.12, 0.12, 0.76, 0.6),
                "ink",
                0.12,
            ),
            shape(circle(60, 122, 9), None, None, "ink", 0.12),
            shape(circle(34, 142, 5), None, None, "ink", 0.12),
        ],
    ),
    box("tip-box", "Tip box", ["tip", "hint", "remember", "study", "box"], "#2f9e44", "Tip"),
    box(
        "warning-box",
        "Warning box",
        ["warning", "careful", "watch out", "danger", "box"],
        "#e8590c",
        "Watch out",
    ),
    box(
        "info-box", "Info box", ["info", "note", "fact", "box", "key point"], "#1c7ed6", "Key point"
    ),
    box(
        "definition-box",
        "Definition box",
        ["definition", "term", "meaning", "study", "glossary"],
        "#7048e8",
        "Definition",
    ),
    box(
        "example-box",
        "Example box",
        ["example", "worked", "case", "study", "box"],
        "#0c8599",
        "Example",
    ),
    element(
        "folded-note",
        "Note with a folded corner",
        ["note", "page", "paper", "memo", "folded"],
        180,
        140,
        [
            shape(
                "M 0 0 L 140 0 L 180 40 L 180 140 L 0 140 Z",
                None,
                (0.06, 0.06, 0.88, 0.88),
                "#f59f00",
                0.2,
            ),
            shape("M 140 0 L 140 40 L 180 40 Z", None, None, "#f59f00", 0.5),
        ],
    ),
    element(
        "banner",
        "Banner",
        ["banner", "ribbon", "title", "heading", "label"],
        260,
        80,
        [
            shape(
                "M 0 10 L 30 10 L 30 0 L 230 0 L 230 10 L 260 10 L 240 40 L 260 70 L 230 70 L 230 80 L 30 80 L 30 70 L 0 70 L 20 40 Z",
                None,
                (0.14, 0.1, 0.72, 0.8),
                "ink",
                0.14,
            )
        ],
    ),
    element(
        "tag",
        "Label tag",
        ["tag", "label", "badge", "category", "pill"],
        140,
        50,
        [shape("M 0 25 L 20 0 L 140 0 L 140 50 L 20 50 Z", None, (0.18, 0, 0.8, 1), "ink", 0.14)],
    ),
    element(
        "step-marker",
        "Step marker",
        ["step", "number", "marker", "circle", "badge"],
        64,
        64,
        [shape(circle(32, 32, 30), "1", (0.1, 0.1, 0.8, 0.8), "ink", 0.2, 3)],
    ),
    element(
        "brace",
        "Curly brace",
        ["brace", "bracket", "group", "curly", "span"],
        40,
        200,
        [
            {
                "key": "p",
                "kind": "sketch",
                "data": {
                    "d": "M 4 0 C 24 0 24 20 24 50 C 24 80 24 96 40 100 C 24 104 24 120 24 150 C 24 180 24 200 4 200",
                    "shape": "line",
                    "color": "ink",
                    "width": 3,
                },
                "z": 5,
            }
        ],
    ),
    element(
        "highlight",
        "Highlight",
        ["highlight", "marker", "emphasis", "underline", "mark"],
        220,
        40,
        [shape("M 0 6 L 220 0 L 216 36 L 4 40 Z", None, None, "#fcc419", 0.45, 1)],
    ),
    element(
        "quote",
        "Quote block",
        ["quote", "quotation", "cite", "source", "block"],
        260,
        110,
        [
            shape(
                rrect(0, 0, 260, 110, 6), "“Quote”\nSource", (0.1, 0.08, 0.86, 0.84), "ink", 0.06
            ),
            shape("M 0 0 L 8 0 L 8 110 L 0 110 Z", None, None, "ink", 0.7, 1),
        ],
    ),
]

if __name__ == "__main__":
    doc = {
        "format": "memorymap-library-set",
        "version": 1,
        "key": "callouts",
        "name": "Callouts and notes",
        "items": ITEMS,
    }
    (LIB / "callouts.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    idx = json.loads((LIB / "index.json").read_text())
    idx["sets"] = [s for s in idx["sets"] if s["key"] != "callouts"]
    at = next(i for i, s in enumerate(idx["sets"]) if s["key"] == "general") + 1
    idx["sets"].insert(at, {"key": "callouts", "name": "Callouts and notes", "count": len(ITEMS)})
    (LIB / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1) + "\n")
    print(len(ITEMS))
