#!/usr/bin/env python3
"""The README's showcase notebook, built through the API on a fresh data dir.

    bash scratchpad/ui-sweeps/serve.sh 8861 /tmp/mm-a861
    .venv/bin/python scratchpad/ui-sweeps/seed-showcase.py 8861 /tmp/mm-a861

INBOX 431 (g), the owner: "make the graph really visually pleasing and
impressive with a mix of connected and non connected, some clusters some
webs, some connections have reasons and others dont etc. make sure all main
features are properly shown."

The earlier screenshots were taken over four seeds stacked on one data dir
(seed.js, seed-timeline.js, seed-readme.js, seed-boardrich.js), each written
for a sweep, and their notes did not belong to one person: "Plain note number
7" sat beside a recipe in the Notes shot. This writes one notebook a person
could have, in seven categories, and nothing else:

- 71 notes. Work and Travel are dense clusters (a hub or two, most notes
  linked to several others), Cooking a looser cluster, Reading a sparse web
  (a chain with a few cross threads), Health a small tree, Home mostly loose
  notes, and Ideas the bridges between them. About half the links carry a
  reason ("why these two"), the rest are plain, so the graph draws both kinds.
- Created dates spread over the last seven weeks (written straight into the
  database after the API made the notes: no route takes a creation date, and
  a notebook made in one second has a one-day timeline and a one-day streak).
- Reminders with priorities and repeats, three linked to their notes.
- Three documents, one long enough to show the editor.
- A board with cards, shapes holding text and labelled connectors (this
  week's two whiteboard features), and a mind map with tasks, a note behind a
  topic and numbered branches, icons and a look per level.
- Saved chats, so Chat and the Library have history.

Everything goes through the same routes the app uses, so the search index,
the audit log and the link table are filled the way they are in use. Run it
once on an empty data dir; it refuses a notebook that already has notes.
"""

from __future__ import annotations

import datetime as dt
import random
import sqlite3
import sys
from pathlib import Path

import requests

PORT = sys.argv[1] if len(sys.argv) > 1 else "8861"
DATA = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/mm-a861")
BASE = f"http://127.0.0.1:{PORT}"
PW = "testpassword123"

S = requests.Session()


def call(method: str, path: str, body: dict | None = None) -> dict | list:
    r = S.request(method, BASE + path, json=body, timeout=60)
    if not r.ok:
        raise SystemExit(f"{method} {path}: {r.status_code} {r.text[:300]}")
    return r.json() if r.content else {}


def sign_in() -> None:
    status = S.get(BASE + "/auth/status", timeout=10).json()
    route = "/auth/setup" if status.get("setup_required") else "/auth/unlock"
    token = S.post(BASE + route, json={"password": PW}, timeout=30).json()["token"]
    S.headers.update({"X-Auth-Token": token})


