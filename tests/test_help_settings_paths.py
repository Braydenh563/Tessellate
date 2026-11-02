"""Every "Settings, A, B" path the Guide names is a real pane and group.

Standing order 13 (help moves with the UI), and the audit of 2026-10-05 that
found the help naming places the UI had renamed: "Settings -> Shortcuts" (the
pane is Keyboard shortcuts), "Settings -> Tools" (Tools it can use), "Account
and security" (Account & security) and "What the notebook learned" (What it
learned). The Settings panes were regrouped and renamed several times and
nothing tied the help's wording to the nav, so each rename left a stale path
behind that read as plausible.

This pins the path itself, not the prose around it. For each place the Guide's
topics (`help_chat.py`, `help_topics_more.py`, their `path` and `steps` meta)
write "Settings" followed by a pane and a group:

- the pane must be a button in index.html's Settings nav, by its label;
- the group after it must be a heading, a fold's summary, a legend, a label or
  a button of that pane's own section (the static markup; a group that a script
  draws is named in `JS_DRAWN`, with the file that draws it, and that file is
  checked for the text);
- the `badge` and `target` the topics carry must point at a real section, tab
  or element id, so a rename of an id cannot leave a dead "open it" button.

It is a lint on the help's text, so it reads text, never the running app: the
live check (every path opened and its control found) is
`scratchpad/ui-sweeps/helpaudit.js`.
"""

from __future__ import annotations

import ast
import html
import re
from html.parser import HTMLParser
from pathlib import Path

from tessellate.ai import help_chat
from tests._repo_files import repo_files

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
JS = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "frontend" / "js").glob("*.js")}

#: Words that may follow a path and start ordinary prose rather than a group,
#: so "Settings, Models, then Settings, Logs" and "Settings, Templates, where
#: Draft with Atlas writes..." are a pane followed by a sentence.
PROSE_AFTER_PANE = ("then", "and", "where", "which", "or", "with", "but", "so", "press", "when")

#: Groups a script draws into a pane, which the static markup does not hold:
#: (pane id, group text) -> the file whose source carries that text.
JS_DRAWN = {
    ("learned", "what may run"): "settings.js",
    ("learned", "margin reader"): "settings.js",
    ("learned", "model bench"): "settings.js",
}


def _norm(text: str) -> str:
    text = html.unescape(text).replace("’", "'")
    return " ".join(text.split()).lower()


class _Index(HTMLParser):
    """The Settings nav (label -> section id) and each section's own labels."""

    #: Elements whose text names a place in a pane.
    NAMING = ("h2", "h3", "h4", "summary", "legend", "label", "button", "option", "span", "p")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.nav: dict[str, str] = {}
        self.sections: dict[str, set[str]] = {}
        self._section: str | None = None
        self._depth = 0
        self._capture: list[str] | None = None
        self._tag = ""
        self._in_nav = False
        self._nav_section = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "nav" and a.get("id") == "settings-nav":
            self._in_nav = True
        if tag == "section" and "settings-section" in a.get("class", "") and a.get("id", "").startswith("settings-"):
            self._section = a["id"][len("settings-"):]
            self.sections[self._section] = set()
            self._depth = 0
        elif self._section and tag == "section":
            self._depth += 1
        if self._in_nav and tag == "button" and a.get("data-section"):
            self._nav_section = a["data-section"]
            self._capture, self._tag = [], tag
            return
        if self._section:
            for key in ("aria-label", "title", "placeholder"):
                if a.get(key):
                    self.sections[self._section].add(_norm(a[key]))
            if tag in self.NAMING:
                self._capture, self._tag = [], tag

    def handle_endtag(self, tag):
        if self._capture is not None and tag == self._tag:
            text = _norm("".join(self._capture))
            if self._in_nav and self._nav_section:
                self.nav[text] = self._nav_section
                self._nav_section = ""
            elif self._section and text:
                self.sections[self._section].add(text)
                # "Load the search model when the app starts (off: a lighter
                # start...)" is named by what comes before the parenthesis.
                self.sections[self._section].add(re.sub(r"\s*\(.*$", "", text))
            self._capture = None
        if tag == "nav":
            self._in_nav = False
        if tag == "section" and self._section:
            if self._depth == 0:
                self._section = None
            else:
                self._depth -= 1

    def handle_data(self, data):
        if self._capture is not None:
            self._capture.append(data)


