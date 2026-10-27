"""The composer's heading and picture-line readers stay linear on long runs of
whitespace (CodeQL: polynomial regular expression on note text), and read the
same lines as before."""

from __future__ import annotations

import time

from tessellate.ai import composer

RUN = "\t" * 40_000


def _fast(call) -> None:
    started = time.perf_counter()
    call()
    assert time.perf_counter() - started < 1.0


def test_whitespace_runs_stay_linear():
    _fast(lambda: composer._heading_text("#" + RUN + "\xa0" * 40_000 + "\nx"))
    _fast(lambda: composer._picture_text_breaks("a" + RUN + "b" + RUN))
    _fast(lambda: composer._picture_groups("-" + RUN + "x:" + RUN + "shows" + RUN))
    _fast(lambda: composer._title("# " + RUN + "x\nbody"))


def test_headings_read_as_before():
    assert composer._heading_text("## Trip plan\n") == "Trip plan"
    assert composer._heading_text("# ") == ""
    assert composer._heading_text("#hashtag") is None
    assert composer._title("# Trip plan\nbody") == ("Trip plan", 11)


def test_picture_line_groups():
    line = '- cat.png: shows a cat on a mat; text in it: "Hello there / 1. Feed 2. Brush"]'
    groups = composer._picture_groups(line)
    caption, at = groups["caption"]
    assert caption == "a cat on a mat" and line[at:].startswith("a cat")
    text, at = groups["text"]
    assert text == "Hello there / 1. Feed 2. Brush" and line[at:].startswith("Hello")
    assert composer._picture_groups("- cat.png: something else") is None
    assert composer._picture_groups("plain words: shows a cat") is None


def test_picture_text_breaks_split_lines_and_numbered_runs():
    text = "Hello there / 1. Feed the cat 2. Brush"
    spans = composer._picture_spans("text", text)
    assert [piece for _, piece in spans] == ["Hello there", "Feed the cat", "Brush"]
    assert all(text[at:].startswith(piece) for at, piece in spans)
