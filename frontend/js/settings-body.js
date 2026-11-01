// settings-body.js: Settings' body is built when it is first needed, not at
// every boot (INBOX 1501, audit PF9 row 54).
//
// `#settings-body-template` in index.html holds the sections (2,700 nodes, 20
// panes, every control's id). The page never draws them until the window opens,
// yet they cost the parse, the memory and a share of every style pass on the
// shell (the Ctrl +/- zoom frame was a relayout of them). So they sit in an inert
// `<template>`, and `settingsBodyBuild` puts them in the page:
//
//   - `openSettingsModal` calls it first (the one place the window opens);
//   - `$` (app.js) calls it when it is asked for an id that lives in the
//     template, so a caller that reaches a control early still gets the control,
//     never null (a control read before it is built reads its saved state, as
//     before, because the build is the whole body at once);
//   - `onSettingsBody(run)` runs a paint that needs the controls once they exist.
//
// A boot script that needs a control must not ask for it (that would build the
// body at boot): the listeners of every control are in settings-controls.js,
// which loads with the first open, and a paint that has to happen at build is
// an `onSettingsBody`. `tests/test_settings_body_1501.py` holds that line.
// Load order: before app.js, so `$` may call these from its first line on.
const SETTINGS_BODY = { tpl: document.getElementById("settings-body-template"), after: [] };

//: Puts the body in the page, once; false when it already is.
function settingsBodyBuild() {
  const { tpl } = SETTINGS_BODY;
  if (!tpl) return false;
  SETTINGS_BODY.tpl = null;
  const host = tpl.parentNode;
  tpl.replaceWith(tpl.content);
  // The sweeps the page ran over every control at boot, now over the ones that
  // just arrived: help popovers (with their Atlas line), and the chord on a
  // button's tooltip.
  window.initHelpToggles?.(host);
  for (const run of SETTINGS_BODY.after.splice(0)) run();
  return true;
}

//: What `$` asks when `getElementById` found nothing: the control, built on demand.
function settingsBodyFind(id) {
  return SETTINGS_BODY.tpl?.content.getElementById(id) && settingsBodyBuild() ? document.getElementById(id) : null;
}

//: Runs `run` now when the body is built, else the moment it is.
function onSettingsBody(run) {
  if (SETTINGS_BODY.tpl) SETTINGS_BODY.after.push(run);
  else run();
}
