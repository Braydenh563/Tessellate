// app-palette.js: the Ctrl/Cmd-K palette's window, that is opening and closing
// it, matching what is typed against the app's commands and places (never its
// content: that is Find anything's, INBOX 666), drawing the rows and the
// preview, and its keyboard. Moved out of
// settings-panes.js on 2026-10-05 (the boot-script gzip budget, ratchet in
// tests/test_static_compression.py): it opens only by a person's chord or a
// click on "Commands", so none of it is needed to draw the first screen.
// Loaded on first use by `LAZY_MODULES.appPalette` (app.js), whose stand-in
// for `openPalette` fetches this file and then calls the real one.
//
// **What stayed at boot, and why.** `paletteCommands` (the registry of rows),
// `catalogueRun`, `paletteKeys`, `paletteAbouts` and `paletteRowParts` are
// read synchronously by other surfaces that are not the palette: Quick access
// on the dashboard, Find anything's action rows, and the Tools and features
// dialog. A stand-in returns a promise, so those could not be lazy without
// making their callers asynchronous. `closePalette` and `renderPalette` are
// called from boot code only behind a "the palette is open" check, and only
// `openPalette` opens it, so the file is always in by then.
//
// The palette's three listeners (the input, its keys, the backdrop) were
// top-level wiring in settings-wiring.js; they are the last lines here, and
// run when the file loads, which is before `openPalette` shows the overlay.

let paletteIndex = 0;

//: What the palette was opened over (Brief 89, utilities rows 3 and 4): the
//: field that had the focus and the text selected in it, caught before the
//: palette's own box takes the focus, so Count words and Insert template act
//: on the editor the person was in.
const paletteCaught = { target: null, selection: "", start: null, end: null, range: null };

//: The usage ledger's counts (core/usage.py, WORLD_CLASS_PLAN H9): with
//: nothing typed, the commands this person runs most come first.
const paletteUsage = new Map();

//: A command's name in the ledger (`usageFeatureName`, navigation.js).
function paletteFeature(match) {
  return usageFeatureName(match.label);
}

//: Every run goes through here, so a command run by click and by Enter is
//: counted once either way. The handoff row ("Search everything for") is a
//: way into another surface, not a feature, and is not counted.
function paletteRun(match) {
  const typed = $("palette-input").value.trim().toLowerCase();
  closePalette();
  if (!match.handoff) {
    const name = paletteFeature(match);
    if (name) usageCount(name);
    if (name && typed) palettePick(typed, name);
  }
  match.run();
}

async function openPalette() {
  //: Opened early by settings-wiring.js's wrapper while this file loaded: what was typed
  //: meanwhile stays, and an Enter pressed meanwhile runs the first row.
  const early = window.paletteEarly;
  window.paletteEarly = null;
  if (early) $("palette-input").removeEventListener("keydown", early.onKey);
  overlayReturnFocus = early ? early.returnFocus : document.activeElement;
  //: A text box keeps its own caret through a blur; a rich editor's lives in
  //: the document's selection, which the palette's box is about to take.
  const held = window.getSelection();
  Object.assign(paletteCaught, {
    target: overlayReturnFocus,
    selection: early ? early.selection : String(held || ""),
    start: overlayReturnFocus?.selectionStart ?? null,
    end: overlayReturnFocus?.selectionEnd ?? null,
    range: early ? early.range : held?.rangeCount ? held.getRangeAt(0).cloneRange() : null,
  });
  const typed = early ? $("palette-input").value : "";
  $("palette-overlay").classList.remove("hidden");
  $("palette-input").value = typed;
  paletteIndex = 0;
  renderPalette(typed);
  quickAddAttach($("palette-input"), "palette");
  $("palette-input").focus();
  const first = early?.enter && paletteMatches(typed)[0];
  if (first) return paletteRun(first);

  apiJson("/usage/summary", { method: "POST", body: JSON.stringify({ known: [] }), silent: true })
    .then((res) => {
      paletteUsage.clear();
      for (const f of res.features || []) paletteUsage.set(f.name, f.count);
      if (!$("palette-input").value) renderPalette("");
    })
    .catch(() => {});
}

function closePalette() {
  $("palette-overlay").classList.add("hidden");
  overlayReturnFocus?.focus?.();
  overlayReturnFocus = null;
}

//: Read a field that is *supposed* to be a string, without letting one bad
//: record throw the whole palette away (a command's label and keywords are the
//: fields read now, and a row built from a name the person typed, a category,
//: may not be a string).
function paletteText(value) {
  return typeof value === "string" ? value.toLowerCase() : "";
}

