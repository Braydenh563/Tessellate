"""The notes behind INBOX 1665 (the owner's Ask, "What have I saved about
courses & study?"), as a fixture: (content, category, tags, written, links)."""

from __future__ import annotations

COURSES = "Courses & Study"
#: (content, category, tags, written, {index of a linked note: reason})
NOTES = [
    ("my uni days this week are tuesday and thursday", COURSES, ["university"], "2026-07-17T09:00",
     {2: "They mention the times you have uni classes"}),
    ("# Cloud computing\n\nCloud computing is the delivery of computing services – including servers, storage, databases, "
     "networking, software, and intelligence – over the Internet (the cloud). It allows users to access and use "
     "resources on demand without needing to manage physical hardware.", COURSES, ["cloud computing", "university"],
     "2026-07-20T09:00", {0: "Both are about uni"}),
    ("I had three lectures for my cloud computing class last week", COURSES, [], "2026-07-26T09:00", {}),
    ("I'm taking one Information Technology (IT) subject and three Design subjects - Tangible Interaction Design, "
     "Cloud Computing, and others, this semester at university.", COURSES, ["university"], "2026-07-27T09:00", {}),
    ("had design class today for prototyping", COURSES, [], "2026-08-04T09:00", {0: "Both are about uni"}),
    ("I missed the bus to uni today but I ran into a uni friend and met her friend as well so it was chill", COURSES,
     [], "2026-10-08T09:00", {}),
    ("# Uni is done!! :D\n\nJust finished my final assignment on friday at 3:30am but it's done haha!", COURSES, [],
     "2026-11-03T09:00", {}),
    ("I got sent home after like 1 hour and 33 minutes today at work lol. need to lock-in for my assignments lmao",
     COURSES, [], "2026-08-09T09:00", {}),
    ("I didnt lock in 😔", COURSES, [], "2026-08-10T09:00", {}),
    ("# CAB432 LLM Agents Lecture Slides\n\nLecture slides for CAB432 on LLM agents, tool use and planning.", COURSES,
     [], "2026-09-04T09:00", {}),
    ("# Meeting\n\nAgenda: attendees, notes, actions for the unit coordinator meeting.", COURSES, [], "2026-10-15T09:00", {}),
    ("# The Complete Social Skills Guide\n\nHow to start conversations, listen well and make friends at parties.",
     "Personal", [], "2026-09-10T09:00", {}),
    ("Why did the student eat his homework? The teacher said it was a piece of cake.", "Personal", [], "2026-09-12T09:00", {}),
    ("something lol", "Personal", [], "2026-09-13T09:00", {}),
    ("# TDD\n\nWrite the failing test first, then the code, then refactor.", "Work", [], "2026-09-20T09:00", {}),
    ("# Party Thoughts\n\nThe party on Saturday needs snacks and a playlist.", "Personal", [], "2026-10-02T09:00", {}),
]
