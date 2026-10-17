"""Proofreading with no model (O7; INBOX 904 B33, the owner: "Can the
composer do these ai actions well and just as good?? And they arent ai
actions if the composer does them when the ai isnt available").

What the app can do itself, and only that: misspelt words read as the word
they are near (`spelling.fix`, the speller the composer reads questions
with), a lone "i" as "I", the first letter of each sentence raised, runs of
spaces closed and a space put after a comma or full stop typed without one.
It never rewords, reorders or shortens: that is writing, and writing needs a
model, which the Improve sheet says. The result says what it changed, so the
before and after the sheet shows are honest about who did it.
"""

from __future__ import annotations

import re

from tessellate.ai import recognise


_WORD = re.compile(r"[A-Za-z][A-Za-z']*")
_SENTENCE_START = re.compile(r"(^|[.!?]\s+|\n\s*)([a-z])")
_LONE_I = re.compile(r"(?<![\w'])i(?=(?:'m|'ve|'ll|'d)?(?![\w']))")
_SPACES = re.compile(r"[ \t]{2,}")
_TIGHT = re.compile(r"(?<=[a-z])([,.])(?=[A-Za-z]{2,})")
#: Kept as typed: a URL, an address, code, a tag or a [[link]]. The runs are
#: bounded so a long line of one repeated character stays linear (CodeQL).
_UNTOUCHED = re.compile(r"(https?://\S+|\S{1,100}@\S{1,255}|`[^`]{0,500}`|#\w+|\[\[[^\]]{0,200}\]\])")


def proofread(text: str, known=frozenset()) -> tuple[str, list[tuple[str, str]]]:  # noqa: ANN001
    """`(proofread text, [(typed, made)])`. `known` are words of the
    person's own (their notes'), never changed."""
    changes: list[tuple[str, str]] = []
    pieces = _UNTOUCHED.split(text or "")
    out = []
    for n, piece in enumerate(pieces):
        out.append(piece if n % 2 else _proofread_plain(piece, known, changes))
    said = "".join(out)
    raised = _SENTENCE_START.sub(lambda m: m.group(1) + m.group(2).upper(), said)
    if raised != said:
        changes.append(("sentence starts", "capitals"))
    return raised, changes


def _proofread_plain(text: str, known, changes: list) -> str:  # noqa: ANN001
    """The misspellings the question reader finds (`question_noise.repair`,
    which reads a word with its neighbours: "we shoud prepare" is "should",
    where the bare speller said "shout"), put right where they stand; slang
    and contractions are left as typed, being the person's style."""
    from tessellate.ai import question_noise

    text = _SPACES.sub(" ", text)
    text = _TIGHT.sub(r"\1 ", text)
    for line in text.split("\n"):
        fixed: list[tuple[str, str]] = []
        question_noise.repair(line, fixed=fixed, known=known)
        for typed, made in fixed:
            if not _WORD.fullmatch(typed) or not made or typed.lower() == made.lower():
                continue
            made = _modal(typed, line) or made
            made = made[:1].upper() + made[1:] if typed[:1].isupper() else made
            replaced = re.sub(rf"(?<![\w']){re.escape(typed)}(?![\w'])", made, text, count=1)
            if replaced != text:
                text = replaced
                changes.append((typed, made))
    named = recognise.capitalise_names(text)
    if named != text:
        changes.append(("day names", "capitals"))
    fixed_i = _LONE_I.sub("I", named)
    if fixed_i != named:
        changes.append(("i", "I"))
    return fixed_i


_MODALS = ("should", "could", "would", "will", "might", "must", "shall")
_SUBJECTS = frozenset("i we you they he she it someone everyone".split())


def _modal(typed: str, line: str) -> str:
    """After a subject ("we shoud prepare"), a slip one letter from a modal
    verb is the modal: the speller, reading the word alone, said "shout"."""
    from tessellate.ai import question_noise

    #: The word before starts at a word start and is a short one (a subject is):
    #: an open-ended `\w+` tried at every letter of a long unbroken run was
    #: quadratic (CodeQL py/polynomial-redos).
    before = re.search(rf"(?<!\w)(\w{{1,20}})\s+{re.escape(typed)}(?![\w'])", line)
    if not before or before.group(1).lower() not in _SUBJECTS:
        return ""
    near = [m for m in _MODALS if question_noise.distance(typed.lower(), m) <= 1.0]
    return near[0] if len(near) == 1 else ""


def said(changes: list[tuple[str, str]]) -> str:
    """One line on what the proofreading changed, for the sheet."""
    words = [(a, b) for a, b in changes if a not in ("sentence starts", "i", "day names")]
    if not changes:
        return "Atlas's assistant read it through and found nothing to change. Rewording needs a model."
    parts = []
    if words:
        shown = ", ".join(f"“{a}” to “{b}”" for a, b in words[:4])
        parts.append(f"put right {len(words)} spelling{'s' if len(words) != 1 else ''} ({shown})")
    if any(a in ("sentence starts", "i", "day names") for a, _ in changes):
        parts.append("raised the capitals")
    return "Atlas's assistant " + " and ".join(parts) + ", with no model. Rewording needs one."
