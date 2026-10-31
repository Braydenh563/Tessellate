"""The app's emblem turns wherever it is drawn (INBOX 426 h).

The owner: "all of the animated logos arent rotating and the one form the
new chat interface is missing". Measured with the system's reduced-motion
hint on (Windows' "Animation effects" off is the common way to have it):
every emblem carried `animation-name: emblem-spin` and its transform did not
move between two samples 500ms apart, on the lock screen, the dashboard's
hero, the top bar's mark and the chat's welcome. And at 1280x720 the chat's
welcome hid its emblem outright (`.chat-empty.is-short`).

The turn itself was never removed. `canvas.emblem-spin` restates its
duration and iteration count under the hint with `:root` and `!important`,
which beat the vestibular blanket in 02-chat-graph.css for as long as that
blanket was a bare `*` (specificity 0,0,0). Commit 08f874d exempted the
companion from the blanket with `*:not(:is(#nm-buddy, ...))`, and a `:not()`
or `:is()` takes the specificity of its most specific argument: the id
raised the whole blanket to 1,0,0, so from then on it beat every
`!important` exemption in the app, the emblem's included, and each one ran
its 43.6s turn in 0.01ms and stopped. The same blanket also stopped the
progress indicators that escape it the same way.

These lints hold the three halves: the blanket stays at no specificity, every
drawn emblem is asked to turn, and the chat's welcome keeps its emblem when
the pane is short.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
CSS = sorted((FRONTEND / "css").glob("*.css"))
JS = sorted((FRONTEND / "js").glob("*.js"))


def _strip_where(selector: str) -> str:
    """The selector with every `:where(...)` group removed, parentheses
    balanced, since `:where` is the one pseudo-class that adds nothing."""
    out = []
    i = 0
    while i < len(selector):
        if selector.startswith(":where(", i):
            depth = 0
            j = i + len(":where")
            while j < len(selector):
                if selector[j] == "(":
                    depth += 1
                elif selector[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            i = j + 1
            continue
        out.append(selector[i])
        i += 1
    return "".join(out)


def _top_level(selector: str) -> list[str]:
    """A selector list split on its own commas, not the ones inside `:is()`."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(selector):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(selector[start:i])
            start = i + 1
    parts.append(selector[start:])
    return [p.strip() for p in parts]


def _blankets() -> list[str]:
    """Every selector list that kills animations under reduced motion."""
    found = []
    for path in CSS:
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
            body = match.group(2)
            if "animation-duration: 0.001ms !important" in body:
                found.append(match.group(1).strip())
    return found


def test_the_reduced_motion_blanket_has_no_specificity() -> None:
    """The blanket must lose to any rule that names what it exempts, so it
    may carry no id and no class outside a `:where()`."""
    blankets = _blankets()
    assert blankets, "the reduced-motion blanket moved; point this lint at it"
    for selector in blankets:
        for part in _top_level(selector):
            bare = _strip_where(part)
            assert "#" not in bare and "." not in bare, (
                "the reduced-motion blanket gained specificity, so it now beats "
                f"every `:root ... !important` exemption (the emblem's turn): {part.strip()}"
            )


def test_every_drawn_emblem_is_asked_to_turn() -> None:
    """The owner: "whenever the generated p5.js node graph logo shows, make
    sure it is never static and always rotating". A call that leaves
    `animate` off draws a still mark."""
    still = []
    for path in JS:
        # Comment lines quote the name (`renderEmblem()` moved ...); only code counts.
        lines = path.read_text(encoding="utf-8").splitlines()
        text = "\n".join(line for line in lines if not line.lstrip().startswith(("//", "*", "/*")))
        for match in re.finditer(r"(?<!function )renderEmblem\(([^)]*)\)", text):
            args = match.group(1)
            if "animate: true" in args or "{ animate }" in args:
                continue
            still.append(f"{path.name}: renderEmblem({args})")
    assert not still, f"an emblem is drawn still: {still}"
    app = app_js_text()
    slots = app.split("const EMBLEM_SLOTS = [", 1)[1].split("];", 1)[0]
    entries = re.findall(r"\[\"[\w-]+\",\s*\d+,\s*(\w+)\]", slots)
    assert entries and set(entries) == {"true"}, f"an emblem slot is still: {slots}"


def test_the_chat_welcome_keeps_its_emblem_when_short() -> None:
    """At 1280x720 the chat pane is 304px and the welcome 326px, so
    `fitChatEmpty` takes the short shape, which used to drop the emblem: the
    "missing" logo of the report. Short makes it smaller, never gone."""
    for path in CSS:
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
            if "chat-empty-emblem" in match.group(1):
                assert "display: none" not in match.group(2), (
                    f"{path.name} hides the chat welcome's emblem: {match.group(1).strip()}"
                )
