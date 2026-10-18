"""Numbered citations inside an AI answer, not only in a row beneath it.

Asked for directly: *"inline referencing with hyperlinks in ai chat messages
would be amazing."*

The data always existed, `ground_answer_sentences` returns {sentence,
note_id} pairs: and only ever reached a chip row under the answer, which is
the one place a claim and its source are *not* read together.

Asserted against the source because this app has no DOM in its Python suite
(same reason `test_frontend_ids.py` exists). The behaviour itself was driven
in Chromium: two grounded sentences in one paragraph produced markers 1 and 2
in the right places, a grounded sentence that does not appear in the answer
produced none, and the chips renumbered to match.
"""

from __future__ import annotations

import re

import pytest
from tests._app_js import app_js_text, frontend_text

@pytest.fixture(scope="module")
def app_js() -> str:
    return app_js_text()


def test_the_function_exists(app_js):
    assert "function addInlineCitations(" in app_js


def test_it_is_actually_called(app_js):
    """CLAUDE.md's own "features that never ran once" category: a function
    with no call site is not a feature. `renderAnswerGrounding` is the one
    place that has both the sentences and the answer element."""
    #: The fourth argument is the Sources panel's own ordering, added when the
    #: Ask tab's markers, chips and panel were made to count the same way
    #: (`citationNumbers`): the call site is what this test is about, not its
    #: arity, but naming it here keeps the assertion honest about the shape.
    assert "addInlineCitations(answerEl, sentences, rawResults, orderedSources)" in app_js


def _grounding_call_args(app_js: str) -> list[list[str]]:
    """The argument list of every `renderAnswerGrounding` call, one list of
    trimmed source expressions per call site, the definition excluded.

    Read positionally rather than grepped for a needle, because the first
    version of this test asserted the literal text `"answerBox\n"`: true only
    while the answer element happened to be the *last* argument. Adding a
    fifth argument (the turn's question, so opening a source teaches the
    search) broke the assertion without breaking anything it was protecting.
    A test whose failure does not mean the bug it names is a test that gets
    widened next time, so it reads the position instead.
    """
    calls = []
    needle = "renderAnswerGrounding("
    at = app_js.find(needle)
    while at != -1:
        start = at + len(needle)
        depth, end = 1, start
        while depth:
            char = app_js[end]
            depth += {"(": 1, ")": -1}.get(char, 0)
            end += 1
        # Comments explaining an argument sit on their own lines above it, and
        # they contain commas and parentheses of their own, so they go before
        # anything is split.
        body = "\n".join(
            line
            for line in app_js[start : end - 1].splitlines()
            if not line.strip().startswith("//")
        )
        # The definition, not a call: its argument list names the parameters.
        if "target" not in body.split(",")[0]:
            args, depth, current = [], 0, []
            for char in body:
                if char in "([{":
                    depth += 1
                elif char in ")]}":
                    depth -= 1
                if char == "," and depth == 0:
                    args.append("".join(current))
                    current = []
                else:
                    current.append(char)
            args.append("".join(current))
            calls.append([" ".join(arg.split()) for arg in args])
        at = app_js.find(needle, end)
    return calls


def test_every_grounding_call_site_passes_the_answer_element(app_js):
    """Four surfaces render grounding: the Ask box, a live chat turn, a
    reopened conversation, and a turn reopened from the Ask history panel
    (INBOX 241, which is why the fourth is here). A call site that forgets the
    fourth argument gets the chips and silently no markers, which is exactly
    the half-wired state this file exists to prevent.

    The inventory is spelled out rather than counted loosely on purpose: a new
    surface has to come here and say so, which is how a fifth one gets read
    against this rule instead of quietly inheriting it.
    """
    calls = _grounding_call_args(app_js)
    assert len(calls) == 4, f"expected 4 call sites, found {len(calls)}"
    fourth = sorted(args[3] for args in calls if len(args) > 3)
    assert len(fourth) == 4, f"a call site passes no answer element: {calls}"
    assert fourth == sorted(
        [
            #: `askQuestion`'s live answer, and `viewAskHistoryTurn`'s
            #: remembered one, which render into the same element.
            "answerBox",
            "answerBox",
            'bubble.querySelectorAll(".bubble-answer")',
            'handles.bubble?.querySelectorAll(".bubble-answer") || null',
        ]
    ), fourth


