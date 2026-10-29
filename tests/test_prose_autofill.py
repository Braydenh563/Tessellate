"""Autofill for prose documents: expansions, shortcodes, pairs, smart punctuation.

The owner, 2026-09-24: "I want cool features for autofill and easy life stuff
in the documents editor like if I type lorem and press enter or a popup that
appears, then it will autofill the lorem ipsum filler text and stuff."

The list, the ghost text and the keys are measured in Chromium by
`scratchpad/ui-sweeps/proseautofill.js`. What decides *what is offered and what
text results* is pure string work in documents-prose.js's `PROSE-FILL` region,
run here in node so every expansion is held to the exact text it must produce.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
PROSE_JS = ROOT / "frontend" / "js" / "documents-prose.js"
DOCUMENTS_JS = ROOT / "frontend" / "js" / "documents.js"
APP_JS = ROOT / "frontend" / "js" / "app.js"
PREFS_JS = ROOT / "frontend" / "js" / "prefs.js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _region() -> str:
    text = PROSE_JS.read_text(encoding="utf-8")
    start, stop = text.find("// PROSE-FILL-BEGIN"), text.find("// PROSE-FILL-END")
    assert start != -1 and stop > start, "the PROSE-FILL markers are missing from documents-prose.js"
    return text[start:stop]


def _function(path: Path, name: str) -> str:
    #: app.js means the app's code, every piece of it (tests/_app_js.py).
    text = app_js_text() if path == APP_JS else path.read_text(encoding="utf-8")
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 2]


def run(calls: list) -> list:
    """Evaluate `[name, *args]` calls against the region, in node."""
    script = (
        _region()
        + "\n"
        + _function(PREFS_JS, "nounCount")
        + "\n"
        + _function(APP_JS, "mdHeadingId")
        + "\nconst NOW = new Date(2026, 8, 24, 14, 5);\n"
        "const ctx = (extra) => ({ now: NOW, locale: 'en-GB', slug: mdHeadingId, ...extra });\n"
        "const fns = {docLorem, docFillTable, docFillSig, docSmartPunct, docPairInput, docPairBackspace,"
        " docFillToken, docFillGhost, docListEnter, docListExitText, docBulletRetype, docFenceCloseIndent};\n"
        "fns.toc = (text) => docFillToc(text, mdHeadingId);\n"
        "fns.date = (kind, locale) => docFillDate(kind, NOW, locale);\n"
        "fns.options = (before, after, extra) => docFillOptions(docFillToken(before, after), ctx(extra || {}))"
        ".map((o) => [o.label, o.detail, o.text, o.select || null]);\n"
        "fns.emoji = (q) => docEmojiMatches(q).map(([n, g]) => [n, g]);\n"
        "fns.emojiCount = () => docEmojiList().length;\n"
        "const calls = JSON.parse(process.argv[2]);\n"
        "console.log(JSON.stringify(calls.map(([name, ...args]) => fns[name](...args))));\n"
    )
    #: The script on stdin, not in argv: conftest's installer guard reads argv
    #: for the letters "pip", which this region's comments spell ("pipes").
    out = subprocess.run(
        ["node", "-", json.dumps(calls)], input=script, capture_output=True, text=True, check=True, timeout=60
    )
    return json.loads(out.stdout)


# --- expansions ----------------------------------------------------------------


@node
def test_lorem_is_a_paragraph_and_loremN_is_that_many_words() -> None:
    para, three, twenty, capped = run([["docLorem", 0], ["docLorem", 3], ["docLorem", 20], ["docLorem", 5000]])
    assert para.startswith("Lorem ipsum dolor sit amet, consectetur") and para.endswith("id est laborum.")
    assert three == "Lorem ipsum dolor."
    assert len(twenty.rstrip(".").split(" ")) == 20 and twenty[0] == "L" and twenty.endswith(".")
    assert len(capped.split(" ")) == 1000


@node
def test_lorem_is_a_trigger_anywhere_but_never_mid_word() -> None:
    anywhere, alone, mid, inside, n = run([
        ["docFillToken", "Some text lorem", ""],
        ["docFillToken", "lorem", ""],
        ["docFillToken", "xlorem", ""],
        ["docFillToken", "lor", "em"],
        ["docFillToken", "lorem20", ""],
    ])
    assert anywhere == {"kind": "lorem", "start": 10, "count": 0, "token": "lorem"}
    assert alone["start"] == 0
    assert mid is None and inside is None
    assert n["count"] == 20


@node
def test_a_bare_word_expands_only_on_a_line_of_its_own() -> None:
    """`now` at the end of "I will do it now" is a word; `now` alone is a request."""
    sentence, alone, indented, capital, trailing = run([
        ["docFillToken", "I will do it now", ""],
        ["docFillToken", "now", ""],
        ["docFillToken", "  todo", ""],
        ["docFillToken", "Now", ""],
        ["docFillToken", "now", " later"],
    ])
    assert sentence is None and capital is None and trailing is None
    assert alone == {"kind": "now", "start": 0, "token": "now"}
    assert indented == {"kind": "todo", "start": 2, "token": "todo"}


@node
def test_dates_are_in_the_locale_asked_for() -> None:
    today, date, iso, now, us = run([
        ["date", "today", "en-GB"],
        ["date", "date", "en-GB"],
        ["date", "iso", "en-GB"],
        ["date", "now", "en-GB"],
        ["date", "today", "en-US"],
    ])
    assert today == "24 September 2026"
    assert date == "24/09/2026"
    assert iso == "2026-09-24"
    assert now.startswith("24 September 2026") and "14:05" in now
    assert us == "September 24, 2026"


@node
def test_the_date_words_offer_their_forms() -> None:
    (rows,) = run([["options", "date", ""]])
    assert [r[2] for r in rows] == ["24/09/2026", "24 September 2026", "2026-09-24"]
    assert all(r[0] == "date" for r in rows)


@node
def test_table_NxM_is_columns_by_rows_with_the_first_header_chosen() -> None:
    plain, slash, spaced, mid = run([
        ["options", "table 3x4", ""],
        ["options", "/table 2x1", ""],
        ["docFillToken", "  table3x2", ""],
        ["docFillToken", "a table 3x4", ""],
    ])
    label, detail, text, select = plain[0]
    assert label == "table 3x4" and detail == "A table, 3 columns by 4 rows"
    assert text == (
        "| Column | Column | Column |\n"
        "| --- | --- | --- |\n"
        "|  |  |  |\n|  |  |  |\n|  |  |  |\n|  |  |  |\n"
    )
    assert text[select[0] : select[1]] == "Column" and select[0] == 2
    assert slash[0][2] == "| Column | Column |\n| --- | --- |\n|  |  |\n"
    assert spaced["start"] == 2 and spaced["cols"] == 3 and spaced["rows"] == 2
    assert mid is None, "a table is a block: it starts a line"


@node
def test_todo_callout_and_hr_write_their_markdown() -> None:
    todo, callout, hr = run([["options", "todo", ""], ["options", "callout", ""], ["options", "hr", ""]])
    assert todo == [["todo", "A task to tick", "- [ ] ", None]]
    assert [r[2] for r in callout] == ["> [!note]\n> ", "> [!tip]\n> ", "> [!warning]\n> "]
    assert hr[0][2] == "---\n"


@node
def test_toc_links_each_heading_to_the_id_the_renderer_gives_it() -> None:
    doc = (
        "# The title\n\nIntro.\n\n## First part\n\n### A *detail*\n\n```\n# not a heading\n```\n\n"
        "## First part\n\n## [Linked](http://x) heading\n"
    )
    toc, none, two_h1 = run([
        ["toc", doc],
        ["toc", "Just text.\n"],
        ["toc", "# One\n\n# Two\n"],
    ])
    assert toc == (
        "- [First part](#first-part)\n"
        "  - [A detail](#a-detail)\n"
        "- [First part](#first-part-2)\n"
        "- [Linked heading](#linkedhttp-x-heading)\n"
    )
    assert "not a heading" not in toc
    assert none is None
    assert two_h1 == "- [One](#one)\n- [Two](#two)\n", "two top-level headings are sections, not a title"


@node
def test_toc_is_not_offered_without_headings() -> None:
    (rows,) = run([["options", "toc", "", {"doc": "No headings here."}]])
    assert rows == []


@node
def test_sig_signs_with_the_name_from_settings_or_chooses_a_placeholder() -> None:
    named, unnamed = run([["docFillSig", "Brayden"], ["docFillSig", ""]])
    assert named["text"] == "Kind regards,\n\nBrayden\n"
    text, (a, b) = unnamed["text"], unnamed["select"]
    assert text[a:b] == "Your name"


@node
def test_ghost_is_the_first_line_cut_to_a_glance() -> None:
    short, long = run([
        ["docFillGhost", {"text": "- [ ] "}],
        ["docFillGhost", {"text": "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do"}],
    ])
    assert short == "- [ ] "
    assert len(long) == 48 and long.endswith("…")


@node
def test_enter_on_an_empty_item_ends_the_list_or_steps_out_a_level() -> None:
    top, task, numbered, nested, deep, tab, full, text = run([
        ["docListEnter", "- "],
        ["docListEnter", "- [ ] "],
        ["docListEnter", "3. "],
        ["docListEnter", "  - "],
        ["docListEnter", "        - [ ] "],
        ["docListEnter", "\t- "],
        ["docListEnter", "- Buy milk"],
        ["docListEnter", "Plain"],
    ])
    assert top == "" and task == "" and numbered == ""
    assert nested == "- " and deep == "    - [ ] " and tab == "- "
    assert full is None and text is None, "an item with words in it continues as before"


@node
def test_retyping_a_dash_on_an_empty_bullet_does_not_nest() -> None:
    plain, indented, star, other_key, filled, three = run([
        ["docBulletRetype", "- -", " "],
        ["docBulletRetype", "  - -", " "],
        ["docBulletRetype", "* -", " "],
        ["docBulletRetype", "- -", "x"],
        ["docBulletRetype", "- a -", " "],
        ["docBulletRetype", "- - -", " "],
    ])
    assert plain == "- " and indented == "  - " and star == "* "
    assert other_key is None and filled is None, "only the space after a second dash collapses"
    assert three is None, "a thematic break typed as '- - -' is left alone"


@node
def test_a_closing_fence_returns_to_the_opening_fence_indent() -> None:
    drifted, fine, no_fence, closed_already, tilde, mismatch, info, inline = run([
        ["docFenceCloseIndent", ["```", "    code"], "    ```"],
        ["docFenceCloseIndent", ["```", "code"], "```"],
        ["docFenceCloseIndent", ["text"], "    ```"],
        ["docFenceCloseIndent", ["```", "x", "```", "text"], "    ```"],
        ["docFenceCloseIndent", ["~~~", "    x"], "    ~~~"],
        ["docFenceCloseIndent", ["~~~", "x"], "    ```"],
        ["docFenceCloseIndent", ["```python", "    x"], "    ```"],
        ["docFenceCloseIndent", ["use ```x``` here", "  y"], "    ```"],
    ])
    assert drifted == "" and fine is None and no_fence is None
    assert closed_already is None, "a fence that opens a new block is not a closer"
    assert tilde == "" and mismatch is None
    assert info == "", "an opening fence may carry an info string"
    assert inline is None


# --- shortcodes ----------------------------------------------------------------


@node
def test_a_colon_and_two_letters_open_the_shortcodes() -> None:
    one, too_short, in_time, in_word, rows = run([
        ["docFillToken", "Great :sm", ""],
        ["docFillToken", "Great :s", ""],
        ["docFillToken", "at 10:30", ""],
        ["docFillToken", "Note:do", ""],
        ["options", "so :thumbsu", ""],
    ])
    assert one == {"kind": "emoji", "start": 6, "query": "sm"}
    assert too_short is None and in_time is None and in_word is None
    assert rows[0][0] == ":thumbsup:" and rows[0][2] == "\U0001F44D"


@node
def test_shortcodes_match_a_later_word_after_the_first() -> None:
    heart, count = run([["emoji", "heart"], ["emojiCount"]])
    names = [n for n, _ in heart]
    assert names[0] == "heart" and "green_heart" in names
    assert count >= 200


# --- pairs ------------------------------------------------------------------------


@node
def test_brackets_pair_and_step_over_their_closer() -> None:
    open_, closed, before_word, step, wiki = run([
        ["docPairInput", "a ", "", "("],
        ["docPairInput", "a ", ") b", "["],
        ["docPairInput", "a ", "word", "("],
        ["docPairInput", "(x", ")", ")"],
        ["docPairInput", "[", "]", "["],
    ])
    assert open_ == {"insert": "()", "caret": 1}
    assert closed == {"insert": "[]", "caret": 1}
    assert before_word is None
    assert step == {"step": 1}
    assert wiki == {"insert": "[", "caret": 1, "removeAfter": 1}, "`[[` is the link menu's, with no closers"


@node
def test_bold_is_two_stars_and_a_bullet_is_one() -> None:
    bullet, bold, bold_mid, step1, step2, rule, after_word = run([
        ["docPairInput", "", "", "*"],
        ["docPairInput", "*", "", "*"],
        ["docPairInput", "say *", "", "*"],
        ["docPairInput", "**bold", "**", "*"],
        ["docPairInput", "**bold*", "*", "*"],
        ["docPairInput", "**", "**", "*"],
        ["docPairInput", "2*", "", "*"],
    ])
    assert bullet is None
    assert bold == {"insert": "***", "caret": 1}
    assert bold_mid == {"insert": "***", "caret": 1}
    assert step1 == {"step": 1} and step2 == {"step": 1}
    assert rule == {"insert": "*", "caret": 1, "removeAfter": 2}, "*** is a divider"
    assert after_word is None


@node
def test_underscore_pairs_away_from_a_word_only() -> None:
    open_, snake, double, close = run([
        ["docPairInput", "an ", "", "_"],
        ["docPairInput", "snake", "", "_"],
        ["docPairInput", "_", "_", "_"],
        ["docPairInput", "_word", "_", "_"],
    ])
    assert open_ == {"insert": "__", "caret": 1}
    assert snake is None
    assert double == {"insert": "__", "caret": 1}
    assert close == {"step": 1}


@node
def test_three_backticks_are_a_fence() -> None:
    first, second, third, after_word = run([
        ["docPairInput", "", "", "`"],
        ["docPairInput", "`", "`", "`"],
        ["docPairInput", "``", "", "`"],
        ["docPairInput", "word", "", "`"],
    ])
    assert first == {"insert": "``", "caret": 1}
    assert second == {"step": 1}
    assert third is None
    assert after_word is None


@node
def test_a_selection_is_wrapped_and_stays_selected() -> None:
    star, tick, plain_text = run([
        ["docPairInput", "a ", " b", "*", "word"],
        ["docPairInput", "", "", "`", "x"],
        ["docPairInput", "", "", "*", "word", False],
    ])
    assert star == {"insert": "*word*", "select": [1, 5]}
    assert tick == {"insert": "`x`", "select": [1, 2]}
    assert plain_text is None, "a plain text file pairs brackets only"


@node
def test_backspace_in_an_empty_pair_takes_both_halves() -> None:
    paren, bold, single_star, text = run([
        ["docPairBackspace", "(", ")"],
        ["docPairBackspace", "**", "**"],
        ["docPairBackspace", "a*", "*"],
        ["docPairBackspace", "ab", "c"],
    ])
    assert paren == 1 and bold == 1
    assert single_star == 0 and text == 0


# --- smart punctuation -------------------------------------------------------------


@node
def test_quotes_open_after_a_space_and_close_after_a_word() -> None:
    open_d, close_d, apostrophe, open_s, in_code = run([
        ["docSmartPunct", "He said ", '"'],
        ["docSmartPunct", 'He said “hi', '"'],
        ["docSmartPunct", "don", "'"],
        ["docSmartPunct", "", "'"],
        ["docSmartPunct", "use `x", '"'],
    ])
    assert open_d == {"back": 0, "insert": "“"}
    assert close_d == {"back": 0, "insert": "”"}
    assert apostrophe == {"back": 0, "insert": "’"}
    assert open_s == {"back": 0, "insert": "‘"}
    assert in_code is None


@node
def test_two_hyphens_make_a_dash_except_where_markdown_needs_them() -> None:
    word, spaced, line_start, table, third = run([
        ["docSmartPunct", "word-", "-"],
        ["docSmartPunct", "word -", "-"],
        ["docSmartPunct", "-", "-"],
        ["docSmartPunct", "| -", "-"],
        ["docSmartPunct", "a--", "-"],
    ])
    assert word == {"back": 1, "insert": "\u2014"} and spaced == word
    assert line_start is None and table is None and third is None


# --- wiring ------------------------------------------------------------------------


def test_the_list_offers_the_expansions_and_enter_takes_one() -> None:
    """The rows reach the prose popup, and Enter is theirs (never a word row's)."""
    docs = DOCUMENTS_JS.read_text(encoding="utf-8")
    render = _function(DOCUMENTS_JS, "renderDocComplete")
    assert "docFillAt(box)" in render
    fill = _function(DOCUMENTS_JS, "docFillAt")
    assert "docFillToken(" in fill and "docFillOptions(" in fill
    keys = _function(DOCUMENTS_JS, "docCompleteKeydown")
    assert 'event.key === "Enter"' in keys and ".fill" in keys
    assert "docProseGhostSet(" in docs


def test_the_pairs_and_the_ghost_are_mounted_in_the_editor() -> None:
    prose = PROSE_JS.read_text(encoding="utf-8")
    hook = _function(PROSE_JS, "docProseToolExtensions")
    assert "docProseFillExtensions(CM)" in hook
    assert re.search(r"EditorView\.inputHandler\.of", prose)


def test_smart_punctuation_is_a_preference_off_by_default(client) -> None:
    assert client.get("/preferences").json()["smart_punctuation"] is False
    assert client.put("/preferences", json={"smart_punctuation": True}).json()["smart_punctuation"] is True
    assert client.get("/preferences").json()["smart_punctuation"] is True


@node
def test_ending_a_list_leaves_the_blank_line_after_it() -> None:
    under_item, under_blank, first_line, nested = run([
        ["docListExitText", "", "- b"],
        ["docListExitText", "", ""],
        ["docListExitText", "", None],
        ["docListExitText", "- ", "- b"],
    ])
    assert under_item == "\n", "dog2 item 6: a heading typed next must not sit flush against the list"
    assert under_blank == "" and first_line == ""
    assert nested == "- ", "stepping out one level keeps the bullet"
