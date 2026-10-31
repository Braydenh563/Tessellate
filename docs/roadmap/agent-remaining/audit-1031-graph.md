# Deep audit 2026-10-31: graph (layout, worker, canvas, labels, legend, filters, focus, drag, zoom, search, popup, settings, phone, 500 and 2,000 notes)

Fable suite, surface 7 of 12. Server on 8852. Notebooks: 506 notes (386
links) and 2,001 notes (1,879 links) seeded through `/entries` (the extra
1,494 removed afterwards). Drives hg1 to hg3 (Playwright, 1440 and 390,
dark; CPU throttled 4x through CDP where marked; frame times from a rAF
sampler, long tasks from PerformanceObserver) and an API probe. Observed
unless marked code. The 1029 audit (`audit-1029-graph.md`) is re-verified
below; the new rows are the ones still open plus what it did not see.

## Rows

| Row | Sev | Kind | Finding | Evidence | Where | Verified | Fix | Size |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GR1 | high | perf | **A 2,000-note map is unusable while it settles.** At 4x CPU: data in 2.0 s, settled at 28.7 s, 120 long tasks summing 20.5 s with one of 947 ms. At 506 notes and 1x: settled at 10.4 s, 44 tasks summing 3.8 s (max 182). 1029 G3 unchanged (28 s, 120 tasks, 21.2 s). | hg2 2000-load-4x; hg1 load | worker frames applied on the main thread per tick (`gcFrameIntro`, `gcDraw` 809 lines) | run | Apply worker frames at most every 100 ms while settling and draw a cheap pass (no labels, no halos) until `end`; show the fitted map from the saved positions first. | M |
| GR2 | med | perf | Interaction at 4x: 506 notes hover sweep p50 52 ms (28 of 54 frames over 50 ms, tasks to 409 ms), wheel p50 76 ms, node drag p50 146 ms; 2,000 notes wheel p50 58 ms, p90 340, max 609. 1029 G5 and G8 open (hover was p50 83). | hg1 hover-sweep-4x, wheel-4x, drag-4x; hg2 2000-wheel-4x | `gcDraw`, `gcHoverStep`, redraw on every pointer move | run | Draw the static scene to an offscreen layer once per camera change and composite the hover and drag layer over it; one draw per frame. | M |
| GR3 | med | perf | Search at 2,000 notes and 4x: typing 14 characters costs 34 long tasks summing 4.6 s, one of 1,228 ms; at 506 notes and 1x, 8 tasks summing 796 ms (max 207). 1029 G10 open. | hg2 2000-search-4x; hg1 search `lt1` | `graphSearchRefresh` `graph.js:2249` → `applyGraphHighlight` per keystroke | run | Debounce to the pause (250 ms) and match on a prebuilt lower-cased title index; highlight through the cheap draw pass. | S |
| GR4 | med | ux | Legibility at default settings: 2,000 notes show 2 labels at fit and 0 labels at zoom 0.48, 0.67, 0.94 and 1.31 (labels start at `GC_LABEL_ZOOM` 1.4); 506 notes show 4 labels at fit of 12 wanted; on a phone the median dot is 1.9 px in radius (min 1.2, max 3.7) with 2 labels, a cloud of dots. 1029 G7 partly (landmarks exist, few are placed). | hg2 2000-labels-zoom; hg1 load `labelsDrawn`; hg3 phone-dots | `graph-canvas.js:274` to `:299` label constants; `gcDrawLabels` | run | Name the top hubs at every zoom (they are 12 at most), lower the label zoom to 0.9 past 1,000 notes, a 2.5 px minimum dot radius on coarse pointers. | S |
| GR5 | med | perf | Adding one note from the map re-runs the whole layout: at 1,041 notes "Added to the map." left `layoutRunning` true. | hg3 new-note-focus `running: true` | `gcStartWorker` on data change | run | Place the new node beside its links and warm the layout for a few ticks only. | S |
| GR6 | low | a11y | The New note dialog (`#graph-new`, a `div` with `role=dialog`, not modal) opens with focus nowhere (the active element stays a `div`); the minimap is `aria-hidden` though it pans on click; keyboard arrows on the map changed nothing measurable in `gcTab.selected` (announcements go to the status region; not followed). | hg1 add-node `focus: ""`; `index.html:4653`; hg3 keyboard-nav | `graph.js` new-note opener; minimap | run (keyboard: not verified) | Focus the title field on open; a labelled minimap button ("Show this part of the map"). | S |
| GR7 | low | copy | The node panel is labelled "Edit note" while it is a read-only card with Open, Focus, Pin, Link, More (editing is in Open). | hg1 popup `label: "Edit note"`, `editable: false` | `#graph-popup` aria-label | run | "Note: {title}". | S |
| GR8 | low | ux | Hide orphans removed 141 of 506 notes with nothing on the control saying how many; the time slider's two ends are two hours apart on a notebook written today, so it hides everything at a nudge. | hg1 focus-filters `orph.stats` "365 notes" | `#graph-hide-orphans`, `#graph-time-slider` | run | "Hide 141 unlinked notes"; snap the slider to days with a label. | S |
| GR9 | low | arch | `gcDraw` 809 lines, `gcWireInteraction` 467, `renderGraphCanvas` 366, `gcStartWorker` 290; `graph.js` 71 `addEventListener` to 1 `removeEventListener`; `graph-worker.js` 3,448 lines. 1029 G26's SVG renderer is gone. | counts | files | code | Split draw into scene, overlay and labels passes with their own tests. | M |

