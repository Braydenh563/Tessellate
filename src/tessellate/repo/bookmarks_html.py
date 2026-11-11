"""Browser bookmarks files: read one, write one (DOCUMENTS_PLAN L6).

Every browser exports the same old Netscape format: nested `<DL>` lists, a folder
as `<DT><H3>Name</H3>` followed by its own `<DL>`, a link as `<DT><A HREF=...>Title</A>`.
The parser is the standard library's `html.parser` (lenient about the unclosed
`<p>` and `<DT>` tags the format never closes) and follows the nesting itself.

Only addresses `repo.bookmarks.normalise_url` would take come in: a `javascript:`
or `place:` row in an export is skipped, not stored. A folder becomes the link's
group; a folder inside a folder joins the names with `/` (the shelf's groups are one
flat list and `/` is its own convention for a hierarchy, `Work/Reading`), and a `/`
inside a folder's own name becomes `-` so it cannot be read as a level.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser

from tessellate.repo import Invalid
from tessellate.repo.bookmarks import normalise_url

#: A shelf file that is bigger than this is not a bookmarks file.
MAX_CHARS = 5_000_000
MAX_LINKS = 20_000
GROUP_SEP = "/"
TITLE_MAX = 200
GROUP_MAX = 120


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        #: The folder names from the outermost in; a `<DL>` pushes the folder named just before it.
        self.path: list[str] = []
        self.rows: list[dict] = []
        self.skipped = 0
        self._pending_folder: str | None = None
        self._in: str | None = None  # "h3" or "a"
        self._text: list[str] = []
        self._href = ""
        self._added = ""
        self._tags = ""
        self._opened: list[bool] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "dl":
            named = self._pending_folder is not None
            self._opened.append(named)
            if named:
                self.path.append(self._pending_folder or "")
            self._pending_folder = None
        elif tag in ("h3", "a"):
            self._in = tag
            self._text = []
            if tag == "a":
                values = {k.lower(): (v or "") for k, v in attrs}
                self._href = values.get("href", "")
                self._added = values.get("add_date", "")
                self._tags = values.get("tags", "")

    def handle_data(self, data: str) -> None:
        if self._in:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "dl":
            if self._opened and self._opened.pop() and self.path:
                self.path.pop()
        elif tag == "h3" and self._in == "h3":
            self._pending_folder = " ".join("".join(self._text).split()).replace(GROUP_SEP, "-")
            self._in = None
        elif tag == "a" and self._in == "a":
            self._in = None
            title = " ".join("".join(self._text).split())
            try:
                url = normalise_url(self._href)
            except Invalid:
                self.skipped += 1
                return
            if len(url) > 2000:
                self.skipped += 1
                return
            group = GROUP_SEP.join(p for p in self.path if p)[:GROUP_MAX].strip()
            self.rows.append({"url": url, "title": title[:TITLE_MAX], "group_name": group, "added": self._added, "tags": self._tags})


def parse(html: str) -> tuple[list[dict], int]:
    """The links in a bookmarks file, in file order, and how many rows were skipped (an address not allowed)."""
    if len(html) > MAX_CHARS:
        raise Invalid("That file is too large to be a bookmarks file.")
    reader = _Reader()
    reader.feed(html)
    reader.close()
    if len(reader.rows) > MAX_LINKS:
        raise Invalid(f"That file has more than {MAX_LINKS:,} links; split it first.")
    return reader.rows, reader.skipped


def render(rows: list[dict]) -> str:
    """A Netscape bookmarks file the browsers import: ungrouped links first, then one folder per group."""
    out = [
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        "<TITLE>Bookmarks</TITLE>",
        "<H1>Bookmarks</H1>",
        "<DL><p>",
    ]

    def link(row: dict) -> str:
        stamp = row.get("created_at")
        added = ""
        if isinstance(stamp, datetime):
            added = f' ADD_DATE="{int(stamp.replace(tzinfo=timezone.utc).timestamp())}"'
        tags = ",".join(row.get("tags") or [])
        marked = f' TAGS="{escape(tags, quote=True)}"' if tags else ""
        return f'<DT><A HREF="{escape(row["url"], quote=True)}"{added}{marked}>{escape(row.get("title") or row["url"])}</A>'

    #: A tree of the group paths: `Work/Reading` is a folder Reading inside a folder Work.
    tree: dict = {"links": [], "kids": {}}
    for row in rows:
        node = tree
        for part in [p.strip() for p in (row.get("group_name") or "").split(GROUP_SEP) if p.strip()]:
            node = node["kids"].setdefault(part, {"links": [], "kids": {}})
        node["links"].append(row)

    def walk(node: dict, depth: int) -> None:
        pad = "    " * depth
        out.extend(pad + link(row) for row in node["links"])
        for name in sorted(node["kids"], key=str.lower):
            out.append(f"{pad}<DT><H3>{escape(name)}</H3>")
            out.append(f"{pad}<DL><p>")
            walk(node["kids"][name], depth + 1)
            out.append(f"{pad}</DL><p>")

    walk(tree, 1)
    out.append("</DL><p>")
    return "\n".join(out) + "\n"