# --- Notes -------------------------------------------------------------------
#
# key, category, tags, content. The key is only this script's handle for the
# links below; the note's title is its first heading, as a person writes one.
NOTES: list[tuple[str, str, list[str], str]] = [
    # Work: the Harbor launch, a dense cluster round two hubs.
    ("w_plan", "Work", ["harbor", "launch"], "# Harbor launch plan\n\nShip the mobile app to the public on the 14th of next month. Three gates before then: beta feedback closed, the onboarding rewrite merged, and the pricing page signed off.\n\n- [x] Beta invite list\n- [x] Crash reporting\n- [ ] Store listing copy\n- [ ] Launch email"),
    ("w_roadmap", "Work", ["roadmap", "planning"], "# Q4 roadmap\n\nThree workstreams: Harbor launch, the sync rewrite and the support backlog. Harbor gets two thirds of the team until launch week, then the sync rewrite takes over."),
    ("w_beta", "Work", ["harbor", "beta"], "# Beta feedback, week 2\n\n41 testers active. The top complaint is the sign-up flow (nine fields). Second is that offline mode is hard to find. Nobody mentioned speed, which is the first time."),
    ("w_onboard", "Work", ["harbor", "design"], "# Onboarding rewrite\n\nCut sign-up from nine fields to four. Ask for the name later, on the first share. Draft screens are on the launch board."),
    ("w_pricing", "Work", ["harbor", "pricing"], "# Pricing page\n\nOne free tier and one paid. The comparison table moves above the fold; the FAQ answers the refund question in its first line."),
    ("w_retro", "Work", ["retro", "team"], "# Sprint 14 retro\n\nWhat helped: measuring before changing anything. What did not: two days lost reading code instead of running it. Keep the Thursday demo."),
    ("w_sync", "Work", ["sync", "engineering"], "# Sync rewrite, first notes\n\nThe conflict rule is last-writer-wins today, which silently drops edits. Proposal: keep both versions and ask, the way a document merge does."),
    ("w_perf", "Work", ["engineering", "performance"], "# Why the list felt slow\n\nIt was not the database. Every row re-measured its own height on scroll. Caching the height per row took a long list from 40ms a frame to 6."),
    ("w_store", "Work", ["harbor", "launch"], "# Store listing\n\nFive screenshots, dark and light. The first line has to say what it does in under ten words: notes that sort themselves, offline."),
    ("w_email", "Work", ["harbor", "marketing"], "# Launch email draft\n\nSubject: Harbor is out. One paragraph, one screenshot, one button. Send at 9 in each time zone, not all at once."),
    ("w_support", "Work", ["support"], "# Support backlog triage\n\n63 open tickets. 20 are the same export question; one help article closes them. Billing questions go to the new form."),
    ("w_hiring", "Work", ["team", "hiring"], "# Hiring a designer\n\nPortfolio review on Tuesday. Looking for someone who has shipped a product end to end, not only screens."),
    ("w_metrics", "Work", ["harbor", "metrics"], "# Launch metrics\n\nDay-one installs matter less than week-two retention. Track: notes created in the first week, and whether people come back on day 8."),
    ("w_risks", "Work", ["harbor", "risks"], "# Launch risks\n\n1. The store review takes longer than a week.\n2. Sync conflicts surface under real load.\n3. The pricing page is not signed off in time."),
    ("w_standup", "Work", ["meetings"], "# Thursday demo notes\n\nShowed the new onboarding to the whole team. Feedback: the progress dots read as a carousel. Replace them with a step count."),
    ("w_offsite", "Work", ["team"], "# Team offsite ideas\n\nOne day, no laptops. A walk in the morning, the roadmap in the afternoon, dinner somewhere with a long table."),
    ("w_api", "Work", ["engineering", "api"], "# Public API, maybe\n\nThree people in the beta asked for one. Not before launch. Write down the read-only version so the idea is not lost."),
    # Travel: a trip to Portugal, a dense cluster round its overview.
    ("t_over", "Travel", ["portugal", "planning"], "# Portugal trip, overview\n\nTen days in May: four in Lisbon, a day in Sintra, three in Porto, two in the Douro valley. Train between the cities, a car only for the valley."),
    ("t_lisbon", "Travel", ["portugal", "lisbon"], "# Lisbon, where to stay\n\nAlfama for the walk-everywhere feel, but the hills are steep with luggage. Príncipe Real is quieter and close to the metro."),
    ("t_sintra", "Travel", ["portugal", "sintra"], "# Sintra day trip\n\nTrain from Rossio, 40 minutes. Pena Palace first thing, timed ticket. Quinta da Regaleira in the afternoon when the tour buses leave."),
    ("t_porto", "Travel", ["portugal", "porto"], "# Porto, three days\n\nRibeira at sunset, the Livraria Lello early or not at all, and a port lodge tour across the bridge in Gaia."),
    ("t_douro", "Travel", ["portugal", "douro"], "# Douro valley\n\nHire a car in Porto. Stay one night at a quinta near Pinhão; the river road from Régua to Pinhão is the drive to do."),
    ("t_flights", "Travel", ["portugal", "bookings"], "# Flights\n\nOut to Lisbon, back from Porto, so no day is lost going back. Booked, seats 14A and 14B."),
    ("t_trains", "Travel", ["portugal", "bookings"], "# Trains\n\nLisbon to Porto on the Alfa Pendular, 2h50. Tickets open 60 days ahead and are half price if booked early."),
    ("t_food", "Travel", ["portugal", "food"], "# Things to eat\n\nPastéis de nata at the Belém bakery, bifana from a counter, francesinha in Porto once, grilled sardines anywhere with a queue."),
    ("t_pack", "Travel", ["portugal", "packing"], "# Packing list\n\n- Walking shoes with grip (the pavements are polished stone)\n- A light jacket for the evenings\n- Plug adapter\n- The rail pass printout"),
    ("t_budget", "Travel", ["portugal", "budget"], "# Trip budget\n\nRoughly 1,900 for two, flights included. The quinta night is the splurge; everything else is mid-range."),
    ("t_phrases", "Travel", ["portugal", "language"], "# Useful phrases\n\nObrigado or obrigada, depending on who is speaking. Uma bica is an espresso in Lisbon and um cimbalino in Porto."),
    ("t_photos", "Travel", ["photography"], "# Photo spots\n\nMiradouro da Senhora do Monte at golden hour. The Dom Luís I bridge from the upper deck. Arrive early, leave the tripod."),
    # Cooking: a looser cluster.
    ("c_sour", "Cooking", ["baking", "sourdough"], "# Sourdough log\n\nLoaf 6: 78% hydration, 20 hour cold proof. Best crumb yet, still pale underneath. Next time the stone goes one shelf lower."),
    ("c_starter", "Cooking", ["baking", "sourdough"], "# Starter feeding\n\n1:5:5 at night, ready by morning in a warm kitchen. In winter it needs the oven with only the light on."),
    ("c_week", "Cooking", ["recipes", "weeknight"], "# Weeknight dinners\n\nFive that take under 30 minutes: miso salmon, chickpea curry, lemon orzo, egg fried rice, and the tomato soup below."),
    ("c_soup", "Cooking", ["recipes"], "# Roast tomato soup\n\nRoast the tomatoes and garlic first, add a little smoked paprika, blend half and leave the rest chunky."),
    ("c_curry", "Cooking", ["recipes", "weeknight"], "# Chickpea curry\n\nOnion, garlic, ginger, a spoon of curry paste, a tin of chickpeas and a tin of coconut milk. Spinach at the end."),
    ("c_pizza", "Cooking", ["baking"], "# Pizza night\n\nThe sourdough discard makes a good thin base. 48 hour dough, hottest oven, steel on the top shelf."),
    ("c_meal", "Cooking", ["planning"], "# Meal prep Sundays\n\nCook grains and one sauce for the week. Freeze half the soup. Saves about four evenings."),
    ("c_nata", "Cooking", ["baking", "portugal"], "# Trying pastéis de nata at home\n\nShop-bought puff pastry, rolled tight into a log. The custard needs the hottest oven the kitchen has; mine scorched at 250."),
    ("c_knife", "Cooking", ["kitchen"], "# Knife sharpening\n\nWhetstone at 15 degrees, 1000 then 6000 grit. Every two months, or when the tomato test fails."),
    ("c_spice", "Cooking", ["kitchen"], "# Spice drawer\n\nToast whole spices before grinding. Buy small, label with the month."),
    # Health: a small tree round the training plan.
    ("h_plan", "Health", ["running", "half-marathon"], "# Half marathon plan\n\nTwelve weeks to the October race. Three runs a week: one easy, one tempo, one long. The long run grows by a kilometre a week."),
    ("h_week4", "Health", ["running"], "# Week 4\n\nEasy pace is still too fast. Slow the Tuesday run down until it is boring, then hold it for three weeks."),
    ("h_knee", "Health", ["running", "physio"], "# Physio, left knee\n\nFoam roll the IT band after every long run. Single-leg squats twice a week, three sets of ten."),
    ("h_shoes", "Health", ["running", "gear"], "# New running shoes\n\nThe old pair has 700 km on it. Try two in the shop, run on the treadmill in both."),
    ("h_sleep", "Health", ["sleep"], "# Sleep notes\n\nScreens off at 10:30 helps more than anything else tried. Coffee after 2pm costs about forty minutes."),
    ("h_fuel", "Health", ["running", "nutrition"], "# Fuel on long runs\n\nA gel every 40 minutes past the first hour. Practise it in training, never new on race day."),
    ("h_stretch", "Health", ["mobility"], "# Morning mobility\n\nTen minutes: hips, hamstrings, thoracic rotation. Done before coffee or it does not happen."),
    ("h_dentist", "Health", ["admin"], "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard."),
    ("h_race", "Health", ["running", "half-marathon"], "# Race day checklist\n\n- Bib and pins the night before\n- Same breakfast as the long runs\n- Start slower than feels right"),
    # Reading: a sparse web, a chain with a few cross threads.
    ("r_systems", "Reading", ["books", "systems"], "# Thinking in Systems\n\nStocks and flows, and why a delay inside a feedback loop makes a system oscillate instead of settle. The bathtub example finally made it click."),
    ("r_weeks", "Reading", ["books", "time"], "# Four Thousand Weeks\n\nThe point is not to get everything done; it is to choose what to neglect on purpose. Pairs well with the systems book."),
    ("r_design", "Reading", ["books", "design"], "# The Design of Everyday Things\n\nA door that needs a sign has failed. Affordances, signifiers and feedback: the three words I now use in every design review."),
    ("r_habits", "Reading", ["books", "habits"], "# Atomic habits, the useful bits\n\nMake the good thing the easy thing. Lay the running kit out the night before; it works better than willpower."),
    ("r_essay", "Reading", ["essays", "writing"], "# On writing short\n\nAn essay about cutting: every sentence should earn its place, and the first draft is for finding out what you think."),
    ("r_pod", "Reading", ["podcasts"], "# Podcast: slow productivity\n\nDo fewer things, work at a natural pace, obsess over quality. Fewer open loops means less time spent switching."),
    ("r_list", "Reading", ["books"], "# Reading list\n\n- Designing Data-Intensive Applications\n- The Mom Test\n- A Pattern Language\n- Ways of Seeing"),
    ("r_data", "Reading", ["books", "engineering"], "# Designing Data-Intensive Applications\n\nChapter 5 on replication is the one to reread before the sync rewrite. Leaderless replication and read repair."),
    ("r_mom", "Reading", ["books", "research"], "# The Mom Test\n\nAsk about their life, not your idea. Specifics in the past beat opinions about the future."),
    ("r_poem", "Reading", ["poetry"], "# A line worth keeping\n\nFrom a poem read on the train: attention is the beginning of devotion."),
    ("r_pattern", "Reading", ["books", "architecture"], "# A Pattern Language\n\nA window place: people are drawn to light. True of rooms, and oddly true of app screens too."),
    # Home: mostly loose notes.
    ("o_garden", "Home", ["garden"], "# Garden, spring jobs\n\nCut back the lavender after the last frost. Move the rosemary into the sun. Sow the beans in the second week of April."),
    ("o_boiler", "Home", ["maintenance"], "# Boiler service\n\nDue in March. The pressure keeps dropping to 0.8; mention it. The engineer last time said the valve was worn."),
    ("o_paint", "Home", ["decorating"], "# Paint for the study\n\nTwo samples on the wall: a warm white and a pale green. The green wins in the afternoon light."),
    ("o_insur", "Home", ["admin"], "# Home insurance renewal\n\nThe renewal quote went up 30%. Compare three before the 1st; the old policy covers accidental damage, keep that."),
    ("o_plants", "Home", ["garden", "plants"], "# Houseplants\n\nThe fiddle leaf wants the east window and less water. Repot the monstera in spring."),
    ("o_shelf", "Home", ["diy"], "# Shelves in the hall\n\nStud finder first. Two brackets per metre, 6mm plugs. The oak board needs a coat of oil before it goes up."),
    ("o_bins", "Home", ["admin"], "# Bin days\n\nRecycling is every other Tuesday; food waste every week. The calendar is on the fridge."),
    ("o_bike", "Home", ["maintenance"], "# Bike service\n\nThe gears skip under load. New chain and a cassette check before the summer."),
    ("o_wifi", "Home", ["tech"], "# Wi-fi in the back room\n\nOne mesh point on the landing fixed it. Speed in the study went from 4 to 180."),
    # Ideas: the bridges between clusters.
    ("i_offline", "Ideas", ["harbor", "product"], "# Offline as the headline\n\nBeta testers did not know Harbor works offline. What if that is the first thing the store page says, not the fifth?"),
    ("i_maps", "Ideas", ["product", "maps"], "# Notes as a map\n\nA node on a board could be a real note, so the map and the notebook stay one thing."),
    ("i_journal", "Ideas", ["writing", "habits"], "# A five-line journal\n\nOne line each: what happened, what I learned, what I am grateful for, what tomorrow needs, one word for the day."),
    ("i_trip", "Ideas", ["portugal", "photography"], "# A photo book of the trip\n\nTwenty pictures, one per page, with a line from these notes under each."),
    ("i_garden", "Ideas", ["garden", "systems"], "# The garden as a system\n\nCompost is the stock, kitchen scraps the inflow. The delay is about six months, which is why it never feels like it is working."),
    ("i_teach", "Ideas", ["writing"], "# Teach what I just learned\n\nWrite a short post after each book: the one idea I would keep. It forces the reading to be active."),
    ("i_bread", "Ideas", ["baking", "habits"], "# A bread habit\n\nBake every Saturday for twelve weeks and log each loaf. Same habit rule as running: make the start easy."),
]

