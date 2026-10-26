"""Adds the student and personal templates (WHITEBOARD_PLAN 1355) to
frontend/board-library/templates.json and maps.json, and the counts in
index.json. Idempotent: an existing key is replaced. Run from the repo root."""

import json
from pathlib import Path

LIB = Path("frontend/board-library")
NOTE = {
    "yellow": ("#fff4a3", "#e8d56a"),
    "blue": ("#cfe8ff", "#94bfe8"),
    "green": ("#d6f5c9", "#9dd18a"),
    "pink": ("#ffd6e0", "#e8a0b4"),
    "orange": ("#ffe0b8", "#e8b070"),
    "violet": ("#e6dcff", "#b9a3ee"),
}


class Board:
    def __init__(self):
        self.items, self.links, self.n = [], [], 0

    def key(self, p):
        self.n += 1
        return f"{p}{self.n}"

    def frame(self, x, y, w, h, title, hint, tint="neutral"):
        self.items.append(
            {
                "key": self.key("f"),
                "kind": "object",
                "type": "frame",
                "data": {"content": title, "hint": hint, "tint": tint},
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "z": -1,
            }
        )

    def note(self, x, y, text, colour="yellow", w=200, h=90):
        bg, border = NOTE[colour]
        k = self.key("s")
        self.items.append(
            {
                "key": k,
                "kind": "object",
                "type": "text",
                "data": {
                    "content": text,
                    "bg": bg,
                    "border_color": border,
                    "color": "#2a2a1f",
                    "font_size": 16,
                },
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "z": 1,
            }
        )
        return k

    def label(self, x, y, text, w=220, h=44, size=20):
        self.items.append(
            {
                "key": self.key("t"),
                "kind": "object",
                "type": "text",
                "data": {"content": text, "color": "ink", "font_size": size},
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "z": 1,
            }
        )

    def line(self, d, arrow=True, width=3):
        data = {"d": d, "shape": "arrow" if arrow else "line", "color": "ink", "width": width}
        if arrow:
            data["endCap"] = "arrow"
        self.items.append({"key": self.key("k"), "kind": "sketch", "data": data, "z": 5})

    def oval(self, cx, cy, rx, ry, colour, label=None):
        d = f"M {cx - rx} {cy} A {rx} {ry} 0 1 0 {cx + rx} {cy} A {rx} {ry} 0 1 0 {cx - rx} {cy} Z"
        data = {
            "d": d,
            "shape": "custom",
            "color": colour,
            "width": 3,
            "fill": colour,
            "fillOpacity": 0.18,
        }
        self.items.append({"key": self.key("o"), "kind": "sketch", "data": data, "z": 5})

    def join(self, a, b):
        self.links.append(
            {
                "from": a,
                "to": b,
                "data": {"type": "link-straight", "color": "ink", "width": 2, "endCap": "arrow"},
            }
        )

    def entry(self, key, name, hint, purpose, tags, w, h):
        assert len(hint) <= 60, hint
        return {
            "key": key,
            "kind": "element",
            "name": name,
            "hint": hint,
            "purpose": purpose,
            "tags": ["template", *tags],
            "template": "board",
            "payload": {"box": {"w": w, "h": h}, "items": self.items, "links": self.links},
        }


def columns(b, titles, tints, x0=0, y=0, w=300, gap=40, h=520, hints=None):
    for i, t in enumerate(titles):
        b.frame(
            x0 + i * (w + gap), y, w, h, t, (hints or [""] * len(titles))[i], tints[i % len(tints)]
        )


def lecture():
    b = Board()
    b.frame(0, 0, 960, 120, "Lecture", "Course, date and the topic in one line", "blue")
    b.frame(0, 160, 300, 460, "Key terms", "Words to define", "amber")
    b.frame(340, 160, 620, 460, "Main points", "What was taught, in your words", "neutral")
    b.frame(0, 660, 460, 220, "Examples", "A case that makes it stick", "green")
    b.frame(500, 660, 460, 220, "Questions", "What to ask or look up", "violet")
    b.note(24, 270, "Term: meaning", "yellow", 250, 80)
    return b.entry(
        "lecture",
        "Lecture notes",
        "Key terms, main points, examples and questions",
        "learn",
        ["lecture", "notes", "class", "study", "university"],
        960,
        880,
    )


