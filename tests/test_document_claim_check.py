"""Source text: the route is exercised through the test client; the front-end half has no browser under pytest, so its script is read as text.

Claim check (the features audit, Phase G): a document's sentences checked
against the notebook. `POST /documents/{id}/claim-check` writes nothing and
marks each claim supported, contradicted or not found, with the note behind the
verdict. A model (a fake transport here) only judges, by number and letter, and
only when a note was found to judge against; with none, a claim is supported
when one note holds most of its words and otherwise not found (it cannot be
contradicted, which takes reading). The search pads thin results with near
misses, so a note counts only when it shares a word with the claim.
"""

from __future__ import annotations

from pathlib import Path

import pytest

DOC = (
    "# Garden plan\n\n"
    "Tomatoes need pruning every single week in summer. The compost heap must be turned monthly by hand. "
    "We will book the flights to Lisbon in March.\n\n"
    "```\nnot a claim at all here in code fence\n```\n"
    "Short one.\n"
)


def _setup(client):
    note = client.post(
        "/entries", json={"content": "# Tomato pruning\n\nTomatoes need pruning every single week in summer, pinch the side shoots."}
    ).json()
    other = client.post("/entries", json={"content": "# Compost heap\n\nTurn the compost heap every week, never monthly."}).json()
    doc = client.post("/documents", json={"title": "Garden", "content": DOC}).json()
    return doc["id"], note, other


def _verdicts(got):
    return {c["text"][:21]: c["verdict"] for c in got["claims"]}


def test_with_no_model_a_claim_a_note_holds_is_supported_and_the_rest_not_found(client):
    doc, note, other = _setup(client)
    out = client.post(f"/documents/{doc}/claim-check", json={"text": DOC})
    assert out.status_code == 200, out.text
    got = out.json()
    assert got["source"] == "words" and got["reason"] == "offline"
    assert _verdicts(got) == {
        "Tomatoes need pruning": "supported",
        "The compost heap must": "not_found",
        "We will book the flig": "not_found",
    }
    first = got["claims"][0]
    assert first["note"] == {"id": note["id"], "title": "Tomato pruning"}
    assert DOC[first["start"] : first["end"]].startswith("Tomatoes need pruning")
    assert got["claims"][2]["note"] is None
    # Headings, code fences and short lines are not claims; nothing is written.
    kept = client.get(f"/documents/{doc}").json()["content"]
    assert kept == DOC


def test_the_model_can_mark_a_claim_contradicted_by_a_note_it_cites(ai_client, fake_ollama):
    doc, note, other = _setup(ai_client)
    fake_ollama.librarian_reply = "1: supported a\n2: contradicted a\n3: unrelated"
    got = ai_client.post(f"/documents/{doc}/claim-check", json={"text": DOC}).json()
    assert got["source"] == "model"
    verdicts = _verdicts(got)
    assert verdicts["Tomatoes need pruning"] == "supported"
    assert verdicts["The compost heap must"] == "contradicted"
    compost = got["claims"][1]
    assert compost["note"]["id"] == other["id"] and "says otherwise" in compost["message"]
    sent = fake_ollama.chat_calls[-1][-1]["content"]
    assert "[2] The compost heap must be turned monthly by hand." in sent and "Compost heap" in sent


def test_a_verdict_that_cites_no_note_or_is_prose_falls_back_to_the_words_rule(ai_client, fake_ollama):
    doc, note, other = _setup(ai_client)
    fake_ollama.librarian_reply = "1: contradicted\n2: supported z\nThe document looks fine."
    got = ai_client.post(f"/documents/{doc}/claim-check", json={"text": DOC}).json()
    verdicts = _verdicts(got)
    # The model's bare verdict is not trusted: the words rule decides.
    assert verdicts["Tomatoes need pruning"] == "supported"
    assert verdicts["The compost heap must"] == "not_found"
    fake_ollama.librarian_reply = "Everything is fine."
    again = ai_client.post(f"/documents/{doc}/claim-check", json={"text": DOC}).json()
    assert again["source"] == "words" and again["reason"] == "unusable"


