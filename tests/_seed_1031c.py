"""The audit-1031 composer notebook (54 notes plus an optional 150 filler
notes, 207 in all), the owner's INBOX 1420 notes and the auditor's titled,
title-less, dated, list and Japanese-script notes, with the clock fixed at
Saturday 31 October 2026, 11:30 (docs/roadmap/agent-remaining/audit-1031-composer.md).
Shared by the composer tests that pin a class of that audit."""

from __future__ import annotations

import json
import random
from datetime import datetime

NOW = datetime(2026, 10, 31, 11, 30)

GUIDE = (
    "**The Complete Social Skills Guide**\n\n"
    "It's in four phases: **the Opener**, **the Connection**, **the Ask** and **the Follow-Up**.\n\n"
    "## Phase 2: the Connection\n\n"
    "**After making an initial connection**\n"
    "- Ask open questions and listen for the details\n\n"
    "For example, if she mentions a trip, ask what the best part was.\n"
)
ICE = "Ice Breakers:\n- What is the best thing that happened to you this week?\n- **Coffee or tea?**\n- What are you reading at the moment?"
PICKUP = (
    "Here are some refined, non-corny pickup and conversation starters that work in most settings:\n"
    "1. I like your jacket, where is it from?\n"
    "2. You look like you know the good coffee places around here."
)
FOLLOW = "Follow- Up Questions:\n- How did that go?\n- What happened next?\n- What made you pick that?"