# Links: (a, b, reason or None). A reason is what the note's Connections
# column and the graph's hover show; a plain link is one made by hand with no
# reason given, which is how most hand links are.
LINKS: list[tuple[str, str, str | None]] = [
    # Work, dense.
    ("w_plan", "w_roadmap", "The launch is the first of the quarter's three workstreams"),
    ("w_plan", "w_beta", "Beta feedback closing is the first launch gate"),
    ("w_plan", "w_onboard", "The onboarding rewrite is the second gate"),
    ("w_plan", "w_pricing", "Pricing sign-off is the third gate"),
    ("w_plan", "w_store", None),
    ("w_plan", "w_email", None),
    ("w_plan", "w_metrics", "What success means for the launch"),
    ("w_plan", "w_risks", "What could move the launch date"),
    ("w_beta", "w_onboard", "The top beta complaint is the nine-field sign-up"),
    ("w_beta", "i_offline", "Testers could not find offline mode"),
    ("w_onboard", "w_standup", None),
    ("w_pricing", "w_risks", "Pricing sign-off is one of the three risks"),
    ("w_roadmap", "w_sync", "The second workstream"),
    ("w_roadmap", "w_support", "The third workstream"),
    ("w_roadmap", "w_hiring", None),
    ("w_sync", "w_risks", "Sync conflicts under load are a launch risk"),
    ("w_sync", "w_perf", None),
    ("w_retro", "w_perf", "Measuring first is what found the slow list"),
    ("w_retro", "w_standup", None),
    ("w_store", "w_email", None),
    ("w_store", "i_offline", "Lead the store page with offline"),
    ("w_metrics", "w_beta", None),
    ("w_support", "w_api", None),
    ("w_api", "w_sync", None),
    ("w_hiring", "w_onboard", None),
    # Travel, dense round the overview.
    ("t_over", "t_lisbon", "Four days of the ten"),
    ("t_over", "t_sintra", "The day trip from Lisbon"),
    ("t_over", "t_porto", "Three days of the ten"),
    ("t_over", "t_douro", "The last two days"),
    ("t_over", "t_flights", None),
    ("t_over", "t_trains", None),
    ("t_over", "t_budget", "What the ten days cost"),
    ("t_over", "t_pack", None),
    ("t_lisbon", "t_sintra", "The Sintra train leaves from Rossio in Lisbon"),
    ("t_lisbon", "t_trains", None),
    ("t_porto", "t_trains", "The Alfa Pendular runs Lisbon to Porto"),
    ("t_porto", "t_douro", "The hire car is collected in Porto"),
    ("t_lisbon", "t_food", None),
    ("t_porto", "t_food", None),
    ("t_flights", "t_budget", None),
    ("t_lisbon", "t_photos", None),
    ("t_porto", "t_photos", "The bridge from the upper deck"),
    ("t_phrases", "t_food", None),
    ("t_pack", "t_trains", None),
    # Cooking, looser.
    ("c_sour", "c_starter", "The log depends on the starter's timing"),
    ("c_sour", "c_pizza", "Pizza uses the sourdough discard"),
    ("c_week", "c_soup", None),
    ("c_week", "c_curry", None),
    ("c_week", "c_meal", "Meal prep is how the weeknights stay under 30 minutes"),
    ("c_meal", "c_soup", None),
    ("c_knife", "c_spice", None),
    ("c_nata", "t_food", "Trying the Belém tart at home"),
    ("c_nata", "c_sour", None),
    ("c_starter", "c_pizza", "Discard from the feed goes into the dough"),
    ("c_curry", "c_meal", None),
    ("c_soup", "c_curry", None),
    ("c_spice", "c_curry", "Toast the whole spices first"),
    ("c_knife", "c_week", None),
    ("c_pizza", "c_week", None),
    # Health, a tree.
    ("h_plan", "h_week4", None),
    ("h_plan", "h_knee", "The knee work keeps the plan on track"),
    ("h_plan", "h_shoes", None),
    ("h_plan", "h_fuel", None),
    ("h_plan", "h_race", "The race the twelve weeks lead to"),
    ("h_knee", "h_stretch", None),
    ("h_sleep", "h_week4", None),
    # Reading, sparse: a chain and a few threads.
    ("r_systems", "r_weeks", None),
    ("r_weeks", "r_pod", None),
    ("r_pod", "r_habits", None),
    ("r_design", "r_pattern", "Both are about what people are drawn to"),
    ("r_list", "r_data", None),
    ("r_list", "r_mom", None),
    ("r_data", "w_sync", "Chapter 5 before the sync rewrite"),
    ("r_mom", "w_beta", "How to ask the beta testers better questions"),
    ("r_design", "w_onboard", None),
    # Ideas, the bridges.
    ("i_maps", "r_design", None),
    ("i_journal", "r_habits", None),
    ("i_journal", "r_essay", None),
    ("i_trip", "t_photos", "The pictures for the book"),
    ("i_trip", "t_over", None),
    ("i_garden", "r_systems", "Stocks, flows and a delay"),
    ("i_garden", "o_garden", None),
    ("i_teach", "r_essay", None),
    ("i_bread", "c_sour", "Log each loaf"),
    ("i_bread", "r_habits", "The same make-it-easy rule"),
    ("r_habits", "h_plan", "Lay the running kit out the night before"),
    # Home, mostly loose: one pair.
    ("o_garden", "o_plants", None),
]