//: **The editor's palette** (DOCUMENTS_PLAN 23, I3): a query that starts
//: with ">" is VS Code's Ctrl+Shift+P, which the code editor opens this
//: palette on (`docIdeOpenPalette`): the open document's commands only,
//: matched as VS Code matches, the letters in order with gaps allowed,
//: runs and word starts first.
function paletteFuzzyScore(label, needle) {
  if (!needle) return 0;
  const hay = label.toLowerCase();
  let at = -1;
  let score = 0;
  let last = -2;
  for (const ch of needle) {
    if (ch === " ") continue;
    at = hay.indexOf(ch, at + 1);
    if (at < 0) return -1;
    score += at === last + 1 ? 3 : 1;
    if (at === 0 || /[\s:(,-]/.test(hay[at - 1])) score += 2;
    last = at;
  }
  //: A typed word found whole counts for more than the same letters
  //: scattered: "run tests" means the row that says "tests".
  for (const word of needle.split(/\s+/)) if (word && hay.includes(word)) score += word.length * 2;
  return score;
}

function paletteEditorMatches(needle) {
  const rows = paletteCommands().filter((c) => c.group === "This document");
  if (!needle) return rows;
  return rows
    .map((c, order) => ({ c, order, score: paletteFuzzyScore(String(c.label).replace(/^ph:[\w-]+\s*/, ""), needle) }))
    .filter((r) => r.score >= 0)
    .sort((a, b) => b.score - a.score || a.order - b.order)
    .map((r) => r.c);
}

function paletteMatches(query) {
  const lowered = query.trim().toLowerCase();
  if (lowered.startsWith(">")) return paletteEditorMatches(lowered.slice(1).trim());
  //: **The app's own commands get a group name too, now that something can
  //: sit above them.** They had none because they were always first and a
  //: header over the top of a list says nothing; with the editor's group
  //: ahead of them, an unlabelled run reads as more of "This document", which
  //: is the one thing it is not. `group` is only set where the row has not
  //: already claimed one, so the editor's stays its own.
  //: The notes rows (`notesPaletteCommands`, below, INBOX 432): a
  //: category to go to, a #tag to show, Move for the note in hand.
  const base = paletteBase(lowered);
  if (!lowered) {
    //: Most used first, within each group, so a group's heading still
    //: comes once; ties keep the registry's own order (a stable sort).
    const used = (c) => paletteUsage.get(paletteFeature(c)) || 0;
    const groups = [...new Set(base.map((c) => c.group))];
    return groups.flatMap((g) => base.filter((c) => c.group === g).sort((a, b) => used(b) - used(a)));
  }
  //: Typed text reaches the generated rows too (Brief 90): every feature,
  //: every act and every setting, ranked by `paletteRanked`. At rest the
  //: list stays the hand-written one, which is the app's own short list.
  const pool = palettePool(base, lowered);
  const commands = paletteRanked(pool, lowered);
  if (!commands.length) commands.push(...paletteNearestRows(pool, lowered));
  commands.push(...paletteNearRows(pool, lowered, commands));

  //: **A question typed into the palette is a question** (INBOX 224). The
  //: palette is a jump list, so "how do I turn off web search?" matches
  //: nothing in it and the box goes empty, which reads as "this app has no
  //: answer". A line ending in a question mark is offered to Atlas instead,
  //: first, with everything the palette did find underneath.
  if (query.trim().endsWith("?")) {
    commands.unshift({
      label: `Ask Atlas: ${query.trim()}`,
      mark: "atlas",
      run: () => askAtlasAbout(query.trim()),
    });
  }

  //: **The palette does not search what you keep** (INBOX 666). Notes,
  //: documents, files, boards, reminders and conversations are Find anything's:
  //: the palette is commands and places in the app (tabs, sub-tabs, Settings
  //: pages, actions, a category, a tag). Typed text always ends with one row
  //: that carries it to Find anything, searched at once; when no command
  //: matched it is the only row, so it is the lit one and Enter takes it.
  const typed = query.trim();
  const handoff = {
    group: "Search",
    label: `ph:magnifying-glass Search everything for \u201c${typed}\u201d`,
    //: With nothing else listed, the row says why (row 3).
    about: commands.length
      ? "Find anything searches your notes, documents, files and the app."
      : `No command or setting is called \u201c${typed}\u201d. Find anything searches what you keep.`,
    handoff: true,
    run: () => openFinder(typed),
  };
  //: The act the words describe, first (quickadd.js, CHAT_PLAN decision 50):
  //: "remind me friday 9 dentist" is a reminder, its chips under the box.
  //: Over a board, a sentence that arranges it (whiteboard-commands.js).
  const act = (typeof quickAddPaletteRow === "function" ? quickAddPaletteRow(query) : null)
    || (typeof wbPaletteActRow === "function" ? wbPaletteActRow(query) : null);
  return [...(act ? [act] : []), ...utilityPaletteRows(lowered), ...commands, handoff];
}

//: "timer 10 minutes", "25 min timer", "countdown 90s": a length read from
//: the words, minutes when no unit is given.
const PALETTE_TIMER = /^(?:start (?:a )?)?(?:timer|countdown)(?: for)? (\d+(?:\.\d+)?) ?([a-z]*)$|^(\d+(?:\.\d+)?) ?([a-z]*) (?:timer|countdown)$/;
const PALETTE_UNITS = { h: 60, hr: 60, hrs: 60, hour: 60, hours: 60, s: 1 / 60, sec: 1 / 60, secs: 1 / 60, second: 1 / 60, seconds: 1 / 60 };

//: The small tools' rows built from what was typed (UI_MODERNISATION
//: utilities rows 2 and 4): a timer of the length named, and the templates
//: (Settings, Templates) for "insert template" or "template meeting".
function utilityPaletteRows(lowered) {
  const rows = [];
  const timer = lowered.match(PALETTE_TIMER);
  if (timer) {
    const amount = Number(timer[1] || timer[3]);
    const unit = timer[2] || timer[4] || "m";
    const minutes = amount * (PALETTE_UNITS[unit] || (/^m/.test(unit) ? 1 : 0));
    if (minutes > 0) {
      rows.push({
        group: "Do it",
        label: `ph:timer Start a timer: ${amount} ${PALETTE_UNITS[unit] === 60 ? "hour" : PALETTE_UNITS[unit] ? "second" : "minute"}${amount === 1 ? "" : "s"}`,
        about: "Counts down on the status bar and says when the time is up. Press it to stop.",
        run: () => ensureModule("utilities").then(() => startUtilityTimer(minutes)),
      });
    }
  }
  //: B55: the clipper lived only in Settings, Import & export. Typing clip, clipper
  //: or bookmarklet finds it, and the row opens it with the bookmark in view.
  if (/\b(?:clip(?:per)?|bookmarklet)\b/.test(lowered)) {
    rows.push({
      group: "Do it",
      label: "ph:bookmark-simple Web clipper",
      about: "Keep a page from your browser as a note: drag the bookmark to your bookmarks bar, then press it on the page.",
      run: () => openSettingsModal("data", "web-clip-box"),
    });
  }
  const asked = lowered.match(/^(?:insert )?(?:a )?(?:templates?|snippets?)\b ?(.*)$/);
  if (asked) {
    //: Before note-templates.js has loaded this is its stand-in's promise:
    //: the rows come on the redraw it ends with.
    const catalogue = templateCatalogue();
    if (catalogue instanceof Promise) {
      catalogue.then(() => renderPalette($("palette-input").value)).catch(() => {});
      return rows;
    }
    const { builtin, custom } = catalogue;
    const caught = { ...paletteCaught };
    for (const template of [...custom, ...builtin].filter((t) => t.name.toLowerCase().includes(asked[1].trim())).slice(0, 10)) {
      rows.push({
        group: "Insert a template",
        label: `ph:note-blank Insert template: ${template.name}`,
        about: template.description || "From Settings, Templates; it goes in where the cursor was.",
        run: () => ensureModule("utilities").then(() => insertTemplate(template, caught)),
      });
    }
  }
  return rows;
}

// ---- generated rows (UI_MODERNISATION "the command palette", rows 1, 3 and 5; Brief 90) ----
// Measured before: 11 of 18 words typed here found no command ("statistics",
// "timer", "word count", "find anything"), while "Tools and features" listed
// most of them by name. The palette was a second hand-written list drifting
// from the first, so typed text now also reaches three sets written once
// where they live (CHAT_PLAN decision 53; tests/test_palette_coverage.py).

//: The acts and the Settings index arrive after the palette opens: the acts
//: are the server's table, the index is in the lazy Settings bundle.
const paletteGen = { acts: null, actsAsked: false, settings: false, settingsAsked: false, near: null, nearAsked: "" };

//: Other words for a row, by where it lands: the words people type that the
//: row's own name does not use. A key is a reveal target, `tab:<tab>` or
//: `settings:<pane>` (tests/test_palette_coverage.py checks each exists).
const PALETTE_ALIASES = {
  "todays-note": "calendar daily journal diary",
  "tab:reminders": "calendar due todo to-do task tasks",
  "board-create": "whiteboard canvas",
  "board-overview": "whiteboard minimap",
  "board-find": "whiteboard",
  "map-create": "mind map mindmap whiteboard",
  "tab:graph": "network links connections",
  "shortcuts": "keys hotkeys keybindings",
  "settings:models": "llm ai ollama download",
  "settings:privacy": "online internet offline network",
  "library-bin": "recycle",
  "page-reader": "ocr scan image picture photo read text",
  "extra-row": "ocr tesseract rapidocr",
  "widget-focus": "timer pomodoro countdown stopwatch",
  "widget-pace": "statistics stats",
  "widget-heatmap": "statistics stats",
  "widget-streak": "statistics stats",
  "doc-word-goal": "word count reading time",
  "chat-answers": "calculator calculate sum maths math percent convert conversion units currency",
  "finder": "find anything search everything",
};

//: Words that say nothing about which row is meant ("how do I", "the").
const PALETTE_FILLER = new Set(["a", "an", "the", "to", "from", "my", "of", "for", "in", "on", "and", "how", "do", "i", "me", "with", "is"]);

//: The hand-written rows: the app's commands and the notes rows
//: (`notesPaletteCommands`, below, INBOX 432: a category to go to, a #tag to
//: show, Move for the note in hand), each with a group.
function paletteBase(lowered) {
  return [...paletteCommands(), ...notesPaletteCommands(lowered)].map((c) => (c.group ? c : { ...c, group: "Everywhere" }));
}

//: Everything typed text can reach: the hand-written rows and the three
//: generated sets.
function palettePool(base, lowered) {
  return [...base, ...paletteFeatureRows(base), ...paletteActRows(), ...paletteSettingRows(lowered)];
}

//: Where a row lands, the key `PALETTE_ALIASES` is read by.
function paletteTarget(row) {
  if (row.reveal) return row.reveal;
  return row.tab ? `tab:${row.tab}` : "";
}

//: The meaning tables (meaning.js) arriving after the first keystroke.
document.addEventListener("meaning-ready", () => paletteRefresh());

//: Re-draw an open palette when a generated set arrives after the first draw.
function paletteRefresh() {
  const input = $("palette-input");
  if (!$("palette-overlay").classList.contains("hidden") && input.value.trim()) renderPalette(input.value);
}

//: Every feature "Tools and features" lists that no hand-written row already
//: lands on. A shared landing ("notes-capture" is three features) keeps all
//: of them, so "note links" still finds its row.
function paletteFeatureRows(commands) {
  const covered = new Set(commands.map(paletteTarget).filter(Boolean));
  const said = commands.map((c) => paletteText(c.label));
  const items = featureCatalog().flatMap((group) => group.items);
  const landings = new Map();
  for (const item of items) landings.set(paletteTarget(item), (landings.get(paletteTarget(item)) || 0) + 1);
  return items
    .filter((item) => {
      const target = paletteTarget(item);
      if (said.some((label) => label.includes(paletteText(item.name)))) return false;
      return !(target && covered.has(target) && landings.get(target) === 1);
    })
    .map((item) => ({ group: "Features", label: `ph:compass ${item.name}`, about: item.desc, reveal: item.reveal, tab: item.tab, run: item.run }));
}

//: Every act Chat does from one sentence (`act_registry.palette_rows`), as a
//: row that starts it there with its words in the box and the caret after them.
function paletteActRows() {
  if (!paletteGen.actsAsked) {
    paletteGen.actsAsked = true;
    apiJson("/read/acts", { silent: true })
      .then((got) => {
        paletteGen.acts = got.rows || [];
        paletteRefresh();
      })
      .catch(() => {});
  }
  return (paletteGen.acts || []).map((act) => ({
    group: "Say it in Chat",
    label: `ph:lightning ${act.label}`,
    about: act.help,
    keywords: act.example,
    run: () => paletteStartAct(act.stem || `${String(act.example || "").split(" ")[0]} `),
  }));
}

//: Chat, with the act's opening words typed and the caret after them. After
//: the tab's own focus handling has settled (measured in toggleAgentPalette:
//: a same-turn focus was gone by the next frame).
async function paletteStartAct(words) {
  await switchTab("chat");
  setTimeout(() => {
    const box = $("chat-input");
    box.value = words;
    box.dispatchEvent(new Event("input", { bubbles: true }));
    box.focus();
    box.setSelectionRange(words.length, words.length);
  }, 80);
}

//: The Settings index's matches (`findSettings`, settings-find.js), four at
//: most: a setting is found by what it does, not only by its pane's name.
function paletteSettingRows(query) {
  if (!paletteGen.settingsAsked) {
    paletteGen.settingsAsked = true;
    ensureModule("settingsUi").then((ok) => {
      paletteGen.settings = ok;
      paletteRefresh();
    });
  }
  if (!paletteGen.settings) return [];
  return findSettings(query, 4).map((row) => ({
    group: "Settings",
    label: `ph:gear ${row.text}`,
    about: `In Settings, ${row.sectionLabel}${row.where ? `, under ${row.where}` : ""}.`,
    keywords: row.haystack,
    run: paletteLater(async () => {
      await openSettingsModal(row.section);
      openSettingRow(row);
    }),
  }));
}

//: The words that name something: "how do I read text from an image" is
//: read, text, image.
function paletteWords(lowered) {
  const words = lowered.split(/\s+/).filter(Boolean);
  const named = words.filter((w) => !PALETTE_FILLER.has(w));
  return named.length ? named : words;
}

//: How well a row answers the words: a word of its name starting with them
//: (4: "timeline" is as much "Go to Timeline" as "Timeline bands") or its
//: name holding them (3), its other words (2: keywords and aliases), its line of
//: what it does (1). 0 is no match.
//: `things` is the query read by meaning (meaning.js, Brief 94): "trash" is
//: the bin's other word, "keybord" a slip of "keyboard". A row its name or
//: other words hold that way scores as another word for it (2).
function paletteScore(row, phrase, words, things = null) {
  const label = paletteText(row.label).replace(/(^|\s)ph:[\w-]+\s*/g, " ").trim();
  if (label.startsWith(phrase) || label.includes(` ${phrase}`)) return 4;
  if (label.includes(phrase)) return 3;
  const named = `${label} ${paletteText(row.keywords)} ${PALETTE_ALIASES[paletteTarget(row)] || ""}`;
  if (named.includes(phrase) || words.every((w) => named.includes(w))) return 2;
  if (things && meaningHolds(things, named)) return 2;
  const about = `${named} ${paletteText(row.about)}`;
  if (words.every((w) => about.includes(w)) || (things && meaningHolds(things, about))) return 1;
  //: All but one of two or more things in its name ("what the ai remembers
  //: about me" is What it remembers): loose, so three at most, last.
  return things && things.length > 1 && meaningMissing(things, named) <= 1 ? 1 : 0;
}

//: The words every row's name, other words and aliases use: what a slip is
//: read against.
function paletteVocab(rows) {
  const out = new Set();
  for (const row of rows) {
    for (const w of meaningWords(`${paletteText(row.label).replace(/(^|\s)ph:[\w-]+/g, " ")} ${paletteText(row.keywords)} ${PALETTE_ALIASES[paletteTarget(row)] || ""}`)) out.add(w);
  }
  return out;
}

//: The matching rows, best first, each group's heading once: groups in the
//: order of their best row, rows within a group by score, then by use.
//: Rows found only by their line of what they do are three at most: "note"
//: is in half the app's descriptions.
function paletteRanked(rows, lowered) {
  const words = paletteWords(lowered);
  const picks = palettePrefixPicks(lowered);
  const things = meaningAlts(lowered, paletteVocab(rows));
  const scored = [];
  let loose = 0;
  rows.forEach((row, index) => {
    const score = paletteScore(row, lowered, words, things);
    if (!score || (score === 1 && ++loose > 3)) return;
    const name = paletteFeature(row);
    //: Between rows of one score, the one nearer the words typed (meaning.js):
    //: "change password" is the password row before the lock.
    const near = 2 * meaningCloseness(things, paletteText(row.label)) + meaningCloseness(things, paletteText(row.keywords));
    scored.push({ row, score, index, near, picked: picks[name] || 0, used: paletteUsage.get(name) || 0 });
  });
  scored.sort((a, b) => b.picked - a.picked || b.score - a.score || b.near - a.near || b.used - a.used || a.index - b.index);
  const groups = [...new Set(scored.map((s) => s.row.group))];
  return groups.flatMap((g) => scored.filter((s) => s.row.group === g).map((s) => ({ ...s.row, why: paletteWhy(s, lowered) })));
}

//: **Learned ranking** (row 5): the row a person ran for these exact words
//: comes first the next time they type them, ahead of how well its name
//: matches (Raycast's and Alfred's learned order). Kept per browser in the
//: prefs module, the 80 most recent queries, each the counts of what was run.
function palettePicks() {
  return prefs.json("palette-picks", {});
}

//: **Prefixes count too, at half weight** (OPEN, the palette row:
//: "Raycast also learns prefixes"; the recommendation taken): "se" lifts
//: what was run for "settings", below what was run for "se" itself. Two
//: letters at least, so one letter does not reorder everything.
function palettePrefixPicks(typed) {
  const all = palettePicks();
  const out = { ...(all[typed] || {}) };
  if (typed.length < 2) return out;
  for (const [query, counts] of Object.entries(all)) {
    if (query === typed || !query.startsWith(typed)) continue;
    for (const [name, n] of Object.entries(counts)) out[name] = (out[name] || 0) + n / 2;
  }
  return out;
}

function palettePick(typed, name) {
  const picks = palettePicks();
  const counts = { ...(picks[typed] || {}) };
  counts[name] = (counts[name] || 0) + 1;
  delete picks[typed];
  picks[typed] = counts;
  const keys = Object.keys(picks);
  for (const old of keys.slice(0, Math.max(0, keys.length - 80))) delete picks[old];
  prefs.setJSON("palette-picks", picks);
}

//: Why a row is where it is, in one line: the row's title, so the order can
//: be asked about with a hover rather than guessed.
const PALETTE_WHY = ["", "Its description has these words", "Another word for it matches", "Its name holds these words", "A word of its name starts with these letters"];
function paletteWhy({ score, picked, used }, typed) {
  const times = (n) => (n === 1 ? "once" : `${n} times`);
  const reason = picked ? `First because you chose it for \u201c${typed}\u201d ${times(picked)}` : PALETTE_WHY[score];
  return used ? `${reason}; used ${times(used)}.` : `${reason}.`;
}

//: **Nothing matched says why, and offers the nearest name** (row 3, CHAT_PLAN
//: decision 49). Measured before: a word one letter out ("calculater",
//: "remidner") left the handoff row alone, a list that reads as "this app
//: has no such thing" when it has. The nearest word of any row's name, its
//: other words or its aliases, within a letter in four.
function paletteNearest(rows, typed) {
  let best = null;
  const said = paletteWords(typed).filter((w) => w.length > 2);
  for (const row of rows) {
    const words = `${paletteText(row.label)} ${paletteText(row.keywords)} ${PALETTE_ALIASES[paletteTarget(row)] || ""}`
      .replace(/(^|\s)ph:[\w-]+/g, " ")
      .split(/[^a-z0-9]+/)
      .filter((w) => w.length > 2);
    for (const one of said) {
      for (const word of words) {
        const d = paletteDistance(one, word);
        if (d <= Math.max(1, Math.floor(one.length / 4)) && (!best || d < best.d)) best = { row, word, d };
      }
    }
  }
  return best;
}

//: Edits between two words (Levenshtein), 99 when the lengths alone rule a
//: near miss out.
function paletteDistance(a, b) {
  if (Math.abs(a.length - b.length) > 2) return 99;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const row = [i];
    for (let j = 1; j <= b.length; j++) {
      row[j] = Math.min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    prev = row;
  }
  return prev[b.length];
}

//: The nearest row, as a row of its own under "Nearest" that says why it is
//: there; none when nothing is close.
function paletteNearestRows(rows, typed) {
  const near = paletteNearest(rows, typed);
  if (!near) return [];
  const { text } = richPickerSplitLabel(near.row.label);
  return [{ ...near.row, group: "Nearest", about: `Nothing here is called “${typed}”; the nearest is ${text}.` }];
}

//: **Close in meaning** (Brief 94): with an embedding model on, up to three
//: rows nearest the words by meaning that the words did not reach, under
//: their own head. Asked once per query (`meaningNear`, meaning.js); the
//: answer redraws the open palette when it lands.
function paletteNearRows(pool, lowered, listed) {
  if (paletteGen.near?.q !== lowered) {
    if (paletteGen.nearAsked !== lowered) {
      paletteGen.nearAsked = lowered;
      meaningNear(lowered, pool.map((row) => `${richPickerSplitLabel(row.label).text}. ${row.about || ""}`)).then((picked) => {
        paletteGen.near = { q: lowered, rows: picked.map((i) => pool[i]).filter(Boolean) };
        if (picked.length) paletteRefresh();
      });
    }
    return [];
  }
  const shown = new Set(listed.map((row) => row.label));
  return paletteGen.near.rows
    .filter((row) => !shown.has(row.label))
    .slice(0, 3)
    .map((row) => ({ ...row, group: "Close in meaning", why: "Close in meaning to what you typed, by the search model." }));
}

//: Find anything's door into the same rows (search.js): its action rows, and
//: the nearest feature when nothing at all matched.
function paletteFind(query) {
  const lowered = query.trim().toLowerCase();
  return lowered ? paletteRanked(palettePool(paletteBase(lowered), lowered), lowered) : [];
}

function paletteNearestCommand(query) {
  const lowered = query.trim().toLowerCase();
  const near = lowered && paletteNearest(palettePool(paletteBase(lowered), lowered), lowered);
  return near ? near.row : null;
}

//: **The rich picker** (rich-picker.js, DESIGN.md's recipe index): the "/"
//: menu's rows, group headings and preview, so the palette and the block
//: menu are one object. The keyboard is unchanged: `paletteKeydown` moves
//: `paletteIndex` and redraws; the pointer lights the row it is over, so
//: Enter and a click always mean the same row.
function renderPalette(query) {
  const list = $("palette-list");
  const matches = paletteMatches(query);
  const needle = query.trim().toLowerCase();
  const abouts = paletteAbouts();
  paletteIndex = Math.min(paletteIndex, Math.max(0, matches.length - 1));
  list.replaceChildren();
  let lastGroup = null;
  const rows = [];
  matches.forEach((match, index) => {
    // A heading whenever the group changes; not an option, so the keys skip it.
    if (match.group && match.group !== lastGroup) {
      list.appendChild(richPickerGroup(match.group, { className: "palette-group-header" }));
      lastGroup = match.group;
    }
    const parts = paletteRowParts(match, abouts);
    const row = richPickerRow({
      ...parts,
      //: The letters marked only where the label is what matched: a note
      //: found by its body would otherwise light letters scattered over a
      //: title that never contained the query.
      query: needle && parts.label.toLowerCase().includes(needle) ? needle : "",
      id: `palette-row-${index}`,
    });
    if (match.why) row.title = match.why;
    row.addEventListener("click", () => paletteRun(match));
    row.addEventListener("mousemove", () => {
      if (paletteIndex === index) return;
      paletteIndex = index;
      paletteLight(rows, matches, abouts);
    });
    list.appendChild(row);
    rows.push(row);
  });
  if (!matches.length) {
    const li = document.createElement("li");
    li.className = "muted palette-empty";
    li.textContent = "Run a command or go to a place. Type to see matches.";
    list.appendChild(li);
  }
  paletteLight(rows, matches, abouts);
}

//: Light the chosen row, tell the input which it is (the input keeps the
//: focus, so it carries `aria-activedescendant`), and show the row in the
//: pane beside the list: what it does and its key.
//: The pane hides itself below 44rem (the stylesheet).
function paletteLight(rows, matches, abouts) {
  const lit = richPickerSetActive($("palette-list"), rows, paletteIndex);
  const input = $("palette-input");
  if (lit) input.setAttribute("aria-activedescendant", lit.id);
  else input.removeAttribute("aria-activedescendant");
  const pane = $("palette-preview");
  const match = matches[paletteIndex];
  pane.classList.toggle("hidden", !match);
  if (!match) return;
  const parts = paletteRowParts(match, abouts);
  richPickerPreview(pane, {
    ...parts,
    keys: parts.keys.replace(/^M (\w)$/, "M then $1"),
    keysLead: "Press",
    keysTail: "to do it without the palette.",
  });
}

function paletteKeydown(event) {
  const matches = paletteMatches($("palette-input").value);
  if (event.key === "Escape") closePalette();
  else if (event.key === "ArrowDown") {
    event.preventDefault();
    paletteIndex = Math.min(paletteIndex + 1, matches.length - 1);
    renderPalette($("palette-input").value);
    scrollPaletteToActive();
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    paletteIndex = Math.max(paletteIndex - 1, 0);
    renderPalette($("palette-input").value);
    scrollPaletteToActive();
  } else if (event.key === "Enter" && matches[paletteIndex]) {
    //: The row may focus an editor (New note), and the Enter went on into
    //: it: measured, every note started from here began with a blank line.
    event.preventDefault();
    paletteRun(matches[paletteIndex]);
  }
}

// Reported live: arrowing past the visible rows left the selection off
// screen: nothing followed it. `renderPalette` rebuilds the list from
// scratch on every keypress (replaceChildren), so there is no focused or
// otherwise browser-tracked element for the browser's own native
// scroll-on-focus to follow; `.active` is a plain CSS class on an
// unfocused `<li>`, invisible to that mechanism entirely.
function scrollPaletteToActive() {
  $("palette-list").querySelector(".active")?.scrollIntoView({ block: "nearest" });
}

// Wired here, not at boot: see the header.
$("palette-input").addEventListener("input", () => {
  paletteIndex = 0;
  renderPalette($("palette-input").value);
});
$("palette-input").addEventListener("keydown", paletteKeydown);
wireBackdropClose($("palette-overlay"), () => closePalette());

// ---- from palette.js (search-boot-1005): notesPaletteCommands ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

function notesPaletteCommands(query = "") {
  const rows = [];
  const ids = paletteNotesInHand();
  if (ids.length) {
    const one = ids.length === 1 ? allEntries.find((e) => e.id === ids[0]) : null;
    rows.push({
      group: "This note",
      label: `ph:folder-open Move ${one ? "note" : "notes"} to category`,
      about: one ? `Now in ${one.category}.` : `${ids.length} selected notes.`,
      run: paletteLater(() => chooseNoteCategory(ids, one?.category || "")),
    });
    rows.push({
      group: "This note",
      label: `ph:tag Add or remove tags on ${one ? "this note" : "these notes"}`,
      about: one ? `${one.tags.length ? one.tags.map((t) => `#${t}`).join(" ") : "No tags yet."}` : `${ids.length} selected notes.`,
      run: paletteLater(() => openBulkTags(ids)),
    });
  }
  //: Tidy (INBOX 691): the reviews, and two of them by name.
  rows.push({
    group: "Notes",
    label: "ph:broom Tidy notes, links and tags",
    about: "Weak links, stray tags, notes without a category, duplicates, old reminders. No AI needed.",
    run: paletteLater(() => openTidySheet()),
  });
  rows.push({
    group: "Notes",
    label: "ph:link Name link reasons",
    about: "Say what two linked notes share instead of “similar in meaning”.",
    run: paletteLater(() => openTidySheet("link-reasons")),
  });
  rows.push({
    group: "Notes",
    label: "ph:copy-simple Find duplicate notes",
    about: "Notes that say much the same thing, merged into one.",
    run: paletteLater(() => openTidySheet("duplicates")),
  });
  rows.push({
    group: "Tags",
    label: "ph:hash Manage tags",
    about: "Rename, merge or remove tags across every note.",
    run: paletteLater(() => openTagsSheet()),
  });
  rows.push({
    group: "Categories",
    label: "ph:sliders-horizontal Manage categories",
    about: "Rename, merge, split or delete categories.",
    run: paletteLater(() => openManageCategories()),
  });
  if (!query) return rows;
  const counts = new Map();
  for (const e of allEntries) if (!e.is_draft) counts.set(e.category, (counts.get(e.category) || 0) + 1);
  for (const [name, n] of [...counts].sort((a, b) => a[0].localeCompare(b[0]))) {
    rows.push({
      group: "Categories",
      label: `ph:folder Go to category: ${name}`,
      about: `${n} ${n === 1 ? "note" : "notes"}`,
      run: paletteLater(() => paletteGoToCategory(name)),
    });
  }
  if (query.startsWith("#")) {
    const typed = query.slice(1).trim();
    const tags = [...new Set(allEntries.flatMap((e) => e.tags || []))]
      .filter((t) => !/\s/.test(t) && t.toLowerCase().startsWith(typed))
      .sort()
      .slice(0, 6);
    if (typed && !/\s/.test(typed) && !tags.some((t) => t.toLowerCase() === typed)) tags.push(typed);
    for (const tag of tags) {
      rows.push({ group: "Tags", label: `ph:tag Show notes tagged #${tag}`, run: paletteLater(() => filterNotesByTag(tag)) });
    }
  }
  return rows;
}

//: The note the palette was opened over: the phone's note page, the inline
//: edit, the batch selection, or the row that had the focus.
function paletteNotesInHand() {
  if (selectMode && selectedIds.size) return [...selectedIds];
  const row = overlayReturnFocus?.closest?.("#entry-list li[data-id]");
  const id = notePageOpenId || editingId || Number(row?.dataset.id);
  return id ? [Number(id)] : [];
}

//: The sidebar's own row is pressed, so the filter is the one a tap on it
//: sets (and on a phone the drawer stays shut). The last match, since "All"
//: comes first and a category may share its name.
async function paletteGoToCategory(name) {
  await switchTab("notes");
  const rows = [...$("category-list").children].filter((li) => li.querySelector(".category-name")?.title === name);
  rows.pop()?.click();
}
