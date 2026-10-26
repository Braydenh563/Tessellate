"""Grammar and spelling, fixed as classes (INBOX 1357, owner-1026b K4, K4b, K11).

The owner's reports were three cases of one thing: the checker marking what a
note legitimately contains. "something" inside a link (K11), "10-20 min"
read as "minimum" and whole pasted list lines underlined (K4b), and "the
grammar and spellchecker need a major upgrade" (K4). Measured on
`tests/grammar_fixture_1026.json`, 85 realistic note lines that contain no
mistake and 33 that contain one, through `tests/_grammar_harness.js`: the
page's own prose pipeline with the real Harper worker, in node. Before: 61
findings on 39 clean lines (Harper 46, the dictionary 13, the rules 2) and
30 of 33 planted errors caught. The first test below is the ratchet: zero on
the clean lines, every planted error caught.

What the harness cannot see (the underline in the browser, the popover) is
`scratchpad/ui-sweeps`; what it holds is the decision about a span.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "_grammar_harness.js"
FIXTURE = ROOT / "tests" / "grammar_fixture_1026.json"
JS = ROOT / "frontend" / "js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


def _run(fixture: Path, options: dict | None = None) -> dict:
    out = subprocess.run(
        ["node", str(HARNESS), str(ROOT), str(fixture), json.dumps(options or {})],
        capture_output=True, text=True, timeout=180, check=False,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.fixture(scope="module")
def measured() -> dict:
    return _run(FIXTURE, {"timing": True, "longSentence": True})


def _shown(item: dict) -> str:
    return f"{item['text']!r} -> " + "; ".join(f"{f['rule']}/{f['kind']} {f['text']!r}: {f['message']}" for f in item["findings"])


def test_no_false_positive_on_the_clean_fixture(measured) -> None:
    """Every class below is also asserted on its own; this is the whole."""
    bad = [_shown(item) for item in measured["clean"] if item["findings"]]
    assert not bad, "\n".join(bad)


def test_every_planted_error_is_still_caught(measured) -> None:
    missed = []
    for item in measured["planted"]:
        expect = item["expect"].lower()
        if not any(expect in f["text"].lower() or f["text"].lower() in expect for f in item["findings"]):
            missed.append(_shown(item))
    assert not missed, "\n".join(missed)


def _tagged(measured: dict, *tags: str) -> list[dict]:
    items = [item for item in measured["clean"] if item["tag"] in tags]
    assert items, tags
    return items


@pytest.mark.parametrize(
    "tags",
    [
        ("link", "link-text", "wiki", "url", "email", "path", "code"),
        ("units",),
        ("list", "list-long", "list-lower", "heading", "heading-long", "heading-lower", "table", "table-lower"),
        ("names", "abbrev", "hyphen"),
    ],
)
def test_each_class_is_clean(measured, tags) -> None:
    bad = [_shown(item) for item in _tagged(measured, *tags) if item["findings"]]
    assert not bad, "\n".join(bad)


def test_the_words_of_a_link_are_skipped_by_default_and_checked_when_asked(tmp_path) -> None:
    """K11. `[their is a problem here](address)`, `[teh docs](address)`,
    `[the the guide][1]` and an image's alt text are the writer's label for an
    address: skipped by default. Settings, Writing, "Check link text" puts them
    back, and then each of those is a real finding."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture["clean"] = [item for item in fixture["clean"] if item["tag"] == "link-text"]
    fixture["planted"] = []
    path = tmp_path / "links.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    default = _run(path)
    assert [item for item in default["clean"] if item["findings"]] == []
    checked = _run(path, {"prefs": {"grammar_check": True, "check_link_text": True}})
    wrong = [item for item in checked["clean"] if re.search(r"their is|teh|the the", item["text"])]
    assert len(wrong) == 4 and all(item["findings"] for item in wrong), [_shown(item) for item in wrong]


