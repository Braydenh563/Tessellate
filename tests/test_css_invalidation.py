"""No stylesheet makes a class change restyle a whole subtree.

**Why this exists (MINDMAP_PLAN.md 13a-view).** A browser keeps, for each
class name and attribute a selector mentions, the list of elements a change
to it can affect, so toggling `.is-open` on one element restyles only what
the rules about `.is-open` can reach. There is one shape it cannot narrow: an
attribute selector on `class` itself (`[class*="card"]`, `[class^="wb-"]`)
in an *ancestor* position. Any class change on any element might have just
made it match, so the browser has to restyle that element's whole subtree on
every class change, for every element in the app.

One rule of that shape was in Settings (`#settings-modal .settings-section
[class*="card"] *`). Measured on a 500-topic mind map, toggling one
unrelated class on the board's container restyled 13,662 elements in 218ms;
with the rule gone, 0.1ms. The id in front of it did not help: the browser
cannot know an element is outside `#settings-modal` until it has restyled it.

So the lint is exactly that shape: a `[class` attribute selector in a
compound that is followed by a descendant or child combinator. The same
selector as the *last* compound (the element itself) is fine, and so is one
followed by a sibling combinator, which reaches one sibling rather than a
subtree.
"""

from __future__ import annotations

import re

from tests._css_paths import FRONTEND_DIR
from tests._app_js import app_js_family, frontend_text


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _selectors(text: str):
    """Yield (line, selector) for every rule prelude, at any nesting depth."""
    text = _strip_comments(text)
    depth_stack = []
    start = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "{":
            prelude = text[start:i].strip()
            line = text.count("\n", 0, i) + 1
            if prelude and not prelude.startswith("@"):
                yield line, prelude
            depth_stack.append(i)
            start = i + 1
        elif ch in "};":
            if ch == "}" and depth_stack:
                depth_stack.pop()
            start = i + 1
        i += 1


def _split_top(selector: str, seps: str):
    """Split at `seps` characters that are outside brackets and parentheses."""
    parts, depth, cur = [], 0, []
    for ch in selector:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if depth == 0 and ch in seps:
            parts.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur))
    return parts


def _ancestor_class_attr(selector: str) -> bool:
    """True when a `[class...]` sits in a compound followed by ' ' or '>'."""
    # Normalise the combinators so each is one token between compounds.
    norm = re.sub(r"\s*([>+~])\s*", r" \1 ", selector.strip())
    tokens = [t for t in _split_top(norm, " ") if t]
    compounds = []  # (compound, combinator that follows it)
    for tok in tokens:
        if tok in (">", "+", "~"):
            if compounds:
                compounds[-1] = (compounds[-1][0], tok)
            continue
        compounds.append((tok, " "))
    if compounds:
        compounds[-1] = (compounds[-1][0], None)
    for compound, comb in compounds:
        if comb in (" ", ">") and "[class" in compound:
            return True
    return False


def test_the_detector_knows_the_shape():
    assert _ancestor_class_attr('#m .s [class*="card"] *')
    assert _ancestor_class_attr('.a > [class^="wb-"] .b')
    assert not _ancestor_class_attr('#m .s [class*="card"]')
    assert not _ancestor_class_attr('.s button:not([class*="card"])')
    assert not _ancestor_class_attr('.d > :is(.x, [class*="help"]) + :is(.y)')


def test_no_class_attribute_selector_in_an_ancestor_position():
    offenders = []
    for path in sorted((FRONTEND_DIR / "css").glob("*.css")):
        for line, prelude in _selectors(path.read_text(encoding="utf-8")):
            for selector in _split_top(prelude, ","):
                if _ancestor_class_attr(selector):
                    offenders.append(f"{path.name}:{line}: {selector.strip()}")
    assert not offenders, (
        "A `[class...]` attribute selector before a descendant or child "
        "combinator makes every class change in the app restyle a whole "
        "subtree (see this file's docstring). Put the rule on the element "
        "itself, or name the classes:\n" + "\n".join(offenders)
    )


# --- The same class of cost, found app-wide (INBOX 400) -----------------------
#
# A trace of every interaction at 500 notes, 50 documents and 40 chats
# (`scratchpad/ui-sweeps/f2-trace.js`, the table in HISTORY.md) found four
# more shapes that do their damage in a style or layout pass nobody sees in
# the code that caused it. Each has its own test below.


