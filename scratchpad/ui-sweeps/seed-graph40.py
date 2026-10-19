#!/usr/bin/env python3
"""40 notes in 6 categories with tags, long titles and ~55 links (INBOX 1306).

    bash scratchpad/ui-sweeps/serve.sh 8797 $SCRATCH/data-graph1306
    .venv/bin/python scratchpad/ui-sweeps/seed-graph40.py 8797

A default-settings map the way the owner described it: about forty notes,
names long enough to collide, one note linked to many (the hub) and links
that cross categories. Links are [[Title]] wikilinks in the text.
"""
import random
import sys

import requests

BASE = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else '8797'}"
S = requests.Session()
st = S.get(BASE + "/auth/status", timeout=10).json()
route = "/auth/setup" if st.get("setup_required") else "/auth/unlock"
S.headers["X-Auth-Token"] = S.post(BASE + route, json={"password": "testpassword123"}, timeout=30).json()["token"]

CATS = {
    "Work": ["Quarterly planning notes for the Harbor launch", "Meeting with the design team about onboarding", "Sprint retrospective and what we would change",
             "Pricing page copy and the comparison table", "Hiring plan for the second half of the year", "Customer interview synthesis from March",
             "Launch checklist and the risks we are watching"],
    "Travel": ["Portugal trip overview and the route between cities", "Where to stay in Lisbon with luggage and hills", "Day trip to Sintra by train from Rossio",
               "Porto in three days and the port lodges", "Flights, seats and the booking references", "Packing list for ten days in May"],
    "Cooking": ["Slow braised short ribs with red wine", "Sourdough starter feeding schedule and timing", "Weeknight dinners that take under thirty minutes",
                "Spice cupboard inventory and what to restock", "Dinner party menu for eight people"],
    "Reading": ["Notes on the book about attention and deep work", "Essay collection on cities and walking", "Reading list for the winter months",
                "Quotes worth keeping from the long novel", "Why the second half of the memoir disappointed me", "Book club questions for next month"],
    "Health": ["Running plan for the spring half marathon", "Sleep log and what changed after the new routine", "Physio exercises for the left shoulder",
               "Blood test results and questions for the doctor", "Meal prep and protein targets"],
    "Ideas": ["App idea: notes that sort themselves offline", "Small essay on why lists beat folders", "Side project: a tiny habit tracker",
              "Gift ideas for the whole family this year", "Garden redesign sketches and the planting order", "A question I keep coming back to about attention",
              "Things to learn this year in order of interest"],
}
HUB = "Quarterly planning notes for the Harbor launch"
titles = [(c, t) for c, ts in CATS.items() for t in ts]
random.seed(7)
by_cat = {c: ts for c, ts in CATS.items()}
links = {t: set() for _, t in titles}
for c, ts in CATS.items():
    for i, t in enumerate(ts[1:], 1):
        links[ts[0] if c != "Work" else HUB].add(t) if i % 2 else links[ts[i - 1]].add(t)
for _, t in titles:           # the hub: linked to by many, across categories
    if t != HUB and random.random() < 0.45:
        links[t].add(HUB)
for _ in range(14):           # bridges
    (ca, a), (cb, b) = random.sample(titles, 2)
    if ca != cb:
        links[a].add(b)
n_links = sum(len(v) for v in links.values())
for cat, t in titles:
    tag = cat.lower()
    body = f"# {t}\n\nA few lines about this, written the way a person would.\n\n" + "\n".join(f"See [[{o}]]." for o in sorted(links[t]))
    r = S.post(BASE + "/entries", json={"content": body, "tags": [tag, random.choice(["later", "now", "idea", tag + "-2"])], "category": cat}, timeout=60)
    r.raise_for_status()
print(f"{len(titles)} notes, {n_links} links, {len(CATS)} categories")