PINNED = ["w_plan", "t_over", "c_sour"]


def note_title(content: str) -> str:
    first = content.strip().splitlines()[0]
    return first.lstrip("# ").strip()


def main() -> None:
    sign_in()
    if call("GET", "/entries?limit=1"):
        raise SystemExit("This notebook already has notes: run me on a fresh data dir.")

    ids: dict[str, int] = {}
    for key, category, tags, content in NOTES:
        made = call("POST", "/entries", {"content": content, "tags": tags, "category": category})
        ids[key] = made["id"]
    print("notes", len(ids))

    ok = 0
    for a, b, reason in LINKS:
        body = {"target_id": ids[b]}
        if reason:
            body["reason"] = reason
        call("POST", f"/entries/{ids[a]}/links", body)
        ok += 1
    print("links", ok, "with a reason", sum(1 for *_, r in LINKS if r))

    for key in PINNED:
        call("PUT", f"/entries/{ids[key]}", {"pinned": True})

    #: Due at a time of day a person would pick, in the zone the screenshots
    #: are taken in (readmeshots.js, TZ_ID, UTC+8 by default): days ahead,
    #: then the hour. Day 0 is today, which takes the evening so it is still
    #: ahead whenever the seed runs.
    zone = dt.timezone(dt.timedelta(hours=8))
    today = dt.datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    reminders = [
        ("Send the launch email to the team for review", 0, 21, "high", "none", "w_email"),
        ("Feed the starter", 1, 8, "normal", "daily", "c_starter"),
        ("Book the Alfa Pendular tickets (60 days ahead)", 1, 12, "high", "none", "t_trains"),
        ("Long run, 14 km", 1, 18, "normal", "weekly", "h_plan"),
        ("Portfolio review for the designer role", 2, 10, "normal", "none", "w_hiring"),
        ("Compare three home insurance quotes", 3, 19, "low", "none", "o_insur"),
        ("Water the houseplants", 4, 9, "low", "weekly", None),
        ("Boiler service: mention the pressure", 5, 9, "normal", "none", "o_boiler"),
        #: Further out, so the Timeline's month calendar (the README shot)
        #: has something in its last weeks, as a real month does.
        ("Harbor launch: go or no-go", 8, 11, "high", "none", "w_email"),
        ("Dentist, 8:30", 10, 8, "normal", "none", None),
        ("Renew the passport photos", 13, 14, "low", "none", "t_trains"),
        ("Sourdough: refresh the starter jar", 15, 9, "low", "none", "c_starter"),
        ("Half marathon registration closes", 17, 12, "normal", "none", "h_plan"),
        ("Fly to Lisbon", 19, 7, "high", "none", "t_trains"),
    ]
    for text, days, hour, priority, recurring, key in reminders:
        due = today + dt.timedelta(days=days, hours=hour)
        if due <= dt.datetime.now(zone):  # a late run: tomorrow, same hour
            due += dt.timedelta(days=1)
        body = {"text": text, "due_at": due.isoformat(), "priority": priority, "recurring": recurring}
        if key:
            body["entry_id"] = ids[key]
        call("POST", "/reminders", body)
    print("reminders", len(reminders))

    for title, content in DOCUMENTS:
        call("POST", "/documents", {"title": title, "content": content})
    print("documents", len(DOCUMENTS))

    board = seed_board()
    mind = seed_map()
    print("board", board, "map", mind)

    for question, answer in CHATS:
        call("POST", "/conversations", {"question": question, "answer": answer})
    print("chats", len(CHATS))

    #: A name for the greeting, set where a person sets it (Settings,
    #: Profile); a fictional one.
    call("PUT", "/preferences", {"display_name": "Maya"})

    answer_suggestions(ids)
    backdate(ids)


