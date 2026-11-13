"""The web clipper: one page the person chose, fetched once, kept as a note.

WORLD_CLASS_PLAN D9. The second thing in this app that goes online, after the
web reader, and held to the rules that one set (`search/websearch.py`):

* **Only on an explicit clip, only with the web opt-in on.** The route
  (`api/routes_webclip.py`) refuses before this module is called while
  `web_search_enabled` is off. Nothing here runs on a timer or a guess.
* **Never a probe of this machine or its network.** Every hop, redirects
  included, goes through `core.security.public_addresses` (S5), which refuses
  anything that is not plain http(s), carries credentials, fails to resolve,
  or resolves (any of its answers) to a private, loopback, link-local,
  reserved or metadata address. The connection is then pinned to the address
  that passed, so a second DNS answer cannot walk past the check (the web
  reader's `pin_url` and `PinnedAdapter`, now in `core/privacy_http.py`).
* **Bounded.** `CLIP_MAX_BYTES` and `CLIP_DEADLINE_SECONDS` cap the whole
  fetch, not each socket read: a server that drips a byte a second passes a
  per-read timeout forever and still runs into the deadline here. Past either
  cap the clip is refused, never kept half-read without saying so.
* **Nothing executable survives.** `extract` walks the page with the standard
  library's HTML parser, drops scripts, styles, frames, forms and the page's
  furniture, and writes markdown: text, headings, lists, quotes, code, and
  links with http(s) targets only, made absolute and cleaned of tracking
  parameters. No attribute is carried over, so no handler can be.

It lives in `core` rather than beside the web reader so the privacy receipt
(`core/egress.py`) names it as its own feature: a clip is not a search.
"""

from __future__ import annotations

import html
import logging
import re
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from tessellate.core import egress
from tessellate.core.privacy_http import PRIVACY_HEADERS, PinnedAdapter, pin_url, strip_tracking
from tessellate.core.security import UnsafeUrl, public_addresses

logger = logging.getLogger("tessellate.webclip")

#: The largest page a clip will read. Well past any article, and small enough
#: that a runaway response (a video served as text/html) is refused quickly.
CLIP_MAX_BYTES = 3_000_000
#: The whole fetch, redirects and body together.
CLIP_DEADLINE_SECONDS = 15.0
#: Per socket operation, inside the deadline above.
CLIP_SOCKET_TIMEOUT = 8
CLIP_MAX_REDIRECTS = 5
#: The longest note a clip makes. A page longer than this is kept to here,
#: and the note says so.
CLIP_MAX_CHARS = 60_000


