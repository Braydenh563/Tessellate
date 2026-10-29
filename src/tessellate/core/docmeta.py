"""A document's frontmatter, read for the list.

DOCUMENTS_PLAN Phase 3 item 4's second clause: "searchable from the Library's
filter". The Library reads its documents list to the end already, so the
filtering itself is client-side and costs no round trip; what it could not do
by itself is *see* the properties, because `_summary()` in
`api/routes_documents.py` deliberately sends a preview rather than a
document's content (a document runs to thousands of words). This module is the
one thing the list needed: a small, read-only parse of the frontmatter block,
whose result rides along on the row.

**Read-only, and that is the whole safety story.** The editable model, the one
that turns a keystroke in the properties panel into a list of `{from, to,
insert}` edits covering nothing but the value's own span, is in
`frontend/js/documents.js` between `DOC-FRONTMATTER-BEGIN` and
`DOC-FRONTMATTER-END`, and `tests/test_doc_frontmatter.py` runs it in node. It
is not duplicated here, and it must not be: two implementations of a *writer*
are two ways to reformat somebody's file. This one only ever reads, so the
worst it can be is incomplete, and an incomplete read shows a filter one key
short rather than a document one paragraph short.

The subset understood is the same one that model understands, and the same one
the editors in the plan's competitor table actually write: `---` on line 1,
`key: value` until the closing `---`, values that are scalars (quoted or not),
inline lists (`[a, b]`) or block lists (`- a` on the lines under the key).
Anything else is skipped rather than guessed at.
"""

from __future__ import annotations

import re

#: A fence line: exactly three dashes and nothing but whitespace after them
#: (a CR too: a note saved with CRLF line ends splits on "\n" and keeps it).
#: Not `---` anywhere in the document, which is a horizontal rule; the only
#: thing that makes these three characters a fence is being the first line.
_FENCE = re.compile(r"^---[ \t\r]*$")

#: The key half of a `key: value` line. What YAML allows unquoted and what the
#: competitor editors write: letters, digits, underscores, dashes, dots, and
#: spaces inside but never at the ends. Kept character for character in step
#: with `DOC_FM_KEY` in documents.js, because a key this reads and that one
#: does not would be a filter offering a property the panel cannot edit.
#: **Split on the first colon, then check the key.** This was one regex,
#: `^([A-Za-z0-9_][A-Za-z0-9_.\- ]*?)[ \t]*:(.*)$`, and CodeQL was right about
#: it (#418, py/polynomial-redos): a lazy run of a class that includes spaces,
#: followed by another run of spaces, is quadratic on a line of spaces with no
#: colon, which is a line any document can contain. `str.partition` finds the
#: colon in one pass and this only has to say whether what precedes it is a
#: key, over a class with no repetition ambiguity in it at all.
_KEY_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\- ]*$")


def _split_key(line: str) -> tuple[str, str] | None:
    """`("key", "the rest")`, or None when the line is not `key: value`."""
    head, sep, rest = line.partition(":")
    if not sep:
        return None
    head = head.rstrip(" \t")
    if not head or not _KEY_NAME.match(head):
        return None
    return head, rest

#: A block list item under a key: `  - value`.
_ITEM = re.compile(r"^[ \t]*-[ \t]?(.*)$")

#: Bounds, because this runs per row of a list that can be the whole notebook.
#: A document with three hundred tags is not a document anybody filters by; it
#: is a document that would put three hundred options in one select and make
#: the control useless for every other document in the list. The caps are
#: generous enough that no real frontmatter meets them and small enough that a
#: pathological one cannot flood the filter.
MAX_KEYS = 40
MAX_VALUES_PER_KEY = 40

#: How far into a document the closing fence is looked for. Frontmatter is a
#: header; a "fence" four hundred lines down is a document that opens with a
#: horizontal rule, and reading the four hundred lines between them as
#: properties is the one failure mode this cannot be allowed to have.
MAX_FENCE_LINES = 200


def _unquote(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def properties(text: str) -> dict[str, list[str]]:
    """`{key: [values]}` for the frontmatter block, or `{}` when there is none.

    A key with nothing after the colon comes back with an empty list rather
    than being dropped: the filter offers the key first, so a document with a
    `status:` nobody has filled in still *has* a status property. It simply
    matches no value.
    """
    source = str(text or "")
    lines = source.split("\n")
    if not lines or not _FENCE.match(lines[0]):
        return {}
    close = -1
    for index in range(1, min(len(lines), MAX_FENCE_LINES + 1)):
        if _FENCE.match(lines[index]):
            close = index
            break
    if close == -1:
        return {}

    found: dict[str, list[str]] = {}
    index = 1
    while index < close:
        split = _split_key(lines[index])
        if not split:
            index += 1
            continue
        key, rest = split
        rest = rest.strip()
        values: list[str] = []
        if rest.startswith("[") and rest.endswith("]"):
            values = [_unquote(part) for part in rest[1:-1].split(",")]
        elif rest:
            values = [_unquote(rest)]
        else:
            #: A key with no value on its own line and `- item` under it is a
            #: block list; a key with no value and nothing under it is a key
            #: with no value. The two are told apart by looking, which is the
            #: only way to tell them apart.
            look = index + 1
            while look < close:
                item = _ITEM.match(lines[look])
                if not item:
                    break
                values.append(_unquote(item.group(1)))
                look += 1
            index = look - 1
        values = [value for value in values if value]
        if len(found) >= MAX_KEYS and key not in found:
            break
        found[key] = values[:MAX_VALUES_PER_KEY]
        index += 1
    return found


def block_end(text: str) -> int:
    """Where the body starts: the offset just past the closing fence's line,
    or 0 when the text opens with no closed block."""
    source = str(text or "")
    if not source.startswith("---"):
        return 0
    lines = source.split("\n")
    if not _FENCE.match(lines[0]):
        return 0
    offset = len(lines[0]) + 1
    for index in range(1, min(len(lines), MAX_FENCE_LINES + 1)):
        line = lines[index]
        if _FENCE.match(line):
            return min(len(source), offset + len(line) + 1)
        offset += len(line) + 1
    return 0
