"""L161 (a), INBOX 1841: one answer-length preference (Short, Normal, Detailed;
the stored `response_mode`) that Settings, the chat dock, the model prompt and
the composer all follow. Short is one or two sentences; Detailed adds a
supporting sentence per source."""

from __future__ import annotations

from pathlib import Path

from tessellate.ai import composer_tone, presets
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

ROOT = Path(__file__).resolve().parents[1]
LONG = "First sentence of the lead. Second sentence of the lead. Third sentence of the lead.\n\nMore below."


def test_the_levels_are_short_normal_detailed_and_normal_is_the_default():
    assert [m.label for m in presets.MODES.values()] == ["Short", "Normal", "Detailed"]
    assert presets.DEFAULT_MODE == "normal"
    assert "one or two sentences" in presets.MODES["quick"].length_hint
    assert "supporting sentence for each source" in presets.MODES["detailed"].length_hint


def test_the_composer_short_is_at_most_two_sentences():
    assert composer_tone.fit(LONG, "short") == "First sentence of the lead. Second sentence of the lead."
    assert composer_tone.fit("Only this.", "short") == "Only this."
    assert composer_tone.fit(LONG, "normal") == LONG


def test_the_composer_detailed_adds_one_supporting_sentence_per_source():
    sources = [
        ("Dentist", "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard."),
        ("Gym plan", "# Gym plan\n\nTuesday and Thursday at six."),
    ]
    lines = composer_tone.supporting("Check-up booked for the 21st.", sources)
    assert lines == ["From Dentist: Ask about the night guard.", "From Gym plan: Tuesday and Thursday at six."]
    out = composer_tone.fit("The dentist is on the 21st.", "long", lines)
    assert out.startswith("The dentist is on the 21st.\n\n- From Dentist")
    assert composer_tone.fit("The dentist is on the 21st.", "long") == "The dentist is on the 21st."


def test_the_preference_is_the_one_the_dock_reads(client):
    first = client.get("/preferences").json()
    saved = client.put("/preferences", json={"response_mode": "quick"}).json()
    assert first["response_mode"] == "normal" and saved["response_mode"] == "quick"
    modes = client.get("/chat/modes").json()
    assert modes["active"] == "quick" and [m["label"] for m in modes["modes"]] == ["Short", "Normal", "Detailed"]


def test_the_composed_answer_follows_it_through_the_route(client, session):
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard. Bring the referral letter.")
    session.commit()
    short = _ask(client, "when is the dentist", mode="quick")["text"]
    detailed = _ask(client, "when is the dentist", mode="detailed")["text"]
    assert len(detailed) > len(short)
    assert short.count(". ") <= 1


def test_settings_has_the_control_beside_the_other_answer_settings():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="pref-answer-length"' in html
    for value, label in (("quick", "Short"), ("normal", "Normal (default)"), ("detailed", "Detailed")):
        assert f'<option value="{value}">{label}</option>' in html
    assert 'data-help-for="answer-length-help"' in html and 'id="answer-length-help"' in html
    assert 'data-help-for="personas-off-help"' in html and 'id="personas-off-help"' in html
    rows = (ROOT / "frontend/js/settings-rows.js").read_text(encoding="utf-8")
    assert '{ key: "response_mode", id: "pref-answer-length" }' in rows
    assert '{ key: "personas_off", id: "pref-personas-off" }' in rows
    prefs = (ROOT / "frontend/js/settings-prefs.js").read_text(encoding="utf-8")
    assert 'prefsCache.response_mode' in prefs and "prefsCache.personas_off" in prefs
    #: Saved on change like the dock's picker, which is then read again.
    assert 'setPreference("response_mode", event.target.value).then(loadResponseModes)' in prefs
    assert 'setPreference("personas_off", event.target.checked)' in prefs