def answer_suggestions(ids: dict[str, int]) -> None:
    """Dismiss the suggested tags that came from another subject.

    With no model, a note's suggested tags come from the tags on the notes
    most like it by words, and in a notebook made in one go that offers
    "harbor" on a bread recipe. A person presses that tag's x ("stop
    suggesting it"); this does the same, through the same route, for every
    suggestion no note of the same category carries, and leaves the rest on
    the cards so the feature still shows.
    """
    import time

    time.sleep(3)  # filing runs after the response; let it settle
    category = {key: cat for key, cat, _tags, _content in NOTES}
    own: dict[str, set[str]] = {}
    for _key, cat, tags, _content in NOTES:
        own.setdefault(cat, set()).update(t.casefold() for t in tags)
    dismissed = kept = 0
    #: Read from the list, not note by note: opening a note counts as a use,
    #: and 75 reads put every note in the sidebar's Most used.
    listed = {e["id"]: e for e in call("GET", "/entries?limit=200")}
    for key, entry_id in ids.items():
        offered = listed[entry_id].get("suggested_tags") or []
        off = [t for t in offered if t.casefold() not in own[category[key]]]
        if off:
            call("POST", f"/entries/{entry_id}/suggested-tags", {"discard": off})
        dismissed += len(off)
        kept += len(offered) - len(off)
    print("suggested tags dismissed", dismissed, "kept", kept)


