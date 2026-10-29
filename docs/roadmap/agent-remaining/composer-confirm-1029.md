# Composer confirm, follow-ups, app verbs (audit 1029): remaining

Done (this branch): rank 4 (C40 to C43), rank 24 (C44), rank 30 except C47.

Left:
- C47, one confirmation template per tense: the five openers and ids in act lines ("Done: created note #49", "Tag 1 note about ...", "Here's the change: ..."). File: src/tessellate/ai/composer_replies.py (CONFIRM, act_line) and commands.py `summarise_done`. Owner words: "one confirmation template per tense; name the note by title, not #29 or 1 note; one time format".
- C44 tail: "what else did Tom do" and "which one is the main one" (not a "more" sentence, no pronoun) still reach search; "undo that" / "pin it" after undo (the referent is an undo, not a note). File: src/tessellate/ai/reading.py `_follow_referent`.
- C46 did not reproduce offline: "show my reminders" reads as navigate (reminders) and "list my reminders" as list_reminders; tests pin both. The audit's live Ask reply "What should I look for?" is composer_suggest.py:174; not driven in a browser.
- C41 cause in the stream path (title cut to "Atlas") was not reproduced; the offline split on the last " to " dropped words from a title that holds "to" (fixed in `_rename`), and the old title line is now replaced, not kept as body.
- Not driven in Playwright or against a real model; all tests use the fake transport.
