"""Generate the five composer eval fixtures CHAT_PLAN section 4 named and L-chat-22 left unbuilt
(`windows_1010`, `recall_1010`, `social_1010`, `ood_1010`, `help_1010`) into tests/fixtures/composer/.

Same rule as `phase6_fixtures.py`: every expected value is worked out here from the row itself
(dates by calendar arithmetic, ids from the row's own notebook, the topic and sentence from the
help table's own text), never by running the engine. Run from anywhere:
`python scripts/composer_fixtures_1113.py`; the floors are in `tests/test_composer_eval_1113.py`."""
import calendar
import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "composer"
MONTHS = "January February March April May June July August September October November December".split()
WEEKDAYS = "monday tuesday wednesday thursday friday saturday sunday".split()
rng = random.Random(1113)


def write(name: str, data: dict) -> None:
    (OUT / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


# --- windows ---------------------------------------------------------------------------
def week_of(d):
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)


def month_of(y, m):
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def past_weekday(now, wd):
    """The most recent `wd` strictly before `now` ("last friday" on a Friday is a week back)."""
    d = now - timedelta(days=1)
    while d.weekday() != wd:
        d -= timedelta(days=1)
    return d


def past_day(now, month, day):
    """The latest `day` `month` that is not after `now` (a date with no year reads as past)."""
    year = now.year if date(now.year, month, day) <= now else now.year - 1
    return date(year, month, day)


def past_month(now, month):
    year = now.year if date(now.year, month, 1) <= now else now.year - 1
    return month_of(year, month)


TUE, FRI, NEW_YEAR, LEAP, SUN = date(2026, 10, 6), date(2026, 11, 13), date(2027, 1, 4), date(2028, 3, 1), date(2026, 10, 11)
windows = []


def add_window(phrase, now, first, last, grain):
    windows.append({"id": f"window-{len(windows) + 1:02d}", "phrase": phrase, "now": now.isoformat(),
                    "start": first.isoformat(), "end": last.isoformat(), "grain": grain})


for now in (TUE, FRI, NEW_YEAR, LEAP):
    add_window("yesterday", now, now - timedelta(days=1), now - timedelta(days=1), "day")
for now in (TUE, NEW_YEAR):
    add_window("last week", now, *week_of(now - timedelta(days=7)), "week")
    add_window("the week before last", now, *week_of(now - timedelta(days=14)), "week")
    add_window("last month", now, *month_of(now.year - (now.month == 1), (now.month - 2) % 12 + 1), "month")
    add_window("last year", now, date(now.year - 1, 1, 1), date(now.year - 1, 12, 31), "year")
add_window("last week", FRI, *week_of(FRI - timedelta(days=7)), "week")
add_window("the week before last", FRI, *week_of(FRI - timedelta(days=14)), "week")
add_window("this week", TUE, *week_of(TUE), "week")
add_window("this week", SUN, *week_of(SUN), "week")
add_window("this month", FRI, *month_of(FRI.year, FRI.month), "month")
add_window("this year", FRI, date(2026, 1, 1), date(2026, 12, 31), "year")
add_window("last month", LEAP, *month_of(2028, 2), "month")
add_window("last weekend", TUE, date(2026, 10, 3), date(2026, 10, 4), "week")
add_window("last weekend", FRI, date(2026, 11, 7), date(2026, 11, 8), "week")
for phrase, days in (("a week ago", 7), ("2 days ago", 2), ("3 weeks ago", 21), ("10 days ago", 10)):
    add_window(phrase, TUE, TUE - timedelta(days=days), TUE - timedelta(days=days), "day")
add_window("a week ago", NEW_YEAR, NEW_YEAR - timedelta(days=7), NEW_YEAR - timedelta(days=7), "day")
#: "since X" runs from the start of X to the day asked (the forms measured as missed, CHAT_PLAN 4).
add_window("since March", TUE, date(2026, 3, 1), TUE, "month")
add_window("since March", NEW_YEAR, date(2026, 3, 1), NEW_YEAR, "month")
add_window("since last week", TUE, week_of(TUE - timedelta(days=7))[0], TUE, "week")
add_window("since last month", FRI, date(2026, 10, 1), FRI, "month")
add_window("since March last year", TUE, date(2025, 3, 1), TUE, "month")
#: A month or a date with no year is read as past, never as the coming one.
for now in (TUE, NEW_YEAR):
    add_window("in March", now, *past_month(now, 3), "month")
    add_window("on 3 March", now, past_day(now, 3, 3), past_day(now, 3, 3), "day")
