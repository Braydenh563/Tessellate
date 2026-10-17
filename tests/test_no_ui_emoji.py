"""No emoji, dingbat or pictograph in the UI's own text (INBOX 506).

The owner: "make sure that the icons are used properly and no text emojis are
still used." Every icon in this app is a Phosphor glyph (`setLabel(el,
"ph:name Label")`, `<i class="ph ph-name" aria-hidden="true">`, or a
`content: "\\e..."` in Phosphor's font for a CSS-drawn mark). A character from
the emoji, dingbat, geometric-shape or misc-symbol blocks drawn in the system
font is a second icon set nobody chose: it differs in size, weight, colour and
baseline from the one beside it.

`tests/test_no_glyph_icons.py` already bans the dozen glyphs the app had a
Phosphor twin for, by the *position* a string sits in. This is the wider net,
by *character class*, over everything that can render: JS string and regex
literals (comments removed, `\\u` escapes decoded, so an escaped emoji is the
same finding as a typed one), the markup's own text, and CSS (comments removed,
`\\2713`-style escapes decoded, so a `content: "\\2713"` is the same finding as
`content: "✓"`).

What is not banned, and why the class is narrow:

* Arrows (U+2190 to U+21FF) in JS strings and markup: a breadcrumb ("Settings →
  Models") and an arrow key's name in a `<kbd>` are typography. In **CSS**
  they are banned, because a `content:` arrow is a drawn mark, not a sentence.
* `×` (U+00D7) in JS and markup: a dimension ("640 × 480"), a count ("used 3×").
  In CSS it is banned, for the same reason as the arrows.
* `⌘` (U+2318), the Mac key's own name; `…`, `·` and the other punctuation.
* The documented data cases in `ALLOWED`, each with its reason. A new one is
  added on purpose, in the commit that adds the data, never to silence a
  finding: if the character stands where an icon belongs, write the icon.

The inventory this was built from is `scratchpad/emoji-icons-506.md`.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def _cls(*ranges: tuple[int, int]) -> str:
    return "[" + "".join(f"\\U{a:08x}-\\U{b:08x}" for a, b in ranges) + "]"


#: Emoji and pictographic blocks: banned everywhere. U+2318 and U+2325 (the
#: Mac Command and Option keys' own names, in shortcut hints) are carved out
#: of the technical block below.
_PICTO = [
    (0x1F000, 0x1FAFF),  # mahjong, cards, pictographs, emoticons, transport, symbols
    (0x2600, 0x27BF),  # misc symbols and dingbats: check, cross, star, warning, gear
    (0x2B00, 0x2BFF),  # misc symbols and arrows: stars, squares, fat arrows
    (0x2300, 0x2317),  # misc technical: hourglass, watch, keyboard, play controls
    (0x2319, 0x2324),
    (0x2326, 0x23FF),
    (0x25A0, 0x25FF),  # geometric shapes: record dots, triangles, chevrons
    (0x2900, 0x297F),  # supplemental arrows B
    (0xFE0F, 0xFE0F),  # emoji presentation selector
    (0x200D, 0x200D),  # zero-width joiner of an emoji sequence
    (0x20E3, 0x20E3),  # keycap
    (0x22EE, 0x22EF),  # vertical and horizontal ellipsis: the kebab icon, typed
    (0x2261, 0x2261),  # the hamburger icon, typed
]
#: Banned only where it is drawn (CSS), allowed in a sentence (JS, markup).
_TYPO = [(0x2190, 0x21FF), (0x00D7, 0x00D7)]

PICTO = re.compile(_cls(*_PICTO) + "+")
PICTO_OR_TYPO = re.compile(_cls(*_PICTO, *_TYPO) + "+")

#: path (relative to the repo) -> [(marker, reason)]. A finding passes when
#: its source line contains the marker; the marker `"*"` passes the whole
#: file. A block entry `("block:const NAME", reason)` passes every line from
#: that declaration to the first line that ends a statement.
ALLOWED: dict[str, list[tuple[str, str]]] = {
    "frontend/js/documents-prose.js": [
        (
            "block:const DOC_EMOJI_SOURCE",
            "the Markdown :shortcode: table (user content: `:fire:` renders an emoji); "
            "marked unslop-ignore in the file",
        ),
    ],
    "frontend/js/icon-picker.js": [
        (
            "block:const ICON_EMOJI_SOURCE",
            "the icon and emoji picker's curated emoji (MINDMAP_PLAN decision 43): "
            "glyphs a person chooses to put in their own map, board or text, never "
            "the app's own icons",
        ),
        (
            "block:const ICON_KAOMOJI",
            "the picker's Japanese emoticons (INBOX 904 B81): text a person inserts "
            "into their own note, made of these characters; no Phosphor glyph can stand in",
        ),
    ],
    "frontend/js/avatars.js": [
        (
            "/u",
            "regexes that recognise emoji the person typed so the companion can react "
            "to them; matching user content, not drawing it",
        ),
        ("/.test(raw)", "the table-flip kaomoji matcher, same reason"),
    ],
    "frontend/js/dashboard.js": [
        ("LEADING_EMOJI", "a regex that strips a leading emoji a person typed into a title"),
    ],
    "frontend/js/status.js": [
        (
            "const AI_STATUS_GLYPH",
            "the colour-blind-safe status mark set, documented at the declaration: the "
            "glyph is the redundant channel and the four marks must read as one family",
        ),
    ],
    "frontend/js/whiteboard.js": [
        (
            "obj.data?.task",
            "the exported SVG's task box: the icon font does not travel into the file "
            "(MINDMAP_PLAN decision 15), so the ballot-box characters are the portable form",
        ),
    ],
    "frontend/js/notes-list.js": [
        ("block:const LATEX_SYMBOLS", "character data: what `\\rightarrow` means"),
    ],
    "frontend/js/documents.js": [
        ("block:const DOC_MATH_LETTERS", "character data: what the math macros mean"),
        ("block:const DOC_MATH_OPERATORS", "character data: what the math macros mean"),
    ],
    "frontend/index.html": [
        ("⋯ menu", "help prose naming the kebab control, which is a word here, not an icon"),
    ],
    "frontend/js/library.js": [
        ("⋯ menu", "help prose naming the kebab control, which is a word here, not an icon"),
    ],
}


# ---------------------------------------------------------------------------
# Source readers


_ESC = re.compile(r"\\u\{([0-9A-Fa-f]{1,6})\}|\\u([0-9A-Fa-f]{4})")
_CSS_ESC = re.compile(r"\\([0-9A-Fa-f]{1,6}) ?")


def _decode(text: str) -> str:
    return _ESC.sub(lambda m: chr(int(m.group(1) or m.group(2), 16)), text)


def _blank(text: str) -> str:
    return "".join(c if c == "\n" else " " for c in text)


def _js_literals(src: str) -> list[tuple[int, str]]:
    """(offset, text) of every string, template and regex literal; comments dropped."""
    out: list[tuple[int, str]] = []
    i, n, prev = 0, len(src), ""
    while i < n:
        c, two = src[i], src[i : i + 2]
        if two == "//":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if two == "/*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "\"'":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            out.append((i, src[i : j + 1]))
            i, prev = j + 1, c
            continue
        if c == "`":
            j, depth = i + 1, 0
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if depth == 0 and src[j] == "`":
                    break
                if src[j : j + 2] == "${":
                    depth += 1
                    j += 2
                    continue
                if depth and src[j] == "}":
                    depth -= 1
                j += 1
            out.append((i, src[i : j + 1]))
            i, prev = j + 1, "`"
            continue
        if c == "/" and (prev == "" or prev in "(,=:[!&|?{};+-*%<>~^"):
            j, cls = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    cls = True
                elif src[j] == "]":
                    cls = False
                elif src[j] == "/" and not cls:
                    break
                j += 1
            out.append((i, src[i : j + 1]))
            i, prev = j + 1, "/"
            continue
        if not c.isspace():
            prev = c
        i += 1
    return out


def _findings(path: Path) -> list[tuple[int, str]]:
    """(line, characters) for every banned character in one frontend file."""
    src = path.read_text(encoding="utf-8")
    found: list[tuple[int, str]] = []
    if path.suffix == ".js":
        for offset, text in _js_literals(src):
            for match in PICTO.finditer(_decode(text)):
                line = src.count("\n", 0, offset) + 1
                #: A literal that spans lines (a template): count to the char.
                decoded_before = _decode(text)[: match.start()]
                found.append((line + decoded_before.count("\n"), match.group(0)))
    elif path.suffix == ".css":
        clean = re.sub(r"/\*.*?\*/", lambda m: _blank(m.group(0)), src, flags=re.S)
        clean = _CSS_ESC.sub(lambda m: chr(min(int(m.group(1), 16), 0x10FFFF)), clean)
        for match in PICTO_OR_TYPO.finditer(clean):
            found.append((clean.count("\n", 0, match.start()) + 1, match.group(0)))
    else:  # index.html: markup text and inline attributes; comments dropped
        clean = re.sub(r"<!--.*?-->", lambda m: _blank(m.group(0)), src, flags=re.S)
        clean = re.sub(r"/\*.*?\*/", lambda m: _blank(m.group(0)), clean, flags=re.S)
        clean = re.sub(r"<kbd\b[^>]*>.*?</kbd>", lambda m: _blank(m.group(0)), clean, flags=re.S)
        for match in PICTO.finditer(clean):
            found.append((clean.count("\n", 0, match.start()) + 1, match.group(0)))
    return sorted(set(found))


def _block_lines(lines: list[str], marker: str) -> set[int]:
    """1-based lines from a declaration to the first line that ends a statement."""
    inside: set[int] = set()
    for start, line in enumerate(lines, 1):
        if marker not in line:
            continue
        for number in range(start, len(lines) + 1):
            inside.add(number)
            code = lines[number - 1].split("//")[0].rstrip()
            if code.endswith(";"):
                break
    return inside


def _allowed(rel: str, line_no: int, lines: list[str]) -> bool:
    for marker, _reason in ALLOWED.get(rel, []):
        if marker == "*":
            return True
        if marker.startswith("block:"):
            if line_no in _block_lines(lines, marker[len("block:") :]):
                return True
        elif line_no <= len(lines) and marker in lines[line_no - 1]:
            return True
    return False


def _files() -> list[Path]:
    return [
        FRONTEND / "index.html",
        *sorted((FRONTEND / "js").glob("*.js")),
        *sorted((FRONTEND / "css").glob("*.css")),
    ]


def test_no_emoji_or_dingbat_in_the_ui():
    offenders: list[str] = []
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_no, chars in _findings(path):
            if _allowed(rel, line_no, lines):
                continue
            names = ",".join(f"U+{ord(c):04X}" for c in chars)
            offenders.append(
                f"{rel}:{line_no}: {chars!r} ({names}) in "
                f"{lines[line_no - 1].strip()[:80]!r}: draw it with a Phosphor icon "
                f"(`ph:name Label`, `<i class=\"ph ph-name\" aria-hidden=\"true\">`, or a "
                f"`content: \"\\e...\"` with `font-family: Phosphor`)"
            )
    assert not offenders, "\n".join(offenders)


def test_the_allowlist_has_no_dead_entries():
    """An entry whose marker no longer matches anything is a rule that has rotted."""
    dead: list[str] = []
    for rel, entries in ALLOWED.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for marker, _reason in entries:
            needle = marker[len("block:") :] if marker.startswith("block:") else marker
            if needle != "*" and needle not in text:
                dead.append(f"{rel}: {marker!r}")
    assert not dead, "allowlist entries that match nothing:\n" + "\n".join(dead)


def test_the_ratchet_sees_what_it_claims_to():
    """Self-check: the scanner catches a typed emoji, an escaped one and a CSS escape."""
    tmp = ROOT / "tests" / "__pycache__"
    tmp.mkdir(exist_ok=True)
    js = tmp / "_emoji_probe.js"
    css = tmp / "_emoji_probe.css"
    try:
        js.write_text('const a = "\\u{1F4CE} attach"; const b = "✓ ok"; // ✨ comment\n', encoding="utf-8")
        css.write_text('/* ✓ comment */ .x::after { content: "\\2713"; } .y::after { content: "↑"; }\n', encoding="utf-8")
        assert sorted(c for _, c in _findings(js)) == sorted(["\U0001f4ce", "✓"])
        assert sorted(c for _, c in _findings(css)) == sorted(["✓", "↑"])
    finally:
        js.unlink(missing_ok=True)
        css.unlink(missing_ok=True)
