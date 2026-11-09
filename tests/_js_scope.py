"""What a frontend script puts in the one shared scope (ranked row 37a).

A classic script's top-level `function`, `let`, `var`, `const` and `class`
are globals every other script can call or overwrite. A script wrapped whole
in one closure (`(() => {` on its first code line, `})();` on its last) keeps
its names to itself and puts on `window` only what its foot lists:

    Object.assign(window, { renderEmbedChoices });

Not named `test_*.py` on purpose, as `_app_js.py` and `_repo_files.py`.
"""

from __future__ import annotations

import re

from tessellate.api.asset_strip import strip_js_comments

_OPEN = re.compile(r"^\(\(\) => \{$")
_CLOSE = re.compile(r"^\}\)\(\);$")
_EXPORT = re.compile(r"^  Object\.assign\(window, \{ ([\w$, ]+) \}\);$", re.M)
_WINDOW_SET = re.compile(r"^  window\.([A-Za-z_$][\w$]*) =", re.M)
_TOP_LEVEL = re.compile(
    r"^(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)|^(?:let|var|const|class)\s+([A-Za-z_$][\w$]*)", re.M
)


def is_wrapped(source: str) -> bool:
    """The whole script is one closure: nothing but comments before its opening
    line, nothing after its closing one."""
    lines = [line for line in strip_js_comments(source).split("\n") if line.strip()]
    return bool(lines) and bool(_OPEN.match(lines[0])) and bool(_CLOSE.match(lines[-1]))


def listed(source: str) -> set[str]:
    """The names a wrapped script's `Object.assign(window, {...})` foot lists."""
    if not is_wrapped(source):
        return set()
    return {n.strip() for match in _EXPORT.findall(source) for n in match.split(",")} - {""}


def exported(source: str) -> set[str]:
    """Every name a wrapped script puts on `window`: its listed foot, and a
    namespace object set whole (`window.SketchPad = {...}`)."""
    if not is_wrapped(source):
        return set()
    return listed(source) | set(_WINDOW_SET.findall(source))


def global_names(source: str) -> set[str]:
    """What the script adds to the shared scope: a wrapped script's exports,
    any other script's top-level declarations."""
    if is_wrapped(source):
        return exported(source)
    return {a or b for a, b in _TOP_LEVEL.findall(strip_js_comments(source))}


def unwrapped(source: str) -> str:
    """A wrapped script's text as it was before it was wrapped: the closure
    lines off and the two-space indent taken back, so a test that slices a
    function by its head and `\n}\n` tail, or runs it in a vm and calls a
    private name, checks the same code. Any other script is returned as it is.
    Only the wrapper changed, so nothing a test asserts is weaker; the closure
    itself is covered by the ratchet. The foot's `Object.assign(window, ...)`
    goes too: unwrapped, every name is a global already.
    A multi-line template literal's continuation lines would lose two spaces
    too; the files read this way have none."""
    if not is_wrapped(source):
        return source
    lines = source.split("\n")
    first = next(i for i, line in enumerate(lines) if _OPEN.match(line))
    last = max(i for i, line in enumerate(lines) if _CLOSE.match(line))
    body = [line[2:] if line.startswith("  ") else line for line in lines[first + 1 : last]]
    body = [line for line in body if not re.match(r"Object\.assign\(window, \{ [\w$, ]+ \}\);$", line)]
    return "\n".join([*lines[:first], *body, *lines[last + 1 :]])
