# settings-1017 (Sonnet agent, port 8782, INBOX 904 B-list)

Order: B60 B65 B66 B56 B57 B63 B14 B68 B61 B75 B59 B53 B55.
Tests: tests/test_settings_bugs_1017.py (one per bug).

## Log
- B60 done: OCR language picker centres in Settings (label cy 2186 vs select 2193, now both 2193). b0c7e36.
- B65 done: Use this model disabled with 0 options; Stop the model disabled unless loaded or an answer runs (probe p/b65.js, MODE=empty/idle/loaded; before all enabled). 6cb4ef9.
- B66 done: mark_interrupted no longer stamps finished_at = start-up time (a 2-day-old run read "26 min ago"); line now reads the run's own start. Cause inferred from code + a seeded row; the owner's exact run was not reproduced. 94db83d.
- B56 done: Auto options in Appearance (density, performance, progress/background movement, Atlas look) and small-model mode name what Auto resolved to ("Auto (compact now)"); /models/status gains chat_model_small. dd53c5f. The rest (Bucket by Auto names its bucket, the Context window placeholder carries what Auto found) landed with the next commit.
- B57 done: Default accent ("indigo") painted #4664f0 inline; now sets nothing (computed back to the palette's #2f5bd3). 5567c10.
- B63 done: renderBrandLogo now repaints #dash-hero-emblem (gradient stayed rgb(91,124,255) after crimson; now rgb(255,91,95)). ae7fc72.
- B14 done: Expand all / Collapse all in the dock of panes with 2+ folds (skills, websearch, appearance, shortcuts, help, about; probe p/b14b.js at 1440 and 390). Left: panes with 0-1 fold (models, personas, tools, ...) get none; their "sections" are not collapsible. a29dfab.
- B68 done: gemma4:26b card labelled "gemma4:26b (a4b)", purpose rewritten (pull tag unchanged). cc91af3.
- B61 done (smallest honest): dictation sizes marked "(on this computer)" / "(~N MB to download)", confirm on choosing a size that is not here (cancel reverts, nothing downloads until first dictation), Remove this size (DELETE /voice/models/{size}); embedding models already had remove. Left: unsloth gemma embedding licence remark (not touched), a delete for other model kinds. 78f9e0f.
- B75 done: 18 '?' popovers in Settings + 8 on tabs + 3 in dialogs read 14.72px; a Settings hint promoted into the same shell (a <small>) read 12.27px. .help-popover now sets --text-lg itself (14.72). 24cf030.
- B55 done in part: the web menu offers Start/Install SearXNG on the DuckDuckGo provider too (was ["Web search settings"] only); palette row finds the Web clipper. Left: the clipper UX redesign (placed). B53: placed (no consume-side MCP UI exists; BACKLOG trust model). B59: investigated, not reproduced (no sentence-transformers here). Next: final report.
