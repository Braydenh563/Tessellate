"""A Library row's one-line preview is plain words, never markdown marks.

The owner, with a screenshot of the Library list (INBOX 244): "inline md
characters show in the document descriptions", the rows reading
`[[# Girl with bell]]`, `**bold** and *italic*` and `| Example Table |
|------|`. Every case here is one of those, plus the marker a clip can split.
"""

from tessellate.api.routes_library import _clip


def test_wiki_links_become_their_titles():
    assert _clip("**Offline Links**: [[# Girl with bell]], [[Slides|the slides]]") == (
        "Offline Links: Girl with bell, the slides"
    )


def test_emphasis_and_lists_are_plain():
    text = "# Title\n\n- We can include **bold** and *italic* text.\n1. And a list"
    # The heading and the list stay apart (INBOX 464); a list item that ends
    # its sentence needs no separator after it.
    assert _clip(text) == "Title · We can include bold and italic text. And a list"


def test_a_table_reads_as_its_cells():
    text = "| Example Table | Value |\n|---------------|-------|\n| Row 1 | 2 |\n| Row 2 | 3 |"
    # One row per block (INBOX 464): the cells of a row run on, rows do not.
    assert _clip(text) == "Example Table Value · Row 1 2 · Row 2 3"


def test_an_unpaired_marker_does_not_survive():
    assert _clip("Offline Links**: no partner ***here") == "Offline Links: no partner here"


def test_an_asterisk_that_is_not_a_marker_stays():
    assert _clip("5 * 3 = 15") == "5 * 3 = 15"


def test_every_table_rule_shape_is_still_dropped():
    for rule in ("|---|---|", "| --- | :---: |", "--- | ---", "  |:--|--:|  ", "|---|---|\r"):
        assert _clip(f"| a | b |\n{rule}\n| 1 | 2 |") == "a b · 1 2", rule


def test_a_long_run_of_blank_lines_or_whitespace_is_not_a_stall():
    """Measured 2026-10-04: 500 blank lines took 0.84 s, 1,000 took 6.5 s and
    2,000 took 49 s, on every Library list that held the note (`\\s` crossed
    newlines in the table-rule pattern, cubic in the run). 20,000 of each
    shape must be instant now."""
    import time

    for text in ("Pasted\n" + "\n" * 20000 + "end", "a" + " " * 20000 + "b", "\t" * 20000 + "x", " \n" * 20000 + "x"):
        started = time.perf_counter()
        _clip(text)
        assert time.perf_counter() - started < 1.0, repr(text[:12])


def test_a_code_fence_marker_is_not_a_word():
    # Dogfood round 1, item 18: the preview read "`py print(1) `".
    text = "# Notes\n\n```py\nprint(1)\n```\n\nAfter"
    assert _clip(text) == "Notes · print(1) After"
    assert _clip("~~~\nx\n~~~") == "x"
