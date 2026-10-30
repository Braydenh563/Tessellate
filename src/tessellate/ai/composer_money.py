"""Amounts worked out from the notes (2026-10-30 sweep).

"How much have I spent this month" and "what's my biggest expense" found
nothing, or quoted the spending note whole: the answer is a sum or a
maximum of the amounts the notes hold, so it is computed here and every
figure is cited to the sentence it came from. Money owed, lent or earned is
not spending and is left out. No model, and the same with one on.
"""

from __future__ import annotations

import re
from datetime import date
from typing import NamedTuple

from tessellate.ai import composer_lists, recognise

#: "How much money have I recorded I've spent" and "what have I spent so far"
#: are the same total: the ask can say where the figures are kept.
_SPENT = re.compile(
    r"^(?:how much|what) (?:money )?(?:have|did|do|has) (?:i|we) "
    r"(?:(?:recorded|logged|noted|tracked|written(?: down)?|put down)(?: (?:that|as))? (?:(?:i|we)(?:'ve| have|ve)? )?)?"
    r"(?:spen[dt]|paid|pay|spending)\b(.*)$",
    re.I,
)
#: "What's my total spending", "total spent in October".
_TOTAL = re.compile(r"^(?:what(?:'s|s| is| was)? )?(?:my |our |the )?total (?:spend(?:ing)?|spent|expenses?)\b(.*)$", re.I)
_MOST = re.compile(r"^what(?:'s| is| was| were)? (?:my|the|our) (biggest|largest|highest|smallest|cheapest|lowest|priciest) (.+)$", re.I)
_MONEY_NOUNS = frozenset({"expense", "expenses", "cost", "costs", "bill", "bills", "purchase", "purchases", "payment", "payments", "spend", "spending"})
_SMALL = frozenset({"smallest", "cheapest", "lowest"})
#: Clauses about money that is not spent.
_NOT_SPENT = re.compile(r"\b(?:owes?|owed|lent|lend|borrow\w*|earn\w*|salary|income|refund\w*|saved|savings|goal)\b", re.I)
#: A note is a spending note when its title or text says so.
_SPENDING = re.compile(r"\b(?:spen[dt]\w*|expenses?|costs?|paid|bought|purchases?|bills?|receipts?)\b", re.I)
_DATE_TAIL = re.compile(r"\s+(?:on|in|at|from|for)\s+.*$", re.I)


class Item(NamedTuple):
    label: str
    symbol: str
    value: float
    view: object
    sentence: object


def _label(clause: str, before: str) -> str:
    """The words before the amount, or the clause's last label when the
    amount stands alone ("Groceries $86 on the 3rd, $112 on the 17th")."""
    words = re.sub(r"[^\w\s'-]", " ", clause).split()
    words = [w for w in words if w.lower() not in ("and", "the", "a", "an", "my", "for")]
    return " ".join(words[-3:]) if words else before


def _items_of(view, sentence) -> list[Item]:  # noqa: ANN001
    found: list[Item] = []
    last = ""
    for clause in re.split(r"[;,.](?!\d)|\band\b", sentence.text):
        said = recognise.amounts(clause)
        if not said or _NOT_SPENT.search(clause):
            continue
        sign, value, at = said[0]
        last = _label(_DATE_TAIL.sub("", clause[:at]), last)
        if last:
            found.append(Item(last, sign, value, view, sentence))
    return found


def _month_asked(rest: str, today: date) -> int | None:
    rest = rest.lower()
    if "this month" in rest:
        return today.month
    if "last month" in rest:
        return 12 if today.month == 1 else today.month - 1
    #: "may" only after "in": "how much may I have spent" names no month.
    named = [w for w in re.findall(r"(?:in|during|for) ([a-z]+)", rest) if w in recognise.MONTH_NAMES]
    return recognise._MONTHS[named[0]] if named else None  # noqa: SLF001


