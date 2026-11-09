# composer-r8-1109 remaining

- done: checklist note of named items (task_acts.read_checklist_note, commands._plan_new_note label), bare "call Anna" (commands._bare_call), a pair said as a phrase in one note stays one subject (composer_ask.NOTE_TEXTS, _said_together), INBOX 1705 (e) integration test (tests/test_composer_r8_1109.py, with the rule switched off it fails).
- r5/r6/r7 items: everything open was built in r6/r7 or above, except the owner decision below.

## Owner decisions (not taken)

- D25, citations double up: `answer-kit.js` adds a numbered mark after every grounded sentence and `ask-compose.js` also links the composer's "[**Title**]". Choosing between decision 5 (the bracketed title opens the note) and INBOX 299 (numbers match the Sources list). Measured by reading the code, never in a browser.

## Left

- "call Anna" needs a capitalised name or a kin word: "call anna" (lower case) and "call the dentist" are still answered from the notes, not offered as a reminder.
- A phrase pair in one note is one subject even when the person meant both ("tom and sara" typed lower case, with a note saying "Tom and Sara went"): the notes win over the guess.
- "make a checklist for my trip" (one subject, no items) is not read as a checklist note.
- "put it in my journal" (bare my journal) is left to the note called journal (r6, kept as decided).
- 1705 (b): the joke note leads by its quote, not by name.
