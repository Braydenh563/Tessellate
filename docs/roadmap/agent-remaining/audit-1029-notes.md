# Notes deep audit, 2026-10-29

Scope: notes end to end (made, written, viewed, managed, found, linked, filed, and shown in other surfaces).
Head: `claude/sharp-thompson-45hngp` merged at f3104bc. Server on port 8802, own data dir, seeded with 200 notes
(some title-less, one private, some of 1,000 words, linked and tagged) plus the edge notes below.

**Caveat, said first:** every provider runs on a fake transport and no model ran. Everything model-on (AI filing,
tag suggest wording, Tidy repairs, entity extraction, meaning search, chat answers beyond the model-off composer) is
unverified. Rows are marked `run` (reproduced on this head, by driving the app or the API) or `code` (read, not run).

## Coverage

- Inventory: `docs/CODEMAP.md` lists 922 frontend functions in 45 note-scoped files (note-*.js, notes-*.js, editor.js,
  capture*.js, quick*.js, search*.js, link-types.js, connections.js, tag-*.js, categories-panel.js, spaces-find.js,
  tidy.js, suggestions-inbox.js, entity-page.js, vault-unlock.js, attach*.js, markdown.js, math-editor.js and
  neighbours). Ticked at module level, not function by function: a module is `driven` when a person-level interaction
  reached its entry point, `checked` when its code and one run path were read.
- Driven: notes list and cards, card menu and context menu (11 top-level rows, all sub-menus listed), filter menu, more
  menu, Tidy, Capture (New note), save, empty save, double save, slash menu, wiki-link picker, Alt+N quick note with
  draft recovery and chips, templates dialog, editor conflict (409) dialog, Esc with unsaved changes, link mode, batch
  tag, finder (Ctrl+P), command palette, bin and restore, dashboard, timeline, graph, Copy diagnostics path.
- API driven: create edge cases, privacy on and off, locked-vault reads and writes, links and unlink on bin and restore,
  search operators (30 queries), connections and references, tags rename, attachments (hostile names), clip (web off),
  chat privacy (locked and unlocked), exports, counts.
- Sweeps: `errors.js` 0 errors and 0 layout findings at 1440, 1024, 820 and 390. `axe.js` at 1440 light and dark (below).
  Phone tap-target measurement at 390x844. CPU 4x throttle numbers. 13 hostile markdown notes rendered in the list.
- Not reached (why): entity page (no entities exist without a model; `/entities` returns `[]`), OCR and voice (no
  engine), import (not driven), web clip (web is off by design; 403 message read and fine), lightbox, spaces,
  properties panel (menu row timed out in my drive), batch "Move to" (selector not found, not retried), keyboard-only
  full walk, touch gestures (swipe), 1024 and 820 axe (sweep stopped: not isolated), model-on parity.

## Findings