# (key, content, category, tags, created_at)
NOTES = [
    ("guide", GUIDE, "Social connections", ["conversation", "social skills"], "2026-07-22T10:00:00"),
    ("ice", ICE, "Social connections", ["conversation"], "2026-07-23T10:00:00"),
    ("pickup", PICKUP, "Social connections", ["conversation", "dating"], "2026-07-24T10:00:00"),
    ("follow", FOLLOW, "Social connections", ["conversation"], "2026-07-25T10:00:00"),
    ("friend", "I had work today and a friend was sad so I stayed with her for a bit :(", "Social connections", ["friends"], "2026-10-04T21:00:00"),
    ("bus", "I just missed the bus to uni today, so I walked and was 20 minutes late to the lecture", "Diary", ["uni"], "2026-10-14T09:00:00"),
    ("meeting", "# Meeting\n\nAttendees:\nAgenda:\nNotes:\nActions:", "Work", ["meeting"], "2026-09-01T09:00:00"),
    ("joke", "Why did the scarecrow win an award? Because he was outstanding in his field", "Fun", ["jokes"], "2026-09-20T10:00:00"),
    ("unidays", "My uni days this week are Tuesday and Thursday, with the cloud lab on Thursday afternoon", "Uni", ["university"], "2026-07-14T09:00:00"),
    ("lectures", "I had three lectures for cloud computing last week and the lab ran over", "Uni", ["university", "cloud computing"], "2026-07-18T17:00:00"),
    ("cloud", "Cloud computing is the delivery of computing services such as servers, storage and databases over the internet, on demand and paid as you go.", "Uni", ["university", "cloud computing"], "2026-07-20T10:00:00"),
    ("leaveout", "What my notes currently leave out, however, is how the three service models compare.\n- IaaS rents the servers\n- PaaS runs your code\n- SaaS is the finished app", "Uni", ["university", "cloud computing"], "2026-07-24T10:00:00"),
    ("itsubject", "I'm taking one Information Technology (IT) subject this semester alongside the double degree", "Uni", ["university"], "2026-07-30T10:00:00"),
    ("design", "had design class today for prototyping", "Uni", ["university"], "2026-07-16T15:00:00"),
    ("unifriend", "Met a uni friend, Jake, at the library and we studied for the cloud exam together", "Uni", ["university", "friends"], "2026-10-20T18:00:00"),
    ("groupmeet", "Group project meeting moved to Friday", "Uni", ["university"], "2026-10-21T12:00:00"),
    # titled, with a defining note per topic and a near-duplicate
    ("starter", "# Sourdough starter\n\nA sourdough starter is flour and water left to ferment with wild yeast. Feed it every 12 hours at room temperature. Mine is called Doug.", "Recipes", ["baking", "sourdough"], "2026-08-02T09:00:00"),
    ("loaf", "# Sourdough loaf attempt two\n\nBake at 230C for 20 minutes lid on, then 25 minutes lid off. The crust was much better and the crumb opened up.", "Recipes", ["baking", "sourdough"], "2026-08-21T09:00:00"),
    ("banana", "# Banana bread\n\n3 ripe bananas, 100 g butter, 150 g sugar, 1 egg, 200 g flour. Bake at 175C for 55 minutes.", "Recipes", ["baking"], "2026-10-24T11:00:00"),
    ("lentil", "# Mum's recipe for lentil soup\n\n- red lentils\n- carrots\n- cumin\n- an onion\n- stock", "Recipes", ["cooking"], "2026-09-12T10:00:00"),
    ("lisbon", "# Lisbon trip\n\nFlying out on 14 November 2026 and back on 21 November. Flights cost $420 return. Staying at Hotel Alfama, 85 euros a night. Need to book the tram to Sintra.", "Travel", ["travel", "lisbon"], "2026-10-05T10:00:00"),
    ("packing", "# Lisbon packing list\n\n- [x] Passport\n- [ ] charger\n- [ ] sunscreen\n- [ ] walking shoes\n- [ ] power adapter", "Travel", ["travel", "lisbon"], "2026-10-20T10:00:00"),
    ("tokyo", "# Tokyo trip\n\nThinking about March 2027. Want to see Kyoto and Nara. Flights are about $1,100.", "Travel", ["travel"], "2026-09-20T10:00:00"),
    ("budget", "# Budget\n\nRent is $1,200 a month. Groceries about $80 a week. Saved $500 in October. Need to cut eating out.", "Money", ["money"], "2026-10-23T10:00:00"),
    ("sara", "# Sara\n\nSara is my sister. Her birthday is 12 December. She likes jazz and the sourdough I make.", "People", ["family"], "2026-09-25T10:00:00"),
    ("tom", "# Tom\n\nMet at the conference in June. He works on the data team at Vireo. Likes good coffee.", "People", ["people"], "2026-10-13T10:00:00"),
    ("atlas", "# Project Atlas\n\nBeta on 10 November. We decided to cut the reporting page. Tom to draft the API spec by Friday.", "Work", ["atlas", "work"], "2026-10-15T10:00:00"),
    ("priya", "# Meeting with Priya\n\nOn 28 October we talked about the Atlas scope. Priya to send mockups. Book the review room.", "Work", ["atlas", "work", "meeting"], "2026-10-28T14:00:00"),
    ("runplan", "# Running plan\n\nTuesday 5 km easy. Thursday intervals. Saturday long run.", "Health", ["running"], "2026-10-01T08:00:00"),
    ("runlog", "# Running log\n\n3 October: 5 km in 28 minutes.\n17 October: 8 km in 46 minutes, knee a bit sore.", "Health", ["running"], "2026-10-17T19:00:00"),
    ("dentist", "# Dentist\n\nDentist appointment on 4 November 2026 at 9:30. Dr Patel said to floss more.", "Health", ["health"], "2026-10-18T10:00:00"),
    ("books", "# Books\n\nFinished Piranesi in September. Loved it, 9/10. A strange house of statues and tides. Dune Part Two was long. Next: The Overstory by Richard Powers.", "Reading", ["books"], "2026-10-09T10:00:00"),
    ("weekend", "# Weekend plans", "Personal", [], "2026-10-29T10:00:00"),
    ("todo", "# Todo\n\n- [x] Pay the electricity bill\n- [ ] Renew passport\n- [ ] Book the dentist follow-up\n- [ ] Finish the cloud assignment\n- [ ] Email the landlord about the boiler", "Personal", ["todo"], "2026-10-26T10:00:00"),
    ("gifts", "# Gift ideas\n\nSara: a jazz record. Mum: a scarf. Tom: coffee beans.", "Personal", ["gifts"], "2026-10-27T10:00:00"),
    ("passport", "# Passport\n\nThe passport expires 3 March 2027. Renewal takes 6 weeks and costs $193.", "Admin", ["admin"], "2026-10-12T10:00:00"),
    ("review", "# Weekly review\n\nRan twice, prepared the Atlas beta and booked nothing. Slept badly on Tuesday.", "Personal", ["review"], "2026-10-30T20:00:00"),
    ("gym", "# Gym log\n\nI went to the gym on Monday and did squats, 5 sets of 5 at 80 kg. I like the morning sessions best.", "Health", ["gym"], "2026-10-04T10:00:00"),
    ("gymplan", "# Gym plan\n\nI plan to go three times a week. Decided to go with the strength programme.", "Health", ["gym"], "2026-09-27T10:00:00"),
    ("spanish", "# Learning Spanish\n\nLearning Spanish with Duolingo, 42 days in a row. Words this week: perro, gato, ventana.", "Learning", ["spanish"], "2026-10-25T10:00:00"),
    # title-less one-liners and diary lines
    ("flights", "Booked flights to Lisbon", "Travel", ["lisbon"], "2026-10-06T10:00:00"),
    ("run6", "Felt really good after the run today, 6 km without stopping", "Health", ["running"], "2026-10-25T09:00:00"),
    ("bank", "Need to call the bank about the card", "Admin", [], "2026-10-29T09:00:00"),
    ("rent", "Remember to pay rent on the 1st", "Money", ["money"], "2026-10-23T12:00:00"),
    ("anna", "Coffee with Anna on Saturday at Brunetti", "Social connections", ["friends"], "2026-10-28T09:00:00"),
    ("podcast", "Idea: a podcast about local history", "Ideas", ["ideas"], "2026-10-27T15:00:00"),
    ("wifi", "The wifi password at the flat is sunflower42", "Admin", [], "2026-10-11T10:00:00"),
    ("diary24", "Diary: Saturday 24 October. Rained all day, baked banana bread and watched Arrival.", "Diary", ["diary"], "2026-10-24T21:00:00"),
    ("mum", "Called mum, she is coming for Christmas", "Diary", ["family"], "2026-10-26T19:00:00"),
    # notes with the word test (owner's ask) and a title-only test note
    ("testdraft", "# test draft", "Uncategorised", [], "2026-10-30T09:00:00"),
    ("testsweep", "Test note from sweep about gardening and tomatoes", "Garden", ["garden"], "2026-10-02T10:00:00"),
    ("unittest", "The unit test for the parser passes now, the date test still fails", "Work", ["code"], "2026-10-19T10:00:00"),
    # Japanese script
    ("jp1", "今日は雨が降っていたので、家で読書をした。村上春樹の新しい本を読み始めた。", "Diary", [], "2026-10-22T20:00:00"),
    ("jp2", "# 日本語の勉強\n\nひらがなを練習した。来週は漢字を始める。", "Learning", ["japanese"], "2026-10-15T20:00:00"),
]

