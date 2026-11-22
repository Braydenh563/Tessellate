"""Comments out of the frontend's CSS, JS and `index.html`, at serve time only.

**Why** (audit 2026-10-05, FE-01): the files in `frontend/` are written to be
read. 64% of the CSS, about 46% of the JS and 39% of `index.html` is comment
text, and every byte of it went to the browser on every cold load, where it
was downloaded, decompressed and (for the JS) scanned by the parser for
nothing. The files on disk keep every comment: the tests read them, and so do
the people editing them. Only what `RevalidatedStatic` hands out is stripped,
and the result is cached per file version (`api/app.py`), so this runs once
per edit, not once per request.

**Why a lexer, not a regex.** A JS line that starts with `//` can sit inside a
multi-line template literal (`` `...\n// not a comment\n...` ``), a `/*` can
sit inside a string or a regex literal (`/[/*]/`), and a `<!--` can sit in an
attribute value or a `<pre>`. A regex over the text cannot tell those apart;
a scanner that knows where strings, templates, regex literals and comments
begin and end can. Each scanner below jumps between the few characters that
can change its state (`re.search` for the next one), so it costs a few
hundred milliseconds over the whole frontend rather than seconds.

**What is kept.** A `/*! ... */` comment, and any comment naming `@license`
or `@preserve`, the conventional "keep me" markers. A `//# sourceMappingURL`
line. **Every line number**: a comment's lines are left empty rather than
removed, so an error's `file:line` in the console or a support bundle is the
same line in the source, and ASI (a `return` before a multi-line comment)
reads the same. (A stylesheet is the exception: no stack trace names a CSS
line, so `strip_css` also drops the empty lines.)

**Indentation.** Scripts and stylesheets also lose the spaces and tabs at the
start of each line (about 8.8 KB gzipped off the boot set), newlines kept.
Not where the leading whitespace is data: the text of a template literal, a
string continued over a line end, a kept multi-line comment, a CSS string or an
unquoted `url(`. The scanners report those ranges and `_drop_indent` skips any
line that starts inside one. It runs on the comment-free text, so it scans
that a second time.

`tests/test_asset_strip.py` holds the edge cases and, where `node` is on the
path, runs `node --check` over every stripped script; the acorn token check in
that file proves the stripped token stream equals the original's.
"""

from __future__ import annotations

import re

#: Bumped whenever the output for the same input changes, so a cached copy
#: from an older stripper (memory, `<data dir>/cache/static-gz`, and the
#: content-hash stamp the browser caches against) is never reused.
STRIP_VERSION = "5"

_IDENT_CHAR = re.compile(r"[\w$]")
#: After these words a `/` starts a regex literal, not a division.
_REGEX_AFTER_WORD = frozenset(
    "return typeof instanceof in of new delete void throw case do else yield await".split()
)


def _keep(comment: str) -> bool:
    return (
        comment.startswith(("/*!", "//#", "//@")) or "@license" in comment or "@preserve" in comment
    )


def _drop_span(text: str, start: int, end: int, cursor: int, joiner: str, out: list[str]) -> int:
    """Emit the text before one comment span and what replaces it; the new cursor."""
    n = len(text)
    line_start = max(text.rfind("\n", 0, start), text.rfind("\r", 0, start)) + 1
    line_end = end
    while line_end < n and text[line_end] in " \t":
        line_end += 1
    alone_before = line_start >= cursor and not text[line_start:start].strip(" \t")
    alone_after = line_end >= n or text[line_end] in "\r\n"
    body = text[start:end]
    if alone_before and alone_after:
        out.append(text[cursor:line_start])
        out.append("\n" * body.count("\n"))
        return line_end  # the line's own newline stays, as text
    before = text[cursor:start]
    if alone_after:
        # A trailing comment: drop it and the spaces before it.
        out.append(before.rstrip(" \t"))
        out.append("\n" * body.count("\n"))
        return end
    out.append(before)
    if joiner and "\n" in body:
        out.append("\n" * body.count("\n"))
    elif not (before[-1:].isspace() or text[end : end + 1].isspace()):
        out.append(joiner)
    elif before[-1:] in (" ", "\t"):
        # `a /* c */ + b` reads `a + b`, not `a  + b`.
        while end < n and text[end] in " \t":
            end += 1
    return end


