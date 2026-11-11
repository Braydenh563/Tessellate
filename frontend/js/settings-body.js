// settings-body.js: surfaces the page shows only on request are built when
// they are first needed, not at every boot (INBOX 1501, audit PF9 row 54;
// audit 1031 row 21 for the surfaces after Settings).
//
// A `<template data-surface="NAME">` in index.html holds one surface's markup
// (Settings' body: 2,700 nodes, 20 panes, every control's id; the board canvas:
// 1,740). The page never draws them until they open, yet in the page they cost
// the parse into the live tree, the memory and a share of every style pass and
// every selector sweep. So they sit inert, inside their live root, and
// `surfaceBuild(name)` puts them in the page:
//
//   - the one place a surface opens calls it first (`openSettingsModal`,
//     `wbShowCanvasView` and `initWhiteboard`);
//   - `$` (app.js) calls `surfaceFind` when it is asked for an id that lives in
//     a template, so a caller that reaches an element early still gets it,
//     never null (a control read before it is built reads its saved state, as
//     before, because the build is the whole surface at once);
//   - `onSurface(name, run)` runs wiring that needs the elements once they exist.
//
// A script that runs at load must not ask for an element of a surface (that
// would build it at boot): its listeners are wired from `onSurface`.
// `tests/test_settings_body_1501.py` and `tests/test_surface_templates.py` hold
// that line. Load order: before app.js, so `$` may call these from its first line on.
//: name -> { tpl, after }: the templates are parsed before this script runs (it loads at the end of the body).
const SURFACES = new Map([...document.querySelectorAll("template[data-surface]")].map((tpl) => [tpl.dataset.surface, { tpl, after: [] }]));

//: Puts the surface in the page, once; false when it already is (or no such surface).
function surfaceBuild(name) {
  const entry = SURFACES.get(name);
  if (!entry?.tpl) return false;
  const { tpl } = entry;
  entry.tpl = null;
  const host = tpl.parentNode;
  tpl.replaceWith(tpl.content);
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
function surfaceFind(id) {
  for (const [name, entry] of SURFACES) {
    if (entry.tpl?.content.getElementById(id) && surfaceBuild(name)) return document.getElementById(id);
  }
  return null;
}

//: Runs `run` now when the surface is built, else the moment it is.
function onSurface(name, run) {
  const entry = SURFACES.get(name);
  if (entry?.tpl) entry.after.push(run);
  else run();
}
