// settings-body.js: surfaces the page shows only on request are built when
// they are first needed, not at every boot (INBOX 1501, audit PF9 row 54;
// audit 1031 row 21 for the surfaces after Settings).
//
// A `<script type="text/x-surface" data-surface="NAME">` in index.html holds one
// surface's markup as raw text (Settings' body: 2,700 nodes, 20 panes, every
// control's id; the board canvas: 1,740). The page never draws them until they
// open, yet in the page they cost the parse into the live tree, the memory and
// a share of every style pass and every selector sweep. So they sit inert,
// inside their live root, and
// `surfaceBuild(name)` puts them in the page:
//
//   - the one place a surface opens calls it first (`openSettingsModal`,
//     `wbShowCanvasView` and `initWhiteboard`);
//   - `$` (app.js) calls `surfaceFind` when it is asked for an id that lives in
//     a surface, so a caller that reaches an element early still gets it,
//     never null (a control read before it is built reads its saved state, as
//     before, because the build is the whole surface at once);
//   - `onSurface(name, run)` runs wiring that needs the elements once they exist.
//
// A script that runs at load must not ask for an element of a surface (that
// would build it at boot): its listeners are wired from `onSurface`.
// `tests/test_settings_body_1501.py` and `tests/test_surface_templates.py` hold
// that line. Load order: before app.js, so `$` may call these from its first line on.
//: name -> { tpl, frag, after, parent, done }. `tpl` holds the markup until the surface is built: a
//: `<script type="text/x-surface">` (raw text, so the parser makes no nodes for it at boot: 4x CPU, the
//: dashboard's first frame lost 150 to 350 ms parsing 693 KB of `<template>` content it never drew) or the
//: `<template>` of a surface nested in another (the board inside the Library). `frag` is its parsed
//: fragment, made once, at the first read or at the build. A nested surface is registered up front
//: from its parent's `data-nests`, with no `tpl` until the parent is parsed, and has its `parent` built first.
//: The helpers are methods on the map, not globals of their own: the shared scope has a name cap
//: (tests/test_global_scope_ratchet.py), and only the four names the page calls are worth a place in it.
const SURFACES = Object.assign(new Map(), {
  register(root, parent) {
    for (const tpl of root.querySelectorAll?.("script[data-surface], template[data-surface]") ?? []) {
      const name = tpl.dataset.surface;
      //: `data-in`: a surface kept outside its parent's text (a script cannot hold a script) and moved
      //: into the parent's `<template data-surface-slot>` when the parent is built (Settings' body).
      const entry = SURFACES.get(name) ?? { after: [], parent: parent ?? tpl.dataset.in, done: false };
      entry.tpl = tpl;
      SURFACES.set(name, entry);
      for (const nested of (tpl.dataset.nests ?? "").split(" ")) {
        if (nested) SURFACES.set(nested, { tpl: null, after: [], parent: name, done: false });
      }
    }
  },

  //: The surface's markup as a fragment, parsed once (a script's text is parsed here, on the first need).
  fragment(name, entry) {
    if (!entry.frag && entry.tpl) {
      if (entry.tpl.content) entry.frag = entry.tpl.content;
      else if (SURFACES.splitMark(entry)) {
        SURFACES.parseNext(entry, Infinity);
        entry.frag = entry.partial;
      } else {
        const holder = document.createElement("template");
        holder.innerHTML = entry.tpl.text;
        entry.frag = holder.content;
      }
      SURFACES.register(entry.frag, name);
    }
    return entry.frag;
  },

  //: **A big surface parsed in pieces** (`data-split-at` on its script: each such mark starts a piece, and each
  //: mark is a place the parser is at the top of the body, so the pieces join to what one parse makes). Settings'
  //: whole text in one `innerHTML` was a 56 ms task at 4x CPU (L-world-class-361); a piece is one pane. Parses
  //: pieces until `budget` ms are spent; true once none are left.
  //: Where a surface's text is cut for `parseNext`: each mark is a place the parser is at the top of the body.
  splitMark: (entry) => ({ settings: '<section class="settings-section' })[entry.tpl.dataset?.surface],

  parseNext(entry, budget) {
    const mark = SURFACES.splitMark(entry);
    entry.pieces ||= entry.tpl.text.split(mark).map((piece, i) => (i ? mark + piece : piece));
    entry.partial ||= document.createDocumentFragment();
    const start = performance.now();
    const holder = document.createElement("template");
    while (entry.pieces.length && performance.now() - start < budget) {
      holder.innerHTML = entry.pieces.shift();
      entry.partial.append(holder.content);
    }
    return !entry.pieces.length;
  },

  //: Whether the unbuilt surface holds the id: its parsed fragment when it has one, else the ids named in
  //: its raw text, listed once (a pass over 700 KB at the first miss, then a lookup).
  holds(name, entry, id) {
    if (entry.frag || entry.tpl.content) return !!SURFACES.fragment(name, entry).getElementById(id);
    entry.ids ??= new Set(Array.from(entry.tpl.text.matchAll(/\sid="([^"]+)"/g), (m) => m[1]));
    return entry.ids.has(id);
  },

  //: An element out of a surface's markup, built or not, for a caller that copies one and has no need of the
  //: surface itself (the dashboard's capture card copies the Notes bar's row). Null when there is none.
  peek(name, id) {
    const entry = SURFACES.get(name);
    const live = document.getElementById(id);
    if (live || !entry || entry.done || !entry.tpl) return live;
    return SURFACES.fragment(name, entry).getElementById(id);
  },

  //: **Parse ahead, in idle time.** Keeping a surface as text moved its parse from the boot to its first open: at 4x
  //: CPU the Settings gear took 428 ms to paint, and 567 ms once the body was text. So one surface at a time is
  //: parsed (not put in the page) in an idle slot a few seconds after load, Settings first, and a later open
  //: only moves the ready fragment in. A surface opened before its turn simply parses then, as before.
  warm() {
    const waiting = [...SURFACES].filter(([, entry]) => entry.tpl && !entry.frag && !entry.done && !entry.tpl.content);
    //: Notes before Settings (L603): the Notes press is the first interaction, and parsing
    //: its surface inside the press was 41 to 105ms of a 55 to 124ms click at 5,000 notes.
    const next = waiting.find(([name]) => name === "notes") ?? waiting.find(([name]) => name === "settings") ?? waiting[0];
    if (!next) return;
    //: A split surface is parsed a few ms at a time with the next slot soon; a whole one in this slot.
    if (SURFACES.splitMark(next[1]) && !SURFACES.parseNext(next[1], 8)) return SURFACES.warmLater(30);
    SURFACES.fragment(next[0], next[1]);
    SURFACES.warmLater(1000);
  },
  //: A listener for a control of an unbuilt surface, added when that surface is built instead of building it
  //: now (L675: each `$` in settings-controls.js built all of Settings). Nested surfaces are asked first.
  wire(id, ...args) {
    const live = document.getElementById(id);
    const hit = !live && SURFACES.owner(id);
    if (hit) onSurface(hit, () => SURFACES.wire(id, ...args));
    else live?.addEventListener(...args);
  },
  //: The unbuilt surface holding the id, nested ones first (their parent's text holds the same ids), or undefined.
  owner(id) {
    return [...SURFACES].sort(([, a]) => (a.parent ? -1 : 0)).find(([name, entry]) => !entry.done && entry.tpl && SURFACES.holds(name, entry, id))?.[0];
  },
  //: `apply(element)` now when the control is in the page, else the moment its surface is built, with the last
  //: `apply` asked for that id. A read of /preferences fills the controls of four panes; each used to build
  //: the others (visiting Personas built five more panes, 5 to 20 ms each at 4x CPU, L675).
  fill(id, apply) {
    const live = document.getElementById(id);
    if (live) return apply(live);
    const name = SURFACES.owner(id);
    if (!name) return;
    const entry = SURFACES.get(name);
    (entry.fills ||= new Map()).set(id, apply);
    entry.flush ||= () => {
      entry.fills.forEach((run, key) => run(document.getElementById(key)));
      entry.fills.clear();
    };
    onSurface(name, entry.flush);
  },
  //: A built surface's nodes moved into a fragment, listeners and typed state with them, for the next
  //: build to move back (L676: a closed Settings kept up to 12,000 elements in the page).
  park(name) {
    const entry = SURFACES.get(name);
    const host = document.getElementById(name);
    if (!entry?.done || !host) return;
    const frag = document.createDocumentFragment();
    frag.append(...host.childNodes);
    host.append((entry.tpl = document.createElement("template")));
    Object.assign(entry, { frag, done: false });
  },
  warmLater(delay) {
    const go = () => SURFACES.warm();
    setTimeout(() => (window.requestIdleCallback ? window.requestIdleCallback(go, { timeout: 6000 }) : go()), delay);
  },
});
SURFACES.register(document);
SURFACES.warmLater(3000);

//: Puts the surface in the page, once; false when it already is (or no such surface).
function surfaceBuild(name) {
  const entry = SURFACES.get(name);
  if (!entry || entry.done) return false;
  if (entry.parent) surfaceBuild(entry.parent);
  if (!entry.tpl) return false;
  const frag = SURFACES.fragment(name, entry);
  const { tpl } = entry;
  entry.done = true;
  entry.tpl = entry.frag = null;
  const host = tpl.parentNode;
  tpl.replaceWith(frag);
  for (const slot of host.querySelectorAll?.("template[data-surface-slot]") ?? []) slot.replaceWith(SURFACES.get(slot.dataset.surfaceSlot).tpl);
  // The sweeps the page ran over every element at boot, now over the ones that
  // just arrived: help popovers, closed dock-menu lists, tooltip chords.
  window.initHelpToggles?.(host);
  window.hideClosedDockMenuLists?.(host);
  window.localizeStaticChords?.(host);
  window.stampShortcutTitles?.(host);
  for (const run of entry.after.splice(0)) try { run(); } catch (error) { console.error(error); }
  return true;
}

//: What `$` asks when `getElementById` found nothing: the element, its surface built on demand.
//: A nested surface's ids are in its parent's text too, so the parent is built first and the walk goes on
//: to the nested entry that building registered.
function surfaceFind(id) {
  for (const [name, entry] of SURFACES) {
    if (entry.done || !entry.tpl || !SURFACES.holds(name, entry, id)) continue;
    if (surfaceBuild(name)) {
      const found = document.getElementById(id);
      if (found) return found;
    }
  }
  return null;
}

//: Runs `run` now when the surface is built, else the moment it is; queued once however often it is asked.
function onSurface(name, run) {
  const entry = SURFACES.get(name);
  if (entry && !entry.done) entry.after.includes(run) || entry.after.push(run);
  else run();
}