def _rebuild(text: str, spans: list[tuple[int, int]], joiner: str = " ") -> str:
    """The text with each comment span removed, **every line number kept**.

    A comment alone on its line(s) leaves those lines empty: the newlines
    stay, so a stack trace, a console error or a support bundle names the
    same line in the served file as in the one on disk (an empty line costs
    gzip next to nothing). A comment sharing a line with code becomes one
    space, or the newlines it held (ASI reads a multi-line comment as a line
    terminator). In HTML a comment separates nothing (`a<!-- -->b` reads
    "ab"), so there the joiner is empty and an inline comment's newlines go
    with it."""
    out: list[str] = []
    cursor = 0
    for start, end in spans:
        if start < cursor:
            continue
        cursor = _drop_span(text, start, end, cursor, joiner, out)
    out.append(text[cursor:])
    return "".join(out)


_LINE_INDENT = re.compile(r"(?<=\n)[ \t]+|\A[ \t]+")


def _drop_indent(text: str, keep: list[tuple[int, int]]) -> str:
    """`text` without the leading spaces and tabs of any line, except a line
    that starts inside a `keep` range (a template's text, a continued string,
    a kept comment): the newline before it is at an index `a <= p - 1 < b`."""
    out: list[str] = []
    cursor = 0
    k = 0
    for m in _LINE_INDENT.finditer(text):
        p = m.start()
        while k < len(keep) and keep[k][1] < p:
            k += 1
        if k < len(keep) and keep[k][0] < p <= keep[k][1]:
            continue
        out.append(text[cursor:p])
        cursor = m.end()
    out.append(text[cursor:])
    return "".join(out)


# ---------------------------------------------------------------- JavaScript

_JS_NEXT = re.compile(r"[\"'`/{}]")
_TEMPLATE_NEXT = re.compile(r"[`\\$]")


def _prev_code(text: str, i: int, spans: list[tuple[int, int]]) -> int:
    """Index of the last character before `i` that is neither blank nor in a
    comment of `spans`, or -1."""
    j = i - 1
    k = len(spans) - 1
    while j >= 0:
        ch = text[j]
        if ch.isspace():
            j -= 1
            continue
        # Skip back over a comment that ends here.
        while k >= 0 and spans[k][1] > j + 1:
            k -= 1
        if k >= 0 and spans[k][1] == j + 1:
            j = spans[k][0] - 1
            k -= 1
            continue
        break
    return j


def _js_regex_allowed(text: str, i: int, spans: list[tuple[int, int]]) -> bool:
    """Whether a `/` at `i` begins a regex literal, from the token before it."""
    j = _prev_code(text, i, spans)
    if j < 0:
        return True
    ch = text[j]
    if _IDENT_CHAR.match(ch):
        start = j
        while start > 0 and _IDENT_CHAR.match(text[start - 1]):
            start -= 1
        word = text[start : j + 1]
        if start > 0 and text[start - 1] == "." and not text[start - 2 : start] == "..":
            return False  # a property name, `x.in / 2`
        return word in _REGEX_AFTER_WORD
    if ch in ")]}\"'`":
        return False
    if ch in "+-" and j > 0 and text[j - 1] == ch:
        return False  # postfix `x++ / 2`
    return True


def _first_doubt(doubt: int, text: str, i: int, spans: list[tuple[int, int]]) -> int:
    """`doubt` if set, else `i` when the division-read `/` at `i` is doubtful."""
    if doubt >= 0:
        return doubt
    return i if _js_slash_doubtful(text, i, spans) else -1