# --- Documents ---------------------------------------------------------------

DOCUMENTS = [
    (
        "Harbor launch brief",
        "\n".join([
            "# Harbor launch brief",
            "",
            "Harbor is a notes app that sorts itself and works with no connection. This brief is the one page everyone on the launch works from: what we are shipping, to whom, and how we will know it worked.",
            "",
            "## What ships on the 14th",
            "",
            "- The mobile app on both stores, free tier and paid tier",
            "- The four-field sign-up, with the name asked for on the first share",
            "- Offline mode on by default, and said so on the first screen",
            "",
            "## Who it is for",
            "",
            "People who write a lot of short notes and never go back to them. The beta told us they want to find things again more than they want features, so the launch leads with search and offline, not with the long feature list.",
            "",
            "## How we will know",
            "",
            "| Measure | Target | Why |",
            "| --- | --- | --- |",
            "| Week-two retention | 35% | People came back after the novelty |",
            "| Notes in week one | 12 per person | The habit started |",
            "| Support tickets per 100 installs | under 3 | The sign-up is clear |",
            "",
            "## Open questions",
            "",
            "The store review could take longer than a week, so the date has one week of slack in it. The pricing page still needs sign-off, and the launch email waits on it.",
            "",
            "## After launch",
            "",
            "Two weeks of fixes only, then the sync rewrite starts. Nothing new ships in those two weeks unless it fixes something a person reported.",
        ]),
    ),
    (
        "Portugal itinerary",
        "# Portugal itinerary\n\n## Lisbon, days 1 to 4\n\nAlfama walk, Belém, the LX Factory market on Sunday.\n\n## Sintra, day 5\n\nPena Palace at opening time, Regaleira after lunch.\n\n## Porto, days 6 to 8\n\nRibeira, Gaia port lodges, the Serralves gardens.\n\n## Douro, days 9 and 10\n\nThe river road to Pinhão, one night at a quinta.",
    ),
    (
        "Sourdough method",
        "# Sourdough method\n\n1. Feed the starter 1:5:5 the night before.\n2. Mix 500g flour, 390g water, 100g starter, 10g salt.\n3. Four sets of folds, thirty minutes apart.\n4. Shape, then 20 hours in the fridge.\n5. Bake at 250 with the lid on for 20 minutes, 230 with it off for 25.",
    ),
]


