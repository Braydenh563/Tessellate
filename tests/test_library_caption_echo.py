"""Row 15, dog3-1026: a sketch note is "caption, blank line, ![caption](url)".
Its Library title and preview read "Sketch 26 Oct · Sketch 26 Oct" because the
image's alt text repeats the caption."""

from __future__ import annotations

from tessellate.api.routes_library import _clip


def test_an_image_that_only_repeats_the_caption_adds_nothing():
    assert _clip("Sketch 26 Oct\n\n![Sketch 26 Oct](/media/a.png)") == "Sketch 26 Oct"


def test_a_different_alt_text_is_still_read():
    assert _clip("Diagram\n\n![water cycle](/media/a.png)") == "Diagram · water cycle"


def test_an_image_only_note_still_reads_as_its_alt():
    assert _clip("![sketch](/media/a.png)") == "sketch"