def _js(name: str) -> str:
    return frontend_text(name)


def _function_body(src: str, signature: str) -> str:
    """The balanced `{...}` block that follows `signature`."""
    start = src.index(signature)
    # The body's brace, not one in a destructured parameter list.
    open_at = src.index(") {", start) + 2
    depth = 0
    for i in range(open_at, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[open_at : i + 1]
    raise AssertionError(f"unbalanced body after {signature}")


#: Every custom property script writes on <html>, and why that is safe. One
#: written there inherits into every element, so a write that changes it
#: restyles the whole document: measured at 1,560 drawn elements on Notes,
#: 33ms per write (`f2-ab.js`, probe `root-var`). These are written when a
#: setting changes or a measured bar changes height, never per frame. A new
#: name here is a question to answer first: can it live on the one element
#: that reads it, or be registered `inherits: false` (as `--wb-grid-*` are)?
ROOT_CUSTOM_PROPERTIES = {
    # settings.js and theme-boot.js, from Appearance: a setting changed.
    "--accent", "--accent-soft", "--accent-surface", "--blob-a", "--page", "--glass-sheen-strength",
    "--bg-art-opacity", "--radius", "--glass-blur", "--glass-opacity", "--zoom",
    "--border-style", "--shadow-intensity",
    # settings.js, `measureLabelOptics`: at boot, when the fonts are ready and
    # when Appearance changes the font (INBOX 592), never per frame.
    "--ph-cap-dy",
    # app.js: a ResizeObserver on the top bar, and the on-screen keyboard.
    "--header-h", "--keyboard-inset",
    # panel-movable.js (INBOX 1474): the app's side margins while a panel is
    # docked to a side, written when it docks, undocks, closes or the window
    # resizes (debounced 120ms), never per frame.
    "--dock-push-left", "--dock-push-right",
}


def test_root_custom_properties_written_from_script_are_known():
    pattern = re.compile(
        r"(?:document\.documentElement|\broot|\b_r)\.style\.setProperty\(\s*[\"'](--[\w-]+)"
    )
    found = {}
    for path in sorted((FRONTEND_DIR / "js").glob("*.js")):
        for name in pattern.findall(path.read_text(encoding="utf-8")):
            found.setdefault(name, path.name)
    unknown = {k: v for k, v in found.items() if k not in ROOT_CUSTOM_PROPERTIES}
    assert not unknown, (
        "A custom property written on <html> restyles every element in the "
        "app each time its value changes. Put it on the element that reads "
        "it, register it `inherits: false`, or add it to "
        "ROOT_CUSTOM_PROPERTIES with the reason it is never written per "
        f"frame: {unknown}"
    )
    # The detector sees the two-line form `setProperty(\n  "--keyboard-inset"`.
    assert "--keyboard-inset" in found and "--header-h" in found


def test_long_lists_skip_rows_that_are_off_screen():
    """The Notes list and the Timeline feed style only what is near the window.

    Traced at 500 notes: 1,206 of the 1,382 elements in the Notes list were
    more than a window below the fold, and entering the tab restyled every one
    (61ms). With `content-visibility: auto` on the rows, 31ms; the Timeline's
    layout on entry went from 48ms to 7ms.
    """
    css = "\n".join(
        _strip_comments(p.read_text(encoding="utf-8"))
        for p in sorted((FRONTEND_DIR / "css").glob("*.css"))
    )
    for row in ("#entry-list > li", ".timeline-feed .timeline-row"):
        bodies = [
            m.group(1)
            for m in re.finditer(re.escape(row) + r"[^{};]*\{([^}]*)\}", css)
            if "content-visibility: auto" in m.group(1)
        ]
        assert bodies, row
        assert "contain-intrinsic-size: auto" in bodies[0], (
            f"{row}: `auto` in the intrinsic size remembers the height a row "
            "last drew at, so the scrollbar does not jump once it has been seen"
        )


def test_a_data_load_does_not_cross_fade_the_library():
    """`loadLibrary` renders without the View Transition.

    The fade snapshots the whole window; on every switch to Library it held
    the window for a 216 to 283ms frame gap, fading a page that was already
    changing because the tab changed.
    """
    src = _js("library.js")
    assert "renderLibrary({ quiet: true })" in _function_body(src, "async function loadLibrary()")
    assert "|| quiet)" in _function_body(src, "function renderLibrary(")


def test_timeline_rows_do_not_build_a_date_formatter_each():
    """`toLocale*String` makes a new `Intl.DateTimeFormat` per call.

    Profiled on a 300-row feed, those calls were 50ms of the 62ms the feed
    took to build. The row builder uses formatters made once.
    """
    body = _function_body(_js("timeline.js"), "function timelineRowElement(")
    assert "toLocale" not in body


#: The loops that write a style and then read a layout, allowed with the
#: reason. Each such loop forces one layout of the whole page per turn.
LAYOUT_READ_AFTER_WRITE_LOOPS = {
    # Deliberate, capped at four passes (COMPOSER_FIT_PASSES): each pass
    # measures the overflow the previous trim left.
    ("app.js", "fitComposerToDock"),
    # The read is of a <pre> not yet in the document, which forces nothing.
    ("app.js", "renderTasks"),
}

_READ = re.compile(
    r"getBoundingClientRect\(|\.offset(?:Height|Width|Top|Left)\b|\.client(?:Height|Width)\b"
    r"|\.scroll(?:Height|Width)\b|getComputedStyle\("
)
_WRITE = re.compile(
    r"\.style\.[a-zA-Z]+\s*=[^=]|\.style\.setProperty\(|\.style\.cssText\s*=|"
    r"classList\.(?:add|remove|toggle)\(|\.className\s*=[^=]"
)


def _enclosing_function(src: str, at: int) -> str:
    names = list(re.finditer(r"^(?:async\s+)?function\s+(\w+)", src[:at], flags=re.M))
    return names[-1].group(1) if names else "?"


def _loop_bodies(src: str):
    """Yield (offset, body) for every braced `for (...) {` and `forEach(x => {`."""
    for m in re.finditer(r"\bfor\s*\(|\.forEach\(\s*(?:\([^)]*\)|\w+)\s*=>", src):
        at = m.end()
        if m.group(0).startswith("for"):
            depth = 1
            while at < len(src) and depth:
                depth += {"(": 1, ")": -1}.get(src[at], 0)
                at += 1
        while at < len(src) and src[at] in " \t\n":
            at += 1
        if at >= len(src) or src[at] != "{":
            continue  # a one-statement loop: no block to look inside
        open_at = at
        depth = 0
        for i in range(open_at, min(len(src), open_at + 20000)):
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    yield m.start(), src[open_at:i]
                    break


def test_no_loop_reads_layout_after_writing_style():
    """Read everything, then write everything.

    `sizeDashWidgets` set a widget's span, read its height and set it again,
    once per widget: every read paid for a layout the write before it had
    dirtied. Profiled on a switch to the dashboard, 14.7ms of a 22ms switch.
    """
    offenders = []
    for path in sorted((FRONTEND_DIR / "js").glob("*.js")):
        if path.name in ("sw.js", "graph-worker.js"):
            continue
        # Comments blanked to the same length, so offsets still give lines.
        src = re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), path.read_text(encoding="utf-8"))
        for at, body in _loop_bodies(src):
            write = _WRITE.search(body)
            if write and _READ.search(body, write.end()):
                #: The pieces of the old app.js answer to app.js's allowances.
                owner = "app.js" if app_js_family(path) else path.name
                key = (owner, _enclosing_function(src, at))
                if key not in LAYOUT_READ_AFTER_WRITE_LOOPS:
                    offenders.append(f"{path.name}:{src.count(chr(10), 0, at) + 1} in {key[1]}")
    assert not offenders, (
        "A loop that writes a style and then reads a layout forces one layout "
        "of the whole page per turn. Read first, then write:\n" + "\n".join(offenders)
    )


def test_the_loop_detector_knows_the_shape():
    thrash = "function f(){ for (const c of cs) { c.style.height = '1px'; h.push(c.offsetHeight); } }"
    batched = "function f(){ for (const c of cs) c.style.height = '1px'; const h = cs.map((c) => c.offsetHeight); }"
    assert any(_WRITE.search(b) and _READ.search(b, _WRITE.search(b).end()) for _, b in _loop_bodies(thrash))
    assert not any(_WRITE.search(b) and _READ.search(b, _WRITE.search(b).end()) for _, b in _loop_bodies(batched))


def test_the_dashboard_measures_its_widgets_in_one_pass():
    body = _function_body(_js("dashboard.js"), "function sizeDashWidgets()")
    assert "getBoundingClientRect" in body and ".map(" in body
