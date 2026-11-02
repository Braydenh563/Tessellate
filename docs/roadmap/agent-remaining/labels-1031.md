# labels-1031: blind test items 7, 9, 10 and the first read

Done (branch agent/labels-1031): second /help/sample-notebook (2 to 1 per boot), bell "2 of 3 done" (it was true: a note and an answer; now names what is left), unclear labels (tag chip, date chip, both Filter menus, Save vs Save as draft), Write another after a Capture save, drag reorder driven with a real mouse (Notes and Library Documents: works, no fix).

Remaining, one line each:
- Filter stays the word on both menus (tests/test_ui_recipes.py, one filter trigger, INBOX 813); only the hover says what it holds.
- Write another is on the save line only; the Notes sub-tab still reopens on Your notes (frontend/js/navigation.js `showNotesSection`), not touched.
- Drag reorder: only Notes and Library Documents were driven; Boards and Media lists (obj-reorder.js `OBJ_SURFACES`) not measured; touch drag is mouse and pen only by design (obj-drag.js).
- `/ask-history/stats` is still fetched twice at boot (first-run.js `firstStepsRead` and one other caller); not looked into.
- Not verified: a model-filed note's "Go to it" beside Write another (with no model "Choose category" replaces it).
