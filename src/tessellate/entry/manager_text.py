"""The words of a note: private-note reading, titles, plain labels, Markdown stripping and the [[link]] text helpers.

Moved whole out of `entry/manager.py` (audit K24, BK11), unchanged. A layer below `entry/manager.py`, which imports it; it imports nothing from there. Callers import these names from here.
"""

from __future__ import annotations

import re
from sqlalchemy import update
from sqlalchemy.orm import Session
from tessellate.core.database import Entry, MediaUpload
from tessellate.core.lookahead import Ahead

#: A `/media/<filename>` in text. Here, not in `core/media_gc.py` (which
#: reads it from here): that module imports this one, and the old lazy import
#: back made an import cycle.
MEDIA_NAME_RE = re.compile(r"/media/([A-Za-z0-9][A-Za-z0-9._-]{0,119})")


# --- private notes -----------------------------------------------------------
# Encryption lives behind these two helpers so every read and write goes
# through the same place. Scattering encrypt/decrypt calls across the routes is
# how a path gets missed and a note is stored in the clear.


def readable_content(entry: Entry) -> str:
    """The note's text, decrypting it if it's private and the vault is open.

    A locked vault returns a placeholder rather than raising: a private note
    must not break the notes list, the graph, or an export for everything else.
    """
    from tessellate.core import crypto, vault

    if not crypto.is_encrypted(entry.content):
        return entry.content
    key = vault.key()
    if key is None:
        return "Private note: unlock to read it."
    try:
        return crypto.decrypt(key, entry.content)
    except crypto.DecryptionError:
        # Kept deliberately non-fatal. The stored bytes are still there, so a
        # key problem is recoverable; crashing the list is not.
        return "This private note couldn't be decrypted."


def _heading_text(stripped: str) -> str | None:
    r"""The text of a leading Markdown heading (1-6 `#`, then a required
    space/tab, then the title), a `#` three paragraphs into a long note is
    a section break, not what the note is *called*, so this only ever looks
    at one already-stripped line. Requires the space after the hashes, so
    "#recipe" (a tag someone typed at the very top) is never mistaken for a
    heading.

    Hand-rolled instead of a `^#{1,6}[ \t]+(\S.*)$` regex: CodeQL flagged
    that shape as a polynomial-ReDoS risk on note content, which is as
    uncontrolled as input gets in this app. This scan is a single linear
    pass with no backtracking.
    """
    n = 0
    while n < len(stripped) and n < 6 and stripped[n] == "#":
        n += 1
    if n == 0 or n >= len(stripped) or stripped[n] not in " \t":
        return None
    text = stripped[n:].lstrip(" \t")
    if not text or text[0].isspace():
        return None
    return text


def _md_links(text: str, image: bool) -> str:
    """`![alt](src)` removed, or `[text](src)` reduced to its text.

    What `!\\[[^\\]]*\\]\\([^)]*\\)` and `\\[([^\\]]*)\\]\\([^)]*\\)` did, with
    the same answers, but linear: those scanned to the end of the line from
    every unclosed `[`, so a first line of `[[[[...` (a note's own text, a
    paste) took 0.3 to 0.8 s at 20 KB (final scan, 2026-10-06). The next `]`
    and the next `)` are looked up through `Ahead`, which remembers its last
    hit, so each is found once per stretch rather than once per `[`.
    """
    opener = "![" if image else "["
    size = len(text)
    close, paren = Ahead(text, r"\]"), Ahead(text, r"\)")
    out: list[str] = []
    done = scan = 0
    while True:
        start = text.find(opener, scan)
        if start < 0:
            break
        mid = close.first(start + len(opener))
        if text.startswith("](", mid):
            end = paren.first(mid + 2)
            if end < size:
                out.append(text[done:start])
                if not image:
                    out.append(text[start + 1 : mid])
                done = scan = end + 1
                continue
        scan = start + 1
    out.append(text[done:])
    return "".join(out)


