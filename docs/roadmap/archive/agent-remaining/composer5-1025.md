# composer5 (1025)

Done (tests/test_composer_five_1025.py, a Biology 101 / WW1 / Maths notebook with reminders):
- 1: a "Remind you to ..." offer only for a question about tasks or a "when" naming the task (`composer_digest._on_topic`); the closing line names a note the answer cited, never the newest note (`routes_chat._cited_titles`).
- 2: "when is my exam", "what date is my exam", "when do I have my exam" name the reminder and the note's own sentence (`composer_plan._when_is`, `_WHEN_IS_ALT`).
- 3: figures in an answer to a date-arithmetic question, and a reminder's ISO fields, are not claims (`source_check.Sources.computed`, `_ISO`).
- 4: "summarise my lecture notes" is every note in the category "Lecture notes" (`composer_study.category_notes`); tilde fences, indented code, pasted statement runs and empty bullets are dropped from summaries (`study._drop_code`, `_MARKER_ONLY`).
- 5: fenced code is not read by the tagger unless it is most of the note (`lexical_filing.clean`); Education, Learning and Study are not offered beside a specific subject (`tagging.GENERIC_TOPICS`).

Left:
- (done, composer7) The "Also:" line of a fact answer still says a checklist item as a fact ("read chapter 4; revise the Krebs cycle diagram" under "what is the Krebs cycle"): composer_digest `_single`, unticked tasks should not be volunteered on a definition.
- The grounding "Heads up" was reproduced only at unit level and through a faked model reply; the exact owner turn ("could not find 14") was not reproduced against a real model.
- (done, composer7) "what's my next exam" answers from the note and ignores the reminder (`composer_plan._WHEN_IS` wants "when"); "exam date" likewise.
- Carried from composer4: compare N-way and as a table, quiz on a whole category, the "Sources: N notes" line (boot JS cap).
