"""avatars.js and atlas.js are a lazy bundle, not boot scripts (audit 1028 S3).

The faces, the companion and Atlas were 133 KB of the 572 KB gzipped the lock
screen waited for. They are `LAZY_MODULES.characters` now, fetched once the
app is open and idle (`loadCharactersIdle`, when the opening curtain lifts).
A boot file that names one of their functions runs before they exist, so each
such mention has to be one of three things (lazy-entries.js says which):

- a stand-in (`installCharacterStandIns`): nobody reads the return value;
- inside `afterCharacters(...)`: it draws a face once they are in;
- a guard, `typeof name === "function"` or `name?.()`: the cue is dropped.

This reads every boot script for a bare mention of a name the two files
declare and fails on one that is none of those, which is the ReferenceError a
boot file would otherwise throw while the page loads.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.api.asset_strip import strip_js

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
ENTRIES = (JS / "lazy-entries.js").read_text(encoding="utf-8")
APP = (JS / "app.js").read_text(encoding="utf-8")

CHARACTER_FILES = ("avatars.js", "atlas.js")
DECLARED = re.compile(r"^(?:async\s+)?(?:function\s*\*?\s*|(?:const|let|var)\s+)([A-Za-z_$][\w$]*)", re.M)


def _boot_scripts() -> list[str]:
    html = re.sub(r"<!--.*?-->", "", INDEX, flags=re.S)
    return re.findall(r'<script[^>]*\ssrc="/js/([\w.-]+\.js)', html)


def _character_names() -> set[str]:
    names: set[str] = set()
    for file in CHARACTER_FILES:
        names |= set(DECLARED.findall(strip_js((JS / file).read_text(encoding="utf-8"))))
    return names


def _stand_ins() -> set[str]:
    found: set[str] = set()
    for block in re.findall(r"installCharacterStandIns\(\s*(\[.*?\])", ENTRIES, flags=re.S):
        found |= set(re.findall(r'"([A-Za-z_$][\w$]*)"', block))
    return found


def test_the_characters_are_not_boot_scripts():
    boot = _boot_scripts()
    assert len(boot) > 20, "the boot scripts were not found: has index.html moved?"
    for file in CHARACTER_FILES:
        assert file not in boot, f"{file} is back in the boot scripts"
    assert 'characters: ["/js/avatars.js", "/js/atlas.js", "/js/characters-ready.js"]' in ENTRIES
    assert (JS / "characters-ready.js").read_text(encoding="utf-8").strip() == "charactersArrived();"


def test_the_desktop_companion_page_keeps_its_own_script_tags():
    page = (ROOT / "frontend" / "desktop-companion.html").read_text(encoding="utf-8")
    assert page.index("/js/avatars.js") < page.index("/js/atlas.js")


def test_nothing_preloaded_pulls_the_characters_in_before_the_app_opens():
    """The 3 s preload (app.js) and the `CHARACTER_DEPENDENTS` that list the files
    first must not meet, or the lock screen would pay for them after all."""
    preload = re.search(r"setTimeout\(\(\) => \[(.*?)\]\.forEach\(ensureModule\)", APP, flags=re.S).group(1)
    preloaded = set(re.findall(r'"(\w+)"', preload))
    dependents = set(re.findall(r'"(\w+)"', re.search(r"CHARACTER_DEPENDENTS = \[(.*?)\]", ENTRIES).group(1)))
    assert dependents and not (preloaded & dependents), preloaded & dependents


def _mentions(code: str, names: set[str]) -> list[tuple[int, str, str]]:
    pattern = re.compile(r"(?<![\w$.])(" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r")\b(?!\s*:)")
    lines = code.split("\n")
    out = []
    for number, line in enumerate(lines, 1):
        if DECLARED.match(line):
            continue
        for match in pattern.finditer(line):
            out.append((number, match.group(1), "\n".join(lines[max(0, number - 6) : number])))
    return out


#: Functions only `afterCharacters` reaches: what they draw with is in by then.
DRAWN_AFTER = {"paintNamedHead", "assistantAvatar", "paintDashFace"}


def _enclosing(code: str, number: int) -> str:
    found = re.findall(r"^(?:async\s+)?function\s*\*?\s*([\w$]+)", "\n".join(code.split("\n")[:number]), re.M)
    return found[-1] if found else ""


def test_every_boot_mention_of_a_character_function_waits_for_it():
    names = _character_names()
    stand_ins = _stand_ins()
    assert {"syncNameMarkBuddy", "atlasOn"} <= stand_ins, "the stand-in list was not read"
    loose = []
    for file in _boot_scripts():
        code = strip_js((JS / file).read_text(encoding="utf-8"))
        own = set(DECLARED.findall(code))
        for number, name, context in _mentions(code, names - own):
            line = context.split("\n")[-1]
            if name in stand_ins or f"typeof {name}" in line or f"{name}?." in line:
                continue
            guarded = re.search(r'typeof [\w$]+ === "function"', context)
            if "afterCharacters(" in context or guarded or _enclosing(code, number) in DRAWN_AFTER:
                continue
            loose.append(f"{file}:{number} {name}")
    assert not loose, "a boot file names a character function that is not there yet: " + ", ".join(loose)
