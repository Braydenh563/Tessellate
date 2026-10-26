# Grammar and spelling upgrade (1026): remaining list

Scope: owner-1026b K4, K4b, K11; INBOX 1357 "The grammar and spellchecker need a major upgrade". Harness: `tests/_grammar_harness.js` runs the page's own prose pipeline (rules, dictionary, Harper lint filtering) in node with the real Harper worker over `tests/grammar_fixture_1026.json` (77 clean lines, 27 planted errors). Command: `node tests/_grammar_harness.js . tests/grammar_fixture_1026.json '{"timing":true}'`.

## What exists (step 1, scouted)

- Harper 2.10.0 (Apache-2.0), slim WASM build, vendored in `frontend/vendor/harper/` (15.9 MB wasm, 8 MB gzipped), run in `frontend/js/harper-worker.js` (module worker, lazy: started on the first prose document). Rules: every Harper default on except `UseTitleCase`; Harper kind `Spelling` dropped in the page (`DOC_GRAMMAR_SKIP_KINDS`), the dictionary does spelling.
- Page rules (`DOC_PROSE_RULES`, documents.js): repeat (16 small words), double-space, space-before-punctuation, missing-space (after full stop), missing-space-comma, double-punctuation, spelling (42-entry autocorrect table plus the 93k word list in `frontend/vendor/wordlist/en.txt`, `docSpellable` filter, personal dictionary), UK/US variant pairs, long-sentence (45 words, panel only), plus link offers and accessibility rules.
- Skip mask (`DOC_PROSE_SKIP`): fenced and inline code, URLs, markdown link destinations, reference definitions, html tags, wiki links, callout markers, frontmatter, suggestion marks. Applied to page rules, to the dictionary and to Harper findings by start offset. Not covered: link text, emails, file paths, units, image alt text.
- Personal dictionary (`docDictionaryAdd`, dictionary dialog) and per-document ignore (`docProseIgnored`, "Ignore in this document") exist.
- `server-side src/tessellate/ai/spelling.py` is the composer/autocorrect fixer (fix(), rejoin, split_run_on); it is not part of the document underlines, left alone.

## Baseline, before changes (77 clean lines; every finding on them is a false positive)

58 false positives on 37 of 77 clean lines. By class: Harper Style 15 (min->minimum x7, config/conf x4, Oxford comma, "w/"), Harper Formatting 8 (hyphen ranges "10-20" want an en dash x7; trailing space in a table row), Harper WordChoice 7 (hr, ms x2, sec x2, "uni" in a path x2), Harper Capitalization 6 ("Sam" canonical all-caps x3, mL, "e.g." at line start, lowercase list item), Harper Typo 3 (camelCase identifiers in prose), Harper Miscellaneous 2 (TODO, FYI), Harper Readability 1 (49-word list item), Harper Grammar 1 (link text), dictionary spelling 13 (names x8: Okafor, Priya, Aroha, Tomasz, Zeynep, Siobhan, Okafor's; "Fi" of Wi-Fi x2; "teh" in link text and image alt; "Autolink"), repeat in link text 1, space-before-punctuation before `![[embed]]` 1.
Planted errors: 24 of 27 caught. Misses: "Your going", "Your welcome", "your not" (you're confusions).
Timing (node, 1,918 words): page rules 17.6 ms (9 ms per 1,000 words), Harper in the worker 119 ms (62 ms per 1,000 words; off the main thread), `docProseExtras` 24 ms.

## After step 2 (fixture grown to 85 clean lines and 33 planted; the same fixture run on the step-1 tree)

Before: 61 false positives on 39 of 85 clean lines; 30 of 33 planted errors caught. After: 0 on 85; 33 of 33. A second set of 9 clean and 8 planted lines written after the fixes (not tuned against) gave 0 false positives and 8 of 8 (its "Reveiw" miss led to the transposition exception for names, then joined the fixture).
Classes fixed: link text (default skipped, toggle `check_link_text`), emails, file paths and names, units after a number, Harper house-style rules off (en dash ranges, Oxford comma, `Expand*`, TODO, FYI), list/heading/table lines never judged for length or capital, `e.g.` at a sentence start, "Sam" as all-caps, identifiers in prose, "Wi-Fi" fragments, names as misspellings, `![[embed]]` space-before-punctuation, your/you're (new rule `confusion`, kind Grammar, never applied by Fix all).
Already present, left alone: repeated words (Harper and the page rule), a/an, its/it's, their/there, capital after a full stop (Harper), "Add to dictionary" and "Ignore in this document" in the word menu.
Tradeoff recorded: a typo in a capitalised word in mid-sentence is marked only when it is a one-swap of a real word ("Reveiw"); other capitalised unknown words are taken for names.

## Steps

- [x] 1 Scout and measure (this file, fixture, harness).
- [x] 2 Fix as classes (K11, K4b, false positives, missing checks, Settings toggle "Check link text").
- [ ] 3 Harper version check (propose only).
- [ ] 4 Speed measurement after.
