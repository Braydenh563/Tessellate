# bt-compcomp-1109: blind test of the composer and the in-app companion (open findings)
Setup: 10 notes made via Notes > Capture: Team sync with Priya (Tue 10 Nov 2pm), Lemon risotto, Weekend todo (plain "- " bullets), Priya Raman, Orchard project (deadline Mon 16 Nov, 4,500 pounds), title-less "Marcus Lee", Harbour project (30 Jan 2027, 12,000 pounds), Gym plan, Book idea, Dentist (Thu 12 Nov 9:30). App date Monday 9 Nov. Asked in the Chat tab.

## Composer
1 (sev 1) Wrong date. "what is my Orchard deadline" -> "One date is ahead in your notes: 9 November. / 9 November: Deadline: Monday 16 November 2026 for the launch. (Orchard project)". Header date is today, not 16 Nov.
2 (sev 1) False absence. "compare Priya and Marcus" -> "Only Priya appears in your notes; nothing mentions Marcus." Marcus is in 3 notes; "who is Marcus" finds 2.
3 (sev 1) Wrong note. "is the dentist tomorrow?" -> "Call the dentist, from your Weekend todo note, written today. Also: Buy printer paper / Renew car insurance / Water the plants". Ignores the Dentist note (Thu 12 Nov). "is the dentist on Thursday?" works.
4 (sev 1) Corrupted quote. "what do I know about the Orchard projcet" -> "It also has Deadline: Monday 2026 for the launch." ("16 November" dropped) and 'You wrote "Orchard is the website redesign for the community garden. Budget is 4,500 pounds"' (non-adjacent sentences joined inside quote marks).
5 (sev 2) "what is the budget for each project" -> "From your Team sync with Priya note: Orchard project budget, hiring a designer." Misses 4,500 and 12,000; wrong note first.
6 (sev 2) "compare Orchard and Harbour" -> "Looking at the notes found, one mentions Orchard and one mentions Harbour." Gives Orchard's budget but not Harbour's 12,000; no real comparison; "[Orchard project]" repeats beside every numbered line.
7 (sev 2) Follow-ups. After "what do I know about Orchard", "and the other one?" re-answers Orchard instead of Harbour. A cold "the other one?" answers Gym plan and Team sync rather than asking what is meant.
8 (sev 2) "what's due this week" lists "Wednesday 11 November: Gym on Monday, Wednesday and Friday at 7am. (Gym plan)" as a dated item; a recurring schedule is not due. Today (Monday) is skipped.
9 (sev 2) "list my todos" -> "You are clear. No reminder is waiting and every checklist item is ticked." Weekend todo has 5 plain-bullet items. "what should I do today" -> "Nothing is dated in that time. No open tasks either."
10 (sev 2) Title-less note: "what did I write about Marcus" -> "On Marcus you've written three notes. ... The other is Marcus Lee." "who is Marcus" says two notes and omits it.
11 (sev 2) "what is my gym schedule" -> "Looking through your notes: Gym on Monday, Wednesday and Friday at 7am. ... [Gym plan] These notes do not mention "schedule"." Finds the answer then denies it.
12 (sev 2) "what do I know about quantum physics" -> 'Your notes don't mention "quantum physics". Could you put it another way?' footer "Sources: 10 notes".
13 (sev 2) "is the meeting tomorrow?" -> "Agenda: orchard project budget, hiring a designer." Proper noun lowercased.
14 (sev 2) "summarise my recipe" -> "Right away. Lemon risotto, boiled down: Recipe: lemon risotto. 300g arborio rice, ... butter. Say "more" for the rest." The summary is the ingredient sentence only, method omitted, title repeated.
15 (sev 3) "what about the dentist" -> 'On dentist you've written two notes. You wrote "Appointment ... filling". You noted down "Call the dentist".2' No citation on the first quote, full stop moved outside the quote, no article.
16 (sev 3) "does Priya like coffee" -> "No note puts it exactly. The nearest is: ... Likes oat flat whites. ... I couldn't find any reference to "coffee"." Adds an irrelevant meeting note.
17 (sev 3) Typo query "wat is the deadlien for harbuor" answers correctly (30 January 2027) but chips read "What else have I saved about the Deadline for harbor?" Chips also say "What else do my notes say about project?" / "about person?" / "about health?" (raw category as noun).
18 (sev 3) "Also:" lists mix punctuation: "Deadline is 30 January 2027 / Needs a booking screen and a timetable view / Budget is 12,000 pounds1". Hint "You were talking about dentist; ask me "what did I write about dentist"..." is robotic.
Good: "what's due next week", "what is due on 16 November", "whats due tommorow", "is the meeting tomorrow?" (right note), "when is my dentist appointment" ("in 3 days"), "which note mentions the lighthouse", hello/thanks.

## Companion (Atlas, 64x92 px)
Off by default; found only via Settings > Appearance > Expand all > Corner companion.
19 (sev 2) Mostly static. Sampled every 3 s for 40 s on each of dashboard, notes, chat, graph: position never changed; one yawn, one look, one nap that held 12+ s. No reaction to typing in #chat-input or to Send (class unchanged, no bubble). It reacts only when poked or thrown.
20 (sev 2) Covers chrome at rest (1440x900): spot (1044..1108, 791..883) overlaps status-bar Agent 32x15 and Guide 31x15; on Chat it overlaps the model select "Default (off)" 36x30 and chat-main 64x56. Clicks are not blocked (elementFromPoint). Start spot differs per load: (1364,39), (1044,791), (1060,791), (1164,39).
21 (sev 2) Drag to (1500,-50) and release -> rect y = -1418 after 1.5 s (invisible); it came back only after a tab switch (y 248, falling).
22 (sev 3) Right-click menu has 11 entries: Say hello, Enlarge, Stay here on every page, Tuck behind the bar, Call back and reset its place, Companion, Atlas look, Size, Quieter, Settings, Hide.
23 (sev 3) Not keyboard reachable: #nm-buddy tabIndex -1, no role or aria-label.
24 (sev 3) Ghost toast at about 30% opacity "Search by meaning needs a one-time download of about 130 MB from huggingface.co and pypi.org. ... [Download] [No thanks]" sat at x 945..1425, y 730..855 behind the Settings dialog in screenshots a minute apart.
25 (sev 3) Phone 390x800: after a resize the buddy (326,616) mid-poof covered Send; at rest on dashboard, chat, notes there were 0 overlaps.
Worked: poke -> wave, double-click -> enlarged viewer (Esc closes), drag and drop (lands where released), throw -> falling, splat, then walks and shrugs within 2.5 s.
Not tried: sound, desktop-tray companion, custom character, real model answers, reduced motion, touch throw.
Console/page errors: none seen in any run.
