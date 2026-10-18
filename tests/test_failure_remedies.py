"""INBOX 272 part 1: "every failure names its way out."

The owner's words: make sure every failure and alternative is easily
noticeable and offered, not filed away in a different screen. Two named
examples, both already built (embedding model failure suggests
`nomic-embed-text`; DuckDuckGo rate-limiting tries SearXNG and suggests
installing it), plus every other point the 2026-09-21 survey found
(`docs/roadmap/WORLD_CLASS_PLAN.md` section 21).

This is a class of bug, and a class needs a registry, not a list of asserts
that each know one string. Two registries hold it:

- `tessellate.core.extras.EXTRAS`: every optional *package* the app can
  install for you, one allowlisted entry each (built before this session,
  reused rather than duplicated).
- `REMEDIES` below: every other failure with a known fix that is not "pip
  install something", switch a setting, pick a different model, wait and
  retry. Each entry names the file the failure is raised or reported in and
  a phrase that MUST appear in the message shown to the person; the phrase
  is the remedy, not the diagnosis, on purpose (CLAUDE.md's own reading of
  this report: "not prose telling the person to go somewhere else", a
  phrase like "Settings, Models" or "nomic-embed-text" is a place or a
  thing to click, not a shrug).

A failure this file does not know about is exactly what the next survey
should add a row for; this file's job is to keep the rows it already has
from rotting silently, the same shape as `test_offline_promise.py`'s count.
"""

from __future__ import annotations

from pathlib import Path

from tessellate.core.extras import EXTRAS

ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


#: (file, a short label for the failure, phrase(s) the message must contain).
#: One row per failure class the survey found with a *known* remedy; a class
#: with no remedy (a real hard dependency, e.g. no Python interpreter at all)
#: is not here on purpose; see WORLD_CLASS_PLAN.md section 21's table for why.
REMEDIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "src/tessellate/ai/ollama_client.py",
        "embedding model is a chat model, not an embedding model",
        ("nomic-embed-text",),
    ),
    (
        "src/tessellate/ai/ollama_client.py",
        "embedding model is selected but not downloaded",
        ("Settings, Models", "nomic-embed-text"),
    ),
    (
        "src/tessellate/search/websearch.py",
        "DuckDuckGo is rate-limiting and no SearXNG was found",
        ("SearXNG", "Settings, Web search"),
    ),
    (
        "src/tessellate/core/docview.py",
        "a PDF has no text layer and pypdfium2 is not installed",
        ("Settings", "Packages"),
    ),
    (
        "src/tessellate/ai/provider.py",
        "the active model can't call tools (INBOX 272 part 1's own fix)",
        ("Settings, Models",),
    ),
)


def test_every_named_remedy_still_names_its_fix():
    for path, label, phrases in REMEDIES:
        text = _read(path)
        for phrase in phrases:
            assert phrase in text, (
                f"{path} no longer offers the remedy for {label!r}: "
                f"{phrase!r} is gone. A failure whose message loses its "
                "fix is the exact regression INBOX 272 part 1 was filed "
                "against; put the phrase back, or if the remedy genuinely "
                "changed, update this row to match it."
            )


def test_requirements_txt_lists_every_extras_package():
    """`core/extras.py` is the live allowlist of what Settings -> Extras can
    install; `requirements.txt`'s "Optional extras" comment is the same list
    for a source install. The survey (WORLD_CLASS_PLAN.md section 21) found
    these had already drifted apart: four of eight extras were missing from
    the comment block. Nothing enforced the two staying in step, so nothing
    would have caught the next package added to one and not the other.
    """
    requirements = _read("requirements.txt")
    missing = [
        extra.label
        for extra in EXTRAS
        # `unavailable` extras (today: llama-cpp-python) are deliberately
        # not offered here: `core/extras.py`'s own docstring for that field
        # says installing one buys nothing yet, and telling a source-install
        # reader to `pip install` it would be the "offering what the app
        # cannot do" shape INBOX 272 part 1 explicitly rules out.
        if not extra.unavailable
        #: A download extra (Pyodide, needle) is a pinned file, not a pip
        #: package, so it has no `pip install` line to drift from.
        and getattr(extra, "kind", "pip") == "pip"
        for package in extra.packages
        # Case-sensitive: pip package names in the comment are written
        # exactly as `pip install` would take them, same as `extra.packages`.
        if package not in requirements
    ]
    assert not missing, (
        "requirements.txt's \"Optional extras\" comment is missing "
        f"{missing}: every package core/extras.py can install for someone "
        "from inside the app should also be named for someone installing "
        "from source, or the two guides disagree about what exists."
    )


def test_extras_registry_entries_are_actionable_or_say_why_not():
    """Every entry either installs into a real feature (has no `unavailable`
    reason) or names, in plain words, why it cannot be installed yet and
    what to do instead: never a bare disabled button with no explanation
    (the shape `core/extras.py`'s own docstring calls out as the thing this
    file must not become)."""
    for extra in EXTRAS:
        assert extra.enables, f"{extra.id} has no 'enables' sentence"
        assert extra.size, f"{extra.id} has no size, INBOX 272 part 1: 'a remedy that costs a download says so before it starts'"
        if extra.unavailable:
            # A reason with no alternative is a dead end dressed as an
            # explanation; the case this app actually has (llama-cpp-python)
            # names the working alternative (llama-server) in the same
            # sentence, and this keeps a future entry to the same standard.
            assert len(extra.unavailable) > 20


def test_ollama_client_forwards_a_message_not_a_bare_event():
    """`ai/agent.py`'s `except ToolsUnsupportedError` used to yield a bare
    `{"type": "unsupported"}`, and `routes_chat.py` silently dropped it
    (`pass`, no `yield`): Agent mode was requested and downgraded to plain
    Q&A with nothing on screen to say so. Both are now required to carry a
    real message; a regression here is invisible to a browser test because
    nothing renders *wrong*, it renders *nothing*, which is exactly how this
    one survived until the 2026-09-21 survey.
    """
    agent_src = _read("src/tessellate/ai/agent.py")
    assert '"message": tools_unsupported_message(agent_model, getattr(exc, "declared", True))' in agent_src
    routes_src = _read("src/tessellate/api/routes_chat.py")
    # The branch that used to be `pass` must now hand the enriched event back
    # (`_choose_events`) and the stream must yield it before the plain answer.
    assert "return events, first" in routes_src
    assert "yield _event(notice)" in routes_src