_CONTROL_HEAD = re.compile(r"[ \t]*(?:\}[ \t]*)?(?:else[ \t]+)?(?:if|while|for|with)\b")


def _js_slash_doubtful(text: str, i: int, spans: list[tuple[int, int]]) -> bool:
    """A `/` read as division that could be a regex statement whose quote or
    backtick would then not open a string, e.g. `if (x) /`/.test(y)`: the
    one guess `_js_scan` cannot settle from the token before. Only a `/`
    right after the `)` of an `if`/`while`/`for`/`with` head, or a `/` that
    starts a line after a `}` or `)`, qualifies; `(a - b) / 100 + "."` does
    not."""
    j = _prev_code(text, i, spans)
    if j < 0 or text[j] not in ")}":
        return False
    line = text.rfind("\n", 0, j) + 1
    first = text.rfind("\n", 0, i) + 1
    control = text[j] == ")" and _CONTROL_HEAD.match(text, line) is not None
    starts_line = first > j and not text[first:i].strip()
    if not (control or starts_line):
        return False
    end = _skip_regex(text, i)
    return end is not None and re.search(r"[\"'`]", text[i:end]) is not None


def _skip_string(text: str, i: int, quote: str) -> int:
    """Index just past the string literal whose opening quote is at `i`."""
    n = len(text)
    j = i + 1
    while j < n:
        ch = text[j]
        if ch == "\\":
            j += 2
            continue
        if ch == quote:
            return j + 1
        if ch == "\n":
            return j  # unterminated: stop at the line, as the parser would
        j += 1
    return n


def _skip_regex(text: str, i: int) -> int | None:
    """Index past the regex literal at `i`, or None when it is not one."""
    n = len(text)
    j = i + 1
    in_class = False
    while j < n:
        ch = text[j]
        if ch == "\\":
            j += 2
            continue
        if ch in "\r\n":
            return None
        if in_class:
            if ch == "]":
                in_class = False
        elif ch == "[":
            in_class = True
        elif ch == "/":
            j += 1
            while j < n and _IDENT_CHAR.match(text[j]):
                j += 1
            return j
        j += 1
    return None


def _keep_after(
    keep: list[tuple[int, int]], doubt: int, n: int
) -> list[tuple[int, int]]:
    """`keep` with everything from the first doubtful `/` on as one range."""
    if doubt < 0:
        return keep
    return [r for r in keep if r[1] <= doubt] + [(doubt, n)]


def js_comment_spans(text: str) -> list[tuple[int, int]]:
    """Every comment's (start, end) in a script, kept ones excluded."""
    return _js_scan(text)[0]


def _js_comment(text: str, i: int, nxt: str, every: list, spans: list, keep: list) -> int:
    """Record the `//` or `/*` comment at `i` (a kept one in `keep`, the rest
    in `spans`, every one in `every`) and return where it ends."""
    n = len(text)
    if nxt == "/":
        end = i + 2
        while end < n and text[end] not in "\r\n":
            end += 1
    else:
        end = text.find("*/", i + 2)
        end = n if end == -1 else end + 2
    every.append((i, end))
    if not _keep(text[i:end]):
        spans.append((i, end))
    elif nxt == "*":
        keep.append((i, end))
    return end


def _closes_substitution(templates: list[int]) -> bool:
    """A `}` outside a string: True when it closes the innermost `${`."""
    if not templates:
        return False
    if templates[-1] == 0:
        templates.pop()
        return True
    templates[-1] -= 1
    return False


def _template_step(text: str, i: int, tstart: int, keep: list, templates: list[int]) -> tuple[int, bool]:
    """At the next special character inside template text: where to go on
    from, and whether that is still template text."""
    ch = text[i]
    if ch == "\\":
        return i + 2, True
    if ch == "`":
        keep.append((tstart, i))
        return i + 1, False
    if text[i + 1 : i + 2] == "{":
        keep.append((tstart, i))
        templates.append(0)
        return i + 2, False
    return i + 1, True


