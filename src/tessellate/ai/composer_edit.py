"""Document edits with no model (CHAT_PLAN B26): tighten a selection, summarise
it, and continue its list. Each only rearranges or takes from the text it is
given, never a word the person did not write; the page applies the result as
one undoable edit, so the original is one Undo away."""

from __future__ import annotations

import re

from tessellate.ai import composer_tidy

_ITEM = re.compile(r"^(\s*)(?:(\d+)([.)])|([-*+])(\s\[[ xX]\])?)\s+(.*)$")
_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
SUMMARY_SENTENCES = 2


def tighten(text: str) -> str:
    """Wordy phrases shortened and fillers dropped; lines, lists and code stay."""
    out: list[str] = []
    for code, lines in composer_tidy._segments(text.replace("\r\n", "\n")):
        for line in lines:
            if code or not line.strip() or composer_tidy._HEADING.match(line):
                out.append(line)
                continue
            line = composer_tidy._FILLERS.sub("", composer_tidy.concise(line))
            line = re.sub(r"(?<=\S)  +", " ", line).replace(" ,", ",")
            out.append(line[:1].upper() + line[1:] if line.strip() and line == line.lstrip() and line[:1].islower() else line)
    return "\n".join(out)


def summarise(text: str) -> str:
    """The text's first sentence, and its last when it runs past three: its own words, in order."""
    sentences = [s for s in composer_tidy.sentences(re.sub(r"^\s*(?:#+|[-*+>]|\d+[.)])\s+", "", text, flags=re.M)) if len(s.split()) >= 3]
    if not sentences:
        return ""
    picked = sentences[:1] + (sentences[-1:] if len(sentences) > 3 else [])
    return " ".join(list(dict.fromkeys(picked))[:SUMMARY_SENTENCES])


def _next_word(items: list[str]) -> str:
    """The word that follows a run of weekdays or months or numbers, or ""."""
    if not items:
        return ""
    last = items[-1].strip().rstrip(".")
    for table in (_DAYS, _MONTHS):
        names = [n.lower() for n in table]
        if last.lower() in names:
            return table[(names.index(last.lower()) + 1) % len(table)]
    if re.fullmatch(r"\d+", last) and len(items) > 1 and re.fullmatch(r"\d+", items[-2].strip()):
        step = int(last) - int(items[-2].strip())
        return str(int(last) + step) if step else ""
    return ""


def continue_list(text: str) -> str:
    """The next line of the list the text ends in (its marker, and the item when the run makes it plain); "" for no list."""
    lines = [ln for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
    found = [_ITEM.match(ln) for ln in lines]
    if not lines or not found[-1]:
        return ""
    last = found[-1]
    items = [m.group(6) for m in found if m]
    word = _next_word(items)
    if last.group(2):
        return f"{last.group(1)}{int(last.group(2)) + 1}{last.group(3)} {word}".rstrip() if word else f"{last.group(1)}{int(last.group(2)) + 1}{last.group(3)} "
    box = " [ ]" if last.group(5) else ""
    return f"{last.group(1)}{last.group(4)}{box} {word}".rstrip() + ("" if word else " ")