def test_a_chat_turn_hands_over_all_of_its_prose_blocks(app_js):
    """INBOX 40: a skill run and an agent turn showed no markers at all.

    The timeline gives each step's prose its own `.bubble-answer` node, so
    `querySelector` handed the citation walker step 1's narration while every
    grounded sentence was in the final answer, several nodes further down.
    `querySelectorAll` is the fix and the rule: a call site that narrows back
    to one node silently loses the markers again on exactly the two surfaces
    that need them most.
    """
    assert 'querySelector(".bubble-answer")' not in app_js
    #: Seven: the three citation sites, the live one that numbers sources while
    #: the answer streams (`placeLiveCitations`), the two that place figures
    #: (INBOX 526) and the digest offer's.
    assert app_js.count('querySelectorAll(".bubble-answer")') == 7


def test_the_live_renderer_is_stopped_before_the_markers_go_in(app_js):
    """The second half of INBOX 40, and the one nothing on screen showed.

    Every streamed delta arms a paint up to `LIVE_RENDER_INTERVAL_MS` ahead.
    A turn that ends between the last delta and that timer had its markers
    placed by the code after `finalise()` and then wiped by the timer, with
    identical prose left behind, so it read as "citations do not work in a
    skill run" rather than as a race. `finalise` cancels the armed paint
    first; without the cancel the markers survive about a tenth of a second.
    """
    assert "render.stop = () => {" in app_js
    body = app_js.split("    finalise() {")[1].split("\n    },")[0]
    assert "step.render?.stop?.()" in body, "finalise must cancel the armed paint first"
    assert body.index("stop?.()") < body.index("renderMarkdown"), (
        "the cancel has to come before the re-render, not after it"
    )


def test_a_sentence_split_across_markup_is_still_found(app_js):
    """INBOX 318, measured with `scratchpad/ui-sweeps/askgrounding.js` against
    an answer shaped the way a model writes (a list with bold labels, a word in
    italics): the grounding named three notes and no marker was placed,
    because the search looked for the raw markdown sentence inside one text
    node at a time. It matches on letters and digits across the block now, and
    the marker goes after the sentence's last letter, so it can never land on
    half a sentence, which was the reason the old rule gave for skipping."""
    body = app_js.split("const CITATION_WORD_CHAR")[1].split("\nfunction citationMarker(")[0]
    assert "NodeFilter.SHOW_TEXT" in body
    #: `anchor` (6bf818a45): the words a mark follows when it sits mid-sentence.
    assert "citationKey(g.anchor || g.sentence)" in body, "sentences are compared on letters and digits"
    assert "index.at[start + key.length - 1]" in body, "the marker goes after the last letter"


def test_placing_the_markers_twice_draws_them_once(app_js):
    """The Ask tab re-places them after every live paint (INBOX 320)."""
    body = app_js.split("function addInlineCitations(")[1].split("\nfunction citationMarker(")[0]
    assert 'querySelectorAll(".answer-citation")) old.remove()' in body


def test_the_chips_are_numbered_to_match_the_markers(app_js):
    body = app_js.split("function renderAnswerGrounding(")[1].split("\n}")[0]
    assert "${n}." in body, "the chip row is the key to the markers, so it has to count"


