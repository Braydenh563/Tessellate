"""The owner's notebook from INBOX 1420, as notes the composer reads: notes
with only a title, notes with no title, a markdown guide with bold phases."""

from __future__ import annotations

from datetime import date

TODAY = date(2026, 10, 27)

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
FRIEND = "I had work today and a friend was sad so I stayed with her for a bit :("
BUS = "I just missed the bus to uni today, so I walked and was 20 minutes late to the lecture"
MEETING = "# Meeting\n\nAttendees:\nAgenda:\nNotes:\nActions:"
JOKE = "Why did the scarecrow win an award? Because he was outstanding in his field"

#: (content, category, tags, written, links by index)
NOTES = [
    (GUIDE, "Social connections", ["conversation", "social skills"], "2026-07-22T10:00:00", [2]),
    (ICE, "Social connections", ["conversation"], "2026-07-23T10:00:00", []),
    (PICKUP, "Social connections", ["conversation", "dating"], "2026-07-24T10:00:00", [0]),
    (FOLLOW, "Social connections", ["conversation"], "2026-07-25T10:00:00", []),
    (FRIEND, "Social connections", ["friends"], "2026-10-04T21:00:00", []),
    (BUS, "Diary", ["uni"], "2026-10-14T09:00:00", []),
    (MEETING, "Work", ["meeting"], "2026-09-01T09:00:00", []),
    (JOKE, "Fun", ["jokes"], "2026-09-20T10:00:00", []),
]

SCORES = (0.72, 0.66, 0.64, 0.62, 0.44, 0.3, 0.2, 0.2)


def notes(count: int = 5) -> list[dict]:
    """The notes a search for social connections returns, closest first."""
    out = []
    for n, (content, category, tags, when, links) in enumerate(NOTES[:count]):
        out.append({"id": n + 1, "content": content, "category": category, "tags": tags, "created_at": when,
                    "match_info": {"type": "semantic", "score": SCORES[n]}, "linked_to": [i + 1 for i in links]})
    return out


#: The owner's uni notes (INBOX 1420, second pass): untitled openings that
#: are sentences, a pasted summary, and the note that defines cloud computing.
UNI = [
    ("My uni days this week are Tuesday and Thursday, with the cloud lab on Thursday afternoon", "Uni", ["university"], "2026-07-14T09:00:00"),
    ("I had three lectures for cloud computing last week and the lab ran over", "Uni", ["university", "cloud computing"], "2026-07-18T17:00:00"),
    ("Cloud computing is the delivery of computing services such as servers, storage and databases over the internet, on demand and paid as you go.",
     "Uni", ["university", "cloud computing"], "2026-07-20T10:00:00"),
    ("What my notes currently leave out, however, is how the three service models compare.\n- IaaS rents the servers\n- PaaS runs your code\n- SaaS is the finished app",
     "Uni", ["university", "cloud computing"], "2026-07-24T10:00:00"),
]
#: Scored as the owner's search scored them: the passing mention first.
UNI_SCORES = (0.6, 0.72, 0.95, 0.66)


def uni_notes() -> list[dict]:
    """The owner's uni search, the passing mention ranked above the definition."""
    order = (1, 2, 3, 0)
    return [{"id": 20 + n, "content": UNI[n][0], "category": UNI[n][1], "tags": UNI[n][2], "created_at": UNI[n][3],
             "match_info": {"type": "semantic", "score": UNI_SCORES[n]}, "linked_to": []} for n in order]