def test_a_document_with_no_sentences_is_refused(client):
    text = "# Only a heading\n\nShort."
    doc = client.post("/documents", json={"title": "Bare", "content": text}).json()["id"]
    refused = client.post(f"/documents/{doc}/claim-check", json={"text": text})
    assert refused.status_code == 422


def test_the_panel_lists_claims_with_the_note_behind_each():
    """`docAiCheck.claims` (kebab menu, palette) fills the same panel as Check
    with AI under "Checked against your notes"; claim-check1112.js measures it."""
    js = Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents.js"
    text = js.read_text(encoding="utf-8")
    assert "/claim-check`" in text
    assert '["claim", "Checked against your notes"]' in text
    assert 'return "backed";' in text and 'return "claim";' in text
    assert "docAiCheck.claims()" in text


def test_front_matter_is_skipped_and_parsed_in_linear_time():
    """CodeQL 2285: the front-matter regex was polynomial on '---\\n' plus many
    'a---\\n'. By line it is linear, and still ends at the closing `---`."""
    import time

    from tessellate.api.routes_document_claims import _claims, _front_matter_end

    text = "---\ntitle: x\n---  \nThe river floods the valley every spring now.\n"
    assert _front_matter_end(text) == text.index("The river")
    assert _front_matter_end("no front matter\n---\n") == 0
    assert _front_matter_end("---\nnever closed\n") == 0
    assert [text[a:b] for a, b in _claims(text)] == ["The river floods the valley every spring now."]
    hostile = "---\n" + "a---\n" * 50_000
    started = time.perf_counter()
    _front_matter_end(hostile)
    assert time.perf_counter() - started < 0.1


def _said(text):
    from tessellate.api.routes_document_claims import _claims

    return [text[a:b] for a, b in _claims(text)]


def test_a_sentence_keeps_its_own_number_and_only_a_list_marker_is_stripped():
    text = "2024 revenue rose by a third against the plan.\n- 12 boxes of seed arrived on Monday morning.\n3. The shed roof leaks over the potting bench.\n"
    assert _said(text) == [
        "2024 revenue rose by a third against the plan.",
        "12 boxes of seed arrived on Monday morning.",
        "The shed roof leaks over the potting bench.",
    ]


def test_a_decimal_and_an_abbreviation_do_not_end_a_sentence():
    text = "Use a mix of compost, e.g. leaf mould and bark, for the beds. The pH should sit near 6.5 for most of the vegetables here.\n"
    assert _said(text) == [
        "Use a mix of compost, e.g. leaf mould and bark, for the beds.",
        "The pH should sit near 6.5 for most of the vegetables here.",
    ]


def test_a_slow_model_times_out_and_the_words_rule_answers(ai_client, fake_ollama, monkeypatch):
    import time

    from tessellate.api import routes_board_affinity

    doc, note, other = _setup(ai_client)
    real = fake_ollama.chat
    monkeypatch.setattr(fake_ollama, "chat", lambda *a, **k: (time.sleep(1.0), real(*a, **k))[1])
    monkeypatch.setattr(routes_board_affinity, "MODEL_SECONDS", 0.1)
    started = time.perf_counter()
    got = ai_client.post(f"/documents/{doc}/claim-check", json={"text": DOC}).json()
    assert time.perf_counter() - started < 0.9
    assert got["source"] == "words" and got["reason"] == "failed"
    assert _verdicts(got)["Tomatoes need pruning"] == "supported"


@pytest.mark.parametrize(
    "hostile",
    ["\t" * 100_000, " \t" * 50_000 + "x", "- " + "\t" * 100_000, "a." * 50_000, "x" + ". " * 50_000],
)
def test_a_line_of_many_tabs_or_stops_is_read_in_linear_time(hostile):
    """CodeQL 2290: the list-marker pattern ran slow on many tabs; the
    abbreviation check re-read the line before every full stop."""
    import time

    from tessellate.api.routes_document_claims import _claims

    started = time.perf_counter()
    _claims(hostile + "\n")
    assert time.perf_counter() - started < 0.5
