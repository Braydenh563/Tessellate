# Composer new, changed, streak (audit 1029 C32, rank 31): remaining

Done (this branch): rank 31. New module `src/tessellate/ai/activity_new.py`, hooked in `routes_chat._activity`; tests `tests/test_composer_streak_1029.py`.

Left:
- "what did I miss" (audit C32 tail) still reads "missed" as a keyword and finds the bus note. It is ambiguous (missed reminders, or new since away); needs the owner's word before it is a shape. File: src/tessellate/ai/activity_new.py `read` (add a lead) or reminders.
- Bare "what changed" in Chat is the starter chip (`starter_acts._changed`, since this time yesterday, day_digest), not the seven-day shape Ask gives; the two windows differ by design today. Decide whether the chip should say its window or follow the shape. File: src/tessellate/ai/starter_acts.py:114.
- "what is new" has no "since you were last here" meaning: the window is the last seven days. A last-visit stamp would make it exact. Files: src/tessellate/ai/activity_new.py `_window`, the session's last-seen record (none exists).
- The streak counts private notes' days (as the welcome's streak does, `greeting_compose.gather`); only a day is read, never a word. If the owner wants private notes left out, change `_local_days`.
- Reminders, documents' edits and boards are counted in "new" for documents, boards and maps via `activity._events`; reminders made are left out of "new" on purpose. Not asked for by the owner; no test pins reminders.
- Not driven in a browser or against a real model; every model-on test uses the fake transport.
