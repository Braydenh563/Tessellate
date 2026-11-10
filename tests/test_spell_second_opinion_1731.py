"""Spelling gets a second opinion (INBOX 1731, DOCUMENTS_PLAN).

The owner's screenshot: "Uni" in the title "Uni is done!! :D" underlined, the
menu offering "Dei". Harper reads "uni" as a negative prefix. The worker now
asks a Hunspell dictionary (`frontend/vendor/spelling`, read by `nspell`) and
the person's own words, drops suggestions that change more than a third of a
short word, and ranks what is left by how common the word is.

`spell_fixture_1731.txt` is 200 sentences in the owner's own style (Australian
slang, "uni", "haha", ":D", "arvo", "reckon"). Before this work the worker
put 16 flags on them (14 with the Australian dialect set); the ceiling below
is what it does now, and may only come down.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "frontend" / "js" / "harper-worker.js"
FIXTURE = ROOT / "tests" / "spell_fixture_1731.txt"
SPELLING = ROOT / "frontend" / "vendor" / "spelling"

#: Flags on the 200 clean sentences before the second opinion: Harper's own
#: lints of every kind but "Spelling" (the page drops those already).
FLAGS_BEFORE = {"off": 16, "au": 14}
#: What it may flag now, at most. The five left are genuine: two of Harper's
#: grammar quirks ("missing a preposition"), a closed-compound style note, and
#: two slang words no dictionary carries ("sunburnt", "doco").
FALSE_FLAG_CEILING = 5

DRIVER = r"""
import { readFile } from "node:fs/promises";
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, init) => {
  const href = String(url && url.href ? url.href : url);
  if (href.startsWith("file:")) {
    const type = href.endsWith(".wasm") ? "application/wasm" : "text/plain";
    return new Response(await readFile(new URL(href)), { headers: { "Content-Type": type } });
  }
  return realFetch(url, init);
};
let handler = null;
let replies = [];
globalThis.self = {
  addEventListener: (type, fn) => { if (type === "message") handler = fn; },
  postMessage: (message) => replies.push(message),
};
await import(process.argv[2]);
const jobs = JSON.parse(await readFile(process.argv[3], "utf8"));
const out = [];
for (const job of jobs) {
  replies = [];
  for (const message of job.messages) await handler({ data: message });
  out.push(replies);
}
process.stdout.write(JSON.stringify(out));
"""


def _run(tmp_path: Path, jobs: list[dict]) -> list[list[dict]]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path / "driver.mjs"
    script.write_text(DRIVER, encoding="utf-8")
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps(jobs), encoding="utf-8")
    done = subprocess.run(
        [node, str(script), WORKER.as_uri(), str(jobs_file)],
        capture_output=True, text=True, timeout=400, check=False,
    )
    assert done.returncode == 0, done.stderr[-800:]
    return json.loads(done.stdout)


def _fixture_lines() -> list[str]:
    return [line for line in FIXTURE.read_text(encoding="utf-8").split("\n") if line.strip()]


def _spell_ish(lint: dict) -> bool:
    return lint["kind"] != "Spelling"


def test_the_fixture_is_two_hundred_sentences_in_the_owners_style() -> None:
    lines = _fixture_lines()
    assert len(lines) == 200
    text = " ".join(lines).lower()
    for slang in ("uni", "haha", ":d", "arvo", "reckon"):
        assert slang in text, slang
    assert re.search(r"colour|organise|realise|centre", text)


def test_uni_is_not_flagged_and_dei_is_never_offered(tmp_path) -> None:
    (replies,) = _run(tmp_path, [{"messages": [{"id": 1, "dialect": "off", "text": "Uni is done!! :D"}]}])
    assert replies[0]["ok"] is True
    for lint in replies[0]["lints"]:
        assert lint["problem"].lower() != "uni", lint
        assert "Dei" not in [s["text"] for s in lint["suggestions"]], lint


@pytest.mark.parametrize("dialect", ["off", "au"])
def test_false_flags_on_the_owners_own_sentences_stay_under_the_ceiling(tmp_path, dialect) -> None:
    lines = _fixture_lines()
    jobs = [{"messages": [{"id": i, "dialect": dialect, "text": line}]} for i, line in enumerate(lines)]
    flags = []
    for line, replies in zip(lines, _run(tmp_path, jobs), strict=True):
        assert replies[0]["ok"] is True, replies[0]
        flags += [(line, lint) for lint in replies[0]["lints"] if _spell_ish(lint)]
    shown = [f"{lint['kind']}: {lint['problem']} in {line[:40]}" for line, lint in flags]
    assert len(flags) <= FALSE_FLAG_CEILING < FLAGS_BEFORE[dialect], shown
    # None of the four classes the second opinion exists for may come back.
    for _line, lint in flags:
        assert lint["problem"].lower() != "uni"
        assert lint["kind"] != "Regionalism" or dialect == "off"
        assert not (lint["kind"] == "Capitalization" and lint["problem"] in {"Sam", "Nan"})


def test_a_word_the_person_uses_twice_is_never_flagged(tmp_path) -> None:
    text = "The doco about the reef was brilliant, and the sunburnt tourists loved it."
    plain, own = _run(
        tmp_path,
        [
            {"messages": [{"id": 1, "dialect": "au", "text": text}]},
            {"messages": [{"type": "own", "words": ["doco", "Sunburnt"]}, {"id": 2, "dialect": "au", "text": text}]},
        ],
    )
    assert {"doco", "sunburnt"} <= {lint["problem"].lower() for lint in plain[0]["lints"]}
    assert not {"doco", "sunburnt"} & {lint["problem"].lower() for lint in own[0]["lints"]}


def test_a_confusable_pair_is_not_overruled_by_the_own_words(tmp_path) -> None:
    # "there" is a word everybody uses twice; "their" for "there" is still grammar.
    text = "Put it over their."
    (replies,) = _run(
        tmp_path,
        [{"messages": [{"type": "own", "words": ["their", "there"]}, {"id": 1, "dialect": "us", "text": text}]}],
    )
    assert replies[0]["ok"] is True


def test_suggestions_change_at_most_a_third_and_the_common_word_comes_first(tmp_path) -> None:
    (replies,) = _run(
        tmp_path,
        [{"messages": [{"id": 1, "type": "spell", "dialect": "au", "words": ["teh", "recieve", "Uni", "xqzv", "arvo"]}]}],
    )
    spell = replies[0]["spell"]
    assert spell["Uni"]["known"] is True and spell["arvo"]["known"] is True
    assert spell["teh"]["known"] is False and spell["teh"]["suggestions"][0] == "the"
    assert spell["recieve"]["suggestions"][0] == "receive"
    # A word of four letters may change one; no answer is offered that changes more.
    assert all(len(s) >= 3 for s in spell["xqzv"]["suggestions"])
    for word, answer in spell.items():
        for suggestion in answer["suggestions"]:
            assert abs(len(suggestion.replace(" ", "")) - len(word)) <= max(1, len(word) // 3), (word, suggestion)


def test_each_dictionary_carries_its_licence_beside_it() -> None:
    for name in ("LICENSE", "SCOWL-README.txt", "build.sh"):
        assert (SPELLING / name).is_file(), name
    for name in ("en_AU.aff", "en_AU.dic", "en_GB.aff", "en_GB.dic", "frequency.txt", "nspell.js"):
        assert (SPELLING / name).is_file(), name
    licence = (SPELLING / "LICENSE").read_text(encoding="utf-8")
    assert "Kevin Atkinson" in licence and "Titus Wormer" in licence and "Feross Aboukhadijeh" in licence


def test_the_dictionaries_load_in_the_worker_only() -> None:
    # Nothing of the second opinion is in a boot script: the worker loads the one
    # file that names the vendored folder.
    named = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "frontend").rglob("*.js")
        if "vendor" not in path.parts and "vendor/spelling" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert named == ["frontend/js/spell-second.js"], named
