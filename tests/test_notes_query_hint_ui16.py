"""Source text: "Show query help in the notes search box and fold editor bars into two."

L-ui-modernisation-16, the first half (13.2: "the inline query grammar is
invisible"; the fix named: "the query help in the box"). Focused and empty,
the notes filter's placeholder is the longest example of the grammar that fits
the field, measured with the field's own font; blurred, it says "Filter notes"
again. Measured room at rest: 222px at 1440, 299 at 1100, 94 at 820, 240 at
390 and 210 at 360, so one fixed placeholder could not hold an example."""

from tests._app_js import frontend_text

#: In search-suggest.js, the lazy file the box's first focus loads: boot code
#: is at its gzip cap (tests/test_static_compression.py TOTAL_CAP).
JS = frontend_text("search-suggest.js")


def _wiring() -> str:
    start = JS.index("The query grammar in the notes box")
    return JS[start : start + 2000]


def test_the_box_shows_an_example_of_the_grammar_when_focused() -> None:
    block = _wiring()
    assert 'addEventListener("focus"' in block and 'addEventListener("blur"' in block
    for word in ("tag:", "is:favourite", "before:"):
        assert word in block, word
    # Fitted to the field, not assumed: the field's own font and width.
    assert "measureText(" in block and "clientWidth" in block


def test_every_example_starts_with_try_and_is_sentence_case() -> None:
    block = _wiring()
    tries = block[block.index("const tries = [") :]
    tries = tries[: tries.index("];")]
    examples = [part.split('"')[1] for part in tries.split(",\n") if '"' in part]
    assert len(examples) >= 3
    assert all(example.startswith("Try ") for example in examples)
    assert all("!" not in example and "—" not in example for example in examples)
