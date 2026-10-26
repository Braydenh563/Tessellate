"""K3 (owner-1026b, INBOX 1357 "fix the class"): the AI-only buttons that a
plain rule can do, do it with no model, and the ones that cannot say why.

The classes, each with several shapes of input the owner did not report:

- **Name a draft** (`/drafts/title`): a title from the draft's own words
  whatever shape it opens with (prose, lead-in, heading, list, checklist,
  fragment); never a word the draft does not hold.
- **Split into notes** (`/entries/extract/preview`): one note per heading or
  paragraph, whatever the line endings, rules or fences; nothing lost, nothing
  added, at most `MAX_EXTRACT_NOTES`, and the same when a model is running but
  its split failed.
- **The buttons**: no button that works without a model carries the gate, and
  every gated button answers a press (`data-model-offer`) rather than doing
  nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tessellate.ai import extractor, no_model_text
from tessellate.entry import manager

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _words(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[A-Za-z0-9']+", text)]


# --- name a draft --------------------------------------------------------------

#: (draft, what the title must contain or None, words the title may add: none)
TITLE_DRAFTS = [
    "We should plan the sprint review for next Thursday and invite the design team.",
    "Remember to book the dentist before the end of October for a checkup.",
    "Note to self: the router password is on the fridge, change it soon.",
    "# Sprint review\n\nThe demo is on Thursday. Invite the design team and book a room.",
    "- buy oat milk\n- buy bananas\n- renew the bus pass",
    "- [ ] email the landlord about the boiler\n- [ ] pay the gas bill",
    "quick thoughts on the sprint planning meeting",
    "**Important:** the deadline for the grant application moved to the fifteenth of November.",
    "> The best way to learn a language is to speak it every single day without fear.",
    "1. Wake early\n2. Stretch\n3. Write for an hour before breakfast",
    "teh meeting is on tuesday\n\nwe shoud prepare the slides",
    "Milk, eggs, bread.",
    "\n\n   Leading blank lines and a long opening sentence that keeps going and going well past seven words.",
]


@pytest.mark.parametrize("draft", TITLE_DRAFTS)
def test_a_draft_is_titled_from_its_own_words(draft):
    title = no_model_text.draft_title(draft)
    assert title, draft
    assert len(title.split()) <= no_model_text.TITLE_WORDS and len(title) <= 80
    held = set(_words(draft))
    assert all(w in held for w in _words(title)), (title, draft)
    assert title[0].isupper() or not title[0].isalpha()
    assert not re.search(r"[#*>\[\]]", title), title


#: The seven-word cut can land on a word that needs one after it.
DANGLING_ENDS = [
    "teh first idea is about how the garden should be laid out",
    "We should talk to the team about the plan for next week at some point",
    "The review of the proposal from the committee and the board is due",
    "Ideas for the kitchen with the new oven and the old sink to keep",
    "Notes on the meeting between the supervisors and the students that was held",
]


@pytest.mark.parametrize("draft", DANGLING_ENDS)
def test_a_title_never_ends_on_a_word_that_needs_another(draft):
    from tessellate.ai import composer_voice

    last = no_model_text.draft_title(draft).split()[-1].lower().strip(",;:")
    assert last not in composer_voice.TITLE_DANGLING, (last, draft)
    assert last not in composer_voice.query_understanding.STOPWORDS, (last, draft)


@pytest.mark.parametrize("draft", ["", "   ", "\n\n", "ok", "# ", "---"])
def test_a_draft_with_nothing_to_name_gets_no_title(draft):
    assert no_model_text.draft_title(draft) == ""


def test_a_heading_only_draft_is_named_by_its_heading():
    assert no_model_text.draft_title("# Sprint review") == "Sprint review"


def test_top_terms_name_a_draft_with_no_sentence():
    title = no_model_text.draft_title("kubernetes kubernetes pods\nkubernetes\nnodes pods")
    assert title and set(_words(title)) <= {"kubernetes", "pods", "nodes"}


def test_the_title_route_composes_when_no_model_runs_and_says_so(client):
    body = client.post("/drafts/title", json={"draft": TITLE_DRAFTS[0]}).json()
    assert body["title"] and body["by"] == "composer"
    nothing = client.post("/drafts/title", json={"draft": "ok"}).json()
    assert nothing["title"] == ""


def test_the_title_route_still_asks_the_model_when_one_runs(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "Sprint review plan"
    body = ai_client.post("/drafts/title", json={"draft": TITLE_DRAFTS[0]}).json()
    assert "by" not in body or body["by"] != "composer"


# --- split into notes ----------------------------------------------------------

P1 = "The first idea is about how the garden should be laid out this spring."
P2 = "A second thought: the shed needs a new roof before the autumn rain comes."
P3 = "Third, the budget for all of this is about four hundred pounds in total."

#: (name, text, number of notes expected, titles expected or None)
SPLITS = [
    ("blank-line paragraphs", f"{P1}\n\n{P2}\n\n{P3}", 3, None),
    ("extra blank lines and trailing spaces", f"{P1}  \n\n\n\n{P2}\n   \n{P3}\n\n", 3, None),
    ("windows line endings", f"{P1}\r\n\r\n{P2}\r\n\r\n{P3}", 3, None),
    ("old mac line endings", f"{P1}\r\r{P2}\r\r{P3}", 3, None),
    ("two headings", f"# Garden\n\n{P1}\n\n# Shed\n\n{P2}", 2, ["Garden", "Shed"]),
    ("three levels of heading", f"## Garden\n{P1}\n### Shed\n{P2}\n## Budget\n{P3}", 3, ["Garden", "Shed", "Budget"]),
    ("text before the first heading", f"{P1}\n\n# Shed\n\n{P2}\n\n# Budget\n\n{P3}", 3, None),
    ("a heading's several paragraphs stay together", f"# Garden\n\n{P1}\n\n{P2}\n\n# Budget\n\n{P3}", 2, ["Garden", "Budget"]),
    ("a lone heading titles the first paragraph", f"# Plans\n\n{P1}\n\n{P2}", 2, None),
    ("horizontal rules from a board selection", f"{P1}\n\n---\n\n{P2}\n\n---\n\n{P3}", 3, None),
    ("one block with no blank lines", f"{P1} {P2} {P3}", 1, None),
    ("a list stays whole", f"Things to buy:\n- oat milk\n- bananas\n- a bus pass\n\n{P2}", 2, None),
    ("a code fence is not split by its blank lines", f"{P1}\n\n```\nfirst = 1\n\nsecond = 2\n```\n\n{P3}", 3, None),
    ("a hash with no space is not a heading", f"#tag {P1}\n\n#another {P2}", 2, None),
]


@pytest.mark.parametrize(("name", "text", "count", "titles"), SPLITS, ids=[s[0] for s in SPLITS])
def test_a_text_is_split_by_its_own_structure(name, text, count, titles):
    notes = no_model_text.split_notes(text, extractor.MAX_EXTRACT_NOTES)
    assert len(notes) == count, [n.content for n in notes]
    if titles:
        assert [n.title for n in notes] == titles
    kept = [w for n in notes for w in _words(n.content)]
    assert kept == _words(text), "words lost, added or reordered"
    assert all(n.content.strip() for n in notes)


def test_a_section_keeps_its_heading_as_the_notes_title_line():
    notes = no_model_text.split_notes(f"# Garden\n\n{P1}\n\n# Shed\n\n{P2}", 4)
    assert notes[0].content.startswith("# Garden") and notes[1].content.startswith("# Shed")


@pytest.mark.parametrize("n", [5, 6, 9, 20])
def test_more_parts_than_the_cap_are_merged_not_dropped(n):
    text = "\n\n".join(f"Paragraph number {i} talks about topic {i} at some useful length." for i in range(n))
    notes = no_model_text.split_notes(text, extractor.MAX_EXTRACT_NOTES)
    assert len(notes) == extractor.MAX_EXTRACT_NOTES
    assert [w for x in notes for w in _words(x.content)] == _words(text)


@pytest.mark.parametrize("scrap", ["Notes:", "TODO", "- ", "see below"])
def test_a_scrap_joins_the_part_beside_it(scrap):
    notes = no_model_text.split_notes(f"{scrap}\n\n{P1}\n\n{P2}", 4)
    assert len(notes) == 2 and scrap.strip("- ") in notes[0].content


def test_a_paragraph_note_gets_a_title_from_its_first_sentence():
    notes = no_model_text.split_notes(f"{P1}\n\n{P2}", 4)
    assert all(n.title and set(_words(n.title)) <= set(_words(n.content)) for n in notes)


def test_the_preview_splits_with_no_model_and_says_so(client, session):
    text = f"# Garden\n\n{P1}\n\n# Shed\n\n{P2}"
    body = client.post("/entries/extract/preview", json={"text": text}).json()
    assert [n["title"] for n in body["notes"]] == ["Garden", "Shed"]
    assert body["ollama_running"] is False
    assert body["message"] == extractor.offline_message() and "split" in body["message"]
    assert all(n["ref"] == f"n{i}" for i, n in enumerate(body["notes"]))


def test_the_preview_links_the_parts_and_their_source_without_a_model(client, session):
    source = manager.create_entry(session, "The garden and the shed, all in one note.")
    session.commit()
    body = client.post(
        "/entries/extract/preview", json={"text": f"{P1}\n\n{P2}", "source_entry_ids": [source.id]}
    ).json()
    kinds = sorted(link["kind"] for link in body["links"])
    assert kinds == ["sibling", "source", "source"]
    assert all(link["reason"] and link["reason"] != manager.AUTO_REASON_TEXT for link in body["links"])


def test_a_failed_model_split_falls_back_to_the_same_plain_split(ai_client, fake_ollama):
    fake_ollama.extract_split_reply = "not json"
    body = ai_client.post("/entries/extract/preview", json={"text": f"{P1}\n\n{P2}\n\n{P3}"}).json()
    assert len(body["notes"]) == 3
    assert body["message"] == extractor.SPLIT_FAILED_MESSAGE


def test_a_commit_of_the_plain_split_needs_no_model(client):
    body = client.post("/entries/extract/preview", json={"text": f"{P1}\n\n{P2}"}).json()
    out = client.post(
        "/entries/extract/commit",
        json={"notes": [{"ref": n["ref"], "title": n["title"], "content": n["content"], "category": n["category"]} for n in body["notes"]]},
    )
    assert out.status_code == 201 and len(out.json()["notes"]) == 2


# --- the buttons ---------------------------------------------------------------

#: Every control that does the job with no model (a plain rule, above).
WORK_WITHOUT_A_MODEL = ["draft-title", "draft-extract", "extract-commit", "doc-extract", "wb-extract-notes"]
#: Model-only buttons: each must answer a press with the reason and Set up a model.
MODEL_ONLY_BUTTONS = ["draft-compose", "draft-refine", "doc-ai", "doc-ai-run", "chat-plan", "template-draft",
                      "assist:explain", "assist:tests", "assist:refactor"]


def _tag(ident: str) -> str:
    attr = f'data-assist="{ident[7:]}"' if ident.startswith("assist:") else f'id="{ident}"'
    match = re.search(rf'<(?:button|input|select)\b[^>]*{attr}[^>]*>', INDEX)
    return match.group(0) if match else ""


@pytest.mark.parametrize("ident", WORK_WITHOUT_A_MODEL)
def test_a_button_that_works_without_a_model_is_not_gated(ident):
    tag = _tag(ident)
    assert tag, ident
    assert "data-needs-model" not in tag, ident


@pytest.mark.parametrize("path", ["selection.js", "note-cards.js"])
def test_no_extract_entry_point_is_gated_in_script(path):
    js = (ROOT / "frontend" / "js" / path).read_text(encoding="utf-8")
    assert not re.search(r"Extracting notes needs the local AI|Splitting a note needs the local AI", js), path


@pytest.mark.parametrize("ident", MODEL_ONLY_BUTTONS)
def test_a_model_only_button_answers_a_press(ident):
    tag = _tag(ident)
    assert tag, ident
    assert "data-needs-model=" in tag and 'data-model-offer="' in tag, ident
    offer = re.search(r'data-model-offer="([^"]+)"', tag).group(1)
    assert offer.endswith(".") and "!" not in offer and chr(0x2014) not in offer, offer