#: **Every live renderer is stopped before its box is written to again.**
#:
#: Reported twice by the owner: *"In-text referencing and grounding in the ask
#: subtab doesn't stick"* and *"Grounding and in-text referencing not working
#: now?? Needs fix."* Measured end to end
#: (`scratchpad/ui-sweeps/askgrounding.js`, against
#: `scratchpad/fake_answer_server.py`): `addInlineCitations` placed all three
#: markers correctly, and a `setTimeout` armed by `liveMarkdownRenderer` up to
#: `LIVE_RENDER_INTERVAL_MS` before the stream ended then fired and repainted
#: `#ai-answer` from the raw markdown, removing every one of them.
#:
#: The renderer has carried a `stop()` for exactly this since INBOX 40, when
#: the same race was fixed for skill runs; the Ask tab was the one caller that
#: never called it. Nothing in the suite could see that, because the prose is
#: identical either way: only the little numbers go.
#:
#: So the rule is the shape, not the bug: a live renderer whose `stop` is never
#: called is a marker race waiting to happen, in whichever surface adds one
#: next.
def test_every_live_markdown_renderer_is_stopped_somewhere() -> None:
    source = app_js_text()
    #: `const x = liveMarkdownRenderer(...)` and `render: liveMarkdownRenderer(...)`
    #: are the two shapes in use; the second is a step field, stopped as
    #: `step.render?.stop?.()`, so the name to look for is the key either way.
    holders = re.findall(
        r"(?:const|let|var)\s+(\w+)\s*=\s*liveMarkdownRenderer\(|(\w+)\s*:\s*liveMarkdownRenderer\(",
        source,
    )
    names = [a or b for a, b in holders]
    assert names, "liveMarkdownRenderer is no longer used under a name this can check"
    unstopped = [
        name
        for name in names
        #: `name.stop()`, `name?.stop?.()` and `step.render?.stop?.()` all end
        #: in the same two tokens, which is what makes one pattern enough.
        if not re.search(rf"\b{re.escape(name)}\??\.\s*stop\??\.?\(\)", source)
    ]
    assert not unstopped, (
        "a liveMarkdownRenderer is never stopped, so a paint armed before the "
        f"stream ended can repaint over the citation markers: {unstopped}"
    )


def test_a_reopened_chat_numbers_its_marks_by_the_panel_it_shows():
    """INBOX 430: a mark read 1 after reopening a chat while its peek and the
    Sources panel called the same note 8. The live path hands the panel's
    order to the citation pass (`turnSources`); the reopen path passed null,
    so the marks fell back to "order first cited". Both paths now build the
    order once and hand the same list to both."""
    reopen = frontend_text("sheets-selects.js")
    start = reopen.index("const savedOrder = chatSourcesFrom(savedInput);")
    rest = reopen[start:]
    assert "chatSourcesPanel({ ...savedInput, sources: savedOrder })" in rest
    call = rest[rest.index("renderAnswerGrounding(") :]
    call = call[: call.index(");")]
    assert "savedOrder" in call, call


def test_the_popup_agent_numbers_its_answer_like_chat():
    """BACKLOG (the owner, 2026-10-12): the popup agent's answers carried a
    Sources list and no in-text marks. It now takes both `grounding` events,
    re-places the marks after every paint (`renderMarkdown` rebuilds the
    answer), numbers them over the list `cmdPaletteSources` draws, and the
    rows carry that number."""
    palette = frontend_text("palette.js")
    start = palette.index("async function cmdPaletteAsk(")
    ask = palette[start:]
    assert "onGrounding: onCites" in ask
    assert "onGroundingLive: onCites" in ask
    call = ask[ask.index("addInlineCitations(") :]
    call = call[: call.index(");")]
    assert "answerBox" in call and "found" in call
    assert "chatSourcesFrom({ meta, touched: [...touched.values()] })" in call
    #: Every paint that rebuilds the answer puts the marks back.
    paints = [m.start() for m in re.finditer(r"renderMarkdown\(answerBox, ", ask)]
    assert paints, "the popup agent paints its answer with renderMarkdown"
    for at in paints:
        assert "cite();" in ask[at : at + 160], ask[at : at + 160]
    #: The row shows the number the mark carries.
    row = palette[palette.index("function cmdSourceRow(") :]
    assert "chat-source-index" in row[: row.index("\n}\n")]
    assert "numbering.indexOf(source) + 1" in frontend_text("chat-agent.js")