def revision():
    b = Board()
    columns(
        b,
        ["This week", "Next week", "Before the exam"],
        ["blue", "amber", "green"],
        h=560,
        hints=["Topics to cover now", "Topics to cover next", "Past papers and a last read"],
    )
    b.note(24, 96, "Subject: topic", "blue")
    b.note(24, 206, "Subject: topic", "blue")
    b.note(364, 96, "Subject: topic", "orange")
    b.note(704, 96, "Past paper 1", "green")
    return b.entry(
        "revision",
        "Revision plan",
        "Topics for this week, next week and before the exam",
        "learn",
        ["revision", "exam", "study", "plan", "timetable"],
        1040,
        560,
    )


def essay():
    b = Board()
    b.note(0, 0, "Thesis: the one claim this essay proves", "yellow", 960, 90)
    for i, (t, c) in enumerate(
        [
            ("Introduction", "blue"),
            ("Point 1", "green"),
            ("Point 2", "green"),
            ("Point 3", "green"),
            ("Conclusion", "violet"),
        ]
    ):
        b.frame(
            i * 216,
            150,
            176,
            420,
            t,
            {"Introduction": "Hook and thesis", "Conclusion": "Answer and so what"}.get(
                t, "Claim, evidence, link"
            ),
            c,
        )
    b.line("M 0 120 L 960 120", arrow=False, width=2)
    return b.entry(
        "essay",
        "Essay outline",
        "A thesis, three points with evidence, a conclusion",
        "learn",
        ["essay", "outline", "writing", "argument", "thesis"],
        960,
        570,
    )


def timeline():
    b = Board()
    b.line("M 0 200 L 1180 200")
    xs = [0, 220, 440, 660, 880]
    for i, x in enumerate(xs):
        b.label(x, 120, f"Date {i + 1}", 180, 40, 18)
        b.note(
            x,
            230 if i % 2 == 0 else 330,
            "What happened",
            ["blue", "green", "orange", "pink", "violet"][i],
            180,
            80,
        )
    return b.entry(
        "timeline",
        "Timeline",
        "Five dates along a line, an event under each",
        "plan",
        ["timeline", "history", "dates", "events", "chronology"],
        1180,
        420,
    )


def venn():
    b = Board()
    b.oval(240, 310, 220, 220, "#3355ff")
    b.oval(520, 310, 220, 220, "#e8590c")
    b.label(80, 20, "Idea A", 200, 40)
    b.label(480, 20, "Idea B", 200, 40)
    b.note(80, 280, "Only A", "blue", 150, 60)
    b.note(360, 280, "Both", "yellow", 120, 60)
    b.note(560, 280, "Only B", "orange", 150, 60)
    return b.entry(
        "venn",
        "Venn diagram",
        "Two overlapping circles: only A, both, only B",
        "decide",
        ["venn", "compare", "contrast", "overlap", "similar"],
        760,
        550,
    )


def brainstorm():
    b = Board()
    c = b.note(340, 200, "The question", "yellow", 220, 100)
    spots = [(0, 0), (340, 0), (680, 0), (0, 400), (340, 400), (680, 400)]
    for i, (x, y) in enumerate(spots):
        k = b.note(x, y, "Idea", ["blue", "green", "orange", "pink", "violet", "blue"][i], 220, 100)
        b.join(c, k)
    return b.entry(
        "brainstorm",
        "Brainstorm",
        "One question in the middle, six ideas around it",
        "learn",
        ["brainstorm", "ideas", "think", "creative"],
        900,
        500,
    )


