"""An icon is an icon, not a character someone typed.

This app ships Phosphor and draws every icon with it: `setLabel(el, "ph:x")`
builds an `<i class="ph ph-x">`. A control whose whole content is the
character U+2715 looks like one of those from across the room and is nothing
of the kind up close. Measured on a button built through the app's own
`smallButton` helper, the two ways side by side:

    "✕"    system-ui  13.6px  weight 500
    "ph:x"      Phosphor   15.6px  weight 400

Two faces, two sizes, two weights, for the same control in the same row. That
is what the owner meant by "I want to strip all signs of being vibecoded by an
ai from the ui" (INBOX 263): not a taste in icons, a UI assembled from
whatever was to hand instead of from the set the app already has.

Seven download buttons said "⬇ Download" while the rest of the app said
`ph:download-simple Download`, and ten close buttons were a typed cross. This
fails the build if either comes back.

**What is not banned, and why the list is short.** An arrow in a sentence
("Settings, Models") is a breadcrumb, which is typography; an arrow key in
a shortcut list is the key's own name. Both stay. What is banned is a glyph
that stands where an icon belongs, so the test looks only at strings that are
*labels*: a string that is nothing but glyphs and spaces, or one whose first
or last non-space character is a banned glyph, which is where an icon goes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_ai_name import _html_outside_comments, _js_string_bodies  # noqa: E402
from tests._app_js import app_js_family  # noqa: E402

#: The glyphs this app has a Phosphor icon for, and reaches for anyway. Each
#: is paired with the icon that replaces it, so a failure says what to write.
INSTEAD = {
    "✕": "ph:x",
    "✖": "ph:x",
    "✗": "ph:x",
    "✘": "ph:x",
    "×": "ph:x",
    "✓": "ph:check",
    "✔": "ph:check",
    "✅": "ph:check-circle",
    "⬇": "ph:download-simple",
    "⬆": "ph:upload-simple",
    "✎": "ph:pencil-simple",
    "✏": "ph:pencil-simple",
    "⚙": "ph:gear",
    "⚡": "ph:lightning",
    "\U0001f50d": "ph:magnifying-glass",
    "\U0001f4ce": "ph:paperclip",
    "\U0001f5d1": "ph:trash",
    "\U0001f4c1": "ph:folder",
    "\U0001f4c4": "ph:file",
    "\U0001f4cc": "ph:push-pin",
    "\u2248": "ph:approximate-equals",
    #: U+29C9, two joined squares, which is what a copy button said in two
    #: places (the chat's table bar and every rendered code block) while five
    #: other Copy buttons in the same app were drawn with `ph:copy`. Added
    #: 2026-09-20, with both call sites fixed in the same commit.
    "\u29c9": "ph:copy",
    #: Added 2026-09-21 with DOCUMENTS_PLAN section 18b, the slash menus. The
    #: eight callout kinds in `editor.js` carried emoji, which the "/" menu
    #: drew beside rows of Phosphor and the renderer drew at the head of every
    #: callout in every note and document: the largest run of typed icons left
    #: in the app, and the one the owner was looking at when he asked for the
    #: slash commands to be "proper objects". The Library's own create table
    #: carried four more, three fullwidth plus signs and a record mark, with
    #: one of its two call sites already working around them by stripping the
    #: leading character before drawing an icon of its own.
    "\U0001f4dd": "ph:note",
    "\U0001f4a1": "ph:lightbulb",
    "\u2139": "ph:info",
    "\u26a0": "ph:warning",
    "\U0001f6d1": "ph:warning-octagon",
    "\u2753": "ph:question",
    "\uff0b": "ph:plus",
    "\u23fa": "ph:microphone",
    "\u2192": "ph:arrow-right",
    "\u2195": "ph:arrows-down-up",
}

#: The one deliberate exception, and it carries its reason in the code beside
#: it: `AI_STATUS_GLYPH` is a colour-blind-safe mark set, where the glyph is
#: the redundant channel that makes the colour readable without it. An icon
#: font would not serve that purpose any better and the four marks have to
#: read as one family.
ALLOWED_LINES = {("app.js", "const AI_STATUS_GLYPH")}

#: Whole object literals that are *character data*, not interface. A LaTeX
#: symbol table maps `\\times` onto U+00D7 and `\\to` onto U+2192 because those
#: are the characters the macros mean; there is no icon to write instead, and a
#: rule that fired on them would be suppressed rather than obeyed, which is the
#: failure mode this file's own decisions keep guarding against. Named rather
#: than pattern-matched, so a new table has to be added here on purpose. Each
#: block runs from `const NAME = {` to the first line that is `};`.
ALLOWED_BLOCKS = {
    ("app.js", "LATEX_SYMBOLS"),
    ("documents.js", "DOC_MATH_LETTERS"),
    ("documents.js", "DOC_MATH_OPERATORS"),
}


def _allowed_line_numbers(name: str, source_lines: list[str]) -> set[int]:
    """1-based line numbers inside this file's allowed data blocks."""
    wanted = {block for file_name, block in ALLOWED_BLOCKS if file_name == name}
    inside: set[int] = set()
    open_block: str | None = None
    for number, line in enumerate(source_lines, 1):
        if open_block is None:
            for block in wanted:
                if line.startswith(f"const {block} = {{"):
                    open_block = block
                    break
            if open_block is not None:
                inside.add(number)
            continue
        inside.add(number)
        if line.rstrip() == "};":
            open_block = None
    return inside