add_window("in December", TUE, *past_month(TUE, 12), "month")
add_window("in January", TUE, *past_month(TUE, 1), "month")
add_window("in February", LEAP, *month_of(2028, 2), "month")
add_window("14 November", TUE, past_day(TUE, 11, 14), past_day(TUE, 11, 14), "day")
add_window("on 21 September", TUE, past_day(TUE, 9, 21), past_day(TUE, 9, 21), "day")
add_window("in 2025", TUE, date(2025, 1, 1), date(2025, 12, 31), "year")
add_window("in 2024", FRI, date(2024, 1, 1), date(2024, 12, 31), "year")
#: "last <weekday>" is the past one, strictly before today ("last friday" on a Friday is a week back).
for name, now in (("friday", TUE), ("friday", FRI), ("monday", TUE), ("sunday", TUE), ("wednesday", FRI), ("tuesday", TUE), ("thursday", NEW_YEAR)):
    day = past_weekday(now, WEEKDAYS.index(name))
    add_window(f"last {name}", now, day, day, "day")
for name in ("monday", "friday"):
    day = past_weekday(TUE, WEEKDAYS.index(name))
    add_window(f"on {name}", TUE, day, day, "day")
add_window("the weekend before last", TUE, date(2026, 9, 26), date(2026, 9, 27), "week")
add_window("today", TUE, TUE, TUE, "day")
add_window("the 21st", TUE, date(2026, 9, 21), date(2026, 9, 21), "day")
add_window("yesterday", SUN, SUN - timedelta(days=1), SUN - timedelta(days=1), "day")
add_window("last week", SUN, *week_of(SUN - timedelta(days=7)), "week")
add_window("today", FRI, FRI, FRI, "day")
add_window("2 days ago", NEW_YEAR, date(2027, 1, 2), date(2027, 1, 2), "day")
add_window("last month", FRI, *month_of(2026, 10), "month")
add_window("this week", NEW_YEAR, *week_of(NEW_YEAR), "week")
assert len(windows) == 60, len(windows)
write("windows_1010.json", {"about": "Time phrases read against a clock (CHAT_PLAN section 4): expected first day, last day and grain, worked out by calendar arithmetic in scripts/composer_fixtures_1113.py. A date or month with no year is read as past; weeks run Monday to Sunday.", "rows": windows})


# --- recall ----------------------------------------------------------------------------
NOW = TUE
recall = []


def note(nid, title, body, day):
    return {"id": nid, "content": f"# {title}\n\n{body}", "created_at": day.isoformat()}


def add_recall(kind, question, notes, ids, *, count=None, empty=False, now=NOW):
    #: The notes go in newest first, as the app hands them over.
    notes = sorted(notes, key=lambda n: n["created_at"], reverse=True)
    recall.append({"id": f"recall-{len(recall) + 1:02d}", "kind": kind, "question": question, "now": now.isoformat(), "notes": notes,
                   "expect_ids": ids, "expect_count": len(ids) if count is None else count, "empty": empty})


def d(offset, now=NOW):
    return now + timedelta(days=offset)


FILLER = [("Errands", "Pick up the parcel and post the letter."), ("Soup", "Simmer the lentils for forty minutes."),
          ("Gym", "Squats and a short run on the treadmill."), ("Reading", "Finished two chapters of the library book.")]


def filler(start, days):
    return [note(start + i, FILLER[i % 4][0] + f" {start + i}", FILLER[i % 4][1], day) for i, day in enumerate(days)]