def concept():
    b = Board()
    c = b.note(300, 180, "Main concept", "yellow", 240, 100)
    for i, (x, y, t) in enumerate(
        [(0, 0, "Part"), (600, 0, "Cause"), (0, 360, "Example"), (600, 360, "Effect")]
    ):
        k = b.note(x, y, t, ["blue", "green", "orange", "pink"][i], 220, 90)
        b.join(c, k)
    return b.entry(
        "concept",
        "Concept map",
        "A main idea joined to its parts, causes and effects",
        "learn",
        ["concept", "map", "study", "relationships", "connect"],
        820,
        450,
    )


def timetable():
    b = Board()
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    columns(
        b,
        days,
        ["blue", "green", "amber", "violet", "red"],
        w=190,
        gap=40,
        h=520,
        hints=["Classes and study"] * 5,
    )
    b.frame(0, 560, 1110, 140, "Weekend", "Catch up, rest, one long session", "neutral")
    return b.entry(
        "timetable",
        "Study timetable",
        "Monday to Friday columns and a weekend row",
        "plan",
        ["timetable", "schedule", "week", "study", "school"],
        1110,
        700,
    )


def habits():
    b = Board()
    b.frame(0, 0, 1000, 110, "Week of", "Tick a note each day you keep the habit", "blue")
    for r, name in enumerate(["Habit 1", "Habit 2", "Habit 3"]):
        b.note(0, 150 + r * 120, name, "yellow", 200, 80)
        for d in range(7):
            b.note(240 + d * 108, 150 + r * 120, "", "green", 90, 80)
    for d, n in enumerate(["M", "T", "W", "T", "F", "S", "S"]):
        b.label(240 + d * 108, 110, n, 90, 36, 18)
    return b.entry(
        "habits",
        "Habit tracker",
        "Three habits across seven days",
        "plan",
        ["habit", "tracker", "routine", "goals", "personal"],
        1000,
        500,
    )


def smart():
    b = Board()
    for i, (t, h, c) in enumerate(
        [
            ("Specific", "What exactly will you do", "blue"),
            ("Measurable", "How will you know", "green"),
            ("Achievable", "Is it within reach", "amber"),
            ("Relevant", "Why it matters now", "violet"),
            ("Time-bound", "The date it is done by", "red"),
        ]
    ):
        b.frame(i * 230, 0, 190, 420, t, h, c)
    b.note(-0, 460, "My goal in one line", "yellow", 1110, 90)
    return b.entry(
        "smart",
        "Goal setting",
        "A goal checked against the five SMART questions",
        "plan",
        ["goal", "smart", "personal", "planning", "target"],
        1110,
        550,
    )


def project():
    b = Board()
    for i, (t, c) in enumerate(
        [("Plan", "blue"), ("Build", "amber"), ("Test", "violet"), ("Finish", "green")]
    ):
        b.frame(i * 290, 0, 250, 520, t, "Tasks in this phase", c)
        b.note(i * 290 + 24, 96, "Task", ["blue", "orange", "violet", "green"][i], 210, 80)
    b.note(0, 570, "Deadline and who is doing what", "yellow", 1160, 80)
    return b.entry(
        "project-plan",
        "Project plan",
        "Four phases, a task in each, a deadline line",
        "plan",
        ["project", "plan", "phases", "assignment", "group"],
        1160,
        650,
    )


def reading():
    b = Board()
    columns(
        b,
        ["To read", "Reading now", "Finished"],
        ["neutral", "blue", "green"],
        h=500,
        hints=["Books and papers lined up", "What you have open", "With a line on what you took"],
    )
    b.note(24, 96, "Title, author", "yellow")
    b.note(364, 96, "Title, author", "blue")
    b.note(704, 96, "Title: one takeaway", "green")
    return b.entry(
        "reading",
        "Reading list",
        "To read, reading now and finished",
        "learn",
        ["reading", "books", "papers", "list", "library"],
        1040,
        500,
    )


def exam():
    b = Board()
    columns(
        b,
        ["Confident", "Shaky", "Not yet"],
        ["green", "amber", "red"],
        h=520,
        hints=["I could teach this", "Needs another pass", "Start here"],
    )
    for i, (x, c) in enumerate([(24, "green"), (364, "orange"), (704, "pink")]):
        b.note(x, 96, "Topic", c)
    return b.entry(
        "exam",
        "Exam readiness",
        "Sort each topic into confident, shaky or not yet",
        "learn",
        ["exam", "revision", "topics", "checklist", "confidence"],
        1040,
        520,
    )