def _in_month(view, month: int | None) -> bool:  # noqa: ANN001
    if month is None:
        return True
    names = {n for n, number in recognise._MONTHS.items() if number == month}  # noqa: SLF001
    title = set(re.findall(r"[a-z]+", str(view.title).lower()))
    if names & title:
        return True
    return bool(view.written and view.written.month == month and not title & recognise.MONTH_NAMES)


def _items(views: list, month: int | None = None) -> list[Item]:
    spending = [v for v in views if _SPENDING.search(str(v.title) + " " + " ".join(s.text for s in v.sentences[:3]))]
    found = []
    for view in sorted(spending, key=lambda v: v.rank):
        if _in_month(view, month):
            for sentence in view.sentences:
                found.extend(_items_of(view, sentence))
    return found


def _money(symbol: str, value: float) -> str:
    return f"{symbol}{value:,.2f}" if value % 1 else f"{symbol}{int(value):,}"


def _cite_all(out, items: list[Item], said: str) -> None:  # noqa: ANN001
    seen = set()
    for item in items:
        key = id(item.sentence)
        if key not in seen:
            seen.add(key)
            composer_lists._cite(out, item.view, item.sentence, said)  # noqa: SLF001


def _spent(out, rest: str, views: list, today: date) -> bool:  # noqa: ANN001
    month = _month_asked(rest, today)
    items = _items(views, month)
    when = f" in {date(2000, month, 1):%B}" if month else ""
    if not items:
        out.lines.append(f"I found no amounts spent{when} in your notes.")
        return True
    symbol = items[0].symbol
    items = [i for i in items if i.symbol == symbol]
    totals: dict[str, float] = {}
    for item in items:
        totals[item.label] = totals.get(item.label, 0) + item.value
    parts = [f"{label.lower() if i else label} {_money(symbol, v)}" for i, (label, v) in enumerate(totals.items())]
    listed = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    notes = sorted({composer_lists._title(i.view) for i in items})  # noqa: SLF001
    line = f"You spent {_money(symbol, sum(totals.values()))}{when}, going by {' and '.join(notes)}: {listed}."
    out.lines.append(line)
    _cite_all(out, items, line)
    return True


def _most(out, size: str, noun: str, views: list) -> bool:  # noqa: ANN001
    if not set(noun.lower().rstrip("?. ").split()) & _MONEY_NOUNS:
        return False
    items = _items(views)
    if not items:
        out.lines.append("I found no amounts spent in your notes.")
        return True
    pick = (min if size.lower() in _SMALL else max)(items, key=lambda i: i.value)
    line = f"{pick.label}, at {_money(pick.symbol, pick.value)}, is the {size.lower()} amount in {composer_lists._title(pick.view)}."  # noqa: SLF001
    out.lines.append(line)
    _cite_all(out, [pick], line)
    return True


#: "How much did I spend on groceries" is one thing's amount, which the
#: count answer says with its week; a total is asked with no "on".
_ON_ONE = re.compile(r"\b(?:on|for)\s+(?!this\b|last\b|the month\b)", re.I)


def _total_asked(q: str):  # noqa: ANN202
    m = _SPENT.match(q) or _TOTAL.match(q)
    return m if m and not _ON_ONE.search(m.group(1)) else None


def asks(question: str) -> bool:
    q = " ".join(composer_lists._q(question).split())  # noqa: SLF001
    if _total_asked(q):
        return True
    m = _MOST.match(q)
    return bool(m and set(m.group(2).lower().rstrip("?. ").split()) & _MONEY_NOUNS)


def records_spending(text: str) -> bool:
    """A note that names spending and holds an amount."""
    return bool(recognise.amounts(text) and _SPENDING.search(text))


def answer(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    """A sum or a maximum of the amounts spent; False when `asked` is not one."""
    q = " ".join(composer_lists._q(asked).split())  # noqa: SLF001
    if m := _total_asked(q):
        return _spent(out, m.group(1), views, today)
    if m := _MOST.match(q):
        return _most(out, m.group(1), m.group(2), views)
    return False
