"""Amounts and measures worked out from the notes (2026-10-30 sweep).

"How much have I spent this month" and "what's my biggest expense" found
nothing, or quoted the spending note whole: the answer is a sum or a
maximum of the amounts the notes hold, so it is computed here and every
figure is cited to the sentence it came from. Money owed, lent or earned is
not spending and is left out. A distance, a weight or a stretch of time
is added up the same way, in the unit table the converter uses ("how far
did I run", "how many hours did I spend on the deck"). No model, and the
same with one on.
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
_KIND_SPENT = re.compile(r"^(?:how much|what(?:'s|s| is)?) (?:my |our )?(?:recorded |paid )?(?P<tail>\S.*)$", re.I)
_KIND_NOUNS = frozenset({"spending", "expense", "expenses", "cost", "costs"})
_KIND_RECORDED = re.compile(r"^(?:have|did|do) (?:i|we) (?:recorded|logged|noted|tracked|got|have)\b", re.I)


def _kind_spent(q: str) -> tuple[str, str] | None:
    """(subject, rest) of "how much grocery spending have I recorded", or
    None. The noun is found word by word, not by a pattern that could split
    the subject many ways (CodeQL)."""
    m = _KIND_SPENT.match(q)
    words = m.group("tail").split(" ") if m else []
    at = next((i for i, w in enumerate(words) if w.lower().rstrip("?.!,") in _KIND_NOUNS), 0)
    if at < 1 or not all(re.fullmatch(r"[\w'-]+", w) for w in words[:at]):
        return None
    rest = " ".join(words[at + 1:])
    recorded = _KIND_RECORDED.match(rest)
    return " ".join(words[:at]), rest[recorded.end():] if recorded else (" " + rest if rest else "")


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
_DATE_TAIL = re.compile(r"(?<!\s)\s+(?:on|in|at|from|for)\s+.*$", re.I)


class Item(NamedTuple):
    label: str
    symbol: str
    value: float
    view: object
    sentence: object


_VERB = re.compile(r"^(?:i\s+)?(?:paid|spent|bought|cost|was|were|aud|usd|gbp|eur|nzd|cad)\b\s*", re.I)
#: Word by word: a blank run is split one way only (CodeQL).
_AFTER = re.compile(r"^\s*(?:for|on|at|to)\s+(?P<what>[\w'-]+(?:\s+[\w'-]+)*?)(?:\s+(?:to|because|as|in|on)\b.*)?\s*$", re.I)


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


def _one_of_several(items: list, views: list, month: int | None, subject: list[str]) -> bool:
    """One amount in a note of several, with no refund or balance beside it:
    nothing to add up, so the digest says it with its week and what sits
    beside it (gold answer 15)."""
    if len(items) != 1 or len(recognise.amounts(" ".join(s.text for s in items[0].view.sentences))) <= 1:
        return False
    return not _items(views, month, subject, refunds=True) and not _still_due(views, month, subject)


def _spent_line(items: list, symbol: str, on: str, when: str) -> tuple[str, float]:
    """The total said once, by note or by label within one note, and the total."""
    by_note: dict[str, float] = {}
    for item in items:
        name = composer_lists._title(item.view)  # noqa: SLF001
        by_note[name] = by_note.get(name, 0) + item.value
    total = sum(by_note.values())
    if len(items) == 1:
        name = next(iter(by_note))
        what = "" if items[0].label == name else f" for {items[0].label}"
        return f"You paid {_money(symbol, total)}{what}, going by {name}.", total
    if len(by_note) == 1:
        by_label: dict[str, float] = {}
        for item in items:
            by_label[item.label] = by_label.get(item.label, 0) + item.value
        listed = _listed([f"{label.lower() if i else label} {_money(symbol, v)}" for i, (label, v) in enumerate(by_label.items())])
        return f"You spent {_money(symbol, total)}{on}{when}, going by {next(iter(by_note))}: {listed}.", total
    listed = _listed([f"{name} {_money(symbol, v)}" for name, v in by_note.items()])
    return f"Your notes record {_money(symbol, total)} spent{on}{when}: {listed}.", total


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
    if _one_of_several(items, views, month, subject):
        return False
    line, total = _spent_line(items, symbol, on, when)
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
    if (kind := _kind_spent(q)) and not re.search(r"\b(?:did|do|does|i|we)\b", kind[0], re.I):
        return f"{kind[0]} {kind[1]}"
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


#: A measure asked by its dimension's word or by a unit: "how far did I run",
#: "how many km have I walked", "what's my total distance".
_MEASURE = re.compile(
    r"^(?:how (?P<far>far)|how (?:many|much) (?P<unit>[a-zµ]+)|how (?P<long>long)(?= (?:have|did) (?:i|we) (?:spen[dt]|practi[sc]ed|worked|studied)\b)"
    r"|what(?:'s|s| is| was)? (?:my |our |the )?total (?P<noun>distance|weight|time))(?P<rest>(?: .*)?)$",
    re.I,
)
#: "How many km did I run on Sunday" is one day's value, the slot's to read.
_ONE_DAY = re.compile(r"\b(?:mon|tues|wednes|thurs|fri|satur|sun)day\b|\b(?:today|yesterday|tonight|last night|this morning)\b", re.I)
_CALENDAR = frozenset({"day", "days", "week", "weeks", "fortnight", "fortnights", "month", "months", "year", "years"})
_DIMENSION_WORDS = {"far": "length", "distance": "length", "weight": "mass", "time": "time", "long": "time"}
_DOER = re.compile(r"^\s*(?:(?:did|have|had|do) (?:i|we)|i've|i have|we've) (?P<verb>[a-z]+)\b(?P<after>.*)$", re.I)
#: Verbs that say a measure was recorded, not what was done: no filter.
_ANY_VERB = frozenset({"spend", "spent", "been", "got", "get", "done", "do", "logged", "recorded", "noted", "tracked", "put", "had", "have"})
_PAST = {"run": ("ran", "run"), "swim": ("swam", "swum"), "ride": ("rode", "ridden"), "drive": ("drove", "driven"), "lose": ("lost", "lost"), "gain": ("gained", "gained")}
_BASE = {forms[0]: verb for verb, forms in _PAST.items()} | {forms[1]: verb for verb, forms in _PAST.items()}


class _Measure(NamedTuple):
    dimension: str
    unit: str
    verb: str
    after: str


def _dimension_of(word: str) -> tuple[str | None, bool]:
    """"far" is a length and "km" one by the unit table; "pounds" is money's."""
    named = recognise.UNITS.get(word) if word not in recognise.CURRENCY_NAMES and len(word) > 1 else None
    return _DIMENSION_WORDS.get(word) or (named[0] if named and named[0] != "temperature" else None), bool(named)