def plain_label(content: str, limit: int = 80) -> str:
    """A note's first line as a *person* would read it, for a chip or a card.

    Reported directly: "the used in note links dont render inline md", a
    usage chip in the Library's file gallery read
    `# Leafeon Pokemon image test ![WallpaperEngineOv…`, because the label was
    the raw first line of markdown. A chip is one line of plain text in a
    pill; it cannot render markdown and should not try, so the markup is
    removed rather than displayed.

    Deliberately small and regex-only: this is a label, not a document render.
    Images lose their alt text entirely (an image is not what the note *says*),
    links keep their text, and the usual inline emphasis/code markers go.
    """
    from tessellate.entry.properties import strip as strip_properties

    #: KG4: a note opening with properties is named by what follows them.
    text = strip_properties(content or "").strip()
    if not text:
        return ""
    first = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        first = stripped
        break
    first = re.sub(r"^#{1,6}\s*", "", first)          # heading markers
    first = re.sub(r"^[-*+]\s+|^>\s*", "", first)     # list bullet / quote
    first = _md_links(first, image=True)               # images, alt and all
    #: **Before the markdown link rule, because that one cannot see this.**
    #: `[text](url)` needs the `(url)` to match, so `[[a wiki link]]` fell
    #: straight through it and every chip for a note whose first line links
    #: to another note read `[[The roof quote]]`, brackets and all. Found
    #: while building the references row (INBOX 246), where four of the five
    #: source labels were wiki links and every one of them showed its
    #: brackets. Same rule as the markdown link below: the link keeps its
    #: text, because the text is what the note says.
    first = wiki_plain(first)
    first = _md_links(first, image=False)              # links keep their text
    first = re.sub(r"[*_`~]{1,3}", "", first)          # emphasis, code, strike
    first = re.sub(r"\s+", " ", first).strip()
    return first[:limit]


def extract_title(content: str) -> str | None:
    """A note's own title, if it wrote one, its first line, when that line
    is a Markdown heading. Not a stored field: there is nothing to fall out
    of sync with the content, and "editing the title" is just editing that
    line, the same as any other (asked for directly, and simpler than a
    second input box fighting the single-box capture flow this app is built
    around).
    """
    from tessellate.entry.properties import strip as strip_properties

    for line in strip_bidi(strip_properties(content or "")).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        text = _heading_text(stripped)
        return text.strip() if text else None
    return None


def _first_content_line(content: str) -> int | None:
    """Index of the first non-blank line, or None if there isn't one."""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip():
            return i
    return None


def _split_block(content: str) -> tuple[str, str]:
    """`(properties block, body)`: a title lives in the body, never in the
    block (KG4), so editing one must leave the block where it is."""
    from tessellate.entry.properties import block_end

    end = block_end(content or "")
    return (content or "")[:end], (content or "")[end:]


def apply_title(content: str, title: str) -> str:
    """Set (or replace) a note's title: its first line, as a heading.
    Prepends a new heading line if the note doesn't have one yet; replaces
    the existing one otherwise, so generating a title for a note that
    already has one swaps it rather than stacking two. A note that opens
    with properties gets its heading after them."""
    block, body = _split_block(content or "")
    lines = body.splitlines()
    i = _first_content_line(body)
    heading = f"# {title}"
    if i is not None and _heading_text(lines[i].strip()) is not None:
        lines[i] = heading
        return block + "\n".join(lines)
    return block + (heading if not body else f"{heading}\n{body}")


def remove_title(content: str) -> str:
    """Take a note's title back out, asked for directly, it's just the
    leading heading line, so removing it is removing that line (and one
    blank line right after it, so the body doesn't start with a gap). A
    note with no title is returned unchanged; properties stay as written.
    """
    block, body = _split_block(content or "")
    lines = body.splitlines()
    i = _first_content_line(body)
    if i is None or _heading_text(lines[i].strip()) is None:
        return content
    del lines[i]
    if i < len(lines) and not lines[i].strip():
        del lines[i]
    return block + "\n".join(lines)