# links by key: (source, target, reason)
LINKS = [
    ("guide", "pickup", "Both offer conversation starters"),
    ("packing", "lisbon", "The packing list is for the **Lisbon trip**"),
    ("loaf", "starter", "The loaf is baked from the starter"),
    ("priya", "atlas", "Priya's meeting was about Project Atlas"),
    ("runlog", "runplan", "The log follows the plan"),
]


def seed(session, *, filler: int = 0) -> dict[str, int]:
    """Create the notes in the audit's order, dated as it dated them; returns key -> id."""
    from tessellate.entry import manager

    ids: dict[str, int] = {}
    entries = {}
    for key, content, cat, tags, when in NOTES:
        entry = manager.create_entry(session, content, category_name=cat, tags=tags)
        entry.created_at = entry.updated_at = datetime.fromisoformat(when)
        ids[key], entries[key] = entry.id, entry
    session.commit()
    for source, target, reason in LINKS:
        manager.create_link(session, entries[source], entries[target], reason)
    words = "garden dentist budget recipe travel project meeting reading health idea invoice plan holiday workout summary draft lecture essay bike coffee".split()
    cats = ["Work", "Health", "Ideas", "Reading", "Travel", "Recipes", "Garden"]
    rnd = random.Random(7)
    for i in range(filler):
        text = " ".join(rnd.choice(words) for _ in range(50))
        entry = manager.create_entry(session, f"Topic {i}\n\n{text}.", category_name=cats[i % 7])
        entry.created_at = entry.updated_at = datetime(2026, 10, 1 + i % 28, 9, 0)
    session.commit()
    return ids


def asker(client, monkeypatch, *, chat=False):
    """`go(question, history=None, open_id=None)` -> (answer text, events); the clock is `NOW`."""
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