def _js_scan(text: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """(comment spans, ranges whose inner line starts are data), in order."""
    spans: list[tuple[int, int]] = []
    #: Template text, strings and kept comments: `_drop_indent` leaves alone
    #: a line that starts inside one.
    keep: list[tuple[int, int]] = []
    tstart = 0
    #: Every comment, kept ones too, in order: what the regex test skips over.
    every: list[tuple[int, int]] = []
    #: Where the first doubtful `/` sits; text after it may be misread, so
    #: its lines keep their indentation.
    doubt = -1
    # One entry per open `${`: the `{` depth inside that substitution.
    templates: list[int] = []
    n = len(text)
    i = 0
    in_template = False
    while i < n:
        if in_template:
            m = _TEMPLATE_NEXT.search(text, i)
            if m is None:
                keep.append((tstart, n))
                return spans, _keep_after(keep, doubt, n)
            i, in_template = _template_step(text, m.start(), tstart, keep, templates)
            continue
        m = _JS_NEXT.search(text, i)
        if m is None:
            break
        i = m.start()
        ch = text[i]
        if ch in "\"'":
            end = _skip_string(text, i, ch)
            keep.append((i, end))
            i = end
        elif ch == "`":
            in_template = True
            i += 1
            tstart = i
        elif ch == "{":
            if templates:
                templates[-1] += 1
            i += 1
        elif ch == "}":
            if _closes_substitution(templates):
                in_template = True
                tstart = i + 1
            i += 1
        else:  # "/"
            nxt = text[i + 1 : i + 2]
            if nxt and nxt in "/*":
                i = _js_comment(text, i, nxt, every, spans, keep)
            elif _js_regex_allowed(text, i, every):
                end = _skip_regex(text, i)
                i = i + 1 if end is None else end
            else:
                doubt = _first_doubt(doubt, text, i, every)
                i += 1
    return spans, _keep_after(keep, doubt, n)


def strip_js_comments(text: str) -> str:
    """Comments gone, indentation kept: for a reader (a test, a lint) that
    tells a top-level line from a nested one by its indent."""
    return _rebuild(text, js_comment_spans(text))


def strip_js(text: str) -> str:
    bare = strip_js_comments(text)
    return _drop_indent(bare, _js_scan(bare)[1])


# ----------------------------------------------------------------------- CSS

_CSS_NEXT = re.compile(r"[\"'/]|url\(", re.IGNORECASE)


def css_comment_spans(text: str) -> list[tuple[int, int]]:
    return _css_scan(text)[0]


def _css_scan(text: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """(comment spans, string / `url(` / kept-comment ranges), as `_js_scan`."""
    spans: list[tuple[int, int]] = []
    keep: list[tuple[int, int]] = []
    n = len(text)
    i = 0
    while i < n:
        m = _CSS_NEXT.search(text, i)
        if m is None:
            break
        i = m.start()
        ch = text[i]
        if ch in "\"'":
            end = _skip_string(text, i, ch)
            keep.append((i, end))
            i = end
        elif ch == "/":
            if text[i + 1 : i + 2] == "*":
                end = text.find("*/", i + 2)
                end = n if end == -1 else end + 2
                if _keep(text[i:end]):
                    keep.append((i, end))
                else:
                    spans.append((i, end))
                i = end
            else:
                i += 1
        else:  # url(
            j = i + 4
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "\"'":
                i = j  # a quoted url is a string, read as one next round
            else:
                close = text.find(")", j)
                end = n if close == -1 else close + 1
                keep.append((i, end))
                i = end
    return spans, keep


_CSS_BLANK_LINE = re.compile(r"\n[ \t]*(?=\n)")


def strip_css(text: str) -> str:
    """Comments gone, and the empty lines they leave with them. Unlike a
    script, a stylesheet is never named by line in a stack trace, and the
    1,300 empty lines a commented file left cost the boot stylesheets about
    three kilobytes gzipped against a cap that was at zero (INBOX 776), and
    the indentation goes too, outside strings and `url(`."""
    bare = _CSS_BLANK_LINE.sub("", _rebuild(text, css_comment_spans(text)))
    return _drop_indent(bare, _css_scan(bare)[1])


# ---------------------------------------------------------------------- HTML

_HTML_NEXT = re.compile(r"<(!--|/?[a-zA-Z])")
#: Elements whose content is not markup (raw text) or must keep its comments
#: as written: everything inside is passed over to the matching close tag.
#: Not `template`: its content is ordinary markup, and Settings' body (62 KB of
#: comments in 317 KB) sits in one (INBOX 1501), so its comments go like the
#: page's own. Nor a `<script type="text/x-surface">`: a surface's markup kept
#: as raw text so the parser makes no nodes for it at boot, which is markup all
#: the same (comments go; the lint holds that none holds a `<script` of its own).
_HTML_OPAQUE = ("script", "style", "textarea", "title", "pre", "xmp")
_TAG_NAME = re.compile(r"[a-zA-Z][a-zA-Z0-9-]*")
_SURFACE_SCRIPT = re.compile(r'<script\s+type="text/x-surface"[\s>]', re.I)


def _html_tag_end(text: str, i: int) -> int:
    """Index past the `>` closing the tag that starts at `i` (quotes respected)."""
    n = len(text)
    j = i + 1
    while j < n:
        ch = text[j]
        if ch in "\"'":
            close = text.find(ch, j + 1)
            j = n if close == -1 else close + 1
            continue
        if ch == ">":
            return j + 1
        j += 1
    return n


def _opens_opaque(text: str, i: int, tag: str, tag_end: int) -> bool:
    """Whether the tag at `i` opens an element whose content is passed over as written."""
    if tag not in _HTML_OPAQUE or text[i:tag_end].rstrip(">").endswith("/"):
        return False
    return not (tag == "script" and _SURFACE_SCRIPT.match(text, i))


def _opaque_end(text: str, lower: str, tag: str, tag_end: int) -> int:
    """Past the matching close tag, counting nested ones of the same name."""
    n = len(text)
    depth = 1
    j = tag_end
    opener = re.compile(rf"<(/?){tag}(?=[\s/>])")
    while depth and j < n:
        found = opener.search(lower, j)
        if found is None:
            return n
        if tag in ("script", "style", "textarea", "title", "xmp") and not found.group(1):
            j = found.end()  # raw text: an opener inside is just text
            continue
        depth += -1 if found.group(1) else 1
        j = _html_tag_end(text, found.start())
    return j


def html_comment_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    n = len(text)
    i = 0
    lower = text.lower()
    while i < n:
        m = _HTML_NEXT.search(text, i)
        if m is None:
            break
        i = m.start()
        if m.group(1) == "!--":
            end = text.find("-->", i + 4)
            end = n if end == -1 else end + 3
            spans.append((i, end))
            i = end
            continue
        tag_end = _html_tag_end(text, i)
        if text[i + 1] != "/":
            name = _TAG_NAME.match(text, i + 1)
            tag = name.group(0).lower() if name else ""
            if _opens_opaque(text, i, tag, tag_end):
                i = _opaque_end(text, lower, tag, tag_end)
                continue
        i = tag_end
    return spans


def strip_html(text: str) -> str:
    return _rebuild(text, html_comment_spans(text), joiner="")


def strip_for_path(name: str, body: bytes) -> bytes:
    """The served bytes for a frontend file named `name` (a path or suffix)."""
    lowered = name.lower()
    if lowered.endswith(".js"):
        fn = strip_js
    elif lowered.endswith(".css"):
        fn = strip_css
    elif lowered.endswith(".html"):
        fn = strip_html
    else:
        return body
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return body
    return fn(text).encode("utf-8")
