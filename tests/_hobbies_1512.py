"""The owner's Hobbies notebook from INBOX 1512, as notes the composer reads:
an untitled gaming mouse note with a picture, two sketches linked with a
slangy lowercase reason, a legs split, and links whose reasons are in the
first person."""

from __future__ import annotations

from datetime import date

TODAY = date(2026, 11, 1)


def _pictures(name: str, caption: str) -> str:
    return f"\n\n[Pictures in this note, as this app read them:\n- {name}: shows {caption}]"


MOUSE = ("I just bought a new gaming mouse from JB Hi-Fi and it has eleven buttons and RGB lighting. It cost $79.\n\n![](/media/mouse.jpg)"
         + _pictures("mouse.jpg", "A photo depicts a black gaming mouse with RGB lighting on a desk"))
LAPTOP = "My laptop is an ASUS ROG Strix G16 with an RTX 4060. I use it for gaming and for uni."
DRAGON = "# Dragon sketch\n\n![](/media/dragon.png)" + _pictures("dragon.png", "The image depicts a pencil sketch of a dragon with its wings spread")
CAT = "![](/media/cat.png)" + _pictures("cat.png", "a cartoon cat drawn in black pen")
LEGS = ("# Legs day\n\nWarm up: five minutes on the bike and leg swings\n\n"
        "The split follows this structure: squats 4x8, Romanian deadlifts 3x10, lunges 3x12 and calf raises 4x15")
GYM = "Go to the gym at 9pm on Tuesday with Sam for legs"

#: (content, tags, written, {linked index: reason})
NOTES = [
    (MOUSE, ["gaming"], "2026-10-20T18:00:00", {1: "the mouse is used as my gaming mouse on my laptop"}),
    (LAPTOP, ["gaming"], "2026-10-02T18:00:00", {}),
    (DRAGON, ["art"], "2026-10-11T20:00:00", {3: "they are both random ass sketches lol"}),
    (CAT, ["art"], "2026-10-12T20:00:00", {}),
    (LEGS, ["gym"], "2026-10-05T07:00:00", {5: "Shared Tuesday 9pm legs training"}),
    (GYM, ["gym"], "2026-10-06T07:00:00", {}),
]
SCORES = (0.7, 0.66, 0.64, 0.62, 0.6, 0.58)


def notes() -> list[dict]:
    """The Hobbies notes as the route hands them over, links both ways."""
    out = [{"id": n + 1, "content": c, "category": "Hobbies", "tags": t, "created_at": w,
            "match_info": {"type": "semantic", "score": SCORES[n]}, "linked_to": [], "link_reasons": {}}
           for n, (c, t, w, _l) in enumerate(NOTES)]
    for n, (_c, _t, _w, links) in enumerate(NOTES):
        for i, reason in links.items():
            for a, b in ((n, i), (i, n)):
                out[a]["linked_to"].append(b + 1)
                out[a]["link_reasons"][b + 1] = reason
    return out
