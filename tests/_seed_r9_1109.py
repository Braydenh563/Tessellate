"""The composer audit round 9 notebook (50 notes, 11 title-less, 3 title-only, near-duplicate topics),
clock fixed at Monday 9 November 2026, 12:00 (docs/roadmap/agent-remaining/composer-r9-1109.md).
Shared by the tests that pin a class of that audit (R9-n)."""
from __future__ import annotations

import json
from datetime import datetime, date

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

TODAY = date(2026, 11, 9)
NOW = datetime(2026, 11, 9, 12, 0)

# (title or None for a title-less note, body, days ago)
NOTES = [
    ("Sourdough", "My sourdough starter is called Doug. Feed it daily with 50 g flour and 50 g water. Bake at 230C for 40 minutes, lid on for the first 20.", 60),
    ("Sourdough attempt 2", "Too dense again. Needs a longer proof, maybe 12 hours in the fridge.", 20),
    (None, "bread was flat again, starter looked sluggish. try warmer spot", 6),
    ("Mum", "Mum's birthday is 2 December. She likes orchids and crime novels. Her phone is 07700 900123.", 90),
    (None, "call mum about christmas plans", 2),
    (None, "Mum's hospital appointment is Thursday 12 November at 10am at St Mary's. I said I'd drive her.", 4),
    ("Book club", "Book club meets the first Tuesday of each month at Hannah's. Next book: The Remains of the Day.", 50),
    ("Book club notes", "We discussed Klara and the Sun. Hannah loved it, Raj didn't. Next time bring wine.", 15),
    ("Reading", "Currently reading Wolf Hall. Want to read: The Overstory, Tomorrow and Tomorrow and Tomorrow, and Piranesi.", 12),
    ("Kitchen renovation", "Budget £8,000. Builder is Marek, phone 07700 900456. Work starts 16 November. Worktops will be oak.", 40),
    ("Kitchen quotes", "| Builder | Quote |\n|---|---|\n| Marek | £7,200 |\n| BuildRight | £9,100 |\n| Kowalski & Sons | £8,400 |", 45),
    (None, "marek said the worktops are delayed by a week", 3),
    ("Car insurance", "Renewal due 28 November. Current provider is Admiral at £412 a year.", 30),
    ("Home insurance", "Home insurance renews in March with Aviva, £180 a year.", 80),
    ("Python course", "Week 3: list comprehensions. Assignment due Friday 13 November.", 9),
    (None, "saw a huge python at the zoo with the kids, they loved the reptile house", 25),
    ("Meeting with Raj", "Raj wants the Q4 report by 20 November. We agreed to move standup to 9:30.", 6),
    ("Q4 report", "Sales up 12%, churn down to 3%. Draft goes to Raj by 20 November.", 8),
    ("Allotment", "Plot 14. Plant garlic in November. Rent is £45 a year, due in January.", 70),
    (None, "planted the garlic today, three rows by the shed", 1),
    ("Wifi", "Network name Fernhill. The password is on the card in the kitchen drawer.", 100),
    ("Ideas", "App idea: a plant watering tracker. Podcast idea: interviews with allotment holders.", 33),
    ("Call plumber", "Call plumber", 5),
    ("Renew passport", "Renew passport", 14),
    ("Thai green curry", "Thai green curry", 22),
    ("Journal 7 November", "Felt tired. Walked to the park with Mum. Started Wolf Hall.", 2),
    (None, "Rough day at work, the Q4 numbers didn't add up and Raj was annoyed.", 10),
    ("Running", "Goal: half marathon in April. Long run every Sunday.", 65),
    ("Running log", "Ran 10 km on 1 November in 58 minutes. Ran 12 km on 8 November in 71 minutes.", 1),
    ("Holiday options", "Japan: £2,400 for two weeks, best in April. Portugal: £1,100 for ten days, best in May.", 18),
    ("Shopping list", "- [ ] oat milk\n- [ ] garlic\n- [x] coffee beans\n- [ ] lemons", 2),
    ("Todo", "- [ ] email Raj the draft\n- [ ] book car service\n- [x] pay council tax\n- [ ] call plumber about the leak", 3),
    ("Plumber", "Leak under the kitchen sink. Plumber is Dave, 07700 900789. He is coming Wednesday 11 November at 8am.", 4),
    ("Doctor", "GP appointment Friday 13 November at 9:10 with Dr Okafor. Bring the blood test letter.", 7),
    ("Hannah", "Hannah is my friend from uni. She hosts book club. She is allergic to nuts.", 120),
    ("Raj", "Raj is my manager. He prefers email to Slack.", 110),
    ("Meditation", "Ten minutes every morning with the Calm app. Helps with sleep.", 35),
    ("Mediterranean diet", "More olive oil, fish twice a week, less red meat.", 36),
    ("Apple crumble", "4 apples, 100 g butter, 150 g flour, 75 g sugar. Bake 35 minutes at 180C.", 55),
    ("Apple watch", "Battery dies by 6pm. Try turning off the always-on display.", 28),
    ("Spanish", "Lesson every Thursday at 7pm. Teacher is Lucía. Homework: irregular verbs.", 26),
    ("Concert", "Arctic Monkeys at the O2 on 5 December. Tickets £75 each, bought two.", 21),
    (None, "Remember the boiler pressure should be 1.5 bar.", 48),
    (None, "need to buy a birthday present for mum, maybe the new Ann Cleeves", 3),
    ("Pickle", "Pickle is our cat. Born April 2019. Eats Felix pouches. Vet is Dr Shah, booster jab due in January.", 75),
    ("Gift ideas", "Mum: orchid, Ann Cleeves novel. Hannah: nut-free chocolates. Raj: nothing, he's my boss.", 11),
    ("Japan", "Want to see Kyoto and Nara. JR pass is about £300.", 19),
    ("Portugal", "Lisbon and Porto. Pastel de nata in Belém.", 17),
    (None, "Doug the starter is bubbly again after moving it near the radiator", 1),
    ("Weekly review 1 November", "Good week. Finished the Q4 draft outline. Ran twice. Skipped meditation.", 8),
]


def seed(session):
    ids = []
    for title, body, ago in NOTES:
        content = body if title is None else (f"# {title}\n\n{body}" if body != title else title)
        e = manager.create_entry(session, content, category_name="Uncategorised")
        e.created_at = e.updated_at = datetime.fromordinal(TODAY.toordinal() - ago).replace(hour=10)
        ids.append(e.id)
    session.commit()
    return ids


def asker(client, monkeypatch, *, chat=False):
    """`go(question, history=None)` -> (answer text, events); Ask by default, Chat with `chat=True`."""
    fix_clock(monkeypatch)

    def go(question, history=None):
        r = ask(client, question, history=history, notes_only=not chat)
        return r["text"], r["events"]

    return go


def fix_clock(monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)


def ask(client, question, history=None, notes_only=False, use_tools=None):
    body = {"question": question, "notes_only": notes_only}
    if use_tools is not None:
        body["use_tools"] = use_tools
    if history:
        body["history"] = history
    out = {"q": question, "notes_only": notes_only, "text": "", "events": []}
    with client.stream("POST", "/chat/stream", json=body) as response:
        out["status"] = response.status_code
        for line in response.iter_lines():
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                out["events"].append({"raw": line[:300]})
                continue
            if ev.get("type") == "answer":
                out["text"] += ev.get("delta", "")
            else:
                out["events"].append(ev)
    return out