#: Inline markdown markers, matched with their content so stripping keeps
#: the words. An image or link becomes its alt/link text, the URL is never
#: captured, only whichever group actually matched ("first non-None group
#: wins", same trick every alternative here relies on). Originally lived
#: only in routes_graph.py (graph node labels); routes_library.py's Library
#: title/preview needed the identical fix, an image-only note (a sketch,
#: most often, but any note whose whole content is a pasted image works the
#: same way) read as literal `![sketch](/media/...)` there too, one surface
#: at a time, until this was factored out to stop that from happening a
#: third time somewhere else.
_INLINE_MD = re.compile(
    r"\*\*([^*\n]{1,500})\*\*|\*([^*\n]{1,500})\*|__([^_\n]{1,500})__"
    r"|_([^_\n]{1,500})_|~~([^~\n]{1,500})~~|`([^`\n]{1,500})`"
    r"|!\[([^\]\n]{0,200})\]\((?:[^)\n]{1,500})\)"
    r"|\[([^\]\n]{1,200})\]\((?:[^)\n]{1,500})\)"
    # A board text run, `{{size=24 ink=red|words}}` (notes-list.js `MD_RUN`).
    r"|\{\{(?:(?:size|font|ink|hl)=[a-z0-9]{1,12} ?){1,4}\|([^}\n]{1,500})\}\}"
)


#: A line that starts a block of its own: a heading, a list item, a quote, a
#: table row.
_BLOCK_LINE = re.compile(r"^(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|>|\|)")
#: A block that already ends its sentence needs no separator after it.
_BLOCK_ENDED = re.compile(r"[.!?:;,…·)\]\"'”’]$")


def join_blocks(text: str, strip=lambda line: line, limit: int | None = None) -> str:
    """A note's or document's lines as one line of prose, its blocks kept apart.

    INBOX 464: a preview that joins every line with a space reads a heading
    and the list under it as one run-on sentence, "Goals Ship the notebook
    redesign Cut travel spend by 15% Risks The hiring freeze...". A boundary
    between blocks (a heading, a list item, a quote, or a blank line) whose
    first half ends without a stop gets the app's dot separator, the one the
    facts lines use; a block that ends its own sentence is followed by a
    space. Lines inside one paragraph (hard-wrapped prose) are joined with a
    space, so an imported file wrapped at 80 columns does not grow dots in
    the middle of its sentences. `strip` cleans one line (its markers) after
    its kind is read; `limit` stops reading once that many characters are
    in, so a long document is not walked to its end for a 240-char preview.
    """
    out: list[str] = []
    size = 0
    gap = prev_block = False
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            gap = True
            continue
        block = bool(_BLOCK_LINE.match(line))
        line = strip(line).strip()
        if not line:
            continue
        if out:
            boundary = gap or block or prev_block
            out.append(" · " if boundary and not _BLOCK_ENDED.search(out[-1]) else " ")
        out.append(line)
        size += len(line)
        gap, prev_block = False, block
        if limit is not None and size > limit:
            break
    return "".join(out)


#: A picture's `|` options in its alt (`![A river|300|right](url)`): a width in
#: pixels (or `300x200`) and left, centre or right. Not words.
_IMAGE_OPTION = re.compile(r"\d{1,4}(?:x\d{1,4})?|left|centre|center|right", re.IGNORECASE)
_IMAGE_ALT_GROUP = 7  # the `!\[(...)\]` group of _INLINE_MD


def _picture_words(alt: str) -> str:
    """A picture's alt as the words it says: the caption written after its
    options when there is one, else its name (image-layout.js
    `imageOptionsFromAlt`, so the preview and the picture agree)."""
    name, *rest = alt.split("|")
    caption = [p.strip() for p in rest if p.strip() and not _IMAGE_OPTION.fullmatch(p.strip())]
    return " ".join(caption) or name.strip()


