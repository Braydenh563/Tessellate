"""Scanners that were quadratic on a crafted line (the final scan,
2026-10-06, `py/polynomial-redos` shapes): a note's first line
(`manager.plain_label`), the model's reply (`answer_trim.strip_prompt_metadata`) and a question's title
(`questions._title`).

Each timing test pumps about 20 KB of one crafted shape and asserts a budget
far under what the old pattern took (measured before each rewrite, numbers in
the CHANGELOG). Each rewrite must also give the old pattern's answer, so the
old patterns are kept here as oracles and compared on the crafted shapes and
on random strings drawn from the markup's own alphabet.
"""

from __future__ import annotations

import random
import re
import time

import pytest

N = 20_000
BUDGET = 0.2  # seconds; the quadratic forms took 0.3 to 15 s


def _timed(fn):
    started = time.perf_counter()
    fn()
    return time.perf_counter() - started


def _random_strings(alphabet: list[str], count: int = 400, length: int = 40):
    rng = random.Random(1006)
    for _ in range(count):
        yield "".join(rng.choice(alphabet) for _ in range(rng.randint(0, length)))


# --- entry/manager.py: plain_label -------------------------------------------

_LABEL_PUMPS = {
    "image-openers": "![" * (N // 2),
    "image-no-close": "![a" * (N // 3),
    "link-openers": "[" * N,
    "link-text": "[a" * (N // 2),
    "link-no-paren-close": "[a](" * (N // 4),
    "image-no-paren-close": "![a](" * (N // 5),
}


@pytest.mark.parametrize("text", _LABEL_PUMPS.values(), ids=_LABEL_PUMPS.keys())
def test_plain_label_is_linear_on_unclosed_markup(text):
    from tessellate.entry.manager import plain_label

    assert _timed(lambda: plain_label(text, 80)) < BUDGET


def _old_label_links(first: str) -> str:
    first = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", first)
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", first)


def test_label_links_match_the_old_patterns():
    from tessellate.entry.manager import _md_links

    def _label_links(text):
        return _md_links(_md_links(text, True), False)

    alphabet = list("ab [](!)\n") + ["![", "](", "[["]
    for text in list(_random_strings(alphabet)) + [
        "a [b](u) c",
        "[a [b](u)",
        "![alt](x) and [t](y)",
        "[](x)",
        "![](x)[]()",
        "[a](b",
        "[a]( b c )d",
    ]:
        assert _label_links(text) == _old_label_links(text), text


# --- ai/answer_trim.py: strip_prompt_metadata --------------------------------

_METADATA_PUMPS = {
    "spaces-then-letter": " " * N + "x",
    "spaces-then-open": " " * N + "(similarity",
    "spaces-then-id": " " * N + "(id 1",
    "comma-then-spaces": "," + " " * N,
    "similarity-then-spaces": "similarity" + " " * N,
    "newlines": "\n" * N + "x",
    "tabs-between-words": "a" + "\t" * N + "b",
}


@pytest.mark.parametrize("text", _METADATA_PUMPS.values(), ids=_METADATA_PUMPS.keys())
def test_strip_prompt_metadata_is_linear_on_whitespace_runs(text):
    from tessellate.ai.answer_trim import strip_prompt_metadata

    assert _timed(lambda: strip_prompt_metadata(text)) < BUDGET


def test_strip_prompt_metadata_matches_the_old_patterns():
    from tessellate.ai.answer_trim import strip_prompt_metadata

    old = (
        (re.compile(r"\((?:note\s+)?id[:\s#]*\d+\)\s*\[[^\]\n]{1,40}\]\s*", re.I), ""),
        (re.compile(r"\s*\((?:note\s+)?id[:\s#]*\d+\)", re.I), ""),
        (re.compile(r"\s*\((?:similarity|score)[:\s]*[01]?\.\d+\)", re.I), ""),
        (re.compile(r"\s*\(matched:[^()\n]{1,80}\)", re.I), ""),
        (re.compile(r",?\s*(?:with\s+)?(?:a\s+)?similarity(?:\s+score)?(?:\s+of|:)?\s*[01]?\.\d+,?", re.I), ""),
        (re.compile(r"\bnote id\s*#?\d+\b", re.I), "the note"),
    )

    def reference(text: str) -> str:
        for pattern, replacement in old:
            text = pattern.sub(replacement, text)
        return text

    alphabet = [
        " ", "  ", "\n", "\t", ",", ", ", "(", ")", "[", "]", "Work", "id", "note ", "note id ", "similarity", "score", "of", "with ", "a ",
        "0.54", ".5", "1", "0", ".", ":", "#", "matched:", "x", "(id 3)", "(note id 3) [Work]", "(similarity: 0.5)", "(matched: a, b)",
    ]
    cases = list(_random_strings(alphabet, count=3000, length=14)) + [
        "",
        "your dentist note (note id 3) said so",
        "1. (id 4) [Work] the roof",
        "a similarity of 0.54, so",
        "a , with a similarity score of 0.5 , b",
        "x  (similarity: 0.5)  y (score 0.25)",
        "the similarity between the plans",
        "see (id badge in the drawer) and (matched: roof, quote)",
        "note id #7 and Note ID 8",
        " , similarity 0.5",
        "x ,similarity: .5, y",
    ]
    for text in cases:
        assert strip_prompt_metadata(text) == reference(text), repr(text)


# --- ai/questions.py: _title -------------------------------------------------
#
# The old `re.match(r"(.+?[.!?])(?:\s|$)", first)` was anchored, so it was
# linear when measured (20,000 to 200,000 characters of every pump below, a
# few milliseconds, ten times the input for ten times the time), and CodeQL's
# `py/polynomial-redos` read it as quadratic anyway. So this one has no
# "failed before" number: the timing test pins the property, and the
# equivalence test pins the answers of the loop that replaced it.

_TITLE_PUMPS = {
    "dots": "a." * (N * 5),
    "spaces": " " * (N * 5) + ".",
    "terminators": "!?." * (N * 3),
    "one-long-word": "x" * (N * 5),
    "hashes": "# " * (N * 5),
}


@pytest.mark.parametrize("text", _TITLE_PUMPS.values(), ids=_TITLE_PUMPS.keys())
def test_question_title_is_linear_on_a_long_first_line(text):
    from tessellate.ai.questions import _title

    assert _timed(lambda: _title(text)) < BUDGET


def test_question_title_matches_the_old_pattern():
    from tessellate.ai.questions import _plain, _title

    def reference(content: str) -> str:
        #: The title is read as a row shows it (`_plain`: no list marker, no
        #: `**` or `__`, INBOX 745 b), so the pin reads the same: it moved with
        #: the code, and the alphabet below now holds the marks it strips.
        first = _plain((content or "").strip().split("\n", 1)[0].strip().lstrip("#").strip())
        sentence = re.match(r"(.+?[.!?])(?:\s|$)", first)
        if sentence and len(sentence.group(1)) <= 60:
            return sentence.group(1)
        return first if len(first) <= 60 else first[:59].rstrip() + "…"

    alphabet = ["a", "b", " ", ".", "!", "?", "...", ". ", "\n", "\t", " ", "#", "1.5", "e.g.", "x" * 20, "**", "__", "- ", "* ", "1. ", "2) "]
    cases = list(_random_strings(alphabet, count=4000, length=14)) + [
        "",
        "Plans for the shed. Then the roof.",
        "A question? Another.",
        "x" * 59 + ". more",
        "x" * 58 + ". more",
        "x" * 60 + ".",
        "x" * 61 + ". more",
        ". leading dot",
        "v1.5 is out",
        "Done!",
        "# Heading. rest",
        "word." + " " + "rest",
    ]
    for content in cases:
        assert _title(content) == reference(content), repr(content)