# --- Board: cards, shapes holding text, labelled connectors -----------------


def seed_board() -> int:
    board = call("POST", "/whiteboard/boards", {"name": "Harbor launch board", "type": "board"})
    bid = board["id"]

    def card(x, y, w, h, text, bg=None, border=None):
        data = {"content": text}
        if bg:
            data["bg"] = bg
        if border:
            data["border_color"] = border
        return call("POST", "/whiteboard/objects", {"kind": "text", "board_id": bid, "x": x, "y": y, "width": w, "height": h, "data": data})["id"]

    def sketch(data: dict, z: int = 5) -> int:
        import json

        return call("POST", "/whiteboard/sketches", {"board_id": bid, "x": 0, "y": 0, "z": z, "data": json.dumps(data)})["id"]

    def rect(x, y, w, h, label, fill, color):
        return sketch({"d": f"M {x} {y} h {w} v {h} h {-w} Z", "color": color, "width": 2, "shape": "rect", "fill": fill, "fillOpacity": 1, "label": label})

    def diamond(cx, cy, w, h, label, fill, color):
        return sketch({"d": f"M {cx} {cy - h / 2} L {cx + w / 2} {cy} L {cx} {cy + h / 2} L {cx - w / 2} {cy} Z", "color": color, "width": 2, "shape": "diamond", "fill": fill, "fillOpacity": 1, "label": label})

    def link(a, b, label=None, curved=False, a_kind="sketch", b_kind="sketch", color="#8a93a6"):
        data = {"type": "link-curved" if curved else "link-straight", "sourceId": a, "targetId": b, "sourceKind": a_kind, "targetKind": b_kind, "color": color}
        if label:
            data["label"] = label
        return sketch(data, z=1)

    # A banner, then the three columns of cards on the left.
    card(40, 30, 1240, 64, "Harbor launch: the last four weeks", "#3b4fd8", "#3b4fd8")
    card(40, 130, 250, 40, "Now")
    card(40, 180, 250, 92, "Rewrite the store listing: one sentence, then the proof", "#1f3a5f", "#3d6fb8")
    card(40, 290, 250, 92, "Five screenshots, dark and light", "#1f3a5f", "#3d6fb8")
    card(320, 130, 250, 40, "Next")
    card(320, 180, 250, 92, "Move the pricing table above the fold", "#2c3a22", "#5f8f3f")
    card(320, 290, 250, 92, "Cut the sign-up from nine fields to four", "#2c3a22", "#5f8f3f")
    card(990, 140, 200, 80, "Store review can take a week: submit by the 7th", "#4d4318", "#d4b24c")
    card(40, 410, 530, 110, "From the Thursday demo: the progress dots read as a carousel. Replace them with a step count.", None, "#6b7280")
    # The release flow on the right: shapes with text, joined by labelled
    # connectors (WHITEBOARD_PLAN decisions 12 and 13).
    freeze = rect(650, 140, 200, 70, "Feature freeze", "#24324a", "#6f8fd6")
    check = diamond(750, 300, 230, 120, "All checks green?", "#3a2f4f", "#a58be0")
    beta = rect(990, 265, 200, 70, "Ship to beta", "#1f3d33", "#4fb38a")
    fix = rect(650, 420, 200, 70, "Fix and rerun", "#4a2c2c", "#d06a6a")
    store = rect(990, 420, 200, 70, "Submit to the stores", "#1f3d33", "#4fb38a")
    link(freeze, check)
    link(check, beta, "yes")
    link(check, fix, "no")
    link(beta, store, "after a week")
    return bid


# --- Mind map: tasks, a note behind a topic, numbered branches ---------------


