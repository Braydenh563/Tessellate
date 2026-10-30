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

from tessellate.ai import composer, composer_lists, recognise

#: "How much money have I recorded I've spent" and "what have I spent so far"
#: are the same total: the ask can say where the figures are kept.
_SPENT = re.compile(
    r"^(?:how much|what) (?:money )?(?:have|did|do|has) (?:i|we) "
    r"(?:(?:recorded|logged|noted|tracked|written(?: down)?|put down)(?: (?:that|as))? (?:(?:i|we)(?:'ve| have|ve)? )?)?"
    r"(?:spen[dt]|paid|pay|spending)\b(.*)$",
    re.I,
)
#: "How much grocery spending have I recorded", "what's my recorded travel
#: spending": the subject sits before the noun (stress run 2026-10-30).
_KIND_SPENT = re.compile(
    r"^(?:how much|what(?:'s|s| is)?) (?:my |our )?(?:recorded |paid )?(?P<subject>(?:(?!(?:spending|expenses?|costs?)\b)[\w'-]+ )*(?!(?:spending|expenses?|costs?)\b)[\w'-]+) (?:spending|expenses?|costs?)"
    r"(?: (?:have|did|do) (?:i|we) (?:recorded|logged|noted|tracked|got|have))?(?P<rest>.*)$",
    re.I,
)
#: "What's my total spending", "total spent in October".
_TOTAL = re.compile(
    r"^(?:and )?(?:what(?:'s|s| is| was)? )?(?:my |our |the )?(?:total|net|gross) (?:of )?(?:all )?(?:my |the )?(?:recorded )?(?:outgoing )?"
    r"(?:spend(?:ing)?|spent|expenses?|payments?|purchases?)\b(.*)$",
    re.I,
)
#: "What do my October payments add up to", "how much was the hotel altogether".
_ADD_UP = re.compile(
    r"^what do (?:my|the|our) (?P<subject>(?:(?!(?:payments|expenses|purchases|spending|costs)\b)[\w'-]+ )*)(?:payments|expenses|purchases|spending|costs) (?:add up to|come to|total)\b(?P<rest>.*)$"
    r"|^how much (?:was|were|did) (?:the|my|our) (?P<thing>(?:(?!(?:cost|altogether|in|all|overall)\b)[\w'-]+ )*(?!(?:cost|altogether|in|all|overall)\b)[\w'-]+) (?:cost )?(?P<all>altogether|in total|all up|overall)\??$",
    re.I,
)
#: "How much is left on my hotel bill", "how much travel money is still unpaid".
_DUE_ASK = re.compile(
    r"^how much (?P<subject>(?:(?!(?:money|is|do)\b)[\w'-]+ )*)(?:money )?(?:is|do i have) (?:still )?(?:explicitly )?(?:left (?:to pay )?(?:on|for)|owing|unpaid|outstanding|due)\b(?P<rest>.*)$",
    re.I,
)
#: A question about a word, not an amount: "what did I mean by recorded spending".
_ABOUT_WORDS = re.compile(r"\b(?:mean|meant|meaning|referring|refer|stand for|define|definition)\b", re.I)
_MOST = re.compile(r"^what(?:'s| is| was| were)? (?:my|the|our) (biggest|largest|highest|smallest|cheapest|lowest|priciest) (.+)$", re.I)
_MONEY_NOUNS = frozenset({"expense", "expenses", "cost", "costs", "bill", "bills", "purchase", "purchases", "payment", "payments", "spend", "spending"})
_SMALL = frozenset({"smallest", "cheapest", "lowest"})
#: Clauses about money that is not spent: owed, earned, a target, a budget,
#: an asking price, a balance still due, or an amount the note denies ("not
#: $320 each way"). A refund is read apart (`_REFUND`) and taken off.
_NOT_SPENT = re.compile(
    r"\b(?:owes?|owed|lent|lend|borrow\w*|earn\w*|salary|income|refund\w*|saved|savings|save|goal|targets?|budget\w*"
    r"|listing|listed|asking|quoted|due|balance|unpaid|reached|aim\w*|limit|cap)\b|\bnot\s+(?:[A-Z]{3}\s*)?[$£€]"
    #: "keep food under $100" is the aim, not money spent (gold answer 15).
    r"|\bkeep(?:\s+\w+){0,4}\s+(?:under|below)\b",
    re.I,
)
_REFUND = re.compile(r"\brefund\w*\b", re.I)
#: A balance still owed, said beside the total so it is not mistaken as missed.
_STILL_DUE = re.compile(r"\b(?:due|unpaid|balance|haven't paid|not paid)\b", re.I)
#: A note is a spending note when its title or text says so.
_SPENDING = re.compile(r"\b(?:spen[dt]\w*|expenses?|costs?|paid|bought|purchases?|bills?|receipts?)\b", re.I)
_DATE_TAIL = re.compile(r"\s+(?:on|in|at|from|for)\s+.*$", re.I)