def _measure_asked(q: str) -> _Measure | None:
    """The dimension, the unit asked, the doing verb and the rest, or None."""
    m = _MEASURE.match(q)
    if not m:
        return None
    word = (m.group("far") or m.group("long") or m.group("noun") or m.group("unit")).lower()
    dimension, named = _dimension_of(word)
    if not dimension:
        return None
    doer = _DOER.match(m.group("rest"))
    #: "How many days until..." and "how far is the station" are a day and a
    #: fact, not a sum: a sum is asked of something done.
    if not doer and not m.group("noun") or word in _CALENDAR or _ONE_DAY.search(m.group("rest")):
        return None
    verb = doer.group("verb").lower() if doer and doer.group("verb").lower() not in _ANY_VERB else ""
    return _Measure(dimension, word if named else "", _BASE.get(verb, verb), doer.group("after") if doer else m.group("rest"))


def _forms(verb: str) -> set[str]:
    """"run": ran, runs, running, run; "cycle": cycled, cycling."""
    stem = verb[:-1] if verb.endswith("e") else verb
    double = verb + verb[-1] if re.fullmatch(r"[^aeiou]*[aeiou][^aeiouwy]", verb) else verb
    return {verb, verb + "s", stem + "ed", stem + "ing", double + "ing", double + "ed", *_PAST.get(verb, ())}


def _done(verb: str) -> str:
    if verb in _PAST:
        return _PAST[verb][1]
    return verb + ("d" if verb.endswith("e") else "ed")


