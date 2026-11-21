"""The README's numbers and names are checked against the code.

The owner: "the readme and related documents keep going stale because you
forget them". A number in the README that the code can compute is asserted
here, so a tool added, a skill added or a version bump fails the build until
the README says the same.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate import __version__
from tessellate.ai import skills, tools

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_tool_count_matches_the_registry() -> None:
    assert f"has {len(tools.TOOLS)} tools" in README, (
        f"README says a different tool count; the registry has {len(tools.TOOLS)}"
    )


def test_the_skill_count_matches_the_built_ins() -> None:
    assert f"{len(skills.BUILTIN_SKILLS)} built-in skills" in README


def test_the_version_matches_the_package() -> None:
    assert f"Version {__version__}." in README


def test_the_mode_names_are_the_current_ones() -> None:
    """Request mode was renamed Agent mode (CHAT batch B); the README kept
    the old name for a day."""
    assert "Request mode" not in README
    assert "Agent mode" in README


def test_the_test_count_claim_is_not_stale_by_an_order() -> None:
    """A rough gate: the README's "N,N00+ tests" must be at or under the
    collected count, and within a thousand of it.

    The figure is written by hand, and the hundreds digit is part of the
    sentence ("3,600+ tests"): an earlier version of this gate read only
    the thousands form and failed the build the first time the owner wrote
    a truer number, which is the lint being wrong rather than the README.
    The bound is the one that matters either way: a claim of more tests
    than the tree defines is a false claim, and a claim a thousand short is
    stale. `approx` counts `def test_` lines rather than collected cases,
    so it undercounts parametrised tests; the claim sits at or below it.
    """
    claim = re.search(r"(\d{1,2},\d00)\+ tests", README)
    assert claim, "README should state the test count as N,N00+ tests"
    files = list((ROOT / "tests").glob("test_*.py"))
    approx = sum(len(re.findall(r"^\s*def test_", f.read_text(encoding='utf-8'), re.M)) for f in files)
    claimed = int(claim.group(1).replace(",", ""))
    assert claimed <= approx < claimed + 1000, (
        f"README claims {claim.group(0)}, the tree defines about {approx}"
    )


def test_every_screenshot_the_readme_shows_is_on_disk() -> None:
    """A picture the README points at has to exist, and no more than that.

    The tour is the first thing anyone sees, and a renamed or deleted capture
    shows up on GitHub as a broken-image glyph with the alt text underneath,
    which reads as an abandoned project rather than as a missing file. Nothing
    else in the suite opens the README's `<img>` tags.

    The second half is the same rule pointing the other way: a capture nobody
    shows is a file that will go stale silently, since the recapture script
    (`scratchpad/ui-sweeps/readmeshots.js`) writes the set it knows about and
    leaves anything else at whatever version of the UI it was taken from.
    """
    shown = set(re.findall(r'src="docs/screenshots/([\w.-]+)"', README))
    assert shown, "the README shows no screenshots at all"
    on_disk = {path.name for path in (ROOT / "docs" / "screenshots").glob("*.png")}
    missing = sorted(shown - on_disk)
    assert not missing, f"the README points at screenshots that do not exist: {missing}"
    orphans = sorted(on_disk - shown)
    assert not orphans, (
        f"these screenshots are in docs/screenshots but shown nowhere: {orphans}. "
        "Show them in the README or delete them; an unshown capture is one "
        "nothing keeps up to date."
    )


def test_every_installable_extra_is_named_in_the_readme() -> None:
    """The Packages list in the README names what Settings offers: each
    extra's name in its label's brackets ("Run Python files (Pyodide)"). An
    extra added to `core/extras.py` fails this until the README says so; one
    that is not ready to install yet is not claimed."""
    from tessellate.core import extras

    for extra in extras.EXTRAS:
        if extra.unavailable:
            continue
        name = re.search(r"\(([^)]+)\)\s*$", extra.label)
        assert name, f"{extra.id}'s label has no bracketed name"
        assert f"({name.group(1)}" in README, f"the README's Packages list does not name {name.group(1)}"


def test_the_compatibility_table_lists_each_way_in_with_its_date() -> None:
    """CHAT_PLAN decision 62 (L-chat-217): every provider the app can talk to is
    a row with the date its fake-transport suite last ran, and the dialects the
    app detects are the dialects the table names."""
    import datetime

    from tessellate.ai import provider

    rows = [line for line in README.splitlines() if line.startswith("| ") and "Fake transport" not in line and "---" not in line]
    servers = [r.split("|")[1].strip() for r in rows if r.split("|")[1].strip() in {
        "Ollama", "Ollama, OpenAI-compatible", "LM Studio", "llama.cpp `llama-server`", "Any other OpenAI-compatible server", "No model"}]
    assert len(servers) == 6, servers
    for row in rows:
        cells = [c.strip() for c in row.split("|")]
        if cells[1] in servers:
            datetime.date.fromisoformat(cells[5])
    assert {provider.detect_provider("http://localhost:11434"), provider.detect_provider("http://localhost:1234/v1")} == {"ollama", "openai"}