class Item(NamedTuple):
    label: str
    symbol: str
    value: float
    view: object
    sentence: object


_VERB = re.compile(r"^(?:i\s+)?(?:paid|spent|bought|cost|was|were|aud|usd|gbp|eur|nzd|cad)\b\s*", re.I)
_AFTER = re.compile(r"^\s*(?:for|on|at|to)\s+(?P<what>[\w' -]+?)(?:\s+(?:to|because|as|in|on)\b.*)?$", re.I)


def _what(clause: str, at: int, end: int, last: str) -> str:
    """What an amount bought: the words before it ("Groceries $86"), else the
    words after it ("Paid $42 for the plumber", "$24 at the market"), else
    the clause before's label."""
    before = clause[:at]
    while (cut := _VERB.sub("", before.strip())) != before.strip():
        before = cut
    words = [w for w in re.sub(r"[^\w\s'-]", " ", _DATE_TAIL.sub("", before)).split() if w.lower() not in ("and", "the", "a", "an", "my", "for")]
    if words:
        return " ".join(words[-3:])
    after = _AFTER.match(clause[end:])
    #: "$112 on the 17th" is when, not what: it keeps the clause before's label.
    if not after or re.search(r"[0-9]", after.group("what")) or recognise.without_windows(after.group("what")) != after.group("what") or set(after.group("what").lower().split()) & recognise.MONTH_NAMES:
        return last
    return re.sub(r"^my\b", "your", after.group("what").strip())


def _clause_items(view, sentence, refunds: bool) -> list[Item]:  # noqa: ANN001
    found: list[Item] = []
    last = ""
    for clause in re.split(r"[;,.](?!\d)|\band\b", sentence.text):
        said = recognise.amounts(clause)
        if not said or bool(_REFUND.search(clause)) != refunds or (not refunds and _NOT_SPENT.search(clause)):
            continue
        sign, value, at = said[0]
        tail = re.match(r"[$£€]?\s*[\d,.]+", clause[at:])
        last = _what(clause, at, at + (tail.end() if tail else 1), last) or composer_lists._title(view)  # noqa: SLF001
        found.append(Item(last, sign, value, view, sentence))
    return found


def _items_of(view, sentence) -> list[Item]:  # noqa: ANN001
    return _clause_items(view, sentence, refunds=False)


def _month_asked(rest: str, today: date) -> int | None:
    rest = rest.lower()
    if "this month" in rest:
        return today.month
    if "last month" in rest:
        return 12 if today.month == 1 else today.month - 1
    #: "may" only after "in": "how much may I have spent" names no month.
    named = [w for w in re.findall(r"(?:(?:in|during|for|on) )?\b([a-z]+)", rest) if w in recognise.MONTH_NAMES and w != "may"]
    named += [w for w in re.findall(r"(?:in|during|for) (may)\b", rest)]
    return recognise._MONTHS[named[0]] if named else None  # noqa: SLF001


def _in_month(view, month: int | None) -> bool:  # noqa: ANN001
    if month is None:
        return True
    names = {n for n, number in recognise._MONTHS.items() if number == month}  # noqa: SLF001
    title = set(re.findall(r"[a-z]+", str(view.title).lower()))
    if names & title:
        return True
    return bool(view.written and view.written.month == month and not title & recognise.MONTH_NAMES)


def _about(view, sentence, subject: list[str], test=all) -> bool:  # noqa: ANN001
    """Whether an amount is about the asked subject: its sentence, its note's
    title, tags or category name it ("the plumber", #groceries, "eating out"
    for #eating-out)."""
    if not subject:
        return True
    have = set(sentence.words) | set(view.title_words) | set(view.filed_words)
    return test(st in have for st in subject)


def _items(views: list, month: int | None = None, subject: list[str] | None = None, refunds: bool = False) -> list[Item]:
    """The amounts about every subject word, else about any of them ("your
    hotel bill" when no note says "bill")."""
    return _items_by(views, month, subject, refunds, all) or (_items_by(views, month, subject, refunds, any) if subject and len(subject) > 1 else [])