def day():
    b = Board()
    b.frame(0, 0, 300, 520, "Morning", "Before lunch", "amber")
    b.frame(340, 0, 300, 520, "Afternoon", "Classes and study", "blue")
    b.frame(680, 0, 300, 520, "Evening", "Dinner and rest", "violet")
    b.frame(1020, 0, 280, 520, "Top three", "Do these first", "red")
    b.note(1044, 96, "1", "pink", 230, 70)
    b.note(1044, 186, "2", "pink", 230, 70)
    b.note(1044, 276, "3", "pink", 230, 70)
    return b.entry(
        "day",
        "Daily plan",
        "Morning, afternoon, evening and a top three",
        "plan",
        ["day", "daily", "planner", "today", "schedule", "personal"],
        1300,
        520,
    )


BOARDS = [
    lecture,
    revision,
    essay,
    timeline,
    venn,
    brainstorm,
    concept,
    timetable,
    habits,
    smart,
    project,
    reading,
    exam,
    day,
]


def branch(key, name, hint, purpose, shape, layout, tags, nodes):
    def tree(n):
        return {"text": n[0], "children": [tree(c) for c in n[1:]]}

    return {
        "key": key,
        "kind": "branch",
        "name": name,
        "hint": hint,
        "purpose": purpose,
        "shape": shape,
        "layout": layout,
        "tags": ["template", *tags],
        "template": "map",
        "payload": {"nodes": [tree(n) for n in nodes]},
    }


