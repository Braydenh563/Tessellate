"""The notebook's AI is called Atlas, once, at the head of each prompt.

INBOX 225, decision taken: a name is a *theme*, not a persona. One constant
(`tessellate.ai.AI_NAME`) and one clause at the head of each prompt that
speaks as the app: the chat and Ask librarian, the agent, and the in-app
help chat. No backstory, no tone instructions, no other prompt growth.

The two things worth testing are the two things that go wrong with a name:
it appears twice (because two layers both prepend it, and the model is then
told who it is in a way no human writes), or it quietly costs context (the
persona is the half of the prompt nothing trims, `PROSE_BUDGET_CHARS`).
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.ai import AI_NAME, help_chat, librarian
from tessellate.ai import agent_policy
from tessellate.ai import agent_turn
from tests._app_js import app_js_text
from tests._app_js import frontend_text

CLAUSE = f"You are {AI_NAME},"


def test_the_name_is_written_down_once():
    assert AI_NAME == "Atlas"
    # The constant, not the string: a second literal somewhere is how the
    # name ends up half changed the next time someone renames it.
    assert AI_NAME in librarian.DEFAULT_PERSONA
    assert AI_NAME in help_chat.SYSTEM_PROMPT


def test_the_librarian_says_it_once():
    assert librarian.SYSTEM_PROMPT.startswith(CLAUSE)
    assert librarian.SYSTEM_PROMPT.count(AI_NAME) == 1


def test_the_help_chat_says_it_once():
    assert help_chat.SYSTEM_PROMPT.startswith(CLAUSE)
    assert help_chat.SYSTEM_PROMPT.count(AI_NAME) == 1


def test_the_agent_says_it_once(app_state):
    """The agent's own system message, built the way a real turn builds it."""
    messages = agent_turn.build_agent_messages("what did I write about the roof?", notes=[])
    system = messages[0]["content"]
    assert system.startswith(CLAUSE), system[:120]
    assert system.count(AI_NAME) == 1, system


def test_a_user_persona_is_not_decorated_with_it(app_state):
    """A persona the user wrote is the user speaking, not the app. Prepending
    a name to it would both contradict what they asked for and pay for the
    name twice in the one place nothing trims."""
    messages = agent_turn.build_agent_messages(
        "what did I write about the roof?",
        notes=[],
        persona_prompt="You are a blunt editor. Say what is wrong and stop.",
    )
    system = messages[0]["content"]
    assert AI_NAME not in system, system[:200]
    assert system.startswith("You are a blunt editor."), system[:120]


def test_the_name_did_not_cost_the_prompt_budget():
    """The persona is resent on every round of every turn and is never
    trimmed to the window, so a name that pushed this over would be paid for
    by a 3B model's context on every single message. It does not: the clause
    is shorter than the sentence it replaced."""
    prose = f"{librarian.DEFAULT_PERSONA} {agent_policy.AGENT_GROUNDING} {agent_policy.TOOLS_GUIDE}"
    assert len(prose) <= agent_policy.PROSE_BUDGET_CHARS, len(prose)
    # A short character since 2026-09-23 (the owner asked for more than a job
    # title); still one sentence's worth, so it cannot grow into a backstory.
    assert len(librarian.DEFAULT_PERSONA) <= 240, librarian.DEFAULT_PERSONA


# --- the same name, on the screen -------------------------------------------
#
# The frontend half of INBOX 225. The decision was that the app names Atlas
# "everywhere the app speaks as it", and for a long time it mostly did not:
# 68 strings across eight files and 41 pieces of markup still said "the AI",
# which is the machinery, not the librarian. They were swept; this is what
# keeps them swept, because the next feature to ship a tooltip will otherwise
# write "the AI" again and nothing will notice.
#
# The rule has one shape and no exemption list: **copy the user reads does not
# call it "the AI"**. Where a line genuinely means the model or the runtime
# that powers it, it says so ("the local AI", "the model", "Ollama"), which
# reads better anyway. A hit here is fixed by rewording, never by adding the
# line to an allowance, which is how a lint stops meaning anything.

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
#: Vendored code is not this app's copy.
COPY_FILES = sorted(p for p in (FRONTEND / "js").glob("*.js")) + [FRONTEND / "index.html"]
#: `\s+`, not a space: two of the three hits this lint found on its first run
#: were a line wrap, "reaches the\n    AI's instructions", which a literal
#: space would have walked straight past in exactly the copy a person reads.
THE_AI = re.compile(r"\b[Tt]he\s+AI\b")
#: **The owner's report named three phrases and this lint only ever caught
#: one.** INBOX 225 was "the AI", "the assistant" or "the guide", and the
#: sweep and the rule above took the first. Eight pieces of copy still said
#: "the assistant" a week later, five of them the Tools and features
#: descriptions a person reads while learning what the app can do, which is
#: the worst place to be vague about who is doing the work.
#:
#: "The guide" is deliberately not here. That one is a surface with a name,
#: the Atlas guide, so a line about it is naming a thing rather than dodging
#: a name, and a lint that fired on it would be teaching people to write
#: around it.
THE_ASSISTANT = re.compile(r"\b[Tt]he\s+assistant\b")