## 1029 graph rows re-verified

| Row | Now | Evidence |
| --- | --- | --- |
| G1 worker throws over 4,000 links | fixed | 2,001 notes settle, `end` arrives, positions saved |
| G2 popup drops edits | fixed (claimed d191ca8) | popup is read-only now; not re-run |
| G3 2,000-note settle | open, GR1 | 28.7 s, 120 tasks, 20.5 s at 4x |
| G4 re-layout on Colour/Size | fixed; Shape re-lays out by design | colour change 5 tasks 536 ms; shape 5.9 s, 26 tasks at 506 notes |
| G5, G8 interaction cost | open, GR2 | |
| G6 drift after reload | fixed | 60 nodes, RMS 0, max 1 px, none moved over 5 px |
| G7 labels at 500 | partly, GR4 | 4 of 12 landmarks at fit |
| G9 legend clipped | fixed | `scrollWidth` 1286 = `clientWidth` 1286, 10 items |
| G10 search cost | open, GR3 | |
| G11 search count, Enter, Esc | fixed | "28 matches", Enter pans (x 409 to 490), Esc clears and keeps focus |
| G12 light contrast | not re-measured | |
| G13 touch slop | fixed | `GC_SLOP_PX` 20 on coarse pointers; a tap on a 3.8 px hub opens its panel |
| G14, G15 refit on dock, link by drop | not re-run | |
| G16 orphan links | fixed (claimed d82fbfe) | not re-run |
| G17, G18 topic chip, hover copy | not re-run | |
| G19 Esc focus | fixed | focus returns to `#graph-box` |
| G20 tab stops before the map | open | Tab from the box: zoom in, out, fit, fullscreen, then the status bar |
| G21 toggles 32 x 18 | not seen | options panel holds selects and sliders, no checkboxes found |
| G22 "No kind 64" chip | not seen | filter fold text has no such chip |
| G23 help clipped | fixed | 467 px panel, `scrollHeight` 465, ends at 583 of 900 |
| G24 furniture overlaps | fixed in the run | a toast overlapped neither zoom, minimap nor legend |
| G25 popup follows in x only | fixed | follows both axes (406, 388 after a 60, 60 drag) |
| G26 SVG renderer | fixed | `renderGraphSvg` gone |
| G27 pin bounds | fixed | 422 over 1,000,000 and for NaN; `/graph/local/999999` 404 |
| G28, G29, G30 | not re-run | tab return at 2,000 notes: 1.66 s, 7 tasks max 132 (G29 better) |
| INBOX 1471 second click closes | fixed | |

## Coverage

| Area | Driven | Notes |
| --- | --- | --- |
| Load, settle, stats, legend at 506 and 2,001 notes | run | `/graph` 274 KB (22 KB gzip) and 629 KB |
| Hover, wheel, drag at 4x | run | |
| Search: count, Enter, Esc | run | |
| Popup: open, second click, Esc, drag the panel, follow a dragged node, actions | run | |
| Context menu (5 items), options (layout, shape, colour, size, minimap, sliders), reset with Undo | run | |
| Focus from the popup (39 of 506), hide orphans, filter fold | run | `#graph-focus-in` did nothing from the panel (not verified what it is for) |
| Minimap, export PNG (1 MB in 1.5 s), add a note from the map, help, keyboard Tab order | run | |
| Reload position drift | run | |
| Phone 390: load, dot sizes, tap, pinch (0.25 to 1.45), controls (all 44 px) | run | |
| API: pin bounds, NaN, unpin-all, local 404, path and topics validation, match cap (200), structure | run | |
| Light theme contrast, groups, clusters colouring, trace, link by drop, selection dock actions, fullscreen, the 40-note case | not driven | |

## Already good

- Search has a live count, Enter steps through matches and pans, Escape clears.
- The panel closes on a second click, drags by its head and follows its node; Escape returns focus to the map box.
- Positions are kept across reloads exactly; colour and size changes no longer re-lay out.
- Pins and bulk pins are bounded and refuse NaN; unknown notes are 404.
- On a phone every control is 44 px, the hit slop is 20 px, pinch zooms.
- The legend fits; the help panel fits; a toast overlaps no furniture.

## Not verified

- Keyboard arrow navigation (the status region's announcements were not followed; `gcTab.selected` stayed empty); light-theme contrast; the 40-note case at 4x; `#graph-focus-in`'s role; `/graph` at 2,000 notes under gzip.