def _measured(views: list, asked: _Measure, month: int | None, subject: list[str]) -> list[Item]:
    forms = _forms(asked.verb) if asked.verb else set()
    found = []
    for view in views:
        if not _in_month(view, month):
            continue
        for sentence in view.sentences:
            said = set(re.findall(r"[a-z]+", (sentence.text + " " + str(view.title)).lower()))
            if _about(view, sentence, subject) and (not forms or forms & said):
                found += [Item(composer_lists._title(view), unit, value, view, sentence) for dim, value, unit, _ in recognise.measures(sentence.text) if dim == asked.dimension]  # noqa: SLF001
    return found


def _figure(value: float, unit: str) -> str:
    size = recognise.UNITS[unit][1]
    shown = f"{value / size:,.2f}".rstrip("0").rstrip(".")
    name = recognise.UNITS[unit][2] if len(unit) == 1 else unit
    return f"{shown} {name[:-1] if shown == '1' and name.endswith('s') and len(name) > 3 else name}"


def _measures_line(items: list[Item], unit: str, tail: str) -> str:
    by_note: dict[str, float] = {}
    for item in items:
        by_note[item.label] = by_note.get(item.label, 0) + item.value
    total = _figure(sum(by_note.values()), unit)
    if len(by_note) == 1:
        return f"Your notes record {total}{tail}, going by {items[0].label}: {_listed([_figure(i.value, i.symbol) for i in items])}."
    ranked = sorted(by_note.items(), key=lambda kv: -kv[1])
    return f"Your notes record {total}{tail}: {_listed([f'{name} {_figure(v, unit)}' for name, v in ranked])}."


def _measure(out, asked: _Measure, views: list, today: date) -> bool:  # noqa: ANN001
    month = _month_asked(asked.after, today)
    subject, said = _subject(asked.after)
    prep = re.match(r"\s*(on|for|with|to|at|in)\s", asked.after)
    tail = (f" {_done(asked.verb)}" if asked.verb else "") + (f" {prep.group(1) if prep else 'on'} {said}" if said else "") + (f" in {date(2000, month, 1):%B}" if month else "")
    items = _measured(views, asked, month, subject)
    if not items:
        out.lines.append(f"I found no {asked.unit or _DIMENSION_NOUN[asked.dimension]}{tail} in your notes.")
        return True
    unit = asked.unit if asked.unit and len(asked.unit) > 1 else max(items, key=lambda i: i.value).symbol
    line = _measures_line(items, unit, tail)
    out.lines.append(line)
    _cite_all(out, items, line)
    return True


_DIMENSION_NOUN = {"length": "distance", "mass": "weight", "time": "time", "volume": "volume", "area": "area", "speed": "speed"}


def asks(question: str) -> bool:
    q = " ".join(composer_lists._q(question).split())  # noqa: SLF001
    if _total_asked(q) is not None or _DUE_ASK.match(q) or _measure_asked(q):
        return True
    m = _MOST.match(q)
    return bool(m and set(m.group(2).lower().rstrip("?. ").split()) & _MONEY_NOUNS)


def sums_a_measure(question: str) -> bool:
    """"How many km have I run" is a sum, asked before the one-value slots
    ("how many km is the walk") read a single sentence."""
    return _measure_asked(" ".join(composer_lists._q(question).split())) is not None  # noqa: SLF001


def records_amounts(text: str) -> bool:
    """A note that names spending or a refund and holds an amount, or holds a measure."""
    return bool(recognise.amounts(text) and (_SPENDING.search(text) or _REFUND.search(text))) or bool(recognise.measures(text))


def answer(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    """A sum or a maximum of the amounts spent; False when `asked` is not one."""
    q = " ".join(composer_lists._q(asked).split())  # noqa: SLF001
    if measure := _measure_asked(q):
        return _measure(out, measure, views, today)
    if (rest := _total_asked(q)) is not None:
        return _spent(out, rest, views, today)
    if m := _DUE_ASK.match(q):
        return _due(out, f"{m.group('subject') or ''} {m.group('rest')}", views, today)
    if m := _MOST.match(q):
        return _most(out, m.group(1), m.group(2), views)
    return False
