"""L-documents-48: the long-form choice at first run. One preference, `writing_style`, picks the surface New opens and the
default document page style; the welcome's preferences card asks it once and Settings, General keeps it changeable."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _text(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_the_preference_defaults_to_notes_and_takes_documents(client: TestClient) -> None:
    first = client.get("/preferences")
    assert first.json()["writing_style"] == "notes"
    put = client.put("/preferences", json={"writing_style": "documents"})
    assert put.json()["writing_style"] == "documents"
    got = client.get("/preferences")
    assert got.json()["writing_style"] == "documents"
    bad = client.put("/preferences", json={"writing_style": "essays"})
    assert bad.status_code == 422


def test_new_follows_the_choice_except_the_notes_own_button() -> None:
    wiring = _text("frontend", "js", "wiring.js")
    assert 'prefsCache?.writing_style === "documents"' in wiring
    assert "createDocument()" in wiring.split("function startNewNote", 1)[1].split("showNotesSection", 1)[0]
    assert '$("notes-new-note").addEventListener("click", () => startNewNote(1))' in wiring


def test_the_page_style_follows_the_choice_until_the_person_picks_one() -> None:
    docs = _text("frontend", "js", "documents.js")
    assert 'prefsCache?.writing_style === "documents"' in docs


def test_the_choice_is_asked_at_first_run_and_kept_in_settings() -> None:
    assert 'key: "writing_style"' in _text("frontend", "js", "onboarding.js")
    assert 'id="pref-writing-style"' in _text("frontend", "index.html")
    assert '"pref-writing-style"' in _text("frontend", "js", "settings-rows.js")
    assert 'setPreference("writing_style"' in _text("frontend", "js", "settings-controls.js")
    assert "writing_style" in _text("frontend", "js", "settings-prefs.js") or "pref-writing-style" in _text("frontend", "js", "settings-prefs.js")