# time: a window of the notebook's own dates (newest first), and a window nothing falls in
add_recall("time", "what did I write yesterday", [note(1, "Boiler", "The boiler pressure dropped to one bar.", d(-1)), *filler(10, [d(-9), d(-20), d(-3)])], [1])
last_week = week_of(NOW - timedelta(days=7))
add_recall("time", "what did I write last week", [note(2, "Chess", "Chess club on the weekend, lost twice.", last_week[0] + timedelta(days=1)),
           note(3, "Pottery", "Pottery class, a blue bowl.", last_week[0] + timedelta(days=4)), note(4, "Rent", "Pay the rent on time.", last_week[1]), *filler(20, [d(-1), d(-30)])], [4, 3, 2])
add_recall("time", "what did I write in March", [note(5, "Spring plan", "Repaint the shed fence.", date(2026, 3, 4)), note(6, "Seeds", "Order the bean seeds.", date(2026, 3, 22)),
           *filler(30, [date(2026, 2, 27), date(2026, 4, 2), d(-5)])], [6, 5])
add_recall("time", "what did I write last month", [note(7, "Dentist", "Check-up went well.", date(2026, 9, 10)), *filler(40, [date(2026, 8, 31), date(2026, 10, 2)])], [7])
add_recall("time", "what did I write on Friday", [note(8, "Plumber", "The plumber fixed the tap.", date(2026, 10, 2)), *filler(50, [date(2026, 10, 1), date(2026, 10, 3)])], [8])
add_recall("time", "what did I write this week", [note(9, "Budget", "Budget review found three cuts.", d(0)), note(11, "Garden", "Compost bags for the beds.", d(-1)), *filler(60, [d(-8), d(-12)])], [9, 11])
add_recall("time", "what did I write in July", filler(70, [date(2026, 6, 28), date(2026, 8, 2), d(-1)]), [], empty=True)
add_recall("time", "what did I write last year", filler(80, [date(2026, 1, 5), d(-2), d(-40)]), [], empty=True)
# person and place: one note names them, the others do not
PEOPLE = [("Priya", "Lunch with Priya on the harbour, she is moving to Leeds."), ("Tomas", "Tomas lent me his drill for the shelf."),
          ("Jess", "Jess is moving to Melbourne in January."), ("Marta", "Marta recommended the pottery class.")]
for i, (name, line) in enumerate(PEOPLE):
    add_recall("person", f"what do I know about {name}", [note(100 + i, f"Catch up {i}", line, d(-3 - i)), *filler(110 + 10 * i, [d(-6), d(-15), d(-25)])], [100 + i])
PLACES = [("Lisbon", "Booked the flat in Lisbon for May, near Alfama."), ("Perth", "The Perth market opens at eight on Saturdays."), ("Kyoto", "Kyoto in autumn: temples and the paper shop.")]
for i, (name, line) in enumerate(PLACES):
    add_recall("place", f"what did I write about {name}", [note(200 + i, f"Trip {i}", line, d(-10 - i)), *filler(210 + 10 * i, [d(-4), d(-18), d(-33)])], [200 + i])

# what changed: the notes made (or edited) in the window the question names, newest first; the clock is 10:00
mon = week_of(NOW)[0]
add_recall("changed", "what is new", [note(300, "Soup", "Lentil soup with cumin.", d(-1)), note(301, "Bike", "Fixed the rear brake.", d(-3)), *filler(310, [d(-20), d(-45)])], [300, 301])
add_recall("changed", "what changed this week", [note(320, "Roof", "The roof leak is back.", d(0)), note(321, "Piano", "Scales in D, then a new piece.", mon), *filler(330, [mon - timedelta(days=3), d(-25)])], [320, 321])
add_recall("changed", "what changed since last week", [note(340, "Tax", "Gather the receipts.", d(-1)), note(341, "Sketch", "Hands, three pages.", d(-5)), note(342, "Cafe", "Try the new cafe.", mon - timedelta(days=6)),
           *filler(350, [mon - timedelta(days=9), d(-40)])], [340, 341, 342])
