"""L210 (R3-20): "who is Priya" over several notes reads as a count line then one paragraph,
not a column of one-line paragraphs, and every note it names is cited."""

from datetime import date

from tessellate.ai import composer_digest

NOTES = [
    "Priya is my cousin who lives in Leeds.",
    "Priya sent the mockups for the landing page.",
    "Dinner with Priya on Friday at the new Thai place.",
    "Buy milk and bread.",
]


def _answer():
    notes = [
        {"id": i + 1, "content": c, "created_at": f"2026-11-0{i + 1}T10:00:00", "category": "", "tags": []}
        for i, c in enumerate(NOTES)
    ]
    return composer_digest.answer("who is Priya", notes, today=date(2026, 11, 10))


def test_who_is_reads_as_lead_plus_one_paragraph():
    out = _answer()
    paragraphs = [p for p in out["text"].split("\n\n") if p.strip()]
    assert paragraphs[0].startswith("Priya comes up in three notes"), out["text"]
    assert len(paragraphs) <= 3, out["text"]
    assert "cousin" in out["text"] and "mockups" in out["text"] and "Thai" in out["text"]


def test_every_note_named_is_cited():
    out = _answer()
    cited = {int(r["note_id"]) for r in out["grounding"]}
    assert {1, 2, 3} <= cited and 4 not in cited
