"""A sum of named things, or of a named note (audit 1030 Z29).

"Sum of rent and groceries", "how much is rent plus groceries", "add up the
budget", "total cost of the Lisbon trip": the amounts the named things hold,
added and said once, each cited to the sentence it came from. A name that is
a note's title (or its category) adds every amount in that note; any other
name adds the amount in the sentence that holds it. Amounts at different
rates ("$1,200 a month", "$80 a week") are added as written and the answer
says the periods differ, so nobody reads the figure as one month's cost. No
model, and the same with one on.
"""

from __future__ import annotations

import re
from datetime import date

from tessellate.ai import composer, composer_lists, composer_money, recognise

#: The phrasings that carry the names to add; the names are cut word by word
#: afterwards (one split, so no pattern can divide them two ways: CodeQL).
_LEADS = (
    re.compile(r"^(?:what(?:'s| is| was)? )?(?:the |my |our )?(?:sum|total(?: cost)?|combined cost|cost) (?:of|for) (?P<terms>\S.*)$", re.I),
    re.compile(r"^(?:please )?add up (?P<terms>\S.*)$", re.I),
    re.compile(r"^what do (?:my |the |our )?(?P<terms>\S.*) (?:come to|add up to|total)$", re.I),
    re.compile(r"^how much (?:is|are|do|does|would) (?P<terms>\S.*)$", re.I),
    re.compile(r"^(?P<terms>\S+(?: \S+)? (?:plus|\+) \S.*)$", re.I),
)
_JOINERS = frozenset({"and", "plus", "+", "&", ","})
_TRAILERS = ("come to", "add up to", "cost together", "together", "altogether", "combined", "in total", "all up", "total")
_DROP = frozenset({"my", "the", "our", "your", "a", "an", "of", "cost", "costs", "total", "sum", "all", "money"})
_PER = frozenset({"a", "an", "per", "each", "every"})
_COPULA = frozenset({"is", "are", "was", "were", "cost", "costs", "about"})


def _terms(rest: str) -> tuple[list[list[str]], bool]:
    """(the names to add, each as its words; whether the ask said "together")."""
    text = rest.strip(" .?!").lower().replace(",", " , ").replace("+", " + ").replace("&", " & ")
    together = False
    for trailer in _TRAILERS:
        if text.endswith(" " + trailer):
            text, together = text[: -len(trailer) - 1], together or trailer != "total"
    names: list[list[str]] = [[]]
    for word in text.split():
        if word in _JOINERS:
            names.append([])
        elif word not in _DROP:
            names[-1].append(word)
    return [n for n in names if n], together


def _read(question: str) -> tuple[list[list[str]], bool] | None:
    q = " ".join(composer_lists._q(question).split())  # noqa: SLF001
    for lead in _LEADS:
        if (m := lead.match(q)):
            names, together = _terms(m.group("terms"))
            #: "How much is the jacket" is a lookup; a sum needs two names, or
            #: a sum word, or the "together" it said.
            summed = lead is not _LEADS[3] or len(names) > 1 or together
            return (names, together) if names and summed and all(len(n) < 4 for n in names) else None
    return None


def asks(question: str) -> bool:
    return _read(question) is not None


def _period(sentence, value: float) -> str:  # noqa: ANN001
    """The word a rate is per ("a month" gives "month"), or "": the first
    amount of `value` and the two words after it."""
    for _sign, found, at in recognise.amounts(sentence.text):
        if found == value:
            tail = re.sub(r"^[$£€]?\s*[\d,.]+", "", sentence.text[at:]).split()
            return tail[1].strip(".,;") if len(tail) > 1 and tail[0].lower() in _PER else ""
    return ""


def _label(item) -> str:  # noqa: ANN001
    words = item.label.split()
    while words and words[-1].lower() in _COPULA:
        words.pop()
    return " ".join(words) or item.label


def _by_note(views: list, stems: set[str]):  # noqa: ANN202
    """The notes the name is the title of, or the category of."""
    #: A title-less note is named by its first words: that is not its title.
    return [v for v in sorted(views, key=lambda v: v.rank) if stems <= (set(v.title_words) if v.titled else set()) or stems <= set(v.filed_words)]


def _items_in(view) -> list:  # noqa: ANN001
    return [i for s in view.sentences for i in composer_money._clause_items(view, s, refunds=False)]  # noqa: SLF001


def _items_for(views: list, name: list[str]) -> tuple[list, bool]:
    """(the amounts a name holds, whether the name is a whole note)."""
    stems = {w for w in composer._words(" ".join(name)) if w}  # noqa: SLF001
    if not stems:
        return [], False
    if noted := _by_note(views, stems):
        return _items_in(noted[0]), True
    for view in sorted(views, key=lambda v: v.rank):
        for sentence in view.sentences:
            if composer_money._about(view, sentence, sorted(stems)):  # noqa: SLF001
                if found := composer_money._clause_items(view, sentence, refunds=False):  # noqa: SLF001
                    return found[:1], False
    return [], False