add_recall("changed", "what have I added this week", [note(360, "Guests", "Twelve guests on Saturday.", d(-1)), *filler(370, [d(-12), d(-30), d(-60)])], [360])
edited = note(380, "Old recipe", "Bread with a slow rise.", d(-60))
edited["edited_at"] = d(-1).isoformat()
add_recall("changed", "what did I edit this week", [edited, note(381, "Fresh note", "Written today, never edited.", d(0)), *filler(390, [d(-14), d(-50)])], [380])
# due: dated sentences inside the window, soonest first; a past date and a far date are left out
add_recall("due", "what's due this week", [note(400, "Rent", "Pay the rent by 9 October.", d(-10)), note(401, "Forms", "Return the forms on 8 October.", d(-8)),
           note(402, "Trip", "Flights leave on 14 October.", d(-6)), note(403, "Old", "The invoice was due on 30 September.", d(-20)), *filler(410, [d(-3)])], [401, 400])
add_recall("due", "what is due this month", [note(420, "Tax", "File the tax return by 31 October.", d(-30)), note(421, "Library", "Return the books on 9 October.", d(-5)),
           note(422, "Party", "The party is on 20 October.", d(-9)), note(423, "Move", "Movers come on 2 November.", d(-4)), *filler(430, [d(-2)])], [421, 422, 420])
add_recall("due", "what is due", [note(440, "Dentist", "Dentist on 12 October at 9am.", d(-11)), note(441, "Class", "Pottery class on 17 October.", d(-7)),
           note(442, "Visa", "The visa runs out on 24 October.", d(-30)), *filler(450, [d(-3)])], [440, 441])
add_recall("due", "what's due next week", [note(460, "Exam", "The exam is on 13 October.", d(-20)), note(461, "Gym", "Gym induction on 15 October.", d(-8)),
           note(462, "Fence", "Paint the fence on 9 October.", d(-5)), note(463, "Wedding", "Wedding on 20 October.", d(-40)), *filler(470, [d(-1)])], [460, 461])
# open: notes that still hold an unticked item, in the notebook's order, and the count of unticked items
add_recall("open", "what is still open", [note(500, "Camping", "- [ ] tent\n- [x] stove\n- [ ] torch", d(-2)), note(501, "Garden jobs", "- [ ] buy compost\n- [ ] fix the gate", d(-6)),
           note(502, "Done list", "- [x] call the bank\n- [x] post the letter", d(-9)), *filler(510, [d(-1)])], [500, 501], count=4)
add_recall("open", "what's left", [note(520, "Packing", "- [x] passport\n- [ ] charger\n- [ ] sunscreen", d(-4)), note(521, "Shopping", "- [ ] milk", d(-7)), *filler(530, [d(-3), d(-5)])], [520, 521], count=3)
add_recall("open", "what's still open in Garden jobs", [note(540, "Garden jobs", "- [x] mow the lawn\n- [ ] buy compost\n- [ ] fix the gate\n- [ ] prune the pear", d(-6)),
           note(541, "Camping", "- [ ] tent", d(-2)), *filler(550, [d(-1)])], [540], count=3)
# contradicts: a preference and a later note the other way about the same thing, earlier note first
PAIRS = [("early train", "I love the early train.", "I hate the early train now."), ("standing desk", "I like the standing desk.", "I don't like the standing desk any more."),
         ("open plan office", "I like the open plan office.", "I can't stand the open plan office.")]
for i, (what, before, after) in enumerate(PAIRS):
    add_recall("contradicts", "do my notes contradict each other", [note(600 + 10 * i, f"Commute {i}", before, d(-70 + i)), note(601 + 10 * i, f"Update {i}", after, d(-9 - i)), *filler(700 + 10 * i, [d(-3), d(-30)])],
               [600 + 10 * i, 601 + 10 * i], count=1)
assert len(recall) == 30, len(recall)
assert {k: sum(r["kind"] == k for r in recall) for k in ("time", "person", "place", "changed", "due", "open", "contradicts")} == dict(time=8, person=4, place=3, changed=5, due=4, open=3, contradicts=3)
write("recall_1010.json", {"about": "Recall questions over a row's own notebook (CHAT_PLAN section 4): the note ids the answer lists in order and the measured count, worked out in scripts/composer_fixtures_1113.py from the notes' own dates and text. Notes are newest first; the clock is 10:00 on `now`.", "rows": recall})
print("ok", len(windows), len(recall))