EDGE = re.compile(r"^\s*(.)|(.)\s*$")

#: The markup's own text, one element's worth at a time.
#:
#: `_html_outside_comments` hands back everything between two comments as one
#: piece, which for `index.html` is thousands of characters. `_offending` looks
#: at a piece's first and last character and at whether the whole piece is
#: marks, so against a piece that size it can never answer yes: the check was
#: alive for JS strings and dead for markup. Found 2026-09-21 by an affordance
#: sweep, not by this test, with three graph zoom buttons reading "＋",
#: "－" and "⤢" beside a fourth drawn with `ph:frame-corners`.
#:
#: So the text between one `>` and the next `<` is scanned on its own, which is
#: exactly the unit a button's whole content is.
HTML_TEXT = re.compile(r">([^<>]+)<")

#: `<kbd>` holds a key's own name. An arrow there is the arrow key, the one
#: case this file's own docstring already carved out ("an arrow key in a
#: shortcut list is the key's own name"), and the shortcuts sheet is full of
#: them. Blanked before the scan rather than listed line by line, because the
#: sheet gains rows and a line-number allowlist would rot.
HTML_KBD = re.compile(r"<kbd\b[^>]*>.*?</kbd>", re.S)


def _html_element_text(source: str) -> list[tuple[int, str]]:
    def keep_lines(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    body = re.sub(r"<!--.*?-->", keep_lines, source, flags=re.S)
    body = HTML_KBD.sub(keep_lines, body)
    out: list[tuple[int, str]] = []
    for match in HTML_TEXT.finditer(body):
        text = match.group(1)
        if not text.strip():
            continue
        out.append((body.count("\n", 0, match.start(1)) + 1, text))
    return out

#: `\u{1F4C1}` and `\u00d7` are the same characters as the ones above, written
#: the way a JS file is allowed to write them, and for a while that was the way
#: past this test. Thirty-eight of the "/" menu's command labels were escaped
#: emoji (`editor.js`, measured 2026-09-21): every one of them drew a system
#: emoji in a menu of Phosphor, every one of them read as a plain backslash
#: sequence to a scanner reading the source text of the literal, and this test
#: said nothing about any of them while it was catching the typed ones one at a
#: time. The escapes are decoded before the glyph check, so the two spellings
#: are the same finding.
ESCAPE = re.compile(r"\\u\{([0-9a-fA-F]{1,6})\}|\\u([0-9a-fA-F]{4})")


def _decode_escapes(body: str) -> str:
    def one(match: re.Match[str]) -> str:
        return chr(int(match.group(1) or match.group(2), 16))

    return ESCAPE.sub(one, body)


#: `\u00d7` is also the multiplication sign, and "\u00d75" ("seen five times")
#: is arithmetic rather than a close button. What follows it is what tells the
#: two apart: a number, or a template hole that will hold one.
TIMES = re.compile(r"\u00d7\s*(\d|\$\{)")


def _offending(body: str) -> str | None:
    """The banned glyph in `body` if it is being used as an icon, else None."""
    stripped = _decode_escapes(body).strip()
    if not stripped:
        return None
    if TIMES.match(stripped):
        return None
    #: Nothing but glyphs and spaces: a label that is only a mark.
    if all(c in INSTEAD or c.isspace() for c in stripped):
        return next(c for c in stripped if c in INSTEAD)
    #: Or one at either end, which is where an icon sits beside its words.
    for candidate in (stripped[0], stripped[-1]):
        if candidate in INSTEAD:
            return candidate
    return None


def _scan(name: str, pairs: list[tuple[int, str]], source_lines: list[str]) -> list[str]:
    found = []
    data_lines = _allowed_line_numbers(name, source_lines)
    for line_no, body in pairs:
        if line_no in data_lines:
            continue
        glyph = _offending(body)
        if glyph is None:
            continue
        line = source_lines[line_no - 1] if line_no <= len(source_lines) else ""
        if any(name == f and marker in line for f, marker in ALLOWED_LINES):
            continue
        found.append(
            f"{name}:{line_no}: {glyph!r} used as an icon in {body.strip()[:60]!r}; "
            f"write {INSTEAD[glyph]!r} instead"
        )
    return found


def test_no_typed_glyph_stands_in_for_an_icon():
    offenders: list[str] = []
    for path in sorted((ROOT / "frontend" / "js").glob("*.js")):
        source = path.read_text(encoding="utf-8")
        #: The pieces of the old app.js answer to app.js's allowances.
        name = "app.js" if app_js_family(path) else path.name
        offenders += _scan(name, _js_string_bodies(source), source.splitlines())
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    offenders += _scan("index.html", _html_outside_comments(html), html.splitlines())
    offenders += _scan("index.html", _html_element_text(html), html.splitlines())
    assert not offenders, "\n".join(offenders)