| id | sev | kind | finding | evidence (file:line or selector, the number) | verified | fix (the class) | effort |
| --- | --- | --- | --- | --- | --- | --- | --- |
| N1 | high | bug | A note with a short title "mentions" and "is mentioned by" most of the notebook: references, connections and the reference counts match the label as a substring (`LIKE %label%`), so a note whose text is `t` has 58 "Mentions it" incoming rows, `rem` and `Friday` 60 (the cap). Connections, "Linked by n" and the rail all inherit it | `api/routes_entries.py:3250-3320` (`Entry.content.like(f"%{label}%")`, how = "mentions it"), `:3796` (`reason: "Mentions it"`); `/entries/258/connections` incoming 58; `/entries/reference-counts?ids=258,260,261` = 60 each | run | one matcher for "mentions": whole word, case-folded, label of at least 3 characters or a title the user gave, shared by references, connections and reference-counts | M |
| N2 | high | bug | `is:pinned` (and every `is:` / `has:` flag filter) answers wrongly. Filter-only queries read the newest `depth` rows of the whole index (notes, chats, reminders mixed) and test the flag after the LIMIT, so older pinned notes vanish. `/search?q=is:pinned` returns 0 hits while notes 29 and 261 are pinned; with `kind:note` it returns only 261 (29 is older). The finder help (`index.html:820-852`) lists `is:pinned` as working. In the finder UI `is:pinned` shows only four Actions, no notes | `search/engine.py:794-870` (`_filter_only`, `ORDER BY written DESC LIMIT :depth`), `:1096-1135`; flags set at `search/index.py:615-637`; API output above | run | apply flag, kind and tag filters in the SQL before the LIMIT (the way `tag:` already is), then rank | S |
| N3 | med | bug | A binned note is returned by default search with no "in the bin" mark on its row; opening it gives the toast "No such note." and leaves a dead `#/notes/286` URL | note 286 created, deleted, finder "Zorbleflux" shows 1 row "Note, Oct 29, matched your words"; click then hash `#/notes/286`, toast "No such note." | run | exclude `deleted` from default search or show a bin chip with Restore as the action | S |
| N4 | med | bug | `title:` is not title-only. `title:Friday` ranks note 6 first, "matched the title", though neither its title nor its text says Friday; `title:Lisbon` also puts note 6 first | `/search?q=title:Friday&kind=note`: hits 6, 261, 279; note 6 content "A very long note title that goes on and on..." | run | the operator must restrict the MATCH to the title column, and say "no title matches" when none | S |
| N5 | med | bug | An exact number query returns notes that do not contain it, labelled "matched your words": `4471` returns 17 notes (budget line 47, Retro long 143 ...) none containing 4471 | `/search?q=4471&kind=note&limit=3` returns ids 99, 195, 107 with `explain: matched your words` | run (cause not isolated; prefix or number splitting suspected) | do not split or prefix-expand digit runs; show why a hit matched (the matched term) | S |
| N6 | med | bug | The server accepts whitespace-only notes (`"   "`, `"\n\n"`) with 201; the UI blocks them ("Write something first"), so the rule lives in one client path only. Blank notes (252, 253, 266) sit in the list, count in totals and are graph nodes with an empty preview | `POST /entries` 201 for `"   "`; `GET /entries` lists ids 266, 253, 252 with empty content; `/graph` nodes 252, 253 preview `""` | run | validate "has non-space content" in `EntryCreate` once so every entrance (quick note, capture, import, API) shares it | S |
| N7 | med | copy | A remote image in a note is shown as "tracker deleted" with a Dismiss control. The image is not deleted; the page's CSP (`img-src 'self' data: blob:`) refuses it. The browser also logs 4 CSP violations per render. A person cannot tell blocked from broken | card html `<span class="entry-inline-image-deleted">tracker deleted</span>`; `requestfailed` x4 `csp` for `https://example.invalid/pixel.png?id=1`; console CSP errors x10 in the list | run | a blocked-remote-image state: "Remote image not loaded (offline notebook)" with the link to open, and do not create the `<img>` at all | S |
| N8 | med | ui | A markdown table or code fence written in a note shows as raw source in the note card: `\| a \| b \|` / `\|---\|---\|` lines and the fence text. Other surfaces (documents, Chat) draw tables. The same note looks different in two places | card `.entry-content` innerHTML for `MDTABLE` is a text run `\| a \| b \|\n\|---\|---\|\n\| 1 \| 2 \|` with only bold and code spans; `MDCODE` card text includes the literal fence. Rail, Read view and export not compared | run (card only) | decide one rule for what a card renders; either render blocks in the expanded card or say in Help that cards are inline-only | M |
| N9 | med | perf | The Notes list draws every row with no virtualisation: 261 rows are 13,074 DOM nodes and 26,802 px; at 4x CPU scrolling to the end took 5,676 ms with 24 long tasks (max 236 ms), first rows 430 ms, filter keystrokes 46-165 ms, opening a 1,000-word note in the editor 1,519 ms (388 ms task), editor keystrokes 71-192 ms. At 1x every drive step still logs 50-200 ms long tasks. The notebook is 12.5k page elements idle | d24 and d9 runs; Copy diagnostics below: `x24 frame 220-3096ms [notes]`, `x12 frame 2280-4584ms [notes]`; `notes-list.js` `renderEntries` | run | window the list (render the viewport plus a margin), cheaper card (about 50 nodes each) | L |
| N10 | med | a11y | axe serious `label-content-name-mismatch`: `#notes-tidy` (name "Tidy", visible count badge is aria-hidden), `#tab-btn-reminders`, and 7 timeline day buttons `button[data-key="2026-10-23"]`... Same in light and dark at 1440 | `index.html:2489-2490`; axe output, 3 findings each theme | run (1440 only) | accessible name must start with the visible text (put the count in the name, or drop the aria-label) | S |
| N11 | med | a11y | On the phone, note-card controls are under the 44 px target the app uses: category chip 104x24 (x60), "More actions" 44x32 (x60), add-tag 30x24 (x36), "N more tags" 24x24, wiki-link chips 98x23 (x240), the suggested-tag chip is 68x14 which fails even WCAG 2.5.8's 24 px floor (x2) | d23 measurement at 390x844 via `getBoundingClientRect` | run | one hit-area rule for chips on coarse pointers (padding or `::after` extension), the suggested chip first | M |
| N12 | med | bug | The export of a note while the vault is locked succeeds with the placeholder as the content: `GET /entries/259/export.md` returns 200 `# Private note: unlock to read it.`; history also returns 200 with placeholder bodies. A person who exports a folder from a locked session gets files that look like notes and are not | `GET /entries/259/export.md` 200, `/entries/259/history` 200 (placeholder text), versus `PUT` and `/privacy` which correctly return 409 | run | exports and history must refuse (409, "Unlock first") like writes do, never emit placeholder text as content | S |
| N13 | med | bug | Four endpoints give four note counts in the same minute with no writes between: `/entries/count` 282, list `X-Total-Count` 279, `/statistics` notebook.notes 277, `/categories` 279, `/diagnostics` 279, `/graph` 279 nodes. The dashboard says "Today has 219 notes" while its own heatmap says "busiest day 220" and the digest "229 notes written" | `a13.py` output; dashboard text d25; blank notes (N6) are a candidate for the 277 | run (cause not isolated) | one `count_notes()` with one definition (boards, drafts, blank, private), used by every surface | M |
| N14 | low | ux | In link mode (card menu, Connect, Link to another) the instruction toast "Now click Link on the entry you want to connect it to (Esc cancels)" is still on screen after Esc; nothing says it was cancelled (Esc clears `linkSource`) | `note-panels.js:361` (toast), `settings-wiring.js:842-843` (Esc handler); d18 `after esc` toasts unchanged | run | on cancel, replace the toast with "Link cancelled", and dismiss the instruction | S |
| N15 | low | bug | A tag with a comma in it is accepted by the API as one tag (`"b,c"`), and the tag shows as "Show every note tagged #b,c", but the UI treats a comma as a separator, so it cannot be typed, renamed to or searched cleanly | `POST /entries` tags `["A","a"," a ","","b,c"]` returns `["A","b,c"]` | run | `normalise_tags` splits on comma or rejects it | S |
| N16 | low | ux | An unknown `has:` or `is:` value silently matches nothing (`has:attachment`, `is:favourite`, `is:private`). The app calls the pin "Favourites" everywhere but the operator is `is:pinned`; Help lists `has:image` and the real words are file, image, link, reminder, highlight | `search/engine.py:1150-1158` (HAS_WORDS, "matches nothing" by design); `/search?q=has:attachment&kind=note` 0 hits while `has:file` finds 270 | run | say "no filter called attachment; try file" in the summary line, alias `favourite` and `attachment` | S |
| N17 | low | a11y | 240 wiki-link chips in the list share one accessible name, "Go to the note starting “Atlas project”", so a screen-reader list of buttons cannot tell them apart; the same for repeated "Add to Favourites ...", "Copy this note's text", "Edit this entry", "More actions" on every card | d2 button list; d19 | run | name card buttons with the note's name ("Edit “Lisbon trip”") | S |
| N18 | low | a11y | An attachment filename has no length cap; a 400-character name becomes a 400-character `aria-label` ("Actions for “xxxx...”") and an unbounded row | `GET /entries/270` attachment 4 filename 400+ chars; `routes_files.py` upload | run | cap the stored display name (for example 120) and ellipsise in the label | S |
| N19 | low | ui | The `[[` picker inserts a title cut at 60 characters, `[[Atlas project line 183: remember to follow up about Atlas pr]]`. It resolves (by prefix to note 235), but the note text now holds a mangled name that will not follow a rename or match a second note with the same first 60 characters | d6 text after Enter; `a13.py` truncated link creates a link to 235 | run | insert the full title, or the id form, and show the short form only in the menu | S |
| N20 | low | security | Bidirectional control characters (U+202E) stored in a note pass into previews and the rail unchanged; display reordering was not checked on screen | note 257 preview `😀 emoji ‮ rtl` in rail (d3) | code (storage and preview seen; visual reorder not verified) | strip or isolate bidi controls in previews and titles (`<bdi>`) | S |
| N21 | low | security | While the vault is locked a private note's tags (`secretz`), word count and presence stay visible in the list, the graph node and `/tags`. The text does not leak (search, chat, graph content, locked read all clean) | `/graph` node 259 tags `["secretz"]`, words 6; `/tags` lists `secretz`; chat probes below | run | decide whether tags of a private note are private (hide them while locked, as the text is) | S |
| N22 | low | ux | A wiki link to a note that does not exist (`[[Nonexistent note target]]`, `[[ ]]`, `[[]]`, `[[a]]`) renders in the card as plain text with no offer to create it | card for `MDWIKI` shows hrefs `[]` and no create chip | run (card only; the editor has `offerToCreateWikiTarget`, which I did not trigger) | show the "create this note" chip on unresolved links in cards | S |

