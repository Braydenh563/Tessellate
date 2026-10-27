# model-facts-1027

The owner, 2026-10-27: "why is it responding as the composer when my ai is in use?? I want the ai to be able to do what the composer can do but better??"

- done: the model writes counts, worked sums, records and read-tool rows from the engine's facts (`routes_chat._fact_events`); see the commit "Chat and the popup agent: with a model up the model writes every answer".
- left: "nothing matched" with a model and no tools (`_no_notes_events`, routes_chat.py) stays the engine's: the figure check cannot catch a model claiming a find; needs a check that reads a negative before it can move.
- done (review of 645e72b): counts checked against the engine's own (`ai/fact_check.py`), counted lists keep their rows, `_asks_change`, thinking held, Ask-mode reads said as acts, private reminders withheld.
- left: "find my gym notes" in Ask mode (a search act, `_act_events`) stays the engine's with a model up; it is no read tool, so it needs its find rows carried as facts first.
- left: "add up my expenses" has no engine sum (utilities read figures from the sentence only), so the model answers it from the notes, unchecked.
- left: the blocking `POST /chat` (routes_chat.py `chat()`) still returns a counted answer as the engine wrote it; no surface calls it.
