"""Generate the five composer eval fixtures CHAT_PLAN section 4 named and L-chat-22 left unbuilt
(`windows_1010`, `recall_1010`, `social_1010`, `ood_1010`, `help_1010`) into tests/fixtures/composer/.

Same rule as `phase6_fixtures.py`: every expected value is worked out here from the row itself
(dates by calendar arithmetic, ids from the row's own notebook, the topic and sentence from the
help table's own text), never by running the engine. Run from anywhere:
`python scripts/composer_fixtures_1113.py`; the floors are in `tests/test_composer_eval_1113.py`."""
import calendar
import json
import random
import re
import sys
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


# --- social ----------------------------------------------------------------------------
social = []
RUNNING = {"question": "what do my notes say about running", "answer": "You ran twice. **Running log** says 5 km."}


def add_social(group, message, kind, previous=""):
    social.append({"id": f"social-{len(social) + 1:02d}", "group": group, "message": message, "previous": previous, "kind": kind})


KINDS = {
    "greeting": ("hi", "hello there", "hey", "good evening"),
    "morning": ("good morning", "morning", "morning all"),
    "thanks": ("thanks", "thank you", "cheers", "thanks a lot"),
    "bye": ("bye", "goodbye", "see you later"),
    "sorry": ("sorry", "my bad", "sorry about that"),
    "how": ("how are you", "how's it going", "what's up"),
    "unclear": ("asdfgh", "qwerty", "zxcvbn"),
    "test": ("test", "testing", "testing 1 2 3"),
    "ack": ("ok", "okay", "got it", "alright then"),
    "reaction": ("wow", "whoa", "yay"),
    "compliment": ("you are great", "you're brilliant", "good job"),
    "confused": ("what?", "huh?", "I don't understand"),
    "frustrated": ("this is useless", "ugh, wrong again", "still wrong"),
    "glad": ("that worked", "awesome, it works", "so happy"),
    "emotion": ("I feel sad today", "I'm so tired", "I am really stressed"),
}
for kind, phrases in KINDS.items():
    for phrase in phrases:
        add_social("kind", phrase, kind)
for phrase, kind in (("tell me a joke", "joke"), ("make me laugh", "joke"), ("got any jokes", "joke"), ("say something funny", "joke"),
                     ("haha", "laugh"), ("lol", "laugh"), ("that was hilarious", "laugh"), ("lmao", "laugh")):
    add_social("humour", phrase, kind)
for phrase in ("who are you", "what's your name", "are you a robot", "are you an AI", "are you human", "who made you"):
    add_social("identity", phrase, "who")
for phrase, kind in (("shorter", "length"), ("longer", "length"), ("make it shorter", "length"), ("make it longer", "length"), ("in more detail", "length"), ("briefly", "length"),
                     ("tell me more", "more"), ("more", "more"), ("say more", "more"), ("go on", "more"), ("why?", "why"), ("and why?", "why")):
    add_social("control", phrase, kind, RUNNING["answer"])
for act, phrase in (("Pinned the dentist note.", "thanks"), ("Moved the sourdough note to Cooking.", "thank you"), ("Set a reminder to call the plumber on Friday.", "cheers"),
                    ("Tagged the knife note with kitchen.", "nice, thanks"), ("Deleted the boiler note. Undo is in the bin.", "perfect, thank you"), ("Renamed the gym note to Strength plan.", "thanks, that worked")):
    add_social("gratitude", phrase, "thanks", act)
assert len(social) == 80, len(social)
write("social_1010.json", {"about": "Conversational turns (CHAT_PLAN section 4): the kind each message is, by what it says. Controls are read against the answer before (`previous`); a thanks after an act is a thanks. The runner reads the kind off `composer_smalltalk.social_kind` or `composer.follow_on`.",
                           "history": [RUNNING], "rows": social})


# --- out of domain ------------------------------------------------------------------------
OOD_NOTES = [note(1, "Football", "Five a side with Sam on Saturday, we lost 4 to 2.", date(2026, 10, 3)), note(2, "Paris trip", "Hotel booked in Paris for May, near the river.", date(2026, 9, 12)),
             note(3, "Pizza night", "Pizza dough needs a day to rest.", date(2026, 9, 28)), note(4, "Weather station", "Fit the rain gauge to the shed wall.", date(2026, 9, 20)),
             note(5, "Mum", "Call mum on Sunday about the party.", date(2026, 10, 4)), note(6, "Reading", "Finished the play, it was Hamlet at the old theatre.", date(2026, 8, 30))]
OOD = {
    "weather": ("what's the weather today", "will it rain tomorrow", "what's the weather in Paris", "is it going to snow this weekend", "how hot is it outside",
                "what's the temperature in Perth", "weather forecast for Friday", "do I need an umbrella"),
    "scores": ("who won the football last night", "what's the score of the Lakers game", "who won the world cup in 2018", "what were the cricket results",
               "when do Arsenal play next", "who is top of the league"),
    "trivia": ("what is the capital of France", "who wrote Hamlet", "how tall is Mount Everest", "when did the Berlin wall fall", "what is the population of Japan",
               "who painted the Mona Lisa", "how many planets are there", "what year did the Titanic sink"),
    "cannot": ("book me a flight to Rome", "order me a pizza", "call my mum", "play some jazz", "send an email to Sam", "turn off the lights",
               "buy a ticket to the concert", "post this on twitter"),
}
ood = [{"id": f"ood-{i + 1:02d}", "group": g, "question": q} for i, (g, q) in enumerate((g, q) for g, qs in OOD.items() for q in qs)]
assert len(ood) == 30, len(ood)
write("ood_1010.json", {"about": "Questions the notebook cannot answer and the app cannot do (CHAT_PLAN section 4, U18, A25): the answer must be the plain no-answer, with a line on what the app can do, and a note it shows must be called the closest. The notebook has decoy notes sharing a word with some questions.",
                        "today": "2026-10-06", "notes": OOD_NOTES, "rows": ood})