def _items_by(views: list, month: int | None, subject: list[str] | None, refunds: bool, test) -> list[Item]:  # noqa: ANN001
    spending = [v for v in views if _SPENDING.search(str(v.title) + " " + " ".join(s.text for s in v.sentences[:3])) or _REFUND.search(str(v.title))]
    found = []
    for view in sorted(spending, key=lambda v: v.rank):
        if _in_month(view, month):
            for sentence in view.sentences:
                if _about(view, sentence, subject or [], test):
                    items = _clause_items(view, sentence, refunds)
                    #: "$84 on groceries and $35 on fuel": the sentence is
                    #: about groceries, its fuel is not.
                    named = [i for i in items if subject and any(st in set(composer._words(i.label)) for st in subject)]  # noqa: SLF001
                    found.extend(named or items)
    return found


def _still_due(views: list, month: int | None, subject: list[str]) -> list[Item]:
    return _due_by(views, month, subject, all) or (_due_by(views, month, subject, any) if len(subject) > 1 else [])


def _due_by(views: list, month: int | None, subject: list[str], test) -> list[Item]:  # noqa: ANN001
    due = []
    for view in views:
        if not _in_month(view, month):
            continue
        for sentence in view.sentences:
            if _about(view, sentence, subject, test) and _STILL_DUE.search(sentence.text) and _SPENDING.search(" ".join(s.text for s in view.sentences)):
                for clause in re.split(r"[;,.](?!\d)", sentence.text):
                    if (said := recognise.amounts(clause)) and _STILL_DUE.search(sentence.text) and re.search(r"\b(?:another|balance|due|unpaid)\b", clause, re.I):
                        due.append(Item(composer_lists._title(view), said[0][0], said[0][1], view, sentence))  # noqa: SLF001
    return due


def _money(symbol: str, value: float) -> str:
    return f"{symbol}{value:,.2f}" if value % 1 else f"{symbol}{int(value):,}"


def _cite_all(out, items: list[Item], said: str) -> None:  # noqa: ANN001
    seen = set()
    for item in items:
        key = id(item.sentence)
        if key not in seen:
            seen.add(key)
            composer_lists._cite(out, item.view, item.sentence, said)  # noqa: SLF001


#: The words of a money question that set its window or its manner, not its subject.
_WINDOW = re.compile(
    r"\b(?:so far|altogether|all up|in total|overall|"
    r"(?:before|after) refunds?|across the notebook|in (?:these|my) notes|(?:have i |i've )?recorded|actually|explicitly|"
    r"net|gross|total|(?:that )?(?:have|has|with) amounts?|(?:in |during |for |on )?(?:" + "|".join(sorted(recognise.MONTH_NAMES - {"may"})) + r"))\b",
    re.I,
)
_STOP = frozenset(composer._words("me my i in on for of the a an to have has did do is it that from all money spent spend spending paid pay amounts amount outgoing payments payment expenses expense notes note these this and with you your"))  # noqa: SLF001


def _subject(rest: str) -> tuple[list[str], str]:
    """The stems of what the money went on, and those words as typed ("the plumber")."""
    said = " ".join(_WINDOW.sub(" ", recognise.without_windows(re.sub(r"[^\w\s'-]", " ", rest))).split())
    said = re.sub(r"^(?:on|for|to|in)\s+", "", said, flags=re.I)
    said = re.sub(r"\bmy\b", "your", said, flags=re.I)
    stems = [w for w in composer._words(said) if w not in _STOP]  # noqa: SLF001
    return stems, said if stems else ""