def test_a_unit_after_a_number_is_not_a_word(tmp_path) -> None:
    """K4b. "10-20 min" was marked "minimum"; "hr", "sec", "ms" and "mL" were
    marked too. Two halves: Harper no longer asks (its Expand* rules are off),
    and the page drops what it still says about a unit that follows a number."""
    fixture = {
        "clean": [
            {"tag": "u", "text": text}
            for text in (
                "Revision plan: 10-20 min of flashcards, then 2 h of problem sets.",
                "The lab ran 1.5 hr; the vial held 15 mL; the response took 250 ms.",
                "About 30 sec per set, 5 km long, 3 x 4 min, 90% done, 37 °C, 10am.",
            )
        ],
        "planted": [],
    }
    path = tmp_path / "units.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    result = _run(path)
    assert [item for item in result["clean"] if item["findings"]] == []
    harper_said = " ".join(lint["message"] for item in result["clean"] for lint in item["lints"])
    assert "minimum" not in harper_said and "milliseconds" not in harper_said


def test_a_pasted_list_is_never_a_long_sentence(tmp_path) -> None:
    """K4b. A list item, a heading and a table row are fragments: the 45-word
    rule did not look at one line but at the whole run-together list, and
    Harper's "this sentence is 49 words long" underlined a list item. A real
    run-on paragraph still gets both."""
    run_on = " ".join(["we looked at the notes again and decided that the plan was fine"] * 6) + "."
    items = [
        "- " + run_on[:-1],
        "- one thing here and now\n" * 1 + "- " + " ".join(["more words"] * 30),
        "## " + run_on[:-1],
        "| " + run_on[:-1] + " | 30 min |",
    ]
    fixture = {"clean": [{"tag": "l", "text": text} for text in items] + [{"tag": "p", "text": run_on}], "planted": []}
    path = tmp_path / "long.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    result = _run(path, {"longSentence": True})
    for item in result["clean"][:-1]:
        assert not [f for f in item["findings"] if f["rule"] == "long-sentence" or f["kind"] == "Readability"], _shown(item)
    paragraph = result["clean"][-1]
    assert [f for f in paragraph["findings"] if f["rule"] == "long-sentence"], _shown(paragraph)


def test_a_name_is_not_a_misspelling_but_a_typo_in_a_capitalised_word_still_is(tmp_path) -> None:
    """Names (Okafor, Priya, Zeynep) were 8 of the 13 false spelling marks.
    A transposition in a capitalised word ("Reveiw") and a typo at the start
    of a sentence ("Recieve") are still caught. The personal dictionary still
    silences a word, whatever it is."""
    fixture = {
        "clean": [
            {"tag": "n", "text": "Met Okafor, Priya and Zeynep near Wellington."},
            {"tag": "n", "text": "Priya will send the notes."},
        ],
        "planted": [
            {"text": "The Reveiw was good.", "expect": "Reveiw"},
            {"text": "Recieve the report today.", "expect": "Recieve"},
            {"text": "I met a flurbish person.", "expect": "flurbish"},
        ],
    }
    path = tmp_path / "names.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    result = _run(path)
    assert [item for item in result["clean"] if item["findings"]] == []
    for item in result["planted"]:
        assert any(item["expect"] in f["text"] for f in item["findings"]), _shown(item)
    muted = _run(path, {"dictionary": ["flurbish"]})
    assert not muted["planted"][2]["findings"]


def test_your_for_youre_is_caught_without_catching_a_possessive(tmp_path) -> None:
    fixture = {
        "clean": [
            {"tag": "y", "text": "Please bring your welcome mat and your right to vote."},
            {"tag": "y", "text": "Your going away party is on Friday."},
        ],
        "planted": [
            {"text": "Your going to love this.", "expect": "Your"},
            {"text": "I think your not late.", "expect": "your"},
            {"text": "Thanks! Your welcome.", "expect": "Your"},
        ],
    }
    path = tmp_path / "your.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    result = _run(path)
    assert [item for item in result["clean"] if item["findings"]] == [], [_shown(i) for i in result["clean"]]
    for item in result["planted"]:
        hits = [f for f in item["findings"] if f["rule"] == "confusion"]
        assert hits, _shown(item)