# --- help ----------------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from tessellate.ai.help_topics_core import HELP_TOPICS  # noqa: E402  # the help table's own text: data, not the engine

BODY = {t["id"]: t["body"] for t in HELP_TOPICS}
INDEX_IDS = set(re.findall(r'\bid="([A-Za-z0-9_-]+)"', (OUT.parent.parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")))


def sentences(body):
    return re.split(r"(?<=[.!?])\s+(?=[A-Z\"\u201c(])", body)


HELP = [
    ("how do I pin a note", "favourites", "Starring (pinning)", None), ("how do I lock the app with a password", "security", "Settings, Account & security: set a password", "lock-btn"),
    ("how do I open the command palette", "command-palette", "Ctrl/Cmd+K opens the command palette", "command-palette-input"), ("how do I find a note", "find-anything", "Find anything (Ctrl+P", "finder-input"),
    ("how do I change the theme", "appearance", "Settings, Appearance controls theme", "theme-btn"), ("where do my notifications go", "notifications", "The bell in the top bar", "notif-btn"),
    ("how do I connect a model", "models", "Connect a model in Settings, Models", "settings-btn"), ("how do I turn on web search", "websearch", "Web search is opt-in", "web-search-toggle"),
    ("does it work offline", "privacy", "Yes, it works offline", "privacy-chip"), ("how do I archive a note", "archive", "Archiving keeps a note", None),
    ("how do I undo a delete", "undo-bin", "Undo and Redo cover everything", None), ("how do I dictate a note", "voice", "The microphone icon on the note composer", "mic-note"),
    ("how do I link two notes", "links", "Link one note to another", None), ("how do I use a template", "templates", "Capture has templates", "entry-template"),
    ("how do I tag a note", "tags-categories", "Atlas files each note into a category", "entry-tags"), ("how do I make a mind map", "mind-maps", "Mind maps live in the Library", "tab-btn-library"),
    ("how do I see my timeline", "timeline", "The Timeline tab lists", "tab-btn-timeline"), ("how do I use the graph", "graph", "The Graph tab shows notes", "tab-btn-graph"),
    ("how do I check for updates", "updates", "Settings, About says which version", "settings-btn"), ("how do I turn on simple mode", "simple-mode", "Settings, General, Simple mode", None),
    ("how do I translate text", "translate", "The Writing room translates", None), ("what is a persona", "personas", "A persona changes how Atlas talks", "persona-select"),
    ("how do I see my statistics", "statistics", "Statistics counts your notebook", None), ("how do I check my spelling", "spelling-check", "Spelling gets a second opinion", None),
    ("where is my data stored", "storage", "Everything lives in a data folder", None), ("what is a space", "spaces", "A space is a separate notebook", "space-switcher-btn"),
    ("how do I see the history of a document", "document-history", "Documents keep a history", "doc-history"), ("how do I export my notes", "import-export", "Export your data as JSON", None),
    ("how do I add a reminder", "reminders", "To add, make or set a reminder", "tab-btn-reminders"), ("how do I switch to another space", "spaces", "Switch or create one", "space-switcher-btn"),
    ("how do I add an action item to a meeting", "meetings", "Write an action item", None), ("how do I search by tag", "search", "Operators: tag:work", "finder-input"),
    ("how do I add a tag as I type", "tags-categories", "Type #word anywhere", "entry-tags"), ("how do I write my own persona", "personas", "Pick one in the Chat tab", None),
    ("how do I lock the screen right now", "security", "The lock button in the top bar", "lock-btn"), ("how do I do a sum", "calculator", "Sum takes a sum typed or keyed", None),
    ("how do I get to the calculator", "calculator", "Open it from the command palette", "command-palette-input"), ("how do I make a diagram without a model", "make-a-diagram", "With no model, two places make a diagram", None),
    ("how do I speed up a slow app", "performance", "If the app feels slow", None), ("is there a tour of the app", "tour", "The guided tour walks", None),
]
help_rows = []
for i, (question, topic, cue, control) in enumerate(HELP):
    parts = sentences(BODY[topic])
    hit = [k for k, x in enumerate(parts) if x.startswith(cue)]
    assert len(hit) == 1, (topic, cue, hit)
    assert control is None or control in INDEX_IDS, control
    help_rows.append({"id": f"help-{i + 1:02d}", "question": question, "topic": topic, "sentence_id": f"{topic}#{hit[0]}", "cue": cue, "controls": [control] if control else []})
assert len(help_rows) == 40, len(help_rows)
write("help_1010.json", {"about": "How-to questions (CHAT_PLAN section 4): the help topic each belongs to and the sentence of its text that is the first step (`topic#n`, n counted by splitting the topic text at sentence ends; `cue` is how that sentence begins). `controls` are element ids in frontend/index.html the step names.",
                         "rows": help_rows})
print("ok", len(windows), len(recall), len(social), len(ood), len(help_rows))
