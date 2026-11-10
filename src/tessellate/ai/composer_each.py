"""A property asked of each of a kind of note ("what is the budget for each project", bt-compcomp-1109 item 5):
one line per note whose title names the kind, each the sentence that holds the property. Word steps on the
question's words, no pattern run over its text, so a long question costs nothing."""

from __future__ import annotations

from tessellate.ai import composer, composer_lists

_EACH = frozenset({"each", "every"})
_LEAD = ("what is the", "what are the", "what was the", "whats the", "what's the", "list the", "show the", "show me the", "give me the")
_JOIN = frozenset({"for", "of", "on", "in"})


def _asked(asked: str) -> tuple[str, str] | None:
    """`(property, kind)` for "what is the budget for each project", else None."""
    words = " ".join(str(asked or "")[:300].split()).rstrip("?.! ").lower().split(" ")
    for lead in _LEAD:
        n = len(lead.split(" "))
        if words[:n] == lead.split(" ") and len(words) == n + 4 and words[n + 1] in _JOIN and words[n + 2] in _EACH:
            return words[n], words[n + 3]
    return None


def answer(out, asked: str, views: list) -> bool:  # noqa: ANN001
    """One line per note titled for the kind, with the sentence that holds the property; False when fewer than
    two notes are titled so (a single note is the ordinary answer's)."""
    parsed = _asked(asked)
    if not parsed:
        return False
    prop, kind = (composer._stem(w) for w in parsed)  # noqa: SLF001
    named = [v for v in views if composer._holds(kind, v.title_words)]  # noqa: SLF001
    found = []
    for view in named:
        sentence = next((s for s in view.sentences if composer._holds(prop, set(s.words))), None)  # noqa: SLF001
        if sentence is not None:
            found.append((view, sentence))
    if len(found) < 2:
        return False
    for view, sentence in sorted(found, key=lambda f: f[0].rank):
        line = f"{composer_lists._title(view)}: {composer_lists._trim(sentence.text)}"  # noqa: SLF001
        out.lines.append(line)
        composer_lists._cite(out, view, sentence, line)  # noqa: SLF001
    return True