# --- the wiring ---------------------------------------------------------------------


def test_the_switch_is_a_preference_off_by_default(client) -> None:
    before = client.get("/preferences").json()
    put = client.put("/preferences", json={"check_link_text": True}).json()
    after = client.get("/preferences").json()
    assert before["check_link_text"] is False
    assert put["check_link_text"] is True
    assert after["check_link_text"] is True


def test_the_switch_is_in_settings_writing_and_the_dictionary_dialog() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<input type="checkbox" id="pref-check-link-text">\s*<span>Check link text in documents</span>', html)
    assert 'id="doc-check-link-text"' in html
    rows = (JS / "settings-rows.js").read_text(encoding="utf-8")
    assert '{ key: "check_link_text", id: "pref-check-link-text" }' in rows
    panes = (JS / "settings-panes.js").read_text(encoding="utf-8")
    assert 'check_link_text: $("pref-check-link-text").checked' in panes
    assert 'prefsCache.check_link_text === true' in panes
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    assert 'check_link_text: event.currentTarget.checked' in docs


def test_the_help_surfaces_say_what_is_skipped_and_where_the_switch_is() -> None:
    from tessellate.ai import help_chat, help_topics_more

    chat = " ".join(str(topic.get("body", "")) for topic in help_chat.HELP_TOPICS if topic.get("id") == "writing-checks")
    assert "Check link text" in chat and "file paths" in chat
    more = json.dumps(help_topics_more.MORE_TOPICS, default=str)
    assert "Check link text" in more
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'Check link text" below puts the link words back' in html


def test_harper_rules_that_are_house_style_or_abbreviation_nags_are_off() -> None:
    worker = (JS / "harper-worker.js").read_text(encoding="utf-8")
    for name in ("NumericRangeEnDash", "OxfordComma", "ToDoHyphen", "ForYourInformation", "UseTitleCase"):
        assert f'"{name}"' in worker
    assert 'HARPER_RULE_PREFIXES_OFF = ["Expand"]' in worker


# --- speed ----------------------------------------------------------------------------


def test_a_pathological_document_cannot_stall_the_skip_mask(tmp_path) -> None:
    """The new skip patterns (emails, paths, file names, link text) first
    backtracked quadratically: 90,000 characters of "a.b" took 6.7 s and of
    "ab-" 12 s, and a 100,000-letter run of one letter aborted node (that one
    was already so in the base). Each of these is now a few ms to tens of ms;
    the bound is 40 times that, for a loaded machine."""
    stress = {
        "dotted": "a.b" * 30000,
        "hyphen": "ab-" * 30000,
        "slashes": "ab/" * 30000,
        "brackets": "[a" * 30000,
        "ats": "a@b." * 25000,
        "run": "x" * 100000,
        "one line of prose": "The meeting went well and we agreed. " * 3000,
    }
    options = tmp_path / "stress.json"
    options.write_text(json.dumps({"stress": stress}), encoding="utf-8")
    fixture = tmp_path / "empty.json"
    fixture.write_text(json.dumps({"clean": [], "planted": []}), encoding="utf-8")
    out = subprocess.run(
        ["node", str(HARNESS), str(ROOT), str(fixture), f"@{options}"],
        capture_output=True, text=True, timeout=180, check=False,
    )
    assert out.returncode == 0, out.stderr
    slow = {k: v for k, v in json.loads(out.stdout)["stress"].items() if v["maskMs"] > 1500 or v["findingsMs"] > 2500}
    assert not slow, slow


def test_checking_stays_off_the_typing_path(measured) -> None:
    """Harper runs in the worker (measured: about 60 ms per 1,000 words, never
    on the main thread). What is on the main thread per keystroke is the rule
    pass and the merge: a few ms per 1,000 words. The budget here is ten times
    what was measured, for a loaded CI machine."""
    timing = measured["timing"]
    per_thousand = timing["extrasMs"] * 1000 / timing["words"]
    assert per_thousand < 50, timing
    assert timing["rulesMs"] * 1000 / timing["words"] < 50, timing
