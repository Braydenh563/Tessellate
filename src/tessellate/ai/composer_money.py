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
from datetime import date, timedelta
from typing import NamedTuple

from tessellate.ai import composer, composer_lists, recognise

#: "How much money have I recorded I've spent" and "what have I spent so far"
#: are the same total: the ask can say where the figures are kept.
_SPENT = re.compile(
    r"^(?:how much|what) (?:money )?(?:have|did|do|has) (?:i|we) "
    r"(?:(?:really|actually|ever|just|already|even) )?(?:(?:recorded|logged|noted|tracked|written(?: down)?|put down)(?: (?:that|as))? (?:(?:i|we)(?:'ve| have|ve)? )?)?"
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
    r"^(?:and )?(?:what(?:'s|s| is| was)? )?(?:my |our |the )?(?:total|net|gross) (?:of )?(?:all )?(?:(?:what|that) (?:i|we)(?:'ve| have)? )?(?:my |the )?(?:recorded )?(?:outgoing )?"
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
#: A goal or a plan is not a measure done: "Q1: run a 10k" adds nothing.
_PLANNED = re.compile(r"\b(?:goals?|plan(?:s|ned|ning)?|targets?|want(?:s|ed)? to|aim(?:s|ing)? to|hope to|going to|will|should|wishlist)\b", re.I)
#: A stretch still to come, said of any quantity: "another 5 hours to go".
_DUE_LEFT = re.compile(
    r"\b(?:due|unpaid|owing|outstanding|remaining|to go|still (?:to|need|left|owed)|left (?:to|over|on|until|before))\b", re.I,
)
#: Words that make a clause no quantity done: a plan, a goal or budget, a
#: balance still to come, a refund (read apart and taken off).
_NOT_DONE = re.compile(_PLANNED.pattern + r"|\bbudget\w*|\blimits?\b|\baim\w*|" + _REFUND.pattern + "|" + _DUE_LEFT.pattern, re.I)
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


_LABEL_TAIL = frozenset({"is", "are", "was", "were", "cost", "costs", "about"})


def _what(clause: str, at: int, end: int, last: str) -> str:
    """What an amount bought: the words before it ("Groceries $86"), else the
    words after it ("Paid $42 for the plumber", "$24 at the market"), else
    the clause before's label."""
    before = clause[:at]
    while (cut := _VERB.sub("", before.strip())) != before.strip():
        before = cut
    words = [w for w in re.sub(r"[^\w\s'-]", " ", _DATE_TAIL.sub("", before)).split() if w.lower() not in ("and", "the", "a", "an", "my", "for")]
    #: "Flights cost $420" is flights, not "flights cost" (audit 1030 Z32).
    while words and words[-1].lower() in _LABEL_TAIL:
        words.pop()
    if words:
        return " ".join(words[-3:])
    after = _AFTER.match(clause[end:])
    #: "$112 on the 17th" is when, not what: it keeps the clause before's label.
    if not after or re.search(r"[0-9]", after.group("what")) or recognise.without_windows(after.group("what")) != after.group("what") or set(after.group("what").lower().split()) & recognise.MONTH_NAMES:
        return last
    return re.sub(r"^my\b", "your", after.group("what").strip())


def _moved(clause: str, said: list) -> bool:
    """"Discounted from $150 to $68": the first figure is where it was, the
    last is where it went."""
    between = clause[said[0].end:said[1].at]
    return bool(re.search(r"\bfrom\s+(?:[A-Z]{3}\s*)?$", clause[:said[0].at], re.I) and re.fullmatch(r"\s*(?:down |up )?to\s*(?:[A-Z]{3}\s*)?", between, re.I))


def _read(text: str, dimension: str = "money") -> list:
    """The measures of one dimension in `text`, left to right: money is read
    by the same reader as a distance or a stretch of time."""
    return [m for m in recognise.measures(text) if m[0] == dimension]


def _clause_items(view, sentence, refunds: bool, dimension: str = "money") -> list[Item]:  # noqa: ANN001
    found: list[Item] = []
    last = ""
    for clause in re.split(r"[;,.](?!\d)|\band\b", sentence.text):
        said = _read(clause, dimension)
        if not said or bool(_REFUND.search(clause)) != refunds or (not refunds and (_NOT_SPENT if dimension == "money" else _NOT_DONE).search(clause)):
            continue
        #: "Discounted from $150 to $68": what was paid is where the price went.
        pick = said[-1] if len(said) > 1 and _moved(clause, said) else said[0]
        last = _what(clause, pick.at, pick.end, last) or composer_lists._title(view)  # noqa: SLF001
        found.append(Item(last, pick[2], pick[1], view, sentence))
    return found


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


class _Win(NamedTuple):
    """The window a question names: a month of a year, or a span of days."""

    month: int | None = None
    span: tuple | None = None
    said: str = ""
    year: int | None = None


def _note_month(view) -> tuple[int | None, int | None]:  # noqa: ANN001
    """(year, month) a note's title names ("Spending October"): its month,
    in the year it was written, or the one before when the month is later
    than the day it was written ("December" written on 2 January)."""
    named = [recognise._MONTHS[w] for w in re.findall(r"[a-z]+", str(view.title).lower()) if w in recognise.MONTH_NAMES]  # noqa: SLF001
    if not named:
        return None, None
    month, written = named[0], view.written
    return (written.year - (1 if month > written.month + 1 else 0) if written else None), month


def _month_dates(views: list, month: int) -> list[date]:
    """The months of `month` the notes are of, as the first of each."""
    found = []
    for view in views:
        year, named = _note_month(view)
        if named == month and year:
            found.append(date(year, month, 1))
        elif named is None and view.written and view.written.month == month:
            found.append(date(view.written.year, month, 1))
    return found


def _year_of(rest: str, month: int, today: date, views: list) -> int:
    """The year a month asked means: the one said ("October 2025", "last
    year"), else the latest year the notes hold that month, else the most
    recent one that has begun."""
    low = rest.lower()
    if said := re.search(r"\b(20\d\d)\b", low):
        return int(said.group(1))
    if "last year" in low:
        return today.year - 1
    if "this year" in low or "this month" in low:
        return today.year
    if "last month" in low:
        return today.year - (1 if month > today.month else 0)
    held = [d.year for d in _month_dates(views, month) if d <= today]
    return max(held) if held else today.year - (1 if month > today.month else 0)


def _window_asked(rest: str, today: date, views: tuple | list = ()) -> _Win | None:
    """"in October", "this month", "last week", "this year": the notes that
    count, or None for all of them."""
    month = _month_asked(rest, today)
    if month is not None:
        year = _year_of(rest, month, today, list(views))
        return _Win(month=month, said=f"in {date(2000, month, 1):%B}" + (f" {year}" if year != today.year else ""), year=year)
    for _s, _e, phrase in recognise.find(rest.lower()):
        if got := recognise.span(phrase, today, "past"):
            return _Win(span=got, said=phrase.lower().strip())
    return None


def _in_month(view, month: int | None, year: int | None = None) -> bool:  # noqa: ANN001
    """Whether a note is of a month: by the month its title names, else by
    the day it was written; of the year asked, when one is."""
    if month is None:
        return True
    named_year, named = _note_month(view)
    if named is not None:
        return named == month and (year is None or named_year is None or named_year == year)
    return bool(view.written and view.written.month == month and (year is None or view.written.year == year))


def _months_of(first: date, last: date) -> set[tuple[int, int]]:
    months, day = set(), first.replace(day=1)
    while day <= last:
        months.add((day.year, day.month))
        day = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return months


def _in_window(view, win: _Win | None) -> bool:  # noqa: ANN001
    """Whether a note belongs to the window: by the month its title names,
    else by the day it was written."""
    if win is None:
        return True
    if win.span is None:
        return _in_month(view, win.month, win.year)
    first, last, grain = win.span
    year, named = _note_month(view)
    if named and grain in ("month", "year"):
        return (year, named) in _months_of(first, last) if year else named in {m for _y, m in _months_of(first, last)}
    return bool(view.written and first <= view.written <= last)


def _about(view, sentence, subject: list[str], test=all) -> bool:  # noqa: ANN001
    """Whether an amount is about the asked subject: its sentence, its note's
    title, tags or category name it ("the plumber", #groceries, "eating out"
    for #eating-out)."""
    if not subject:
        return True
    have = set(sentence.words) | set(view.title_words) | set(view.filed_words)
    #: A compound names its stem: "books" finds "Bookshop receipt", "rent" "Rental bond".
    return test(st in have or (len(st) >= 4 and any(w.startswith(st) for w in have)) for st in subject)


def _items(views: list, win: _Win | None = None, subject: list[str] | None = None, refunds: bool = False, dimension: str = "money", forms: frozenset = frozenset()) -> list[Item]:
    """The quantities about every subject word, else about any of them ("your
    hotel bill" when no note says "bill")."""
    return _items_by(views, win, subject, refunds, all, dimension, forms) or (_items_by(views, win, subject, refunds, any, dimension, forms) if subject and len(subject) > 1 else [])


def _noted(views: list, dimension: str) -> list:
    """Money is read in the notes that are about spending; another quantity in any note."""
    if dimension != "money":
        return views
    return [v for v in views if _SPENDING.search(str(v.title) + " " + " ".join(s.text for s in v.sentences[:3])) or _REFUND.search(str(v.title))]


def _is_done(view, sentence, dimension: str, forms: frozenset) -> bool:  # noqa: ANN001
    """A quantity other than money counts when its sentence is no plan and
    says the doing asked ("ran", "run"); money counts wherever it stands."""
    if dimension == "money":
        return True
    said = set(re.findall(r"[a-z]+", (sentence.text + " " + str(view.title)).lower()))
    return (not forms or bool(forms & said)) and not _PLANNED.search(sentence.text + " " + str(view.title))


def _items_by(views: list, win: _Win | None, subject: list[str] | None, refunds: bool, test, dimension: str = "money", forms: frozenset = frozenset()) -> list[Item]:  # noqa: ANN001
    found = []
    for view in sorted(_noted(views, dimension), key=lambda v: v.rank):
        if _in_window(view, win):
            for sentence in view.sentences:
                if _about(view, sentence, subject or [], test) and _is_done(view, sentence, dimension, forms):
                    items = _clause_items(view, sentence, refunds, dimension)
                    #: "$84 on groceries and $35 on fuel": the sentence is
                    #: about groceries, its fuel is not.
                    named = [i for i in items if subject and any(st in set(composer._words(i.label)) for st in subject)]  # noqa: SLF001
                    found.extend(named or items)
    return found


def _still_due(views: list, win: _Win | None, subject: list[str], dimension: str = "money") -> list[Item]:
    return _due_by(views, win, subject, all, dimension) or (_due_by(views, win, subject, any, dimension) if len(subject) > 1 else [])


#: A balance or a stretch still to come: money says "another $160 is due",
#: any other quantity "another 5 hours to go" or "8 km left".
_DUE_CLAUSE = re.compile(r"\b(?:another|balance|due|unpaid)\b", re.I)


def _due_by(views: list, win: _Win | None, subject: list[str], test, dimension: str = "money") -> list[Item]:  # noqa: ANN001
    due = []
    money = dimension == "money"
    said, clause_words = (_STILL_DUE, _DUE_CLAUSE) if money else (_DUE_LEFT, _DUE_LEFT)
    for view in views:
        if not _in_window(view, win) or (money and not _SPENDING.search(" ".join(s.text for s in view.sentences))):
            continue
        for sentence in view.sentences:
            if _about(view, sentence, subject, test) and said.search(sentence.text):
                due.extend(
                    Item(composer_lists._title(view), found[0][2], found[0][1], view, sentence)  # noqa: SLF001
                    for clause in re.split(r"[;,.](?!\d)", sentence.text)
                    if (found := _read(clause, dimension)) and clause_words.search(clause)
                )
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
    r"net|gross|total|(?:that )?(?:have|has|with) amounts?|(?:in |during |for |on |over |across |throughout )?(?:" + "|".join(sorted(recognise.MONTH_NAMES - {"may"})) + r")(?:\s+(?:of\s+)?20\d\d)?|(?:in |of |during )?(?:this|last) year|(?:in |of )20\d\d)\b",
    re.I,
)
_STOP = frozenset(composer._words("me my i in on for of the a an to have has did do is it that from all money spent spend spending paid pay amounts amount outgoing payments payment expenses expense notes note these this and with you your"))  # noqa: SLF001