_parsed = _Index()
_parsed.feed(INDEX)
NAV = _parsed.nav
SECTIONS = _parsed.sections


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _strings(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            yield from _strings(value)


def _help_texts() -> list[str]:
    return list(_strings(help_chat.HELP_TOPICS)) + list(_strings(help_chat.TOPIC_META))


def _paths() -> set[str]:
    """Everything written after a "Settings" that reads as a path."""
    found: set[str] = set()
    for text in _help_texts():
        text = text.replace(" -> ", ", ").replace(" → ", ", ")
        for match in re.finditer(r"Settings, ([^.:;()\n]{1,140})", text):
            found.add(match.group(1).strip())
    return found


def _resolve(path: str) -> tuple[str | None, list[str]]:
    """Split "Appearance, Atlas and faces, Atlas style and Atlas look" into the
    pane's section id and the group segments that name something real. Returns
    (None, []) when the start is no pane. The trailing prose is dropped."""
    labels = sorted(NAV, key=len, reverse=True)
    low = _norm(path)
    pane = next((label for label in labels if low == label or low.startswith(label + " ") or low.startswith(label + ",")), None)
    if pane is None:
        return None, []
    section = NAV[pane]
    rest = low[len(pane):]
    names = sorted(SECTIONS.get(section, set()), key=len, reverse=True)
    segments: list[str] = []
    while rest.startswith(", "):
        rest = rest[2:]
        if rest.split(" ", 1)[0] in PROSE_AFTER_PANE:
            break
        hit = next((n for n in names if rest == n or rest.startswith(n + " ") or rest.startswith(n + ",")), None)
        if hit is None:
            segments.append(rest.split(",", 1)[0])
            break
        segments.append(hit)
        rest = rest[len(hit):]
    return section, segments


def _drawn_by_script(section: str, name: str) -> bool:
    file = JS_DRAWN.get((section, name))
    if not file:
        return False
    return name in _norm(JS[file])


def test_the_scan_finds_paths_to_check():
    # A parser that quietly finds nothing would pass every other test here.
    assert len(NAV) >= 20, NAV
    assert len(_paths()) >= 60, len(_paths())


def test_every_settings_path_names_a_real_pane():
    bad = []
    for path in sorted(_paths()):
        section, _ = _resolve(path)
        if section is None:
            bad.append(path)
    assert not bad, (
        "The Guide names a Settings pane the nav does not have. The pane names are the nav's labels in "
        "frontend/index.html (#settings-nav); fix the help, never rename the UI to match it:\n  " + "\n  ".join(bad)
    )


def test_every_settings_path_names_a_real_group():
    bad = []
    for path in sorted(_paths()):
        section, segments = _resolve(path)
        if section is None:
            continue
        known = SECTIONS.get(section, set())
        for segment in segments:
            # The segment may be a longer control name than the heading it starts with.
            if any(name == segment or name.startswith(segment) or segment.startswith(name) for name in known):
                continue
            if _drawn_by_script(section, segment):
                continue
            bad.append(f"Settings, {path}  ({segment!r} is not in pane {section!r})")
    assert not bad, (
        "The Guide names a group or control a Settings pane does not have. Check the heading in "
        "frontend/index.html, fix the help to say what the UI says, and if a script draws it add it to "
        "JS_DRAWN here:\n  " + "\n  ".join(bad)
    )


def test_no_arrow_paths_are_left_in_the_guide():
    # "Settings -> X" was the older spelling; the audit moved every one to the
    # comma form the rest of the help uses, so a path reads the same everywhere.
    arrows = sorted({t[max(0, m.start() - 10): m.end() + 30] for t in _help_texts() for m in re.finditer(r"Settings (?:->|→)", t)})
    assert not arrows, arrows


def test_every_badge_and_target_points_at_something_real():
    tabs = set(re.findall(r'data-tab="([a-z-]+)"', INDEX)) | set(re.findall(r'id="tab-([a-z-]+)"', INDEX))
    sections = set(NAV.values())
    ids = set(re.findall(r'\bid="([^"]+)"', INDEX))
    bad = []
    for topic in help_chat.HELP_TOPICS:
        badge = topic.get("badge") or {}
        if badge.get("section") and badge["section"] not in sections:
            bad.append(f"{topic['id']}: badge section {badge['section']!r} is not a Settings section")
        if badge.get("tab") and badge["tab"] not in tabs:
            bad.append(f"{topic['id']}: badge tab {badge['tab']!r} is not a tab")
    for topic_id, meta in help_chat.TOPIC_META.items():
        target = meta.get("target")
        if target and target not in ids:
            bad.append(f"{topic_id}: target {target!r} is not an id in index.html")
    assert not bad, "\n  ".join(bad)


def _ui_strings():
    """Text a person can read in the shipped app: HTML without its comments,
    JS string literals on lines that are not comments, Python string constants
    that are not docstrings."""
    html_text = re.sub(r"<!--.*?-->", "", INDEX, flags=re.S)
    yield "index.html", html_text
    for name, text in JS.items():
        for line in text.splitlines():
            if line.lstrip().startswith(("//", "*", "/*")):
                continue
            yield name, line
    for path in repo_files(ROOT / "src" / "tessellate", suffixes=(".py",)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                    docstrings.add(id(first.value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                yield path.name, node.value


def test_every_pane_the_app_names_in_its_own_text_is_a_real_pane():
    """"Settings, Models" in a toast, an error or a hint: the same rename that
    stranded the Guide stranded these (Settings, Extras, → Tools, → Import)."""
    bad = set()
    for name, text in _ui_strings():
        text = " ".join(html.unescape(text).split())
        for match in re.finditer(r"Settings(?: \u2192| ->|,) ([A-Z][^.:;()\n\"'`<]{0,60})", text):
            section, _ = _resolve(match.group(1))
            if section is None:
                bad.add(f"{name}: {match.group(0)!r}")
    assert not bad, (
        "Text the app shows names a Settings pane the nav does not have (the nav's labels are in "
        "frontend/index.html, #settings-nav):\n  " + "\n  ".join(sorted(bad))
    )


def test_a_topic_badge_opens_the_pane_its_path_names():
    """A topic whose path starts "Settings, <pane>" has a badge that opens that
    pane. The audit found the autonomous-AI entry badged Profile (it moved to
    Background tasks) and nothing noticed, because the badge is a button and a
    button that opens the wrong pane still opens a pane."""
    bad = []
    for topic in help_chat.HELP_TOPICS:
        section = (topic.get("badge") or {}).get("section")
        path = help_chat.TOPIC_META.get(topic["id"], {}).get("path", "")
        if not (section and path.startswith("Settings, ")):
            continue
        pane, _ = _resolve(path[len("Settings, "):])
        if pane and pane != section and " and " not in path:
            bad.append(f"{topic['id']}: path {path!r} is pane {pane!r} but the badge opens {section!r}")
    assert not bad, "\n  ".join(bad)


def test_the_readme_names_real_panes_and_groups():
    """The README is a help surface too: the audit found it sending a reader to
    Settings, Models for the search engine (it is under Search and index) and
    spelling a pane "Account and security"."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # The screenshots' <summary> is a list of picture names ("Settings, Your
    # look, the popup agent"), not a path; bold markers sit inside names.
    readme = "\n".join(line for line in readme.splitlines() if not line.lstrip().startswith("<summary"))
    text = " ".join(readme.replace("*", "").replace("\n", " ").split())
    bad = []
    checked = 0
    for match in re.finditer(r"Settings(?:,| >) ([A-Z][^.:;()]{0,100})", text):
        path = match.group(1).replace(" > ", ", ")
        # "(Settings, then Help)" and "from Settings, ..." prose: a path starts at a pane.
        section, segments = _resolve(path)
        if section is None:
            bad.append(f"Settings, {path[:60]}")
            continue
        checked += 1
        known = SECTIONS.get(section, set())
        for segment in segments:
            if not any(name == segment or name.startswith(segment) or segment.startswith(name) for name in known):
                bad.append(f"Settings, {path[:60]} ({segment!r} is not in that pane)")
    assert checked >= 5, checked
    assert not bad, "README paths that do not match the Settings nav:\n  " + "\n  ".join(bad)
