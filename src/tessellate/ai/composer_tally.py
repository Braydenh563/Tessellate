"""A superlative over a table, a count of what a list holds, and a distance on a named day, worked out from
the lines (R9-10, composer audit round 9). "Which builder was cheapest" names the smallest quote beside the
others, "how many quotes did I get" counts the table's rows, "how many books do I want to read" counts the
list after "Want to read:", and "how far did I run on 8 November" is that day's line, not the whole log."""

from __future__ import annotations

import re

from tessellate.ai import composer, composer_lists, realise

_MONEY = re.compile(r"([$£€¥])\s?(\d[\d,]*(?:\.\d+)?)")
_SIZE = {"cheapest": min, "lowest": min, "smallest": min, "dearest": max, "highest": max, "biggest": max, "largest": max, "most expensive": max}
_SUPERLATIVE = re.compile(
    r"^(?:which|what|who)\s+(?:was\s+|is\s+|were\s+|are\s+)?(?:my\s+|the\s+)?(?P<noun>[a-z]+)\s+(?:was|is|were|are)\s+(?:the\s+)?(?P<size>cheapest|dearest|most expensive|lowest|highest|smallest|biggest|largest)$"
)
_HOW_MANY_ROWS = re.compile(r"^how many (?P<noun>[a-z]+) (?:did i get|have i got|have i had|do i have|did i receive|have i collected)$")
_HOW_MANY_WANTED = re.compile(r"^how many (?P<noun>[a-z]+) do i want to (?P<verb>[a-z]+)$")
_HOW_FAR = re.compile(r"^how far did i (?:run|walk|cycle|ride|swim|jog)(?: on (?P<day>\d{1,2}(?:st|nd|rd|th)? [a-z]+|[a-z]+ \d{1,2}(?:st|nd|rd|th)?))?$")
_DISTANCE = re.compile(r"(\d[\d.,]*)\s*(km|kilometres|kilometers|miles|mi)\b", re.I)


def _rows(view) -> list:  # noqa: ANN001
    """The list or table lines of a note that carry exactly one amount each."""
    return [s for s in view.sentences if s.kind == "item" and len(_MONEY.findall(s.text)) == 1]


def _label(text: str) -> str:
    return _MONEY.sub("", text).strip(" |:-,")


def _superlative(out, q: str, views: list) -> bool:  # noqa: ANN001
    found = _SUPERLATIVE.match(q)
    if not found:
        return False
    noun, pick = found["noun"], _SIZE[found["size"]]
    for view in views:
        rows = _rows(view)
        if len(rows) >= 2 and re.search(rf"\b{re.escape(noun)}s?\b", str(view.note.get("content") or ""), re.I):
            break
    else:
        return False
    best = pick(rows, key=lambda s: float(_MONEY.search(s.text).group(2).replace(",", "")))
    others = ", ".join(s.text.replace("|", "").strip() for s in rows if s is not best)
    sign, amount = _MONEY.search(best.text).groups()
    line = f"{_label(best.text)}, at {sign}{amount} ({others})."
    out.lines.append(line)
    composer_lists._cite(out, view, best, line)  # noqa: SLF001
    return True


def _count_rows(out, q: str, views: list) -> bool:  # noqa: ANN001
    found = _HOW_MANY_ROWS.match(q)
    if not found:
        return False
    stem = composer._stem(found["noun"])  # noqa: SLF001
    for view in views:
        rows = [s for s in view.sentences if s.kind == "item"]
        if len(rows) >= 2 and view.titled and composer._holds(stem, view.title_words):  # noqa: SLF001
            names = [_label(s.text) or s.text for s in rows]
            line = f"{realise.count_word(len(rows)).capitalize()} {found['noun']}, in {composer_lists._title(view)}: {realise.join_items(names)}."  # noqa: SLF001
            out.lines.append(line)
            composer_lists._cite(out, view, rows[0], line)  # noqa: SLF001
            return True
    return False


def _count_wanted(out, q: str, views: list) -> bool:  # noqa: ANN001
    found = _HOW_MANY_WANTED.match(q)
    if not found:
        return False
    label = re.compile(rf"\bwant to {re.escape(found['verb'])}\s*:\s*(?P<list>[^.]+)", re.I)
    for view in views:
        for s in view.sentences:
            if m := label.search(s.text):
                items = [re.sub(r"^and\s+", "", part.strip()) for part in m["list"].split(",") if part.strip()]
                if len(items) >= 2:
                    line = f"{realise.count_word(len(items)).capitalize()} {found['noun']} to {found['verb']}, in {composer_lists._title(view)}: {realise.join_items(items)}."  # noqa: SLF001
                    out.lines.append(line)
                    composer_lists._cite(out, view, s, line)  # noqa: SLF001
                    return True
    return False


def _how_far(out, q: str, views: list) -> bool:  # noqa: ANN001
    found = _HOW_FAR.match(q)
    if not found or not found["day"]:
        return False
    day = re.sub(r"(?<=\d)(?:st|nd|rd|th)", "", found["day"])
    parts = day.split()
    wanted = re.compile(rf"\b{re.escape(parts[0])}\s+{re.escape(parts[1])}\b", re.I)
    for view in views:
        for s in view.sentences:
            if (d := _DISTANCE.search(s.text)) and wanted.search(s.text):
                line = f"{d.group(1)} {d.group(2)} on {found['day']} ({composer_lists._title(view)})."  # noqa: SLF001
                out.lines.append(line)
                composer_lists._cite(out, view, s, line)  # noqa: SLF001
                return True
    return False


def answer(out, asked: str, views: list) -> bool:  # noqa: ANN001
    """Say the superlative, the count or the day's distance; False when `asked` is none of these."""
    q = " ".join(composer_lists._q(asked).lower().split())  # noqa: SLF001
    return _superlative(out, q, views) or _count_rows(out, q, views) or _count_wanted(out, q, views) or _how_far(out, q, views)
