# model-facts-1027

The owner, 2026-10-27: "why is it responding as the composer when my ai is in use?? I want the ai to be able to do what the composer can do but better??"

- done: the model writes counts, worked sums, records and read-tool rows from the engine's facts (`routes_chat._fact_events`); see the commit "Chat and the popup agent: with a model up the model writes every answer".
- left: "nothing matched" with a model and no tools (`_no_notes_events`, routes_chat.py) stays the engine's: the figure check cannot catch a model claiming a find; needs a check that reads a negative before it can move.
- done (review of 645e72b): counts checked against the engine's own (`ai/fact_check.py`), counted lists keep their rows, `_asks_change`, thinking held, Ask-mode reads said as acts, private reminders withheld.
- done (re-review of 645e72b, second pass): a windowed list's count, spans and conversions checked in any unit, a bare "one", amounts in words, years and times after "by", ISO dates, nested result counts limited to `by_` breakdowns, `_asks_change` needs an object the app can change, and the day's activity withholds a private note's reminder.
- left: "update on my reminders" and "remind me what is due this week" now read as questions, but the engine has no read for either (no `tool_read`), so the model answers them from the notes; the engine's reminder reader needs those phrasings.
- left: "find my gym notes" in Ask mode (a search act, `_act_events`) stays the engine's with a model up; it is no read tool, so it needs its find rows carried as facts first.
- left: "add up my expenses" has no engine sum (utilities read figures from the sentence only), so the model answers it from the notes, unchecked.
- left: the blocking `POST /chat` (routes_chat.py `chat()`) still returns a counted answer as the engine wrote it; no surface calls it.
- done (third review): `_asks_change` passes "to"/"from" and takes a part of a note as an object ("change the title of my first note", "remind me about ..."), a bare "one" after a determiner and plain words points, spans are checked with a tolerance and against the facts' dates (`fact_check._dated_spans`), reminder windows are read forwards (`routes_chat._reminder_window`: tomorrow, next week, on friday, the next 3 days), a figure after "by", a range and a year are verified (`fact_check._known`), amounts in words are read whole.
- left: a span in the prose is checked against the facts' dates only to the nearest unit, and a date in the facts with no year takes the year nearest now (`fact_check._moments`).
- left: "by 10" is a time only if the facts or the question state an hour 10; a model saying "by 5" about a reminder due at 5pm that the engine did not list is refused (the engine's answer stands).
- left: a window `composer_plan.window` does not read ("next fortnight", "last weekend") gives the whole list's count; measured: both return None.