#: `![[Title]]`: a diagram written into a document (documents-mermaid.js). Not a block embed (`#^id`) and not a file (`.png`).
_EMBED = re.compile(r"!\[\[[ \t]*([^\]\n|#]{1,300}?)[ \t]*\]\]")


def readable_embeds(text: str) -> str:
    """A diagram embed as words for a preview: `Diagram: Trip map`, or the title alone when it starts with Diagram
    (dgbt-1109 12: the Library printed "!Diagram 2026-11-09 19:11"). An image embed is left alone."""

    def label(m: re.Match) -> str:
        title = m.group(1)
        if re.search(r"\.\w{2,5}$", title):
            return m.group(0)
        return title if title.lower().startswith("diagram") else f"Diagram: {title}"

    return _EMBED.sub(label, text)


def strip_inline_markdown(text: str) -> str:
    """A note's text as plain words: bold/italic/strike/code markers gone,
    an image or link reduced to its alt/link text (a picture's width and
    alignment dropped). Markers only: block structure (headings,
    blockquotes, wiki-links) is each caller's own concern, since callers
    disagree on what to do with those."""
    return _INLINE_MD.sub(
        lambda m: _picture_words(m.group(m.lastindex))
        if m.lastindex == _IMAGE_ALT_GROUP
        else next(g for g in m.groups() if g is not None),
        text,
    )


def content_for_entry(entry: Entry, text: str) -> str | None:
    """`text` (from a past version) in the form this note stores its text in
    now: ciphertext when it is private, plain when it is not. None when that
    needs the vault and it is locked. A version written while the note was in
    the other state would otherwise put ciphertext in a note anyone reads, or
    plain text in a private one."""
    from tessellate.core import crypto, vault

    if bool(entry.is_private) == crypto.is_encrypted(text):
        return text
    key = vault.key()
    if key is None:
        return None
    return crypto.encrypt(key, text) if entry.is_private else crypto.decrypt(key, text)


def flag_private_media(session: Session, text: str) -> None:
    """Mark the uploads a private note's readable text embeds (SEC-A2), so a
    locked session can tell them from plain orphans (`MediaUpload.in_private_note`)."""
    names = set(MEDIA_NAME_RE.findall(text or ""))
    if names:
        session.execute(
            update(MediaUpload).where(MediaUpload.filename.in_(names)).values(in_private_note=True)
        )


WIKI_LINK = re.compile(r"\[\[([^\[\]]{1,120})\]\]")


def wiki_target(inner: str) -> str:
    """The note a `[[Target|Shown]]` names: the part before the first `|`.

    The part after the bar is only what is drawn. One definition, because
    several readers (`sync_wiki_links`, a document's backlinks, a note's
    references row) each used to decide for themselves and gave different
    answers for the same text.
    """
    return (inner or "").split("|", 1)[0].strip()


def wiki_shown(inner: str) -> str:
    """The words a `[[Target|Shown]]` draws: the part after the bar, else the target."""
    target, bar, shown = (inner or "").partition("|")
    return (shown.strip() if bar else "") or target.strip()


#: Bidi embedding, override and isolate controls: they reorder what follows on
#: screen, so a label could read differently from the note (audit 1029 N20).
_BIDI_CONTROLS = re.compile("[\u202a-\u202e\u2066-\u2069]")


def strip_bidi(text: str) -> str:
    """`text` without bidi controls, for anything shown as a label."""
    return _BIDI_CONTROLS.sub("", text or "")


def wiki_plain(text: str) -> str:
    """Some text with each `[[link]]` replaced by the words it draws, bidi
    controls dropped (it builds previews)."""
    return WIKI_LINK.sub(lambda match: wiki_shown(match.group(1)), strip_bidi(text))