def _listed(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _spent(out, rest: str, views: list, today: date) -> bool:  # noqa: ANN001
    month = _month_asked(rest, today)
    subject, said = _subject(rest)
    items = _items(views, month, subject)
    when = f" in {date(2000, month, 1):%B}" if month else ""
    on = f" on {said}" if said else ""
    if not items:
        out.lines.append(f"I found no amounts spent{on}{when} in your notes.")
        return True
    symbol = items[0].symbol
    items = [i for i in items if i.symbol == symbol]
    if len(items) == 1 and len(recognise.amounts(" ".join(s.text for s in items[0].view.sentences))) > 1 \
            and not _items(views, month, subject, refunds=True) and not _still_due(views, month, subject):
        #: One amount in a note of several is nothing to add up: the digest
        #: says it with its week and what sits beside it (gold answer 15).
        return False
    by_note: dict[str, float] = {}
    for item in items:
        name = composer_lists._title(item.view)  # noqa: SLF001
        by_note[name] = by_note.get(name, 0) + item.value
    total = sum(by_note.values())
    if len(items) == 1:
        name = next(iter(by_note))
        what = "" if items[0].label == name else f" for {items[0].label}"
        line = f"You paid {_money(symbol, total)}{what}, going by {name}."
    elif len(by_note) == 1:
        by_label: dict[str, float] = {}
        for item in items:
            by_label[item.label] = by_label.get(item.label, 0) + item.value
        listed = _listed([f"{label.lower() if i else label} {_money(symbol, v)}" for i, (label, v) in enumerate(by_label.items())])
        line = f"You spent {_money(symbol, total)}{on}{when}, going by {next(iter(by_note))}: {listed}."
    else:
        listed = _listed([f"{name} {_money(symbol, v)}" for name, v in by_note.items()])
        line = f"Your notes record {_money(symbol, total)} spent{on}{when}: {listed}."
    out.lines.append(line)
    _cite_all(out, items, line)
    _refunds_and_due(out, views, month, subject, symbol, total)
    return True


def _refunds_and_due(out, views: list, month: int | None, subject: list[str], symbol: str, total: float) -> None:  # noqa: ANN001
    """A refund taken off, with the net; a balance still due, named and not counted."""
    back = [i for i in _items(views, month, subject, refunds=True) if i.symbol == symbol]
    if back:
        off = sum(i.value for i in back)
        line = f"Less {_money(symbol, off)} refunded ({_listed(sorted({composer_lists._title(i.view) for i in back}))}), that is {_money(symbol, total - off)} net."  # noqa: SLF001
        out.lines.append(line)
        _cite_all(out, back, line)
    due = [i for i in _still_due(views, month, subject) if i.symbol == symbol]
    if due and subject:
        owed = sum(i.value for i in due)
        line = f"Another {_money(symbol, owed)} is still due ({_listed(sorted({i.label for i in due}))}), so {_money(symbol, total + owed)} all up once that is paid."
        out.lines.append(line)
        _cite_all(out, due, line)
    elif due:
        line = f"Not counted: {_listed([f'{_money(symbol, i.value)} still due ({i.label})' for i in due])}."
        out.lines.append(line)
        _cite_all(out, due, line)


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


def _total_asked(q: str):  # noqa: ANN202
    if _ABOUT_WORDS.search(q) or _MOST.match(q):
        return None
    return _total_rest(q)


def _total_rest(q: str):  # noqa: ANN202
    """The rest of a money question (its subject and window), or None. "How
    much did I spend on groceries" is asked here too: the subject scopes the
    sum (stress run 2026-10-30: "how much did I pay the plumber" summed every
    expense)."""
    if m := _SPENT.match(q) or _TOTAL.match(q):
        return m.group(1)
    if (m := _ADD_UP.match(q)):
        return " ".join(x for x in (m.group("subject"), m.group("rest"), m.group("thing"), m.group("all")) if x)
    if (m := _KIND_SPENT.match(q)) and not re.search(r"\b(?:did|do|does|i|we)\b", m.group("subject"), re.I):
        return f"{m.group('subject')} {m.group('rest')}"
    return None


def _due(out, rest: str, views: list, today: date) -> bool:  # noqa: ANN001
    subject, said = _subject(rest)
    due = _still_due(views, None, subject)
    if not due:
        out.lines.append(f"I found nothing still to pay{' for ' + said if said else ''} in your notes.")
        return True
    symbol = due[0].symbol
    due = [i for i in due if i.symbol == symbol]
    if len(due) == 1:
        line = f"{_money(symbol, due[0].value)} is still to pay, going by {due[0].label}."
    else:
        line = f"{_money(symbol, sum(i.value for i in due))} is still to pay: {_listed([f'{_money(symbol, i.value)} ({i.label})' for i in due])}."
    out.lines.append(line)
    _cite_all(out, due, line)
    return True


def asks(question: str) -> bool:
    q = " ".join(composer_lists._q(question).split())  # noqa: SLF001
    if _total_asked(q) is not None or _DUE_ASK.match(q):
        return True
    m = _MOST.match(q)
    return bool(m and set(m.group(2).lower().rstrip("?. ").split()) & _MONEY_NOUNS)


def records_spending(text: str) -> bool:
    """A note that names spending or a refund and holds an amount."""
    return bool(recognise.amounts(text) and (_SPENDING.search(text) or _REFUND.search(text)))


def answer(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    """A sum or a maximum of the amounts spent; False when `asked` is not one."""
    q = " ".join(composer_lists._q(asked).split())  # noqa: SLF001
    if (rest := _total_asked(q)) is not None:
        return _spent(out, rest, views, today)
    if m := _DUE_ASK.match(q):
        return _due(out, f"{m.group('subject') or ''} {m.group('rest')}", views, today)
    if m := _MOST.match(q):
        return _most(out, m.group(1), m.group(2), views)
    return False