class ClipRefused(Exception):
    """A clip that will not be made, with a sentence fit to show a person.

    `status` is the HTTP answer the route gives: 400 for an address the app
    will not fetch, 502 for a site that did not answer usefully."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _new_session() -> requests.Session:
    """A one-shot session with the web reader's quiet headers and no cookies.
    A seam for the tests, which replace it with a fake network."""

    session = requests.Session()
    session.headers.update(PRIVACY_HEADERS)
    session.cookies.clear()
    return session


def clean_url(url: str) -> str:
    return strip_tracking((url or "").strip())


def _clip_hop(session, url: str):  # noqa: ANN001
    """One request of the walk: the address checked, the connection pinned to it."""
    try:
        addresses = public_addresses(url)
    except UnsafeUrl as exc:
        # `UnsafeUrl` is a sentence written for a person (core/security.py).
        raise ClipRefused(str(exc)) from exc
    pinned, host_header = pin_url(url, addresses[0])
    parsed = urlparse(pinned)
    if parsed.scheme == "https":
        session.mount(f"https://{parsed.netloc}", PinnedAdapter(urlparse(url).hostname))
    # CodeQL reads this as SSRF, as it does the web reader's: fetching
    # the page the person asked to clip is the feature. The address
    # was checked on this hop and the connection is pinned to it.
    try:
        return session.get(
            pinned,
            headers={"Host": host_header},
            timeout=CLIP_SOCKET_TIMEOUT,
            stream=True,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise ClipRefused(f"Couldn't reach {urlparse(url).hostname}.", 502) from exc


def _redirect_url(response, url: str, deadline: float) -> str:  # noqa: ANN001
    """Where a redirect points, checked and made absolute."""
    location = response.headers.get("location", "")
    response.close()
    if not location:
        raise ClipRefused("That page redirected to nowhere.", 502)
    url = clean_url(urljoin(url, location))
    if time.monotonic() > deadline:
        raise ClipRefused("That page took too long to answer.", 502)
    return url


def check_status(response, url: str) -> None:  # noqa: ANN001
    """Refuse an error status (shared with `core/webimage.py`)."""
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise ClipRefused(
            f"{urlparse(url).hostname} answered {response.status_code}, so there was nothing to clip.",
            502,
        ) from exc


def _check_clippable(response, url: str) -> None:  # noqa: ANN001
    """Refuse an error status, a non-page or a page declared too large."""
    check_status(response, url)
    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type and "text/plain" not in content_type:
        response.close()
        raise ClipRefused("That link isn't a web page, so it can't be clipped as text.")
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > CLIP_MAX_BYTES:
        response.close()
        raise ClipRefused("That page is too large to clip.")


def _read_clip_body(response, deadline: float) -> bytes:  # noqa: ANN001
    body = bytearray()
    for chunk in response.iter_content(65536):
        body.extend(chunk)
        if len(body) > CLIP_MAX_BYTES:
            response.close()
            raise ClipRefused("That page is too large to clip.")
        if time.monotonic() > deadline:
            response.close()
            raise ClipRefused("That page took too long to arrive.", 502)
    return bytes(body)


@egress.labelled(lambda url, *a, **k: f"Clipping a page: {egress.short(url, 80)}")
def fetch_page(url: str) -> dict:
    """GET one public page, checking every hop. Returns
    `{"url": final_url, "html": text}` or raises `ClipRefused`."""
    url = clean_url(url)
    deadline = time.monotonic() + CLIP_DEADLINE_SECONDS
    session = _new_session()
    try:
        for _ in range(CLIP_MAX_REDIRECTS + 1):
            response = _clip_hop(session, url)
            if response.is_redirect or getattr(response, "is_permanent_redirect", False):
                url = _redirect_url(response, url, deadline)
                continue
            _check_clippable(response, url)
            body = _read_clip_body(response, deadline)
            encoding = response.encoding or "utf-8"
            return {"url": url, "html": body.decode(encoding, errors="replace")}
        raise ClipRefused("That page redirected too many times.", 502)
    finally:
        session.close()


# --- extraction ---------------------------------------------------------------------

#: Dropped with everything inside them: never text a reader wanted.
_DROP = {
    "script", "style", "noscript", "template", "iframe", "frame", "object", "embed",
    "svg", "canvas", "form", "button", "select", "textarea", "input", "head",
    "nav", "header", "footer", "aside", "dialog", "menu",
}
_VOID = {"br", "hr", "img", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed", "param", "track"}
_BLOCKS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre", "td", "th", "dt", "dd", "figcaption"}
#: class/id words that mark a container as furniture rather than content.
#: **Containers a class name never drops.** Reported with a screenshot: a
#: Squarespace blog read as one word. Its `<body>` carries dozens of theme
#: classes ("tweak-...-header-...", "header--menu-open"), `_JUNK` read
#: "header" in them, and the whole page went with the body. The page's own
#: frame and its declared content are never chrome, whatever they are named.
_NEVER_JUNK = {"html", "body", "main", "article"}

#: Below this many words the class filter is assumed to have eaten the page,
#: and it is read again without it (`extract`).
_THIN_WORDS = 40

_JUNK = re.compile(
    r"(^|[\s_-])(nav|navigation|menu|sidebar|footer|header|comment|comments|cookie|banner|ad|ads|advert|"
    r"promo|related|share|social|subscribe|newsletter|breadcrumb|toc|popup|modal)([\s_-]|$)",
    re.I,
)


#: The `<meta>` names that fill a clipped note's properties, and which one.
_META_FACTS = {
    "og:site_name": "site",
    "author": "author",
    "article:author": "author",
    "article:published_time": "published",
    "og:article:published_time": "published",
    "datepublished": "published",
    "date": "published",
    "pubdate": "published",
}
_ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


class _Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: dict, parent: "_Node | None"):
        self.tag = tag
        self.attrs = attrs
        self.children: list = []
        self.parent = parent


class _Tree(HTMLParser):
    """A forgiving tree of the page: every element that is not dropped, with
    its text. The standard library parser, not a regex, so a `<p>` inside an
    attribute value or a `</script>` in a string cannot fool it."""

    def __init__(self, junk: bool = True) -> None:
        super().__init__(convert_charrefs=True)
        #: Whether class and id names can drop an element (see `extract`).
        self.junk = junk
        self.root = _Node("root", {}, None)
        self.cur = self.root
        self.skip = 0
        self.title = ""
        self._in_title = False
        self.og_title = ""
        #: What the page says about itself, for the note's properties.
        self.facts: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            if attrs.get("property", "").lower() == "og:title":
                self.og_title = attrs.get("content", "").strip()
            self._meta_fact(attrs)
        if self.skip:
            if tag not in _VOID:
                self.skip += 1
            return
        if tag in _DROP or (
            self.junk
            and tag not in _NEVER_JUNK
            and _JUNK.search(f"{attrs.get('class', '')} {attrs.get('id', '')} {attrs.get('role', '')}")
        ):
            if tag not in _VOID:
                self.skip = 1
            return
        node = _Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in _VOID:
            self.cur = node

    def _meta_fact(self, attrs: dict) -> None:
        """Keep the first site, author and publish date a `<meta>` names."""
        key = (attrs.get("property") or attrs.get("name") or attrs.get("itemprop") or "").lower()
        field = _META_FACTS.get(key)
        value = " ".join(attrs.get("content", "").split())
        if not field or not value or field in self.facts:
            return
        if field == "published":
            found = _ISO_DAY.match(value)
            value = found.group(0) if found else ""
        elif field == "author" and value.lower().startswith(("http://", "https://")):
            value = ""  # article:author is often a profile address, not a name
        if value:
            self.facts[field] = value[:120]

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if self.skip:
            if tag not in _VOID:
                self.skip -= 1
            return
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.cur = node.parent

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self.skip:
            return
        self.cur.children.append(data)


def _text(node) -> str:
    if isinstance(node, str):
        return node
    return "".join(_text(child) for child in node.children)


def _link_text(node) -> int:
    if isinstance(node, str):
        return 0
    if node.tag == "a":
        return len(_text(node))
    return sum(_link_text(child) for child in node.children)


def _score(node: _Node) -> float:
    """How much reading a container holds: the text of its own paragraph-like
    children, less what of it is links (a menu is all links). Readability's
    idea, in its smallest form."""
    total = 0.0
    for child in node.children:
        if isinstance(child, _Node) and child.tag in ("p", "pre", "blockquote", "li"):
            words = len(_text(child).split())
            if words >= 4:
                total += words
    text_len = len(_text(node)) or 1
    return total * (1 - min(0.9, _link_text(node) / text_len))


def _main(tree: _Tree) -> _Node:
    """`<article>`, else `<main>`, else the container with the most prose."""
    found: dict[str, _Node] = {}
    best, best_score = tree.root, 0.0

    def walk(node: _Node) -> None:
        nonlocal best, best_score
        for child in node.children:
            if not isinstance(child, _Node):
                continue
            if child.tag in ("article", "main") and child.tag not in found:
                found[child.tag] = child
            score = _score(child)
            if score > best_score:
                best, best_score = child, score
            walk(child)

    walk(tree.root)
    if "article" in found and _score_deep(found["article"]) > 0:
        return found["article"]
    if "main" in found and _score_deep(found["main"]) > 0:
        return found["main"]
    return best


def _score_deep(node: _Node) -> float:
    return _score(node) + sum(_score_deep(c) for c in node.children if isinstance(c, _Node))


def _safe_href(href: str, base: str) -> str:
    absolute = urljoin(base, html.unescape(href or "").strip())
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        return ""
    return clean_url(absolute)


#: Walked into as blocks, never read as one inline run. `html` and `body`
#: are here because a page with no paragraph tags anywhere scores nothing,
#: `_main` then falls back to the document root, and inlining that ran every
#: div's text together ("wordmore") into one block.
_CONTAINERS = {"ul", "ol", "table", "tr", "div", "section", "article", "main", "figure", "dl", "tbody", "thead", "html", "body"}


#: The inline tags that wrap their text in a markdown mark.
_INLINE_MARKS = {"strong": "**", "b": "**", "em": "*", "i": "*", "code": "`"}


class _Markdown:
    def __init__(self, base: str):
        self.base = base
        self.blocks: list[str] = []

    def inline(self, node) -> str:
        if isinstance(node, str):
            return re.sub(r"\s+", " ", node)
        inner = "".join(self.inline(child) for child in node.children)
        tag = node.tag
        mark = _INLINE_MARKS.get(tag)
        if mark and inner.strip():
            return f"{mark}{inner.strip()}{mark}"
        if tag == "br":
            return "\n"
        if tag == "a":
            return self._link(node, inner.strip())
        if tag == "img":
            return ""
        return inner

    def _link(self, node, label: str) -> str:
        href = _safe_href(node.attrs.get("href", ""), self.base)
        # A link to a place on the same page means nothing in a note.
        same_page = "#" in href and href.split("#", 1)[0] == self.base.split("#", 1)[0]
        if href and label and not same_page:
            return f"[{label}]({href})"
        return label

    def flush_inline(self, parts: list[str]) -> None:
        text = re.sub(r"[ \t]+", " ", "".join(parts)).strip()
        if text:
            self.blocks.append(text)
        parts.clear()

    def _heading(self, child: _Node) -> str:
        text = self.inline(child).strip()
        return f"{'#' * int(child.tag[1])} {text}" if text else ""

    def _quote(self, child: _Node) -> str:
        text = " ".join(self.inline(child).split())
        return f"> {text}" if text else ""

    def _pre(self, child: _Node) -> str:
        code = _text(child).strip("\n")
        return f"```\n{code}\n```" if code.strip() else ""

    def _list(self, child: _Node, depth: int) -> str:
        items = [c for c in child.children if isinstance(c, _Node) and c.tag == "li"]
        lines = []
        for n, item in enumerate(items, 1):
            text = " ".join(self.inline(item).split())
            if text:
                marker = f"{n}." if child.tag == "ol" else "-"
                lines.append(f"{'  ' * depth}{marker} {text}")
        return "\n".join(lines)

    def _table(self, child: _Node) -> str:
        rows = []
        for tr in _descendants(child, "tr"):
            cells = [" ".join(self.inline(c).split()) for c in tr.children if isinstance(c, _Node) and c.tag in ("td", "th")]
            if any(cells):
                rows.append("| " + " | ".join(cells) + " |")
        if not rows:
            return ""
        rows.insert(1, "|" + " --- |" * (rows[0].count("|") - 1))
        return "\n".join(rows)

    def _own_block(self, child: _Node, depth: int) -> str | None:
        """The markdown block a heading, quote, code, list or table makes ("" when it
        is empty); None for any other tag."""
        tag = child.tag
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return self._heading(child)
        if tag == "blockquote":
            return self._quote(child)
        if tag == "pre":
            return self._pre(child)
        if tag in ("ul", "ol"):
            return self._list(child, depth)
        if tag == "table":
            return self._table(child)
        return None

    def block(self, node: _Node, depth: int = 0) -> None:
        loose: list[str] = []
        for child in node.children:
            if isinstance(child, str) or child.tag not in _BLOCKS | _CONTAINERS:
                loose.append(self.inline(child))
                continue
            self.flush_inline(loose)
            made = self._own_block(child, depth)
            if made is not None:
                if made:
                    self.blocks.append(made)
            elif child.tag in ("p", "dt", "dd", "figcaption", "li", "td", "th"):
                self.flush_inline([self.inline(child)])
            else:
                self.block(child, depth)
        self.flush_inline(loose)


def _descendants(node: _Node, tag: str):
    for child in node.children:
        if isinstance(child, _Node):
            if child.tag == tag:
                yield child
            else:
                yield from _descendants(child, tag)


def _read(page: str, url: str, junk: bool) -> tuple[_Tree, str]:
    """The parsed page and its main content as markdown."""
    tree = _Tree(junk=junk)
    try:
        tree.feed(page)
        tree.close()
    except Exception:  # noqa: BLE001  # a malformed page is still a page
        pass
    md = _Markdown(url)
    md.block(_main(tree))
    return tree, "\n\n".join(md.blocks).strip()


def extract(page: str, url: str) -> dict:
    """`{"title", "markdown", "words", "facts"}` for a page's main content;
    `facts` holds the `site`, `author` and `published` day the page names."""
    tree, markdown = _read(page, url, junk=True)
    #: A theme can hang a "junk" word on the one wrapper everything sits in
    #: (a `div.site-header-wrapper` around the whole page is common), and the
    #: exemptions above only cover the standard tags. A reading that thin is
    #: taken again without the class filter; the tag filter (nav, header,
    #: footer, aside) still keeps the real chrome out.
    if len(markdown.split()) < _THIN_WORDS:
        loose_tree, loose = _read(page, url, junk=False)
        if len(loose.split()) > len(markdown.split()):
            tree, markdown = loose_tree, loose
    main = _main(tree)
    title = " ".join((tree.og_title or tree.title or "").split())
    if not title:
        first = next(_descendants(main, "h1"), None)
        title = " ".join(_text(first).split()) if first else ""
    if not title:
        title = urlparse(url).hostname or "Clipped page"
    # A page's own h1 repeating the title is the title twice in the note.
    blocks = markdown.split("\n\n")
    names = {title.lower(), tree.og_title.lower()} - {""}
    if blocks and blocks[0].startswith("# ") and blocks[0][2:].strip().lower() in names:
        markdown = "\n\n".join(blocks[1:])
    return {"title": title[:300], "markdown": markdown, "words": len(markdown.split()), "facts": dict(tree.facts)}


def page_facts(page: str) -> dict[str, str]:
    """Only the `site`, `author` and `published` a page names, for a clip
    whose text was selected by hand (the selection is the body, the page
    still says who wrote it)."""
    tree = _Tree()
    try:
        tree.feed(page)
        tree.close()
    except Exception:  # noqa: BLE001  # a malformed page is still a page
        logger.debug("page facts: the page did not parse to the end; keeping what it named so far", exc_info=True)
    return dict(tree.facts)


def note_properties(extracted: dict, url: str, clipped: str) -> dict[str, str]:
    """The `---` block a clipped note opens with: where it came from, who
    wrote it and when, and the day it was clipped (passed in, so a test holds
    the clock still). Empty values are left out."""
    facts = extracted.get("facts") or {}
    props = {
        "source": url,
        "site": facts.get("site") or "",
        "author": facts.get("author") or "",
        "published": facts.get("published") or "",
        "clipped": clipped,
    }
    return {k: v for k, v in props.items() if v}


def note_content(extracted: dict, url: str) -> str:
    """The note a clip becomes: the title as its heading, where it came from,
    and the page's text."""
    body = extracted["markdown"]
    cut = len(body) > CLIP_MAX_CHARS
    if cut:
        body = body[:CLIP_MAX_CHARS].rsplit("\n\n", 1)[0]
    parts = [f"# {extracted['title']}", f"Source: <{url}>", body or "*The page had no text to keep.*"]
    if cut:
        parts.append("*The page was longer than a note keeps; the rest is at the source.*")
    return "\n\n".join(parts)
