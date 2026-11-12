"""The blind tester's ten notes (bt-compcomp-1109), clock fixed at Monday 9 November 2026, 12:00."""

from __future__ import annotations

from datetime import datetime

from tessellate.entry import manager
from tests._seed_r9_1109 import NOW, ask, fix_clock

#: Re-exported for the bt tests (`sd.ask`, `sd.fix_clock`); `__all__` marks them used (CodeQL 2127).
__all__ = ["NOTES", "NOW", "ask", "fix_clock", "seed"]

# (content, created_at); the tester captured all ten today, in this order
NOTES = [
    ("Team sync with Priya\n\nTuesday 10 November at 2pm. Agenda: Orchard project budget, hiring a designer.", "2026-11-09T09:00:00"),
    ("Lemon risotto\n\nRecipe: lemon risotto. 300g arborio rice, 1 litre vegetable stock, 1 lemon, parmesan, butter.\n"
     "Toast the rice, add the stock a ladle at a time, then stir in the lemon and butter.", "2026-11-09T09:01:00"),
    ("Weekend todo\n\n- Call the dentist\n- Buy printer paper\n- Renew car insurance\n- Water the plants\n- Clean the bike", "2026-11-09T09:02:00"),
    ("Priya Raman\n\nPriya works in design. Likes oat flat whites. Marcus introduced us at the garden meeting.", "2026-11-09T09:03:00"),
    ("Orchard project\n\nOrchard is the website redesign for the community garden. Deadline: Monday 16 November 2026 for the launch. "
     "Budget is 4,500 pounds.", "2026-11-09T09:04:00"),
    ("Marcus Lee, chair of the garden committee. Priya introduced us. Phone 07700 900123.", "2026-11-09T09:05:00"),
    ("Harbour project\n\nDeadline is 30 January 2027. Needs a booking screen and a timetable view. Budget is 12,000 pounds.\n"
     "Marcus wants a demo first.", "2026-11-09T09:06:00"),
    ("Gym plan\n\nGym on Monday, Wednesday and Friday at 7am.", "2026-11-09T09:07:00"),
    ("Book idea\n\nA novel about a lighthouse keeper. Marcus liked the idea.", "2026-11-09T09:08:00"),
    ("Dentist\n\nThu 12 Nov 9:30. Appointment for a filling.", "2026-11-09T09:09:00"),
]


def seed(session):
    for content, when in NOTES:
        e = manager.create_entry(session, content, category_name="Uncategorised")
        e.created_at = e.updated_at = datetime.fromisoformat(when)
    session.commit()
