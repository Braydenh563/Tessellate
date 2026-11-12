"""A sentence quoted without its neighbour says what its "it" was (R9-6, composer audit round 9).

"We discussed Klara and the Sun. Hannah loved it, Raj didn't." quoted as the second sentence alone has lost what
Hannah loved; the sentence before it names the thing, so it is said back in place of "it"."""

from __future__ import annotations

import re

_THING = re.compile(r"^(?:we|i) (?:discussed|read|watched|saw|finished|started|tried|visited|listened to) (?P<thing>[^.!?,;]{1,60})[.!?]?$", re.I)
_IT = re.compile(r"(?<=[a-z] )it\b")


def resolved(view, sentence) -> str:  # noqa: ANN001
    """The text of `sentence` with a mid-sentence "it" replaced by the thing the sentence before it in the note
    names; the text as written when there is none."""
    text = sentence.text.strip()
    before = [s for s in view.sentences if s.end <= sentence.start]
    found = _THING.match(before[-1].text.strip()) if before else None
    if not found or not _IT.search(text):
        return text
    return _IT.sub(found["thing"].strip(), text, count=1)