MAPS = [
    branch(
        "lecture-map",
        "Lecture notes",
        "The topic, its key ideas, examples and questions",
        "learn",
        "tree",
        "tree-right",
        ["lecture", "notes", "class", "study"],
        [
            ("Key ideas", ("Idea 1", "Detail"), ("Idea 2", "Detail"), ("Idea 3", "Detail")),
            ("Examples", ("Case 1",), ("Case 2",)),
            ("Questions", ("To ask",), ("To look up",)),
            ("Summary",),
        ],
    ),
    branch(
        "revision-map",
        "Revision plan",
        "Subjects, topics to cover and how you will revise",
        "learn",
        "radial",
        "radial",
        ["revision", "exam", "study", "subjects"],
        [
            ("Subject 1", ("Topic",), ("Topic",)),
            ("Subject 2", ("Topic",), ("Topic",)),
            ("Subject 3", ("Topic",), ("Topic",)),
            ("Methods", ("Flashcards",), ("Past papers",), ("Teach someone",)),
        ],
    ),
    branch(
        "exam-map",
        "Exam preparation",
        "What is tested, what you know and what to practise",
        "learn",
        "tiers",
        "tree-down",
        ["exam", "preparation", "study", "test"],
        [
            ("Format", ("Date and room",), ("Marks",)),
            ("Know well", ("Topic",)),
            ("Practise", ("Topic",), ("Past paper",)),
            ("Day before", ("Sleep",), ("Kit ready",)),
        ],
    ),
    branch(
        "research-map",
        "Research project",
        "Question, sources, method, findings and write-up",
        "learn",
        "phases",
        "tree-down",
        ["research", "project", "dissertation", "sources"],
        [
            ("Question", ("Why it matters",)),
            ("Sources", ("Books",), ("Papers",), ("Interviews",)),
            ("Method", ("Steps",)),
            ("Findings", ("Result",)),
            ("Write-up", ("Draft",), ("Edit",), ("Submit",)),
        ],
    ),
    branch(
        "presentation-map",
        "Presentation",
        "Message, sections, visuals and rehearsal",
        "plan",
        "tiers",
        "tree-down",
        ["presentation", "talk", "slides", "speech"],
        [
            ("Message", ("One sentence",)),
            ("Opening", ("Hook",)),
            ("Middle", ("Point 1",), ("Point 2",), ("Point 3",)),
            ("Close", ("Ask",), ("Thanks",)),
            ("Rehearse", ("Timing",), ("Questions",)),
        ],
    ),
    branch(
        "group-map",
        "Group project",
        "Who does what, by when, and how you will meet",
        "plan",
        "tree",
        "tree-right",
        ["group", "project", "team", "assignment"],
        [
            ("Tasks", ("Research",), ("Writing",), ("Slides",)),
            ("People", ("Name: role",), ("Name: role",)),
            ("Dates", ("Draft",), ("Final",)),
            ("Meetings", ("When",), ("Where",)),
        ],
    ),
    branch(
        "goals-map",
        "Personal goals",
        "Work, health, money, people and learning",
        "plan",
        "radial",
        "radial",
        ["goals", "personal", "life", "year"],
        [
            ("Work", ("Next step",)),
            ("Health", ("Next step",)),
            ("Money", ("Next step",)),
            ("People", ("Next step",)),
            ("Learning", ("Next step",)),
        ],
    ),
    branch(
        "routine-map",
        "Daily routine",
        "Morning, study, meals, exercise and wind-down",
        "plan",
        "two-sided",
        "tree-both",
        ["routine", "day", "habits", "schedule"],
        [
            ("Morning", ("Wake",), ("Breakfast",)),
            ("Study", ("Block 1",), ("Block 2",)),
            ("Meals", ("Lunch",), ("Dinner",)),
            ("Exercise", ("Walk",)),
            ("Evening", ("Free time",)),
            ("Wind down", ("Screens off",), ("Bed",)),
        ],
    ),
    branch(
        "career-map",
        "Career plan",
        "Where you are, where to, skills and next steps",
        "plan",
        "phases",
        "tree-down",
        ["career", "job", "future", "skills"],
        [
            ("Now", ("Skills",), ("Experience",)),
            ("Aim", ("Role",), ("Employer",)),
            ("Gaps", ("Skill to learn",)),
            ("Steps", ("This month",), ("This year",)),
        ],
    ),
    branch(
        "reading-map",
        "Reading list",
        "Topics, the books under each and what to read first",
        "learn",
        "tree",
        "tree-right",
        ["reading", "books", "list", "library"],
        [
            ("Topic 1", ("Book",), ("Book",)),
            ("Topic 2", ("Book",), ("Book",)),
            ("Read first", ("Title",)),
            ("Notes", ("Quotes",), ("Ideas",)),
        ],
    ),
    branch(
        "habits-map",
        "Healthy habits",
        "Sleep, food, movement, mind and people",
        "plan",
        "radial",
        "radial",
        ["health", "habits", "wellbeing", "sleep"],
        [
            ("Sleep", ("Bedtime",)),
            ("Food", ("Water",), ("Meals",)),
            ("Movement", ("Walk",), ("Stretch",)),
            ("Mind", ("Breaks",), ("Journal",)),
            ("People", ("Call a friend",)),
        ],
    ),
    branch(
        "moving-map",
        "Moving house",
        "Before, packing, the day and after",
        "plan",
        "phases",
        "tree-down",
        ["moving", "house", "home", "checklist"],
        [
            ("Before", ("Notice",), ("Quotes",)),
            ("Packing", ("Boxes",), ("Labels",)),
            ("Moving day", ("Keys",), ("Van",)),
            ("After", ("Post",), ("Utilities",)),
        ],
    ),
]


def merge(path, new):
    data = json.loads(path.read_text())
    keep = [i for i in data["items"] if i["key"] not in {n["key"] for n in new}]
    data["items"] = keep + new
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    return len(data["items"])


if __name__ == "__main__":
    boards = [f() for f in BOARDS]
    nb = merge(LIB / "templates.json", boards)
    nm = merge(LIB / "maps.json", MAPS)
    idx = json.loads((LIB / "index.json").read_text())
    for row in idx["sets"]:
        row["count"] = {"templates": nb, "maps": nm}.get(row["key"], row["count"])
    (LIB / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1) + "\n")
    print(nb, nm)