def seed_map() -> int:
    board = call("POST", "/whiteboard/boards", {"name": "Portugal trip", "type": "map", "layout": "tree-both"})
    bid = board["id"]
    nodes: dict[str, dict] = {}

    def node(key, text, parent=None):
        body = {"kind": "topic", "text": text}
        if parent:
            body["parent_id"] = nodes[parent]["id"]
        nodes[key] = call("POST", f"/whiteboard/boards/{bid}/nodes", body)

    def style(key, **patch):
        obj = nodes[key]
        data = {k: v for k, v in (obj.get("data") or {}).items() if v is not None}
        data.update(patch)
        body = {k: obj[k] for k in ("kind", "board_id", "x", "y", "z", "width", "height")}
        body["data"] = data
        nodes[key] = call("PUT", f"/whiteboard/objects/{obj['id']}", body)

    node("root", "Portugal trip")
    node("book", "Bookings", "root")
    node("flights", "Flights", "book")
    node("trains", "Alfa Pendular tickets", "book")
    node("quinta", "Quinta near Pinhão", "book")
    node("car", "Hire car in Porto", "book")
    node("lis", "Lisbon", "root")
    node("alfama", "Alfama walk", "lis")
    node("belem", "Belém and the tarts", "lis")
    node("sintra", "Sintra day trip", "lis")
    node("porto", "Porto", "root")
    node("ribeira", "Ribeira at sunset", "porto")
    node("gaia", "Port lodge in Gaia", "porto")
    node("pack", "Packing", "root")
    node("shoes", "Shoes with grip", "pack")
    node("adapter", "Plug adapter", "pack")
    node("jacket", "Light jacket", "pack")
    node("budget", "Budget, about 1,900", "root")
    # Tasks: the bookings and the packing are things to tick off.
    for key, state in (("flights", "done"), ("trains", "open"), ("quinta", "done"), ("car", "open"), ("shoes", "done"), ("adapter", "open"), ("jacket", "open")):
        style(key, task=state)
    # A note behind a topic (the mark on it opens it).
    style("sintra", note="Train from Rossio, 40 minutes. Pena Palace first with a timed ticket; Regaleira after lunch when the buses leave.")
    style("flights", note="Out to Lisbon, back from Porto. Seats 14A and 14B.")
    # Icons on a few topics (a Phosphor name, or one emoji), as the strip's
    # Icon picker writes them.
    for key, icon in (("flights", "airplane-tilt"), ("quinta", "bed"), ("lis", "tram"), ("porto", "wine"), ("pack", "backpack"), ("budget", "coins")):
        style(key, icon=icon)
    # A look per level (decision 40): a boxed hierarchy, a vivid palette, the
    # centre larger and the main branches bold.
    call(
        "PUT",
        f"/whiteboard/boards/{bid}",
        {
            "numbered": True,
            "theme": {
                "palette": "vivid",
                "hierarchy": "boxed",
                "levels": {"0": {"font_size": 25, "bold": True}, "1": {"font_size": 19, "bold": True, "fill": "tint"}, "2": {"font_size": 12}},
            },
        },
    )
    return bid


# --- Chats -------------------------------------------------------------------

CHATS = [
    (
        #: Not the Harbor question: readmeshots.js asks that one live, and
        #: a saved copy sat under it in the chat list as a duplicate.
        "Where should we stay in Lisbon?",
        "Your note weighs two areas. Alfama has the walk-everywhere feel, but its hills are steep with luggage. Príncipe Real is quieter and close to the metro, which suits four days with a day trip to Sintra from Rossio.",
    ),
    (
        "Plan a quick dinner from my recipes",
        "The chickpea curry is the quickest: onion, garlic and ginger, a spoon of curry paste, a tin of chickpeas and one of coconut milk, with spinach stirred in at the end. If you did the Sunday meal prep, the frozen tomato soup is even faster.",
    ),
    (
        "How is my half marathon training going?",
        "You are in week 4 of twelve. Your note says the easy pace is still too fast, so the plan is to slow the Tuesday run until it is boring. The knee work (foam rolling and single-leg squats) is keeping you on track, and the shoes are due for replacing at 700 km.",
    ),
    (
        "Summarise what I have read about systems",
        "Two books carry it. Thinking in Systems gave you stocks, flows and delays in feedback loops; you later used the same idea for the garden, where compost is the stock and the delay is six months. Four Thousand Weeks adds the other half: choosing what to neglect on purpose.",
    ),
]


# --- Dates -------------------------------------------------------------------


def backdate(ids: dict[str, int]) -> None:
    """Spread the notes over the last seven weeks, one or two most days.

    Straight into the database, because no route takes a creation date.
    Shuffled first (seeded, so every run is the same notebook), so the
    categories interleave over the weeks the way a real notebook's do rather
    than arriving one subject at a time, and the streak and the timeline have
    a shape. A link is dated with the newer of its two notes.
    """
    rng = random.Random(14)
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    keys = list(ids)
    rng.shuffle(keys)
    # The last eight notes written today and yesterday, the rest spread back.
    stamps = []
    for i in range(len(keys)):
        days_ago = (len(keys) - 1 - i) * 48 / len(keys)
        when = now - dt.timedelta(days=days_ago, hours=rng.uniform(0, 6), minutes=rng.uniform(0, 59))
        stamps.append(min(when, now - dt.timedelta(minutes=5 + (len(keys) - i) * 3)))
    #: The file the app writes: `tessellate.db`, or the old name on a notebook from before the rename (audit 1031 N29).
    db = sqlite3.connect(next((p for p in (DATA / "tessellate.db", DATA / "memorymap.db") if p.exists()), DATA / "tessellate.db"))
    with db:
        for key, when in zip(keys, stamps):
            iso = when.strftime("%Y-%m-%d %H:%M:%S.%f")
            db.execute("UPDATE entries SET created_at = ?, updated_at = ? WHERE id = ?", (iso, iso, ids[key]))
        db.execute("UPDATE entry_links SET created_at = (SELECT MAX(created_at) FROM entries WHERE entries.id IN (entry_links.source_entry_id, entry_links.target_entry_id))")
    db.close()
    print("dates spread over", round((now - stamps[0]).days), "days")


if __name__ == "__main__":
    main()