def _said(items: list, whole: bool) -> list[str]:
    parts = []
    for item in items:
        period = _period(item.sentence, item.value)
        label = _label(item)
        parts.append(f"{label if whole else label.lower()} {composer_money._money(item.symbol, item.value)}{' a ' + period if period else ''}")  # noqa: SLF001
    return parts


def _total_line(items: list, whole: bool, label: str) -> str:
    symbol = items[0].symbol
    items = [i for i in items if i.symbol == symbol]
    total = composer_money._money(symbol, sum(i.value for i in items))  # noqa: SLF001
    periods = {_period(i.sentence, i.value) for i in items}
    parts = composer_money._listed(_said(items, whole))  # noqa: SLF001
    tail = ", though the periods differ" if len(periods) > 1 else ""
    if whole and len(items) == 1:
        return f"{label} holds one amount: {parts}."
    if whole:
        return f"{label} holds {parts}: {total} in all{tail}."
    if len(items) == 1:
        return f"{parts.capitalize()}."
    return f"{parts.capitalize()} come to {total} as written{tail}."


def answer(out, question: str, views: list, today: date) -> bool:  # noqa: ANN001, ARG001
    """A sum of the named things; False when `question` names no sum or a name holds no amount."""
    read = _read(question)
    if read is None:
        return False
    found, missing, whole_note = [], [], False
    for name in read[0]:
        items, whole = _items_for(views, name)
        if items:
            found.extend(items)
        else:
            missing.append(" ".join(name))
        whole_note = whole_note or whole
    if not found:
        return False
    label = composer_lists._title(found[0].view)  # noqa: SLF001
    line = _total_line(found, whole_note and len(read[0]) == 1, label)
    out.lines.append(line)
    composer_money._cite_all(out, found, line)  # noqa: SLF001
    if missing:
        out.lines.append(f"I found no amount for {composer_money._listed(missing)}.")  # noqa: SLF001
    return True


#: "What's the biggest expense in my budget", "the priciest thing on the list",
#: "what's the cheapest thing I bought" (audit 1030 Z31): the size word, the
#: kind of thing and, when it names one, the note or category it is in.
_MOST = re.compile(
    r"^what(?:'s| is| was| were)? (?:my |the |our )?(?P<size>biggest|largest|highest|greatest|smallest|cheapest|lowest|priciest|most expensive|least expensive|costliest) "
    r"(?P<noun>\S.*)$",
    re.I,
)
_SMALL = frozenset({"smallest", "cheapest", "lowest", "least expensive"})
_KINDS = frozenset({"expense", "expenses", "cost", "costs", "bill", "bills", "purchase", "purchases", "payment", "payments", "spend", "spending", "thing", "item", "amount", "buy", "bought", "paid", "spent"})
_AMOUNT_SIZES = frozenset({"biggest", "largest", "highest", "greatest", "smallest", "lowest"})
_SCOPE_AT = frozenset({"in", "on", "from", "of"})


def _most_read(question: str) -> tuple[str, list[str]] | None:
    """(the size word, the scope's words) of a superlative about amounts, or None."""
    m = _MOST.match(" ".join(composer_lists._q(question).split()))  # noqa: SLF001
    if not m:
        return None
    words = m.group("noun").lower().split()
    at = next((i for i, w in enumerate(words) if w in _SCOPE_AT), len(words))
    if not set(words[:at]) & _KINDS:
        return None
    return m.group("size").lower(), [w for w in words[at + 1:] if w not in _DROP]


def asks_most(question: str) -> bool:
    return _most_read(question) is not None


def _holds_none(out, views: list, scope: list[str]) -> bool:  # noqa: ANN001
    """The named note is there and holds no amount: said, not guessed at."""
    stems = {w for w in composer._words(" ".join(scope)) if w}  # noqa: SLF001
    if not (stems and (noted := _by_note(views, stems))):
        return False
    out.lines.append(f"{composer_lists._title(noted[0])} holds no amounts.")  # noqa: SLF001
    return True


def most(out, question: str, views: list, today: date) -> bool:  # noqa: ANN001
    """The biggest or smallest amount in the named note, or among those spent."""
    read = _most_read(question)
    if read is None:
        return False
    size, scope = read
    items = _items_for(views, scope)[0] if scope else composer_money.spent_only(composer_money._items(views), today)  # noqa: SLF001
    if not items:
        return _holds_none(out, views, scope)
    pick = (min if size in _SMALL else max)(items, key=lambda i: i.value)
    where = f" in {composer_lists._title(pick.view)}" if scope or len({id(i.view) for i in items}) == 1 else ""  # noqa: SLF001
    line = f"{_label(pick)}, at {composer_money._money(pick.symbol, pick.value)}, is the {size} {'amount' if size in _AMOUNT_SIZES else 'one'}{where}."  # noqa: SLF001
    out.lines.append(line)
    composer_money._cite_all(out, [pick], line)  # noqa: SLF001
    return True


def holds_amount(question: str, text: str) -> bool:
    """Whether a note belongs in the pool of a scoped superlative ("the
    biggest expense in my budget"): it holds an amount, and the ask is one."""
    return asks_most(question) and bool(recognise.amounts(text))