## Checked and fine (reproduced, not assumed)

- Hostile markdown: 13 notes (`<script>`, `onerror`, `javascript:` and `data:` links, iframe, remote image, long unbroken 400-character token, math, mermaid, footnote, deep nesting) gave 0 dialogs, 0 `script`/`iframe`/`[onerror]` nodes, `javascript:` and `data:` hrefs dropped, no horizontal overflow (document width 1440 = window).
- Remote images never leave the machine: every attempt failed with `csp` (N7 is the wording and noise, not a leak).
- Attachments: hostile names (`../../etc/evil.txt`, `a.html`, `a.svg`) stored under their own names; download is `octet-stream` with the sandbox CSP (`routes_files.py:173`).
- Privacy with the vault locked: the private note does not appear in search, list text, graph text or chat `raw_results` (`4471`, `launch` absent in 6 chat probes, locked and unlocked); writes and privacy toggles return 409.
- Bin and restore: links in and out come back after restore (delta/gamma/epsilon probe); a second link between the same notes is refused with a clear 400.
- Edit conflict: a 409 on save opens "This note changed in another window" with focus inside; Esc with unsaved changes asks to discard.
- Quick note (Alt+N): opens focused, restores the draft ("Your unsaved words are back."), offers date and tag chips, saves one note and one reminder; Capture empty save keeps focus on Save and says why; double save adds one note.
- Templates dialog opens with focus on a template, Use fills the Capture box.
- Batch tag on two notes: "Added “batchtag” (2 notes). Undo", verified 2 tagged.
- `errors.js` 0 errors, 0 layout findings at 1440, 1024, 820, 390. No document overflow at 390.
- Search with hostile input (`(`, `"`, `*`, `OR`, `NEAR(`, `%`, `_`, `\`, SQL text, emoji): 200, no error, 4-10 ms.
- Chat answers in model-off mode cite notes with working `#/notes/<id>` links.

## Cross-references

- Searched `audit-1028-ranked.md` and `audit-1029-composer.md` for each row above: none of N1 to N22 is held there (S34 "no single-note export from the overflow menu" is a different thing: the menu has Download .md).
- The persistent toast "Search by meaning is not working. Search is using keywords for now. Fix it" is on screen in nearly every drive of a model-off notebook; ranked E30 is the loading message, not this. Not counted as a new row.

## What could not be verified

- No model ran (fake transport): AI filing, "Accept the filing", Explain, Continue thought, Translate, tag suggest reasons, Tidy fixes, link reasons, entity pages, meaning search and model-on chat answers.
- Entity page, OCR, voice, import, lightbox, spaces, properties panel, batch "Move to", swipe gestures and a keyboard-only walk were not driven.
- axe ran at 1440 only; phone and 1024 axe not run. Dark mode driven only through axe.
- Counts N13: cause of the 277 vs 279 vs 282 split not isolated.
- Lag lines older than 2026-10-29T00:40Z in the report below come from an earlier agent on the same machine and are not mine.

## Copy diagnostics (from `diagCollect()`, the function behind Settings > Logs > Copy diagnostics; top of the lag list)

```
== Tessellate diagnostics ==
Made 2026-10-29T01:17:21.005Z | version 0.6.2 build 40019e8a88
Device: HeadlessChrome 153, Chromium 153 on Linux | viewport 1440x900 @1x | 4 cores | 16 GB
Notebook: 281 notes, 2 boards, 2 documents, 23 links | 12,569 page elements | heap 18 MB
Settings: embedding_backend=fastembed, llm_provider=ollama, local_only_ai=true, web_search_enabled=false; frame sampler on

== Lag (55 kinds, worst first) ==
x24 frame 220-3096ms [notes] no detail from the browser (11.7-22.8k elements)
x12 frame 2280-4584ms [notes] no script attributed (16.2k elements)
x22 frame 228-2161ms [library] no detail from the browser (11.7-15.7k elements)
x8 frame 259-2096ms [dashboard] no detail from the browser (11.7-13.4k elements)
x7 frame 1659-2363ms [timeline] no detail from the browser (11.9-16k elements)
x3 frame 220-264ms [notes] app.js Response.json.then 43-214ms (forced layout 22-200ms)
x2 frame 350-564ms [notes] settings-wiring.js TimerHandler:setTimeout 194-373ms after keydown input#note-search
x1 frame 310ms [notes] notes-list.js IntersectionObserverCallback 127ms after keydown input#note-search

== Errors in the browser (0 total, 0 kinds) ==
none
== Slow routes (a second or more) ==
GET /  1  1126 ms
== Server exceptions ==
none
== Failed jobs ==
none
== Complexity snapshot ==
12,569 elements; heap 18 MB. Largest child list: div#wb-more-menu 175 children
```

(The whiteboard lag rows in the full report come from other work on this machine and are left out here.)
