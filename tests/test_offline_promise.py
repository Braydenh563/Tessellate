"""The privacy promise is the product, so it is held to the code.

This app's whole claim is that it runs on your machine and nothing goes out.
That claim is made to the person in several places, and it is enforced in
exactly one: whether a preference is on. Nothing kept the two in step, and on
2026-09-21 they had come apart.

**What was measured.** Three places told the person that web search is "the
ONE feature that goes online": `routes_settings.py`, `routes_websearch.py`'s
own 403, and the Tools and features row in `dashboard.js`. Two lines below the
first of them sat `update_check_enabled`, commented "The other opt-in network
call", and `routes_update.py` does `requests.get` against `api.github.com`.
Settings, About also said "Nothing ever leaves this computer", unqualified, in
the same panel that offers both switches.

Nothing was leaking: `llm_provider` defaults to `ollama`, the
OpenAI-compatible client defaults to `http://localhost:1234/v1`, and both
network features default to `False`, so a fresh install really does make no
outbound request. The behaviour was right and the sentence describing it was
wrong, which for a privacy-first app is its own kind of bug: the reader who
cares enough to check is the reader who stops trusting the rest.

So this test counts the opt-in network features in the code and fails when the
copy no longer matches. Add a third and it goes red until somebody has
rewritten the sentences and thought about whether the promise still holds.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import app_js_files

ROOT = Path(__file__).resolve().parents[1]

#: Every preference that gates an outbound request, with where the request is
#: made. A feature that reaches the network and is NOT here is the thing this
#: file exists to catch, so adding a row is a deliberate act, not a formality.
NETWORK_FEATURES = {
    "web_search_enabled": "src/tessellate/search/websearch.py",
    "update_check_enabled": "src/tessellate/api/routes_update.py",
}

#: The AI provider is deliberately not in that set and the distinction is the
#: whole point. `llm_provider` defaults to `ollama` and the OpenAI-compatible
#: client to `http://localhost:1234/v1`, both on this machine; a person may
#: point either at a remote address, and then their prompts go there. That is
#: a destination they typed, not a feature the app switched on, so it is named
#: in the copy rather than counted here.
PROVIDER_DEFAULTS = {
    "llm_provider": "ollama",
    "base_url": "http://localhost:1234/v1",
}

#: Copy that used to claim there was only one way out.
BANNED = (
    re.compile(r"the (ONE|one|only) feature that goes online"),
    re.compile(r"[Nn]othing (ever )?leaves this (computer|machine)\."),
)

#: **The rule is not "never say it", it is "never say it flatly."** Several of
#: these sentences are about one feature and are true of it: the meeting
#: transcript never leaves the machine, an answer is assembled from your own
#: notes. Banning the words outright would have deleted four true sentences to
#: fix two false ones, and the true ones are what a cautious reader is looking
#: for. So a claim passes when the same line or the one on either side says
#: what it is scoped to, or what it depends on.
QUALIFIERS = re.compile(
    r"out of the box|unless you|until you|opt.?in|your audio|from your own notes|"
    r"two features|web search|update check|model on this machine",
    # "with a model on this machine" is the qualifier that matters most and
    # is the easiest to leave off. The Ask panel said "nothing leaves this
    # machine" flatly, on the one surface where a person types the thing
    # they would least like to send anywhere, and whether that is true
    # depends on where they pointed the provider.
    re.I,
)

COPY = [
    *app_js_files(),
    ROOT / "frontend" / "js" / "dashboard.js",
    ROOT / "frontend" / "index.html",
    ROOT / "src" / "tessellate" / "api" / "routes_websearch.py",
    ROOT / "src" / "tessellate" / "api" / "routes_settings.py",
    ROOT / "src" / "tessellate" / "api" / "routes_settings_transfer.py",
    ROOT / "src" / "tessellate" / "api" / "routes_settings_extras.py",
    ROOT / "src" / "tessellate" / "api" / "routes_settings_logs.py",
    #: The two a person reads *before* installing, which is when the promise
    #: does most of its work. `PRIVACY.md` is the worse place to be wrong: its
    #: own heading says it exists to be precise "since it's the whole promise",
    #: and it carried an explicitly exhaustive table that said "Three things do
    #: touch the network" and listed three, with the update check missing.
    ROOT / "README.md",
    ROOT / "docs" / "PRIVACY.md",
]


def test_every_network_feature_is_off_by_default():
    """The promise holds on a fresh install or it is not a promise."""
    config = (ROOT / "src" / "tessellate" / "core" / "config.py").read_text(encoding="utf-8")
    for preference in NETWORK_FEATURES:
        match = re.search(rf'"{preference}":\s*(\w+)', config)
        assert match, f"{preference} has no default in core/config.py"
        assert match.group(1) == "False", (
            f"{preference} defaults to {match.group(1)}, so a fresh install would "
            "make an outbound request nobody asked for"
        )


def test_the_ai_provider_points_at_this_machine_by_default():
    """A remote provider is a destination the person typed, never a default."""
    config = (ROOT / "src" / "tessellate" / "core" / "config.py").read_text(encoding="utf-8")
    assert re.search(r'"llm_provider":\s*"ollama"', config), (
        "the default provider must be the one that runs on this machine"
    )
    client = (ROOT / "src" / "tessellate" / "ai" / "openai_client.py").read_text(encoding="utf-8")
    assert 'base_url: str = "http://localhost:1234/v1"' in client, (
        "the OpenAI-compatible client must default to a local address; a remote "
        "default would send notes off the machine with no one having chosen it"
    )


def test_no_copy_claims_there_is_only_one_way_out():
    """The sentences and the count agree, or this goes red.

    Written as a ban on the old wording rather than a check of the new: there
    are many true ways to say it and only a few false ones, and the false ones
    are what came back last time.
    """
    offenders = []
    for path in COPY:
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            #: The comment that records the fault is allowed to quote it.
            if "//:" in line or line.lstrip().startswith("#"):
                continue
            window = " ".join(lines[max(0, number - 2):number + 1])
            for pattern in BANNED:
                if pattern.search(line) and not QUALIFIERS.search(window):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()[:90]}")
    assert not offenders, (
        "copy claims one way out, or claims none at all, while "
        f"{len(NETWORK_FEATURES)} opt-in network features exist "
        f"({', '.join(sorted(NETWORK_FEATURES))}):\n" + "\n".join(offenders)
    )


def test_the_privacy_page_counts_the_same_network_features():
    """`PRIVACY.md` enumerates what goes out. An enumeration can be wrong in a
    way prose cannot: it says how many, and then lists them.

    It said three (a model pull, the embedding download, web search) and left
    out the update check, under a heading promising precision. This checks the
    number in the sentence against the rows in the table under it, so the two
    cannot come apart again.
    """
    page = (ROOT / "docs" / "PRIVACY.md").read_text(encoding="utf-8")
    said = re.search(r"(\w+) things do touch the network", page)
    assert said, "PRIVACY.md no longer says how many things touch the network"
    words = {"Two": 2, "Three": 3, "Four": 4, "Five": 5, "two": 2, "three": 3, "four": 4, "five": 5}
    claimed = words.get(said.group(1))
    assert claimed, f"unreadable count in PRIVACY.md: {said.group(1)!r}"
    table = re.search(r"\| What \| When \| What goes out \|\n\|[^\n]*\|\n((?:\|[^\n]*\|\n)+)", page)
    assert table, "the network table in PRIVACY.md has moved or changed shape"
    rows = [r for r in table.group(1).strip().splitlines() if r.strip().startswith("|")]
    assert claimed == len(rows), (
        f"PRIVACY.md says {claimed} things touch the network and its table lists "
        f"{len(rows)}. An exhaustive list that is not exhaustive is worse than no "
        "list: it invites the reader to stop looking."
    )
    #: Both opt-in features must appear by name, whatever the count says.
    assert "Web search" in table.group(1), "web search is missing from the network table"
    assert "update check" in table.group(1).lower(), (
        "the update check reaches api.github.com and must be in the table"
    )


def test_the_documented_count_matches_the_code():
    """If a third network feature is added, the copy has to be revisited.

    The count lives in one place and the sentences quote it in words, so this
    is the line that makes somebody stop and think rather than adding a switch
    and moving on.
    """
    assert len(NETWORK_FEATURES) == 2, (
        "NETWORK_FEATURES changed. Every user-facing sentence that says 'two "
        "features can go online' now says the wrong number: Settings About, the "
        "storage line, the web search 403 and the Tools and features row. Update "
        "them in the same commit, then update this count."
    )
    for preference, where in NETWORK_FEATURES.items():
        source = (ROOT / where).read_text(encoding="utf-8")
        assert "requests." in source or "urlopen" in source, (
            f"{where} is listed as {preference}'s outbound call but makes none"
        )
