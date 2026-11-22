"""Both command tables are tables of the same object.

The owner, INBOX 295: "I want them to be properly structured elements ...
proper objects". Reading the code before believing the brief (DOCUMENTS_PLAN
section 18) found two reasonable tables rather than a mess, but two shapes:
`DOC_COMMANDS` in documents.js carried its icon in its own `icon` field, and
editor.js's per-context lists packed theirs into the front of `label`, as a
string the row builder printed whole.

That difference was not cosmetic. It is why the eight callout commands reached
for emoji: the row builder used `textContent`, so a `ph:` token written into a
label would have printed as the literal text "ph:note Note box". And it quietly
broke the menu's own ranking, which scores `label.startsWith(query)` first: no
label started with a letter, so that branch could never fire and typing the
first word of a command ranked it no better than a keyword hit.

So: one row shape, and the icon is a field. This test reads both tables from
source, without a browser, the way `test_doc_commands.py` already reads one.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

#: A row is `{ ... }` with an `id:` in it, inside one of the arrays below. Read
#: by brace matching rather than by a regex over the whole literal: several
#: rows hold a `run` whose arrow function contains its own braces.
def _rows(source: str, start: int) -> list[str]:
    depth = 0
    rows: list[str] = []
    current: list[str] = []
    i = start
    while i < len(source):
        ch = source[i]
        if ch == "[" and depth == 0:
            depth = 1
            i += 1
            continue
        if depth == 0:
            i += 1
            continue
        if ch == "]" and depth == 1:
            break
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 1:
                rows.append("".join(current) + "}")
                current = []
                i += 1
                continue
        if depth > 1:
            current.append(ch)
        i += 1
    return rows


def _doc_command_rows() -> list[str]:
    source = (FRONTEND / "js" / "documents-commands.js").read_text(encoding="utf-8")
    at = source.index("const DOC_COMMANDS = [")
    return _rows(source, at)


def _editor_command_rows() -> list[str]:
    """Every object literal in editor.js that declares a command `id`.

    editor.js builds its rows in four functions rather than one array, so they
    are found by shape: an object with an `id:` and a `run:`, which is what a
    command is.
    """
    source = (FRONTEND / "js" / "editor.js").read_text(encoding="utf-8")
    rows = []
    for match in re.finditer(r"\{[^{}]*\bid:[^{}]*\brun:", source):
        depth = 0
        for end in range(match.start(), len(source)):
            if source[end] == "{":
                depth += 1
            elif source[end] == "}":
                depth -= 1
                if depth == 0:
                    rows.append(source[match.start():end + 1])
                    break
    return rows


ICON = re.compile(r'icon:\s*(?:"(ph:[a-z0-9-]+)"|meta\.icon)')
LABEL = re.compile(r"label:\s*[\"`]")


def test_every_command_row_carries_its_icon_as_its_own_field():
    rows = _doc_command_rows() + _editor_command_rows()
    assert len(rows) > 40, f"only {len(rows)} command rows found; has a table moved?"
    missing = [r for r in rows if not ICON.search(r)]
    assert not missing, "command rows with no `icon` field:\n" + "\n".join(
        r.strip()[:110] for r in missing
    )


def test_no_command_label_carries_an_icon_token():
    """The icon lives in `icon`, never at the front of `label`.

    A token inside a label is what the row builder used to print as text, and
    it is what stopped `label.startsWith(query)` from ever matching.
    """
    offenders = []
    for row in _doc_command_rows() + _editor_command_rows():
        for label in re.findall(r"label:\s*[\"`]([^\"`]*)[\"`]", row):
            if label.strip().startswith("ph:"):
                offenders.append(label.strip()[:80])
    assert not offenders, "labels opening with an icon token:\n" + "\n".join(offenders)


def test_no_command_label_opens_with_a_character_outside_ascii():
    """The emoji check, at the table rather than at the screen.

    `test_no_glyph_icons.py` holds the named glyphs; this holds the shape, so a
    character it has never seen cannot arrive as a row's first mark.
    """
    offenders = []
    for row in _doc_command_rows() + _editor_command_rows():
        for label in re.findall(r"label:\s*\"((?:[^\"\\]|\\.)*)\"", row):
            decoded = re.sub(
                r"\\u\{([0-9a-fA-F]{1,6})\}|\\u([0-9a-fA-F]{4})",
                lambda m: chr(int(m.group(1) or m.group(2), 16)),
                label,
            ).strip()
            if decoded and not (0x20 <= ord(decoded[0]) <= 0x7E):
                offenders.append(f"{decoded[:60]!r} opens with {decoded[0]!r}")
    assert not offenders, "command labels drawing their own icon:\n" + "\n".join(offenders)