_AUX = frozenset("is are was were am be been being do does did have has had there it actually really recorded logged noted tracked".split())


def _subject(rest: str) -> tuple[list[str], str]:
    """The stems of what the money went on, and those words as typed ("the plumber")."""
    said = " ".join(_WINDOW.sub(" ", recognise.without_windows(re.sub(r"\b(?:of )?20\d\d\b", " ", re.sub(r"[^\w\s'-]", " ", rest)))).split())
    said = re.sub(r"^(?:on|for|to|in)\s+", "", said, flags=re.I)
    said = re.sub(r"\bmy\b", "your", said, flags=re.I)
    #: "book spending is actually recorded": the subject stops at the verb.
    words = said.split()
    said = " ".join(words[:next((i for i, w in enumerate(words) if w.lower() in _AUX), len(words))])
    stems = [w for w in composer._words(said) if w not in _STOP]  # noqa: SLF001
    return stems, said if stems else ""


def _listed(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _one_of_several(items: list, views: list, win: _Win | None, subject: list[str]) -> bool:
    """One amount in a note of several, with no refund or balance beside it:
    nothing to add up, so the digest says it with its week and what sits
    beside it (gold answer 15)."""
    if len(items) != 1 or len(_read(" ".join(s.text for s in items[0].view.sentences))) <= 1:
        return False
    return not _items(views, win, subject, refunds=True) and not _still_due(views, win, subject)


#: What an untitled note says was bought ("I just bought a new gaming mouse
#: discounted from $150 to $68": "a new gaming mouse"), its name in a list of
#: spending rather than the whole sentence with its old price (INBOX 1456).
_BOUGHT = re.compile(
    r"\b(?:bought|purchased|ordered|got|paid for)\s+(?P<what>(?:(?!for|at|from|on|discounted|reduced|marked|haha|lol)[\w'-]+\s?){1,5})",
    re.I,
)


def _note_name(view) -> str:  # noqa: ANN001
    if not view.titled and (m := _BOUGHT.search(str(view.note.get("content") or ""))):
        return m.group("what").strip()
    return composer_lists._title(view)  # noqa: SLF001


def _spent_line(items: list, symbol: str, on: str, when: str) -> tuple[str, float]:
    """The total said once, by note or by label within one note, and the total."""
    by_note: dict[str, float] = {}
    for item in items:
        name = _note_name(item.view)
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


_PAID = re.compile(r"\b(?:paid|spent|bought|booked|purchased|ordered|charged|got)\b", re.I)


def _planned(view, today: date) -> bool:  # noqa: ANN001
    """A note about something still ahead (a dated trip) that says nothing was
    paid: its amounts are prices, not spending (audit 1030 Z30)."""
    return not any(_PAID.search(s.text) for s in view.sentences) and bool(composer_lists._dated(view, today, "future"))  # noqa: SLF001


def spent_only(items: list[Item], today: date) -> list[Item]:
    """`items` without the amounts of notes that are plans."""
    plans: dict[int, bool] = {}
    return [i for i in items if not plans.setdefault(id(i.view), _planned(i.view, today))]


def _only_priced(out, items: list[Item]) -> bool:  # noqa: ANN001
    """Every amount found sits in a note about something ahead: said as a
    price, not as money spent."""
    parts = [f"{i.label.lower()} {_money(i.symbol, i.value)}" for i in items]
    line = f"Nothing says that was paid yet; your notes price it: {_listed(parts)}."
    out.lines.append(line)
    _cite_all(out, items, line)
    return True


def _spent(out, rest: str, views: list, today: date) -> bool:  # noqa: ANN001
    win = _window_asked(rest, today, views)
    subject, said = _subject(rest)
    every = _items(views, win, subject)
    items = spent_only(every, today)
    if every and not items:
        return _only_priced(out, every)
    when = f" {win.said}" if win else ""
    on = f" on {said}" if said else ""
    if not items:
        out.lines.append(f"I found no amounts spent{on}{when} in your notes.")
        return True
    signs = list(dict.fromkeys(i.symbol for i in items))
    if len(signs) == 1 and _one_of_several(items, views, win, subject):
        return False
    for sign in signs:
        #: Each currency is said on its own, never dropped or added to another.
        mine = [i for i in items if i.symbol == sign]
        line, total = _spent_line(mine, sign, on, when)
        out.lines.append(line)
        _cite_all(out, mine, line)
        _refunds_and_due(out, views, win, subject, "money", sign, total)
    return True


def _say(unit: str, value: float) -> str:
    """A figure said in its unit: "$1,200", "13.5 km"."""
    return _money(unit, value) if unit in _SIGNS else _figure(value, unit)


_SIGNS = frozenset("$£€¥")


def _refunds_and_due(out, views: list, win: _Win | None, subject: list[str], dimension: str, unit: str, total: float) -> None:  # noqa: ANN001
    """A refund taken off, with the net; a balance still due, named and not
    counted. Said of any quantity (a refund of hours, a stretch still to go)."""
    def mine(items: list[Item]) -> list[Item]:
        return [i for i in items if dimension != "money" or i.symbol == unit]

    back = mine(_items(views, win, subject, refunds=True, dimension=dimension))
    if back:
        off = sum(i.value for i in back)
        line = f"Less {_say(unit, off)} refunded ({_listed(sorted({composer_lists._title(i.view) for i in back}))}), that is {_say(unit, total - off)} net."  # noqa: SLF001
        out.lines.append(line)
        _cite_all(out, back, line)
    if due := mine(_still_due(views, win, subject, dimension)):
        line = _due_line(due, bool(subject), dimension, unit, total)
        out.lines.append(line)
        _cite_all(out, due, line)


def _due_line(due: list[Item], named: bool, dimension: str, unit: str, total: float) -> str:
    """A balance still due, added to the total when the ask named a subject."""
    if not named:
        return f"Not counted: {_listed([f'{_say(unit, i.value)} still due ({i.label})' for i in due])}."
    owed = sum(i.value for i in due)
    paid = " once that is paid" if dimension == "money" else ""
    return f"Another {_say(unit, owed)} is still {'due' if dimension == 'money' else 'to go'} ({_listed(sorted({i.label for i in due}))}), so {_say(unit, total + owed)} all up{paid}."


def _most(out, size: str, noun: str, views: list) -> bool:  # noqa: ANN001
    if not set(noun.lower().rstrip("?. ").split()) & _MONEY_NOUNS:
        return False
    items = _items(views)
    if not items:
        out.lines.append("I found no amounts spent in your notes.")
        return True
    for sign in dict.fromkeys(i.symbol for i in items):
        #: The most of each currency: a dollar is not weighed against a pound.
        pick = (min if size.lower() in _SMALL else max)((i for i in items if i.symbol == sign), key=lambda i: i.value)
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
    if m := _LISTING.match(q):
        return " ".join(x.strip() for x in m.groups() if x and x.strip())
    return _bare_total(q)


#: "What expenses have I recorded", "list my purchases", "what have I bought"
#: (INBOX 1456): a list of what was spent is the sum with its items named.
_LISTING = re.compile(
    r"^(?:what|which) ([\w'-]+ )?(?:expenses|purchases|payments|costs|bills|spending) (?:have|did|do) (?:i|we) "
    r"(?:recorded|logged|noted|tracked|made|had|written down|got)\b(.*)$"
    r"|^(?:list|show)(?: me)? (?:all )?(?:my|our|the) (?:recorded )?([\w'-]+ )?(?:expenses|purchases|payments|spending)\b(.*)$"
    r"|^what (?:have|did) (?:i|we) (?:bought|buy|purchased|purchase|paid for|pay for)\b(.*)$",
    re.I,
)

_ALL_UP = ("all up", "altogether", "in total", "overall")
_NOT_A_THING = frozenset({"is", "are", "was", "were", "did", "do", "does", "have", "has", "had", "i", "we", "money", "time", "can", "should", "will", "would"})


def _bare_total(q: str) -> str | None:
    """"How much desk all up after that money back thing": a thing and a
    total word with no verb, read word by word (CodeQL); "money back" is a
    refund (stress run 2026-10-30)."""
    low = q.lower()
    at = min((i for i in (low.find(f" {w}") for w in _ALL_UP) if i > 0), default=-1)
    if not low.startswith("how much ") or at < 0:
        return None
    thing = low[len("how much "):at].split()
    if not thing or set(thing) & _NOT_A_THING or not all(re.fullmatch(r"[\w'-]+", w) for w in thing):
        return None
    rest = re.sub(r"\b(?:(?:that|the) )?money back(?: thing)?\b", "refunds", q[at:], flags=re.I)
    return f"{' '.join(thing)} {rest}"


def _unit_of(items: list[Item], dimension: str, asked: str = "") -> str:
    """The unit a total is said in: the one asked by name, else the largest
    written ("km" over "m"); money's is its sign."""
    if dimension == "money":
        return items[0].symbol
    return asked if len(asked) > 1 else max(items, key=lambda i: i.value).symbol


def _due(out, rest: str, views: list, today: date, dimension: str = "money", asked: str = "") -> bool:  # noqa: ANN001
    subject, said = _subject(rest)
    due = _still_due(views, None, subject, dimension)
    if not due:
        out.lines.append(f"I found nothing still {'to pay' if dimension == 'money' else 'to go'}{' for ' + said if said else ''} in your notes.")
        return True
    unit = _unit_of(due, dimension, asked)
    due = [i for i in due if dimension != "money" or i.symbol == unit]
    owed = "to pay" if dimension == "money" else "to go"
    if len(due) == 1:
        line = f"{_say(unit, due[0].value)} is still {owed}, going by {due[0].label}."
    else:
        line = f"{_say(unit, sum(i.value for i in due))} is still {owed}: {_listed([f'{_say(unit, i.value)} ({i.label})' for i in due])}."
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


def _one_day(rest: str) -> bool:
    """"How many km did I run on Sunday" is one day's value, the slots' to
    read. The anchor only places the day; whether it is one does not move."""
    return any((got := recognise.span(phrase, date(2026, 1, 5), "past")) and got[0] == got[1] for _s, _e, phrase in recognise.find(rest.lower()))


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
    if not doer and not m.group("noun") or word in _CALENDAR or _one_day(m.group("rest")):
        return None
    verb = doer.group("verb").lower() if doer and doer.group("verb").lower() not in _ANY_VERB else ""
    return _Measure(dimension, word if named else "", _BASE.get(verb, verb), doer.group("after") if doer else m.group("rest"))


def _one_short_vowel(verb: str) -> bool:
    """One vowel, second from last, then a consonant ("run", "stop"): the
    last letter doubles before -ing. Said without a regex (CodeQL 1872)."""
    vowels = [i for i, c in enumerate(verb) if c in "aeiou"]
    return len(verb) >= 2 and vowels == [len(verb) - 2] and verb[-1] not in "aeiouwy"


def _forms(verb: str) -> set[str]:
    """"run": ran, runs, running, run; "cycle": cycled, cycling."""
    stem = verb[:-1] if verb.endswith("e") else verb
    double = verb + verb[-1] if _one_short_vowel(verb) else verb
    return {verb, verb + "s", stem + "ed", stem + "ing", double + "ing", double + "ed", *_PAST.get(verb, ())}


def _done(verb: str) -> str:
    if verb in _PAST:
        return _PAST[verb][1]
    return verb + ("d" if verb.endswith("e") else "ed")


def _figure(value: float, unit: str) -> str:
    size = recognise.UNITS[unit][1]
    shown = f"{value / size:,.2f}".rstrip("0").rstrip(".")
    #: "10k" is said "10 km"; another glued letter by its name ("800m", 800 metres).
    name = unit if len(unit) > 1 else "km" if unit == "k" else recognise.UNITS[unit][2]
    #: "40 hour goal" is said "40 hours".
    name = recognise.UNITS[unit][2] if len(unit) > 1 and recognise.UNITS[unit][2] == unit + "s" else name
    return f"{shown} {name[:-1] if shown == '1' and name.endswith('s') and len(name) > 3 else name}"


def _measures_line(items: list[Item], unit: str, tail: str) -> str:
    by_note: dict[str, float] = {}
    for item in items:
        name = composer_lists._title(item.view)  # noqa: SLF001
        by_note[name] = by_note.get(name, 0) + item.value
    total = _figure(sum(by_note.values()), unit)
    if len(by_note) == 1:
        return f"Your notes record {total}{tail}, going by {next(iter(by_note))}: {_listed([_figure(i.value, i.symbol) for i in items])}."
    ranked = sorted(by_note.items(), key=lambda kv: -kv[1])
    return f"Your notes record {total}{tail}: {_listed([f'{name} {_figure(v, unit)}' for name, v in ranked])}."


def _measure(out, asked: _Measure, views: list, today: date) -> bool:  # noqa: ANN001
    win = _window_asked(asked.after, today, views)
    subject, said = _subject(asked.after)
    prep = re.match(r"\s*(on|for|with|to|at|in)\s", asked.after)
    tail = (f" {_done(asked.verb)}" if asked.verb else "") + (f" {prep.group(1) if prep else 'on'} {said}" if said else "") + (f" {win.said}" if win else "")
    items = _items(views, win, subject, dimension=asked.dimension, forms=frozenset(_forms(asked.verb) if asked.verb else ()))
    if not items:
        out.lines.append(f"I found no {asked.unit or _DIMENSION_NOUN[asked.dimension]}{tail} in your notes.")
        return True
    unit = _unit_of(items, asked.dimension, asked.unit)
    line = _measures_line(items, unit, tail)
    out.lines.append(line)
    _cite_all(out, items, line)
    _refunds_and_due(out, views, win, subject, asked.dimension, unit, sum(i.value for i in items))
    return True


_DIMENSION_NOUN = {"length": "distance", "mass": "weight", "time": "time", "volume": "volume", "area": "area", "speed": "speed"}


#: A stretch or a balance asked as what is left: "how many hours are left on
#: the deck", "how many hours do I have left", "how much time is still to go".
#: Money's own wording is `_DUE_ASK`.
_LEFT_ASK = re.compile(
    r"^how (?:(?P<far>far)|(?:many|much) (?P<unit>[a-zµ]+))\b(?P<subject>(?: (?!(?:is|are|do|does|have|has|will|would|can|did|left|remain|remains)\b)[\w'-]+)*?)"
    r"(?: (?:is|are|do i have|do we have|have i got|remain|remains))? (?:still )?(?:left|remaining|remain|to go|outstanding|owing|due)\b(?P<rest>.*)$",
    re.I,
)
#: "How many days are left until Christmas" is a day, not a stretch to go.
_UNTIL = re.compile(r"\b(?:until|till|before|by)\b", re.I)


def _left_asked(q: str) -> tuple[str, str, str] | None:
    """(dimension, the unit asked, the rest) of "how many hours are left on
    the deck", or None; money's "how much is left on the bill" is not one."""
    m = _LEFT_ASK.match(q)
    if not m or _UNTIL.search(m.group("rest")):
        return None
    word = (m.group("far") or m.group("unit")).lower()
    dimension, named = _dimension_of(word)
    if not dimension or word in _CALENDAR:
        return None
    return dimension, word if named else "", f"{m.group('subject')} {m.group('rest')}"


_DEFAULT_UNIT = {"length": "km", "mass": "kg", "time": "hours", "volume": "litres", "money": "$"}
_CEILING = frozenset({"budget", "limit", "cap"})
_TARGET_WORD = re.compile(r"\b(goal|target|budget|limit|cap|aim)s?\b", re.I)
_TARGET_ASK = re.compile(r"^(?:and )?how (?P<head>far|many|much|long|close|near)\b(?P<rest>.*)$", re.I)
#: What makes "how much is my budget" a question about a figure, and "how far
#: am I from my goal" one about the distance left to it.
_TARGET_CUE = re.compile(
    r"\b(?:short|left|remain\w*|to go|further|farther|more|away|off|until|before|toward\w*|from|reach\w*|hit|get(?:ting)? to|need|close|near|under|over|within|behind|ahead|past|beyond|exceed\w*|used|used up|against|spent|spend)\b",
    re.I,
)


class _Target(NamedTuple):
    dimension: str
    value: float | None
    unit: str
    noun: str
    forms: frozenset
    after: str


def _ing_forms(word: str) -> frozenset:
    """"walking": walk, walked, walks; "running": run, ran, runs."""
    stem = word[:-3]
    bases = {stem, stem + "e"} | ({stem[:-1]} if len(stem) > 2 and stem[-1] == stem[-2] else set())
    return frozenset(f for b in bases for f in _forms(b))


_NOT_A_DOING = frozenset({"still", "also", "really", "actually", "just", "now", "need", "want", "get", "ever", "even", "already", "managed", "got"})


def _target_verb(rest: str) -> frozenset:
    """The doing a goal is for, from "have I run" or "my walking target"."""
    if doer := re.search(r"\b(?:did|have|had|do) (?:i|we) ([a-z]+)\b", rest, re.I):
        verb = doer.group(1).lower()
        return frozenset(_forms(_BASE.get(verb, verb))) if verb not in _ANY_VERB | _NOT_A_DOING else frozenset()
    if ing := re.search(r"\b([a-z]{4,}ing) (?:goal|target|budget|limit|aim)", rest, re.I):
        return _ing_forms(ing.group(1).lower())
    return frozenset()


def _target_dimension(head: str, rest: str, figure: list, word: str) -> str | None:
    """What a goal is of: the figure's own dimension, else the head word
    ("far", "long"), the unit after it ("how many km"), else money for a budget."""
    first = rest.split()[0].lower() if rest.split() else ""
    if figure:
        return figure[0][0]
    return _DIMENSION_WORDS.get(head) or _dimension_of(first)[0] or ("money" if word in _CEILING else None)


def _target_asked(q: str) -> _Target | None:
    """"How far short of my 10k goal am I", "how many km left to my 50 km
    target", "how much of my $400 budget is left": the figure aimed at, the
    quantity it is of and the doing, or None. A money goal that is not a
    ceiling (a savings goal) is not spending's to answer."""
    m = _TARGET_ASK.match(q)
    if not m or _ABOUT_WORDS.search(q):
        return None
    rest = m.group("rest")
    noun = _TARGET_WORD.search(rest)
    if not noun or not _TARGET_CUE.search(q):
        return None
    word, figure = noun.group(1).lower(), recognise.measures(rest)
    dimension = _target_dimension(m.group("head").lower(), rest, figure, word)
    if not dimension or (dimension == "money" and word not in _CEILING):
        return None
    first = rest.split()[0].lower() if rest.split() else ""
    unit = figure[0][2] if figure else first if _dimension_of(first)[1] else ""
    return _Target(dimension, figure[0][1] if figure else None, unit, word, _target_verb(q), rest)


def _goal_in(views: list, dimension: str) -> Item | None:
    """The newest figure a note sets as a goal, target or budget."""
    goals = []
    for view in views:
        for sentence in view.sentences:
            if _TARGET_WORD.search(sentence.text + " " + str(view.title)):
                goals += [(bool(_TARGET_WORD.search(sentence.text)), view.written or date.min, Item(composer_lists._title(view), m[2], m[1], view, sentence)) for m in _read(sentence.text, dimension)]  # noqa: SLF001
    return max(goals, key=lambda g: g[:2])[2] if goals else None


def _adjective(unit: str, value: float) -> str:
    """A figure before a noun: "50 km", "40-hour", "$400"."""
    said = _say(unit, value)
    figure, _, name = said.partition(" ")
    return f"{figure}-{name[:-1]}" if name.endswith("s") and len(name) > 3 and unit not in _SIGNS else said


def _verdict(noun: str, aim: str, left: float, unit: str) -> str:
    if noun in _CEILING:
        return f"You have {_say(unit, left)} left of your {aim} {noun}." if left > 0 else f"You are {_say(unit, -left)} over your {aim} {noun}." if left < 0 else f"You have used all of your {aim} {noun}."
    return f"You are {_say(unit, left)} short of your {aim} {noun}." if left > 0 else f"You are {_say(unit, -left)} past your {aim} {noun}." if left < 0 else f"You have just reached your {aim} {noun}."


def _toward(out, ask: _Target, views: list, today: date) -> bool:  # noqa: ANN001
    """What is left of a goal, target or budget: the figure aimed at less the
    quantity the notes record, both cited."""
    win = _window_asked(ask.after, today, views)
    aim, goal = ask.value, None
    if aim is None:
        goal = _goal_in(views, ask.dimension)
        if goal is None:
            out.lines.append(f"I found no {ask.noun} figure in your notes.")
            return True
        aim = goal.value
    items = _items(views, win, [], dimension=ask.dimension, forms=ask.forms)
    pool = items or ([goal] if goal else [])
    unit = _unit_of(pool, ask.dimension, ask.unit) if pool else ask.unit or _DEFAULT_UNIT[ask.dimension]
    left: list[Item] = []
    if ask.dimension == "money":
        ([items], left) = _in_one_currency(items)
        unit = items[0].symbol if items else unit
    done = sum(i.value for i in items)
    out.lines.append(_verdict(ask.noun, _adjective(unit, aim), aim - done, unit))
    if items:
        line = _spent_line(items, unit, "", "")[0] if ask.dimension == "money" else _measures_line(items, unit, "")
        out.lines.append(line)
        _cite_all(out, items, line)
    if goal:
        _cite_all(out, [goal], out.lines[0])
    _left_out(out, left)
    return True


#: A difference between two stretches of the notes: "how much further did I
#: run than last week", "how much more did I spend in October than
#: September", "how much heavier am I this month than last month".
#: DOTALL and no `$`: the rest always matches, so a failed start cannot
#: rescan the tail (CodeQL 1873, polynomial on "than vs vs ...").
_LINK = re.compile(r"\s(?P<link>than|compared (?:to|with)|versus|vs\.?)\s+(?P<other>\S.*)", re.I | re.S)
_HOW = re.compile(r"^(?:and )?how (?:much|many)\b(?P<body>.*)$", re.I)
_DOING = re.compile(r"\b(?:did|have|had|do) (?:i|we) (?P<verb>[a-z]+)\b", re.I)
_MORE = {"more": "less", "further": "less", "farther": "less", "longer": "less", "heavier": "lighter"}
_LESS = {"less": "more", "fewer": "more", "lighter": "heavier", "shorter": "longer"}
_COMPARATIVE_DIMENSION = {"further": "length", "farther": "length", "heavier": "mass", "lighter": "mass", "longer": "time"}
#: What a doing is measured in, when the ask names no unit.
_VERB_DIMENSION = {
    "spend": "money", "pay": "money", "buy": "money",
    "run": "length", "walk": "length", "swim": "length", "ride": "length", "cycle": "length", "drive": "length", "hike": "length", "row": "length",
    "lift": "mass", "weigh": "mass", "lose": "mass", "gain": "mass",
    "work": "time", "study": "time", "practise": "time", "practice": "time", "sleep": "time",
}
_SPENT_FORMS = {"spent": "spend", "paid": "pay", "bought": "buy"}
_SIMPLE_PAST = {"spend": "spent", "pay": "paid", "buy": "bought"}


class _Diff(NamedTuple):
    dimension: str
    unit: str
    verb: str
    comparative: str
    being: str
    first: str
    second: str


def _names_window(text: str) -> bool:
    """Whether `text` names a month or a stretch of days, read against no clock."""
    return _month_asked(text, date(2000, 1, 1)) is not None or bool(recognise.find(text.lower()))


def _unit_named(body: str) -> tuple[str, str] | None:
    """The first real unit a question says ("km", "hours"): "in", "k" and
    "m" are units only glued to a number."""
    for word in re.findall(r"[a-zµ]+", body.lower()):
        dimension, named = _dimension_of(word)
        if named and dimension and word not in _CALENDAR and word not in recognise._GLUED_ONLY:  # noqa: SLF001
            return dimension, word
    return None


def _dimension_asked(body: str, comparative: str, verb: str) -> tuple[str | None, str]:
    """The dimension a difference is of: a distance, weight or time unit
    named; else money for spending; else another unit named, the doing
    ("run") or the comparative ("heavier")."""
    named = _unit_named(body)
    if named and named[0] in ("length", "mass", "time"):
        return named
    if _VERB_DIMENSION.get(verb) == "money":
        return ("time", "") if comparative == "longer" else ("money", "")
    return named or (_VERB_DIMENSION.get(verb) or _COMPARATIVE_DIMENSION.get(comparative), "")


def _difference_asked(q: str) -> _Diff | None:
    """The doing, the two windows and the comparative, or None. A comparison
    with no window after "than" ("a plane ticket than a train ticket") is
    not a difference of two sums."""
    link, how = _LINK.search(q), _HOW.match(q)
    if not link or not how or _ABOUT_WORDS.search(q) or not _names_window(link.group("other")):
        return None
    body = _LINK.sub("", how.group("body")).strip()
    comparative = next((w for w in re.findall(r"[a-z]+", body.lower()) if w in _MORE or w in _LESS), "")
    if not comparative and link.group("link").lower() == "than":
        return None
    doing = _DOING.search(body)
    verb = doing.group("verb").lower() if doing else ""
    verb = _SPENT_FORMS.get(verb, _BASE.get(verb, verb))
    dimension, unit = _dimension_asked(body, comparative, verb)
    if not dimension:
        return None
    return _Diff(dimension, unit, verb, comparative, "are" if re.search(r"\bam i\b", body, re.I) else "were" if re.search(r"\bwas i\b", body, re.I) else "", body, link.group("other"))


def _first_window(second: _Win, today: date) -> _Win | None:
    """"Than last week" compares with this week; "than September" with this month."""
    grain = second.span[2] if second.span else "month"
    return _window_asked({"week": "this week", "year": "this year", "day": "today"}.get(grain, "this month"), today)


def _past(verb: str, dimension: str) -> str:
    if verb in _PAST:
        return _PAST[verb][0]
    return _SIMPLE_PAST.get(verb) or ("spent" if dimension == "money" else verb + ("d" if verb.endswith("e") else "ed") if verb else "")


def _word_for(comparative: str, diff: float) -> str:
    """The comparative that is true of the difference: "further" for more, "less" for less."""
    comparative = "further" if comparative == "farther" else comparative
    up = comparative if comparative in _MORE else _LESS.get(comparative, "more")
    down = comparative if comparative in _LESS else _MORE.get(comparative, "less")
    return up if diff > 0 else down


def _side(items: list[Item], win: _Win, unit: str) -> str:
    if not items:
        return f"nothing recorded {win.said}"
    by_note: dict[str, float] = {}
    for item in items:
        name = composer_lists._title(item.view)  # noqa: SLF001
        by_note[name] = by_note.get(name, 0) + item.value
    return f"{_say(unit, sum(by_note.values()))} {win.said} ({_listed([f'{name} {_say(unit, v)}' for name, v in by_note.items()])})"


def _in_one_currency(*sets: list[Item]) -> tuple[list[list[Item]], list[Item]]:
    """The sets kept to the currency most of their amounts are in, and the
    amounts of any other, which the answer names and does not add."""
    both = [i for one in sets for i in one]
    if not both:
        return list(sets), []
    signs = list(dict.fromkeys(i.symbol for i in both))
    sign = max(signs, key=lambda g: sum(1 for i in both if i.symbol == g))
    return [[i for i in one if i.symbol == sign] for one in sets], [i for i in both if i.symbol != sign]


def _left_out(out, left: list[Item]) -> None:  # noqa: ANN001
    """"Not counted": an amount in another currency, named beside the total."""
    if left:
        line = f"Not counted, in another currency: {_listed([f'{_money(i.symbol, i.value)} ({composer_lists._title(i.view)})' for i in left])}."  # noqa: SLF001
        out.lines.append(line)
        _cite_all(out, left, line)


def _both_sets(d: _Diff, views: list, first: _Win, second: _Win) -> tuple[list[Item], list[Item], str, list[Item]]:
    """The items of each window, in one currency when money, the subject
    said, and the amounts left out for being in another."""
    drop = {*(_forms(d.verb) if d.verb else ()), d.comparative, d.unit, "did", "have", "had", "do", "am", "was", "i", "we", "much", "many"}
    subject, said = _subject(" ".join(w for w in d.first.split() if w.lower().strip("?.,") not in drop))
    forms = frozenset(_forms(d.verb)) if d.verb and d.dimension != "money" else frozenset()
    one, two = (_items(views, win, subject, dimension=d.dimension, forms=forms) for win in (first, second))
    left: list[Item] = []
    if d.dimension == "money":
        (one, two), left = _in_one_currency(one, two)
    return one, two, said, left


def _gap_line(d: _Diff, gap: float, unit: str, said: str, first: _Win, second: _Win, shown: float) -> str:
    on = f" on {said}" if said else ""
    if not gap:
        return f"Your notes record {_say(unit, shown)} both {first.said} and {second.said}{on}."
    lead = d.being or _past(d.verb, d.dimension) or "record"
    who = "You" if d.being or d.verb or d.dimension == "money" else "Your notes"
    return f"{who} {lead} {_say(unit, abs(gap))} {_word_for(d.comparative, gap)}{on} {first.said} than {second.said}."


def _difference(out, d: _Diff, views: list, today: date) -> bool:  # noqa: ANN001
    """Two sums over the same quantity in two windows, their difference, and
    both sets cited."""
    second = _window_asked(d.second, today, views)
    first = _window_asked(d.first, today, views) or (_first_window(second, today) if second else None)
    if not first or not second:
        return False
    one, two, said, left = _both_sets(d, views, first, second)
    if not one and not two:
        out.lines.append(f"I found no {d.unit or _DIMENSION_NOUN.get(d.dimension, 'amounts spent')} {first.said} or {second.said} in your notes.")
        return True
    unit = _unit_of(one + two, d.dimension, d.unit)
    total = sum(i.value for i in one)
    out.lines.append(_gap_line(d, total - sum(i.value for i in two), unit, said, first, second, total))
    both = f"That is {_side(one, first, unit)} against {_side(two, second, unit)}."
    out.lines.append(both)
    _cite_all(out, one + two, both)
    _left_out(out, left)
    return True


def asks(question: str) -> bool:
    q = " ".join(composer_lists._q(question).split())  # noqa: SLF001
    if _total_asked(q) is not None or _DUE_ASK.match(q) or _measure_asked(q) or _left_asked(q) or _target_asked(q) or _difference_asked(q):
        return True
    m = _MOST.match(q)
    return bool(m and set(m.group(2).lower().rstrip("?. ").split()) & _MONEY_NOUNS)


def sums_a_measure(question: str) -> bool:
    """"How many km have I run" is a sum, asked before the one-value slots
    ("how many km is the walk") read a single sentence."""
    q = " ".join(composer_lists._q(question).split())  # noqa: SLF001
    return _measure_asked(q) is not None or _left_asked(q) is not None or _target_asked(q) is not None or _difference_asked(q) is not None


#: The notes the money path reads: a page at a time, newest first, so a
#: notebook past one page is scanned whole, and at most this many hits are
#: read (the composer's cost, not the notebook's size, is the bound).
SCAN_PAGE = 400
SCAN_HITS = 400


def recorded_notes(list_page) -> list:  # noqa: ANN001
    """The newest notes that record an amount or a measure. `list_page` is
    `manager.list_entries` bound to a session; scanning stops at `SCAN_HITS`
    hits, never at the first page (second eye F1: a notebook past 400 notes
    answered "no amounts")."""
    found: list = []
    offset = 0
    while len(found) < SCAN_HITS:
        page = list_page(limit=SCAN_PAGE, offset=offset)
        found += [e for e in page if re.search(r"\d", e.content or "") and records_amounts(e.content or "")]
        if len(page) < SCAN_PAGE:
            break
        offset += SCAN_PAGE
    return found[:SCAN_HITS]


def records_amounts(text: str) -> bool:
    """A note that names spending, a refund or a budget and holds an amount, or holds a measure."""
    return bool(_read(text) and (_SPENDING.search(text) or _REFUND.search(text) or _TARGET_WORD.search(text))) or any(m[0] != "money" for m in recognise.measures(text))


def answer(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    """A sum or a maximum of the amounts spent; False when `asked` is not one."""
    q = " ".join(composer_lists._q(asked).split())  # noqa: SLF001
    if (diff := _difference_asked(q)) and _difference(out, diff, views, today):
        return True
    if target := _target_asked(q):
        return _toward(out, target, views, today)
    if left := _left_asked(q):
        return _due(out, left[2], views, today, left[0], left[1])
    if measure := _measure_asked(q):
        return _measure(out, measure, views, today)
    if (rest := _total_asked(q)) is not None:
        return _spent(out, rest, views, today)
    if m := _DUE_ASK.match(q):
        return _due(out, f"{m.group('subject') or ''} {m.group('rest')}", views, today)
    if m := _MOST.match(q):
        return _most(out, m.group(1), m.group(2), views)
    return False
