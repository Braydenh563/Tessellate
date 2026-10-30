"""The audit-1030 composer notebook (49 notes, ids 1 to 49 in creation order)
and a way to ask it through the chat route, shared by the composer tests that
pin a class of the audit (docs/roadmap/agent-remaining/audit-1030-composer.md).
Content, tags and days-ago are the auditor's seed."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

NOW = datetime(2026, 10, 30, 2, 50)

# (content, tags, days_ago)
NOTES = [
("# Lisbon trip\nFlying out on 14 November 2026 and back on 21 November. Staying at Hotel Alfama near the castle. Flights cost $420 return. The hotel is 85 euros a night. Need to book the tram to Sintra.", ["travel","lisbon"], 12),
("# Lisbon packing list\n- [x] passport\n- [ ] charger\n- [ ] sunscreen\n- [ ] power adapter\n- [x] euros", ["travel","lisbon"], 10),
("# Tokyo trip\nPlanning for April 2027. Rough budget $3,000. Want to see Kyoto and Nara. Need a rail pass.", ["travel"], 40),
("# Budget\nRent is $1,200 a month. Groceries about $80 a week. Phone $35. Spotify $11.99. Saved $500 in October.", ["money"], 20),
("# Sourdough starter\nFeed the starter every 12 hours with equal parts flour and water. Keep it at 24C. I named it Doug. Hydration is 100%.", ["baking"], 30),
("# Sourdough loaf\nBake at 230C for 20 minutes lid on, then 25 minutes lid off. Rested the dough for 12 hours in the fridge. The loaf came out dense on 12 October.", ["baking"], 18),
("# Banana bread\nThree ripe bananas, 200g flour, 100g sugar, 2 eggs. Bake at 175C for 55 minutes. Added walnuts last time and it was better.", ["baking"], 25),
("# Running log\nRan 5 km on 3 October in 28 minutes. Ran 8 km on 17 October. Goal is a half marathon in March 2027.", ["fitness","running"], 27),
("# Running plan\nMonday rest. Tuesday 5 km easy. Thursday intervals. Saturday long run.", ["fitness","running"], 26),
("# Gym\nSquat 80kg, bench 60kg, deadlift 100kg. Gym on Monday, Wednesday and Friday.", ["fitness"], 33),
("# Sara\nSara is my sister. Her birthday is 12 December. She likes jazz and dark chocolate. I called her on 25 October.", ["people","family"], 35),
("# Tom\nTom from work. Met at the conference in June. He works on the data team. He said he would send the report by Friday.", ["people","work"], 22),
("# Dentist\nDentist appointment on 4 November 2026 at 9:30. Dr Patel. Bring the insurance card.", ["health"], 9),
("# Project Atlas\nAtlas is the new onboarding tool at work. Beta on 10 November. Launch on 20 November. Priya owns it.", ["work","atlas"], 21),
("# Meeting with Priya\nOn 28 October we talked about the Atlas scope. We decided to cut the reporting page. Next check in on 6 November.", ["work","atlas"], 2),
("# Books\nReading Dune by Frank Herbert. Finished Piranesi in September. Want to read The Overstory next.", ["books"], 15),
("# Piranesi\nLoved it. A strange house of statues and tides. I gave it 9/10.", ["books"], 44),
("# Movies\nWatched Arrival on 9 October and liked it a lot. Dune Part Two was long. Next up is Past Lives.", ["movies"], 21),
("# Uni\nSemester two. The cloud computing assignment is due on 15 November. Exam on 12 December.", ["uni"], 16),
("# Cloud computing\nLecture notes: IaaS, PaaS and SaaS are the three service models. Containers share the host kernel. Autoscaling adds servers when load rises.", ["uni"], 14),
("Just missed the bus to uni today, so annoyed.", [], 4),
("Need to call the bank about the card", [], 3),
("Idea: a podcast about local history", [], 11),
("Mum's recipe for lentil soup: onions, carrots, red lentils and cumin. Simmer for 30 minutes.", ["recipes"], 29),
("Bought a new jacket for $129 at Uniqlo", [], 6),
("The wifi password at the flat is in the kitchen drawer", [], 50),
("Felt really good after the run today, 6 km without stopping", ["running"], 5),
("Remember to pay rent on the 1st", [], 7),
("Garden: plant the tulip bulbs before the first frost. Bought 30 bulbs for $18.", ["garden"], 8),
("Coffee with Anna on Saturday at Brunetti", [], 1),
("# Shopping list\n- [ ] milk\n- [ ] eggs\n- [x] bread\n- [ ] oat milk\n- [ ] tomatoes", ["shopping"], 2),
("# Todo this week\n- [x] Email the landlord\n- [ ] Renew passport\n- [ ] Book the dentist\n- [ ] Finish the cloud assignment", [], 3),
("# Gift ideas\n- Sara: a jazz record\n- Mum: a scarf\n- Tom: coffee beans", ["people"], 13),
("# Weekend plans", [], 4),
("# Ideas", [], 19),
("# Weekly review\nThis week I ran twice, prepared the Atlas beta and booked nothing. Slept badly on Tuesday.", ["review"], 0),
("Diary: Saturday 25 October. Went to the markets with Sara and bought tomatoes and basil. Felt happy.", ["diary"], 5),
("# Passport\nThe passport expires on 3 March 2027. Renewal takes 6 weeks and costs $193.", ["admin"], 32),
("# Sleep\nSlept 6 hours on average this week. Aim for 8.", ["health"], 6),
("# Spanish\nLearning Spanish with Duolingo. The streak is 42 days. Words: biblioteca, ventana, cocina.", ["languages"], 17),
("# Car\nRego is due on 18 December. Service at 90,000 km. Mechanic is Joe's Garage.", ["admin"], 36),
("# Meditation\nTried 10 minutes a day for 5 days. Feels calmer.", ["health"], 24),
("# Apartment\nThe lease ends on 28 February 2027. Landlord is Mr Chen. Rent is due on the 1st.", ["admin"], 60),
]


def seed(session):
    """Create the notes oldest-id-first, dated as the audit's seed dated them."""
    from tessellate.entry import manager

    for content, tags, days in NOTES:
        entry = manager.create_entry(session, content, tags=tags)
        entry.created_at = entry.updated_at = (NOW - timedelta(days=days)).replace(hour=10, minute=0)
    session.commit()


def asker(client, monkeypatch, *, chat=False):
    """`go(question, history=None, open_id=None)` -> (answer text, events)."""
    from tessellate.api import routes_chat
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def go(question, history=None, open_id=None):
        body = {"question": question}
        body.update({"use_tools": True} if chat else {"answer_from": "notes", "notes_only": True, "use_tools": False})
        if history:
            body["history"] = history
        if open_id:
            body["open_note_id"] = open_id
        text, events = "", []
        with client.stream("POST", "/chat/stream", json=body) as response:
            for line in response.iter_lines():
                if line.strip():
                    event = json.loads(line)
                    events.append(event)
                    if event.get("type") == "answer":
                        text += event["delta"]
        return text, events

    return go
