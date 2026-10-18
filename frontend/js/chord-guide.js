// chord-guide.js: the panel the "m" chord opens (every key it waits for, as a
// button), built on first use. Moved out of settings-wiring.js on 2026-10-05
// (search-boot-1005, the boot-script gzip budget in
// tests/test_static_compression.py and tests/test_boot_budget.py): it draws
// only after the first `m`, none of it is needed for the first screen.
// Loaded by `LAZY_MODULES.chordGuide` (app.js), whose stand-in for
// `showTabJumpHint` fetches this file and then calls the real one.
//
// **What stayed at boot.** The chord itself (`tabJumpArmedAt`, `TAB_JUMP_KEYS`,
// `CHORD_ACTIONS`, the keydown branch), `hideChordGuide` and
// `closeOverlaysForChord`: the keys work with the guide never drawn, and
// Escape or a second `m` hides it with no file loaded.
//
// **The race a lazy guide adds, and its two answers.** A stand-in returns a
// promise, so the guide would appear a moment after the first `m`, and a fast
// second key (`m` then `g`) could resolve the chord first and leave a guide
// nobody is waiting for stuck on screen. (1) app.js fetches this file three
// seconds after boot (`quickNote`'s own preload), so by the first `m` it is
// almost always in and the call is synchronous. (2) `showTabJumpHint` draws
// only while the chord is still armed, so a late load after the second key
// draws nothing.

function chordGuideEl() {
  let guide = document.getElementById("chord-guide");
  if (!guide) {
    guide = document.createElement("div");
    guide.id = "chord-guide";
    guide.className = "chord-guide hidden";
    guide.setAttribute("role", "status");
    guide.setAttribute("aria-live", "polite");
    document.body.appendChild(guide);
  }
  return guide;
}

//: `entries` is `[key, label, run, icon, here]`. The `run` comes from the same
//: two tables the keyboard reads (`TAB_JUMP_KEYS`, `CHORD_ACTIONS`), so a row
//: and its key are two doors onto one action rather than two copies of one.
//: **The rich picker's row** (INBOX 484, the owner: "more professional, more
//: modern and more impressive"): the icon tile, the name, and the key in the
//: keycap column at the right edge, the "/" menu's own anatomy, as buttons
//: because a pointer can pick one too.
function chordGuideGroup(title, entries) {
  const group = document.createElement("section");
  group.className = "chord-guide-group";
  const heading = document.createElement("h3");
  heading.className = "chord-guide-title";
  heading.textContent = title;
  const list = document.createElement("div");
  list.className = "chord-guide-list rich-picker-list";
  for (const [key, label, run, icon, here] of entries) {
    const row = richPickerRow({ tag: "button", role: null, icon, label, keys: key, className: "chord-guide-row" });
    row.title = `${label} (t then ${key})`;
    //: The tab you are on is marked, so "Go to" also says where you are.
    if (here) {
      row.classList.add("is-here");
      row.setAttribute("aria-current", "page");
    }
    row.addEventListener("click", () => {
      //: Disarmed first: the chord has been answered, and leaving it armed
      //: would make the next letter you type navigate somewhere.
      tabJumpArmedAt = 0;
      hideChordGuide();
      //: The keyboard branch's two lines, in its order: leave whatever is over
      //: the page, or the destination lands behind a modal holding focus.
      closeOverlaysForChord();
      run();
    });
    list.appendChild(row);
  }
  group.append(heading, list);
  return group;
}

//: A key drawn as a key, for the head and the hint line.
function chordGuideKey(text) {
  const kbd = document.createElement("kbd");
  kbd.className = "chord-guide-key";
  kbd.textContent = text;
  return kbd;
}

function showTabJumpHint() {
  //: Still armed: see the header, the second answer to the race.
  if (!tabJumpArmedAt) return;
  const guide = chordGuideEl();
  //: **The head: what the app is waiting for, and the way out** (the dialog
  //: head's shape: the title, then the Close at the right). It is a mode, not
  //: a menu, so it says so: "m" is down, the next key decides.
  const head = document.createElement("div");
  head.className = "chord-guide-head";
  const title = document.createElement("p");
  title.className = "chord-guide-lead";
  const words = document.createElement("span");
  words.textContent = "then a key";
  title.append(chordGuideKey("t"), words);
  //: Asked for directly: "press m again to close it or an x close button".
  //: In the head now rather than the window's corner, beside what it closes.
  const close = document.createElement("button");
  close.type = "button";
  close.className = "icon-only ghost small dialog-head-btn chord-guide-close";
  close.title = "Close (Esc)";
  close.setAttribute("aria-label", "Close");
  setLabel(close, "ph:x");
  close.addEventListener("click", () => {
    tabJumpArmedAt = 0;
    hideChordGuide();
  });
  head.append(title, close);
  //: The hint line: the three ways out of the mode, said once at the foot.
  const hint = document.createElement("p");
  hint.className = "chord-guide-hint";
  hint.append("Press a key or pick a row. ", chordGuideKey("t"), " or ", chordGuideKey("Esc"), " closes.");
  //: **One panel on the popover shell** (the owner's screenshot, 2026-09-23:
  //: pills drawn straight over the dashboard's text read through it). The
  //: tab's icon is read off its own button in the tab bar, so the two cannot
  //: disagree.
  const tabIcon = (tab) => {
    const glyph = document.querySelector(`#tab-btn-${tab} i.ph`);
    const name = glyph && [...glyph.classList].find((c) => c.startsWith("ph-"));
    return name ? `ph:${name.slice(3)}` : "ph:arrow-right";
  };
  const current = document.querySelector('[role="tab"][data-tab].active')?.dataset.tab;
  const panel = document.createElement("div");
  panel.className = "chord-guide-panel";
  panel.setAttribute("role", "group");
  panel.setAttribute("aria-label", "t, then a key");
  const body = document.createElement("div");
  body.className = "chord-guide-body";
  body.append(
    chordGuideGroup(
      "Go to",
      Object.entries(TAB_JUMP_KEYS).map(([key, tab]) => [
        key,
        tab[0].toUpperCase() + tab.slice(1),
        () => switchTab(tab),
        tabIcon(tab),
        tab === current,
      ]).concat(
        Object.entries(CHORD_ACTIONS)
          .filter(([, action]) => action.group === "go")
          .map(([key, action]) => [key, action.label, action.run, action.icon])
      )
    ),
    chordGuideGroup(
      "Do",
      Object.entries(CHORD_ACTIONS)
        .filter(([, action]) => action.group !== "go")
        .map(([key, action]) => [key, action.label, action.run, action.icon])
    )
  );
  panel.append(head, body, hint);
  guide.replaceChildren(panel);
  guide.classList.remove("hidden");
}
