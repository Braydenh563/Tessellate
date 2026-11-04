# Remaining after widgets-1104 (INBOX 1617)

Done: Focus timer (typeable 1 to 180, steps 1 below 10 and 5 above, preset 60), Stopwatch and Alarm widgets, Convert widget with a Time zone kind. Currency was already offered (hand-set dated rates).

- The Alarm widget lists no upcoming alarms: an alarm is an ordinary reminder, and a reminder made as an alarm is not marked as one, so the widget cannot show "your alarms" after a reload. Needs a source tag on the reminder (src/tessellate reminders model) or a label convention; the owner's call.
- The Convert pane's amount, two units and swap wrap to two or three rows in a 340px card (94px high at 1440, 205px at 390). It is the Calculator's existing layout and tests/test_calc_fit_1622.py holds it; a one-row version would be a Calculator change.
- Time zones use the zone database on this computer; a machine without it answers from the built-in table of places only (utilities.CONVERT_PLACES are all in the table or the database).
- Not verified: sound and system notification at an alarm's due time (the fake-transport caveat; reminders ring through the existing path, not changed here); a real touch device.
- Docs left for the orchestrator (told not to touch): CHANGELOG line, INBOX 1617 resolve, the plan's Built block move to HISTORY.