def _js_string_bodies(source: str) -> list[tuple[int, str]]:
    """Every string and template literal in a JS file, with its line number.

    Hand-scanned for the reason `test_frontend_symbols._strip` is: a regex
    cannot tell the `//` that opens a comment from the one inside
    `"https://..."`, and a lint that reads a URL as a comment goes quiet
    about the file it was written to watch.

    Regex literals are tracked because one of them proved they have to be.
    `whiteboard.js`'s `WB_MAP_INLINE` holds three backticks, so a scanner
    that reads them as code opens a template literal on the odd one and
    swallows the next hundred and thirty lines, comments and all, reporting
    a phrase from a comment as copy. A `/` opens a regex only where a value
    cannot already have appeared, which is the rule every JS tokeniser uses
    for the `a / b` against `/ab/` question.

    Quoted strings also end at the newline, since JS forbids a literal
    newline in one: it bounds any remaining mis-read to its own line.
    Template literals may legitimately span lines and are left unbounded.
    """
    #: After one of these a `/` cannot be division: there is no value to its
    #: left to divide, so it opens a regex literal.
    before_regex = set("(,=:[!&|?{};+-*%~^<>") | {""}
    keywords = {"return", "typeof", "case", "in", "of", "new", "delete", "void", "do", "else", "yield", "await"}
    bodies: list[tuple[int, str]] = []
    i, n, line = 0, len(source), 1
    previous, word = "", ""
    while i < n:
        ch = source[i]
        if ch == "\n":
            line += 1
            i += 1
        elif ch == "/" and source[i + 1 : i + 2] == "/":
            while i < n and source[i] != "\n":
                i += 1
        elif ch == "/" and source[i + 1 : i + 2] == "*":
            end = source.find("*/", i + 2)
            end = n if end == -1 else end + 2
            line += source.count("\n", i, end)
            i = end
        elif ch == "/" and (previous in before_regex or word in keywords):
            #: A regex literal: its body is not copy, so it is skipped whole.
            #: What matters is that its slashes, quotes and backticks are not
            #: read as code.
            i += 1
            in_class = False
            while i < n and source[i] != "\n":
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == "[":
                    in_class = True
                elif source[i] == "]":
                    in_class = False
                elif source[i] == "/" and not in_class:
                    break
                i += 1
            i += 1
        elif ch in "\"'`":
            start, at = i + 1, line
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == ch:
                    break
                if source[i] == "\n":
                    if ch != "`":
                        break
                    line += 1
                i += 1
            bodies.append((at, source[start:i]))
            i += 1
        else:
            i += 1
        #: The last character that was not whitespace, and the word it ends,
        #: which is what tells a regex from a division.
        tail = source[i - 1 : i]
        if tail and not tail.isspace():
            previous = tail
            word = word + tail if tail.isalpha() else ""
    return bodies


def _html_outside_comments(source: str) -> list[tuple[int, str]]:
    """Markup with its `<!-- -->` blocks removed, as (line, text) pieces."""
    pieces: list[tuple[int, str]] = []
    at, line = 0, 1
    for match in re.finditer(r"<!--.*?-->", source, re.S):
        pieces.append((line, source[at : match.start()]))
        line += source.count("\n", at, match.end())
        at = match.end()
    pieces.append((line, source[at:]))
    return pieces


def test_the_interface_never_calls_it_the_ai():
    hits = []
    for path in COPY_FILES:
        source = path.read_text(encoding="utf-8")
        pieces = (
            _html_outside_comments(source)
            if path.suffix == ".html"
            else _js_string_bodies(source)
        )
        for line, text in pieces:
            for pattern in (THE_AI, THE_ASSISTANT):
                for match in pattern.finditer(text):
                    offset = text.count("\n", 0, match.start())
                    hits.append(f"{path.name}:{line + offset}: {match.group(0)}")
    assert not hits, (
        "copy that calls the app's AI \"the AI\" or \"the assistant\" rather than "
        "by name; reword it (say the name, or name the model or runtime if that "
        "is what is meant):\n" + "\n".join(hits[:40])
    )


def test_the_frontend_spells_the_name_once():
    """In app.js, which index.html loads first.

    It lived in settings.js, the *last* script on the page, which is why
    `aiNameNow()` carries a `typeof` fallback and why no module-level string
    anywhere else could read it. Moving it forward is what let the swept copy
    be checked against the backend's own constant below.
    """
    app = app_js_text()
    settings = (FRONTEND / "js" / "settings.js").read_text(encoding="utf-8")
    assert f'const AI_NAME = "{AI_NAME}"' in app
    assert "const AI_NAME" not in settings
    assert "const GUIDE_NAME = AI_NAME;" in settings


def test_the_copy_scanner_still_sees_the_whole_file():
    """The guard that makes the lint above mean something.

    Its first version lost a hundred and thirty lines of `whiteboard.js` to a
    regex holding three backticks and reported a phrase out of a comment as
    copy. A scanner that quietly stops reading is worse than no scanner, so
    this asserts it reaches the far end of the two largest files and picks up
    strings that are known to be there.
    """
    for name, needle in (
        ("app.js", "Ask Atlas about this"),
        ("whiteboard.js", "wb-expanded-nodes"),
        ("documents.js", "The code panel could not be loaded."),
    ):
        source = frontend_text(name)
        bodies = _js_string_bodies(source)
        assert any(needle in body for _, body in bodies), f"{name}: lost {needle!r}"
        #: And it got to the bottom: the last literal it found is near the end
        #: of the file, not stranded a third of the way down.
        last = max(line for line, _ in bodies)
        total = source.count("\n") + 1
        assert last > total * 0.9, f"{name}: stopped at line {last} of {total}"
