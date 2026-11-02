"""Sweep 1028b W14: a count in words goes through `nounCount(n, one, many)`
(prefs.js), never a template literal that always pluralises. "1 more tags" was
on the note card's tag fold and "1 more notifications" in the bell; the same
shape sat in nine more places. The remaining unguarded literals are ones whose
guard is on the line above (a `n === 1 ? ... :` ternary spread over lines) or
whose verb agrees with a count above one; the count only goes down.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR

NOUNS = (
    "notes|tags|reminders|notifications|items|links|files|boards|documents|words|days|questions|chats|results|entries|cards|"
    "topics|pages|lines|characters|attachments|categories|people|places|sources|steps|hours|minutes|sentences|paragraphs|"
    "headings|images|folders|spaces|maps|backups|models|skills|tasks|answers|changes|versions|messages|devices"
)
COUNT = re.compile(r"\$\{[\w.\[\]()]*(?:length|count|size|total|rest|words|done|steps|days|minutes|stepCount|omitted_results|more)\} (?:more )?(?:" + NOUNS + r")\b")
GUARD = re.compile(r"[=!]==? 1\b|>\s*1\b|nounCount|toLocaleString|^\s*(?://|\*)")
CAP = 9


def _unguarded() -> list[str]:
    found = []
    for path in sorted(JS_DIR.glob("*.js")):
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if COUNT.search(line) and not GUARD.search(line):
                found.append(f"{path.name}:{number}")
    return found


def test_the_helper_pluralises():
    app = (JS_DIR / "prefs.js").read_text(encoding="utf-8")
    assert "function nounCount(n, one, many = `${one}s`)" in app
    assert 'n === 1 ? one : many' in app


def test_the_two_reported_places_use_it():
    cards = (JS_DIR / "note-cards.js").read_text(encoding="utf-8")
    assert 'nounCount(fold.length, "more tag", "more tags")' in cards
    status = (JS_DIR / "status.js").read_text(encoding="utf-8")
    assert 'nounCount(rest, "more notification", "more notifications")' in status


def test_unguarded_plural_literals_only_go_down():
    found = _unguarded()
    assert len(found) <= CAP, f"{len(found)} `${{n}} <noun>s` literals (cap {CAP}); use nounCount: {found}"
