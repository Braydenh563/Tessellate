// desk-companion.js: the desktop companion's window (desktop-companion.html;
// core/desk_companion.py makes the window, this is the page in it).
//
// The chosen companion, drawn by the app's own files, in a small frameless
// window at the screen's corner while the app window is in the tray. A click
// opens a menu (Quick note, Quick search, Open Tessellate), a right-click
// another (Settings, Hide), and a drag moves the window. Quick note and Quick
// search are panels in this same window; the window is asked to grow for
// them and to shrink back (SIZES), always about its bottom-right corner.
//
// **Locked means the companion and Open only.** The page asks the notebook
// whether it is open (`GET /preferences` with the app's own token) every time a
// menu or panel is about to show, and on any refusal, or when the server cannot
// be reached, it draws no note, no search box and no result: the same 401 that
// guards every note route is the real gate, this is only what the page says.
// What the page asks of its window goes through pywebview's `js_api`
// (`window.pywebview.api`), never an HTTP route.

(() => {
  const $ = (id) => document.getElementById(id);

  //: The window's sizes, in the units pywebview takes: [width, height].
  const SIZES = {
    rest: [112, 152],
    menu: [248, 312],
    context: [248, 268],
    note: [320, 500],
    search: [340, 440],
  };
  const PANELS = { menu: "desk-menu", context: "desk-menu", note: "desk-note", search: "desk-search" };
  let state = "rest";
  let locked = true;
  let seedShown = "";

  const card = new URLSearchParams(location.search).has("card");
  document.body.classList.toggle("desk-card", card);
  //: The overlay's quick panel (core/overlay): the figure walks the desktop on its
  //: own, so this window is only the menu and panels, beside it; no pet here, and
  //: the pet's 152 and its gap come off every size.
  const overlay = new URLSearchParams(location.search).has("overlay");
  document.body.classList.toggle("desk-overlay", overlay);
  const OVERLAY_TRIM = 160;

  //: What the app's window saved in this browser's storage (the window shares it).
  const token = () => prefs.get("token", "");

  //: The window's one kind of request: signed in, in the space open in the app.
  const call = (path, method = "GET", body = null) => {
    const form = body instanceof FormData;  // a file: the browser sets the multipart type itself
    return fetch(path, {
      method,
      headers: { ...(form ? {} : { "Content-Type": "application/json" }), "X-Auth-Token": token(), "X-Workspace-ID": prefs.get("spaceId", "") || "all" },
      ...(body ? { body: form ? body : JSON.stringify(body) } : {}),
    });
  };

  const host = () => window.pywebview?.api || null;
  const ask = (name, ...args) => {
    const api = host();
    return api && typeof api[name] === "function" ? api[name](...args) : Promise.resolve(null);
  };

  // --- who it is -----------------------------------------------------------
  //: The companion Appearance chose, as `nameMarkBuddySeed` reads it, without the
  //: chat window's persona picker, which this page has no copy of: "the chat's
  //: persona" is the greeting's, else Atlas. Nobody chosen draws Atlas, the app's
  //: own guide: the person turned this on, so something should be there.
  function seed() {
    const choice = prefs.get("avatar-buddy", "off");
    if (choice === "me") return (prefsCache.display_name || "").trim() || "You";
    if (choice === "persona") return prefsCache.dashboard_persona || "Atlas";
    if (choice === "custom") return nameMarkBuddyCustom().name;
    return "Atlas";
  }

  function draw() {
    const name = seed();
    //: The key holds the parts you chose as well as the name: the same name with a changed look is a new
    //: drawing (INBOX 1692 k: the card kept the bare name's figure after the profile's look was saved).
    const key = `${name}|${JSON.stringify(nameMarkOwnFor(name) || {})}`;
    if (key === seedShown) return;
    seedShown = key;
    $("desk-figure").replaceChildren(characterFor(name).figure());
    $("desk-pet").setAttribute("aria-label", `${name}, your companion. Click for the menu, right-click for settings, drag to move it.`);
  }

  // --- locked or open ----------------------------------------------------------
  //: Asks the notebook, and reads the two settings the faces use while at it.
  async function probe() {
    try {
      const response = await call("/preferences");
      locked = !response.ok;
      if (response.ok) {
        const body = await response.json();
        window.prefsCache = { display_name: body.display_name, avatar_style: body.avatar_style, dashboard_persona: body.dashboard_persona };
      }
    } catch {
      locked = true;
    }
    document.body.dataset.locked = locked ? "1" : "0";
    draw();
    return !locked;
  }

  // --- the window ----------------------------------------------------------------
  function show(next) {
    //: Pictures and files staged in the note card go with it when the panel is left (capture-stage.js).
    if (state === "note" && next !== "note") window.discardCaptureStage?.();
    state = next;
    document.body.dataset.state = next;
    document.body.dataset.size = SIZES[next].join("x");
    for (const id of new Set(Object.values(PANELS))) $(id).classList.toggle("hidden", PANELS[next] !== id);
    $("desk-pet").setAttribute("aria-expanded", String(next === "menu" || next === "context"));
    if (overlay && next === "rest") return;
    asked = 0;
    fit();
  }

  //: The overlay's window is as tall as the open panel's content, every panel, not
  //: the menu alone: a fixed 216 squashed Quick note's field to one line, and a fixed
  //: 280 left a band above Quick search (INBOX 1670). Asked again when the width
  //: changes the wrapping and when search hits arrive; only a change is asked.
  let asked = 0;
  function fit() {
    if (state === "rest") return;
    let height = SIZES[state][1] - (overlay ? OVERLAY_TRIM : 0);
    if (overlay) height = panelHeight($(PANELS[state]), height, state);
    else if (state === "menu" || state === "context") height = cardHeight(height, state);
    if (Math.abs(height - asked) <= 2) return;
    asked = height;
    ask("set_size", SIZES[state][0], height, state);
  }
  window.addEventListener("resize", () => {
    if (overlay) fit();
  });

  //: A panel's own height in CSS pixels: its children's extent plus its padding and
  //: border, plus the page's padding round it, so a two or three row menu never shows
  //: a scrollbar at any Windows scale (the owner, 2026-11-04: the fixed 108 was too
  //: small for two rows). Measured from the children, not the panel, because the
  //: panel fills the window (no band above it). `fallback` is used only when the
  //: page has no layout to measure.
  function panelHeight(panel, fallback, kind) {
    const root = panel.parentElement;
    const kids = [...panel.children].filter((k) => k.getClientRects().length && getComputedStyle(k).position !== "absolute");
    if (!kids.length || !root) return fallback;
    const top = Math.min(...kids.map((k) => k.getBoundingClientRect().top));
    const bottom = Math.max(...kids.map((k) => k.getBoundingClientRect().bottom));
    if (!(bottom > top)) return fallback;
    const ps = getComputedStyle(panel);
    const rs = getComputedStyle(root);
    const edge = ["paddingTop", "paddingBottom", "borderTopWidth", "borderBottomWidth"].reduce((sum, k) => sum + (parseFloat(ps[k]) || 0), 0);
    const wanted = Math.ceil(bottom - top + edge + (parseFloat(rs.paddingTop) || 0) + (parseFloat(rs.paddingBottom) || 0));
    // Capped to the screen (search to a compact column); the panel scrolls inside past it.
    const most = Math.floor((window.screen.availHeight || wanted) * 0.9);
    return Math.min(wanted, kind === "search" ? Math.min(most, SEARCH_MOST) : most);
  }
  const SEARCH_MOST = 520;

  //: The card window (macOS, and Windows when the see-through figure fails) holds the menu
  //: above the companion, so its height is the menu's own plus the companion's box and the gap:
  //: the fixed 312 and 268 left the six-row menu scrolling 95 px and the context 24 px (Q34
  //: sweep, 2026-11-11). A locked menu (Open only) gets a shorter window the same way.
  function cardHeight(fallback, kind) {
    const pet = $("desk-pet").getBoundingClientRect().height;
    const gap = parseFloat(getComputedStyle($("desk-pet").parentElement).rowGap) || 0;
    if (!(pet > 0)) return fallback;
    return Math.ceil(panelHeight($(PANELS[kind]), fallback - pet - gap, kind) + pet + gap);
  }

  //: Why the figure stands still, for the right-click menu's one muted line.
  const STILL_WHY = {
    os: "Windows animation effects are off",
    app: "Motion is Off in Appearance",
    setting: "Companion movement is Fades only",
    avatar: "Avatar animation is off",
  };

  function item(label, icon, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "menu-item desk-item";
    button.setAttribute("role", "menuitem");
    const mark = document.createElement("i");
    mark.className = `ph ph-${icon}`;
    mark.setAttribute("aria-hidden", "true");
    button.append(mark, document.createTextNode(label));
    button.addEventListener("click", onClick);
    return button;
  }

  //: A hairline between two groups of rows (the menu recipe's `.menu-sep`).
  const separator = () => {
    const rule = document.createElement("hr");
    rule.className = "menu-sep";
    rule.setAttribute("role", "separator");
    return rule;
  };
  const note = (text) => {
    const p = document.createElement("p");
    p.className = "muted desk-note";
    p.textContent = text;
    return p;
  };
  //: Asks the walking figure for something; the menu closes either way.
  const figure = (label, icon, name, motion) => {
    const row = item(label, icon, () => leave(() => ask("figure_do", name)));
    if (motion?.still) {
      row.disabled = true;
      row.title = "Standing still: movement is off";
    }
    return row;
  };
  //: A switch row: says which way it is (a checked menu item) and flips it.
  const toggle = (label, on, call) => {
    const row = item(label, on ? "check-square" : "square", call);
    row.setAttribute("role", "menuitemcheckbox");
    row.setAttribute("aria-checked", String(on));
    return row;
  };
  //: Rows in groups, a separator wherever the group changes; an empty group draws nothing.
  const groups = (...lists) => lists.filter((list) => list.length).flatMap((list, at) => (at ? [separator(), ...list] : list));

  //: The figure's own rows (overlay only): things to ask of it, from `panel_motion`'s answer.
  function companionRows(motion) {
    if (!overlay || !motion?.figure) return [];
    const stays = motion.stay === true;
    const rows = [
      figure("Wave", "hand-waving", "wave", null),
      figure("Come here", "arrow-fat-lines-left", "come", motion),
      figure("Go somewhere else", "compass", "wander", motion),
      motion.asleep ? figure("Wake up", "sun-horizon", "wake", null) : figure("Take a nap", "moon-stars", "nap", null),
    ];
    const perch = figure("Sit on a window", "app-window", "perch", motion);
    const noPerch = { on: "Already sitting on a window", none: "No window to sit on right now" }[motion.perch];
    if (motion.roam === false || stays || noPerch) {
      perch.disabled = true;
      perch.title = stays ? "Choose Roam first" : motion.roam === false ? "Roam over windows is off" : noPerch;
    }
    rows.push(perch);
    return rows;
  }
  const hideRow = () => item("Hide for 10 minutes", "timer", () => leave(() => ask("snooze")));

  //: The row `keepOpen` redraws the menu for: the focus goes back to it, not to the first row.
  let refocus = "";
  async function openMenu(kind) {
    await probe();
    const menu = $("desk-menu");
    let rows = [];
    const motion = overlay || kind === "context" ? await Promise.resolve(ask("panel_motion")).catch(() => null) : null;
    if (kind === "context") {
      const notes = [];
      if (!overlay && motion?.note) notes.push(note(motion.note));
      if (overlay && motion?.doing) notes.push(note(`Right now: ${motion.doing}.`));
      if (motion?.still) notes.push(note(`Standing still: ${STILL_WHY[motion.reason] || "movement is off"}.`));
      const look = [];
      if (overlay) look.push(item("Companion", "user-switch", openCompanion));
      look.push(item("Settings", "gear", () => leave(() => ask("open_app", "settings"))));
      const motionRows = [];
      if (overlay && !locked && motion?.still && motion.reason !== "avatar") motionRows.push(item("Let it walk", "person-simple-walk", () => leave(() => ask("let_it_walk"))));
      if (overlay && motion && typeof motion.stay === "boolean" && !motion.still) {
        motionRows.push(motion.stay ? item("Roam", "person-simple-walk", () => keepOpen(() => ask("set_stay", false), "Stay here")) : item("Stay here", "push-pin", () => keepOpen(() => ask("set_stay", true), "Roam")));
      }
      //: Roam over windows: a switch, not a one-way action.
      if (overlay && motion && typeof motion.roam === "boolean") motionRows.push(toggle("Roam over windows", motion.roam, () => keepOpen(() => ask("set_roam", !motion.roam), "Roam over windows")));
      //: How lively it is: one row that steps Calm, Usual, Lively (saved, and the figure follows).
      if (overlay && motion && typeof motion.lively === "string") {
        const levels = ["calm", "usual", "lively"];
        const names = { calm: "Calm", usual: "Usual", lively: "Lively" };
        const at = Math.max(0, levels.indexOf(motion.lively));
        motionRows.push(item(`Activity: ${names[levels[at]]}`, "lightning", () => keepOpen(() => ask("set_lively", levels[(at + 1) % levels.length]), "Activity: ")));
      }
      //: The in-app Companion size steps (`NMB_SIZES`); a size pulled with the corner handle marks none.
      const sizeRows = overlay && !locked && typeof motion?.size === "number"
        ? [["Small", "small", 0.8], ["Medium", "medium", 1], ["Large", "large", 1.3]].map(([label, name, size]) => toggle(label, Math.abs(motion.size - size) < 0.005, () => keepOpen(() => ask("set_figure_size", name), label)))
        : [];
      const away = [hideRow()];
      away.push(item("Turn off", "power", () => (overlay ? leave(() => ask("hide_companion")) : ask("hide_companion"))));
      rows = [...notes, ...groups(look, motionRows, sizeRows, away)];
    } else {
      const capture = locked
        ? [note("Tessellate is locked. Open it to unlock.")]
        : [
            item("Quick note", "note-pencil", () => openPanel("note")),
            item("Quick search", "magnifying-glass", () => openPanel("search")),
            item("New reminder", "bell-ringing", () => leave(() => ask("open_app", "reminder"))),
          ];
      const open = locked ? [] : [item("Open today", "sun", () => leave(() => ask("open_app", "today")))];
      open.push(item("Open Tessellate", "arrow-square-out", () => leave(() => ask("open_app"))));
      const withFigure = companionRows(motion);
      withFigure.push(hideRow());
      rows = groups(capture, open, withFigure);
    }
    menu.replaceChildren(...rows);
    show(kind);
    const live = rows.filter((row) => row.tagName === "BUTTON" && !row.disabled);
    const again = refocus;
    refocus = "";
    (live.find((row) => again && row.textContent.startsWith(again)) || live[0])?.focus();
  }

  //: The right-click menu's "Companion": every choice the app's Appearance offers
  //: (Atlas masculine or feminine, matching your faces, You, the chat's persona, your
  //: own character, each saved companion), the current one marked. A choice is written
  //: to the app's own prefs by the host and the figure restarts with the new look. The
  //: overlay draws all of them (the app window renders the frames), so every row can be picked.
  async function openCompanion() {
    const got = await Promise.resolve(ask("companion_choices")).catch(() => null);
    const rows = [item("Back", "caret-left", () => openMenu("context"))];
    if (got?.locked) rows.push(note("Tessellate is locked. Open it to unlock, then choose."));
    else if (!got?.options?.length) rows.push(note("Tessellate did not answer. Open it and try again."));
    if (got?.note) rows.push(note(got.note));
    let group = "";
    for (const option of got?.options || []) {
      if (option.group !== group) {
        group = option.group;
        rows.push(note(group));
      }
      const row = item(option.label, option.current ? "check-circle" : "circle", () => leave(() => ask("choose_companion", option.key)));
      row.setAttribute("role", "menuitemradio");
      row.setAttribute("aria-checked", String(!!option.current));
      row.disabled = !option.enabled;
      rows.push(row);
    }
    $("desk-menu").replaceChildren(...rows);
    show("context");
    rows.find((row) => row.tagName === "BUTTON" && !row.disabled)?.focus();
  }

  //: A choice that changes a setting (Activity, Stay here or Roam, Roam over windows, a size) keeps the menu
  //: open, drawn again with the new tick and the focus back on that row (INBOX 1696); a request that moves the
  //: figure or opens something closes it (`leave`).
  async function keepOpen(action, row) {
    try {
      await action();
    } finally {
      refocus = row;
      await openMenu("context");
    }
  }

  //: Run `action` first, then rest: the click that brought the app forward is the
  //: one Windows lets this process raise a window for, and hiding this window
  //: before asking could lose that right (the owner, 2026-11-04: Settings hid the
  //: panel and the app came forward by hand, seconds later). The panel is left
  //: open only until the action answers, which is at once.
  async function leave(action) {
    try {
      await action();
    } finally {
      show("rest");
      if (overlay) ask("hide_panel");
    }
  }

  async function openPanel(kind) {
    if (!(await probe())) return openMenu("menu");
    show(kind);
    if (kind === "note") return openNoteCard();
    $("desk-search-text").focus();
  }

  function rest() {
    show("rest");
    if (overlay) ask("hide_panel");
    else $("desk-pet").focus();
  }

  // --- Quick note --------------------------------------------------------------
  //: The Notes tab's capture card, the one the dashboard's Quick capture opens (capture-card.js,
  //: fetched on first use): title, words or a to-do list, tags, Ctrl+Enter or Save. It saves
  //: through the two functions it asks the page for (`createNoteSafely`, `announceSavedNote`),
  //: answered here with this window's own request and its Undo (INBOX 1688).
  const noteStatus = (text, isError = false) => {
    $("desk-note-status").textContent = text;
    $("desk-note-status").classList.toggle("error", isError);
  };

  async function openNoteCard() {
    noteStatus("");
    document.querySelector(".desk-actions").replaceChildren();
    if (!(await ensureModule("captureCard"))) return noteStatus("Couldn't open the note card.", true);
    captureCard.discardOnClose = true;  // this window rests on Close: what the card held back goes with it
    openCaptureCard($("desk-capture"), "focusin");
    focusCaptureCard();
    fit();  // the card is in the DOM now: measuring forces the layout, so no frame wait (and no new wake source)
  }

  //: The two calls capture-stage.js uploads through (the app's, in its window), answered with this
  //: window's token: a picture to /media/upload, a file to the new note's /files.
  const deskApiJson = async (path, { method = "GET", body = null } = {}) => {
    const response = await call(path, method, body);
    if (!response.ok) {
      const detail = (await response.json().catch(() => ({}))).detail;
      throw new Error(typeof detail === "string" ? detail : "That didn't go through.");
    }
    return response.json();
  };
  Object.assign(window, { apiJson: deskApiJson, authHeaders: () => ({}) });

  const createNote = async (body) => {
    const response = await call("/entries", "POST", { defer_filing: true, inline_tags: true, ...body });
    if (response.status === 401) {
      await probe();
      openMenu("menu");
    }
    if (!response.ok) throw new Error("Couldn't save that note.");
    return { saved: await response.json() };
  };

  const announceSaved = async (made) => {
    noteStatus("Saved and being filed.");
    fit();
    //: The app's window puts it on its Undo stack when it answers; with no
    //: answer this window offers the Undo itself.
    const taken = made?.id != null && (await window.standaloneUndo.announce(made, "Captured a note"));
    if (taken || made?.id == null) setTimeout(() => state === "note" && rest(), 900);
    else window.standaloneUndo.offer({ id: made.id, send: call, status: noteStatus, row: document.querySelector(".desk-actions") });
    fit();
  };

  //: Named on the window because the card, a file of the app's, asks for them by these names.
  Object.assign(window, { createNoteSafely: createNote, announceSavedNote: announceSaved });

  // --- Quick search ------------------------------------------------------------
  //: This page loads no chat.js, so it spells the cap itself: chat.js's
  //: `QUESTION_CAP` and `search/query.py`'s, held equal by tests/test_warm12_1101.py.
  const DESK_QUESTION_CAP = 4000;
  //: chat.js's clip rule (INBOX 1528): over the cap, the opening and the end (the ask) are kept.
  const deskClip = (q) => {
    if (q.length <= DESK_QUESTION_CAP) return q;
    return `${q.slice(0, DESK_QUESTION_CAP - 1002)}\n\n${q.slice(-1000)}`;
  };
  let searchTimer = 0;
  let searchSeq = 0;
  //: The fetch is out. Enter pressed meanwhile opens the first match when it lands (`enterAt` is that run).
  let searching = false;
  let enterAt = 0;
  const plain = (text) =>
    String(text || "")
      .replace(/<[^>]*>/g, "")
      .replace(/!?\[([^[\]\n|]*)(?:\|[^[\]\n]*)?\]\([^()\n]*\)?/g, "$1")
      .replace(/^#{1,6}\s+/, "")
      .trim();

  function hitRow(hit) {
    const row = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "menu-item desk-hit";
    const title = document.createElement("span");
    title.className = "desk-hit-title";
    title.textContent = plain(hit.title) || "Untitled";
    button.append(title);
    //: A snippet opens with the title as often as not: only what it says
    //: beyond the title is shown, and nothing when there is none. The kind leads the same line.
    const said = plain(hit.snippet).slice(0, 140);
    const words = said.startsWith(title.textContent) ? said.slice(title.textContent.length).replace(/^[\s:.,;·-]+/, "") : said;
    const meta = document.createElement("span");
    meta.className = "muted desk-hit-meta";
    const kind = document.createElement("span");
    kind.className = "desk-hit-kind";
    kind.textContent = hit.kind;
    meta.append(kind, document.createTextNode(words));
    button.append(meta);
    button.addEventListener("click", () => leave(() => ask("open_hit", hit.kind, hit.id)));
    row.append(button);
    return row;
  }

  //: The empty state under the field: what to do before a word is typed, and what to do when
  //: nothing matched; hidden while there are hits.
  function searchEmpty(kind, q = "") {
    const box = $("desk-search-empty");
    box.classList.toggle("hidden", kind === "hits");
    if (kind === "none") {
      $("desk-search-empty-title").textContent = "Nothing found";
      $("desk-search-empty-hint").textContent = `No match for “${q.slice(0, 40)}”. Try fewer or different words.`;
    } else {
      $("desk-search-empty-title").textContent = "Search your notes";
      $("desk-search-empty-hint").textContent = "Enter opens the first match.";
    }
  }

  async function runSearch() {
    const q = $("desk-search-text").value.trim();
    const mine = ++searchSeq;
    const list = $("desk-search-hits");
    searching = !!q;
    if (!q) {
      list.replaceChildren();
      $("desk-search-status").textContent = "";
      searchEmpty("idle");
      if (overlay) fit();
      return;
    }
    try {
      const response = await call(`/search?q=${encodeURIComponent(deskClip(q))}&limit=6`);
      if (mine !== searchSeq) return;
      if (response.status === 401) {
        searching = false;
        list.replaceChildren();
        await probe();
        return openMenu("menu");
      }
      if (!response.ok) throw new Error("Search is not available right now.");
      const body = await response.json();
      list.replaceChildren(...(body.hits || []).map(hitRow));
      $("desk-search-status").textContent = "";
      searchEmpty(body.hits?.length ? "hits" : "none", q);
      searching = false;
      if (overlay) fit();
      if (enterAt === mine) list.querySelector("button")?.click();
    } catch (error) {
      if (mine !== searchSeq) return;
      searching = false;
      $("desk-search-status").textContent = error.message || "Search is not available right now.";
      if (overlay) fit();
    }
  }

  // --- the companion itself: click, right-click, drag -------------------------------
  const pet = $("desk-pet");
  let press = null;

  pet.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    pet.setPointerCapture?.(event.pointerId);
    press = { x: event.screenX, y: event.screenY, moved: false, from: ask("drag_start"), busy: false };
  });

  pet.addEventListener("pointermove", async (event) => {
    if (!press) return;
    const dx = event.screenX - press.x;
    const dy = event.screenY - press.y;
    if (!press.moved && Math.hypot(dx, dy) < 5) return;
    press.moved = true;
    if (press.busy) return;
    press.busy = true;
    const from = await press.from;
    if (Array.isArray(from)) await ask("drag_to", from[0] + dx, from[1] + dy);
    press.busy = false;
  });

  pet.addEventListener("pointerup", () => {
    const done = press;
    press = null;
    if (!done) return;
    if (done.moved) ask("drag_end");
    else if (state === "rest") openMenu("menu");
    else rest();
  });

  pet.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    openMenu("context");
  });
  pet.addEventListener("keydown", (event) => {
    if (event.key === "ContextMenu" || (event.key === "F10" && event.shiftKey)) {
      event.preventDefault();
      openMenu("context");
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state !== "rest") rest();
  });
  //: A menu's rows are walked with the arrows, as every menu in the app is.
  $("desk-menu").addEventListener("keydown", (event) => {
    const rows = [...$("desk-menu").querySelectorAll("[role^=menuitem]:not(:disabled)")];
    const at = rows.indexOf(document.activeElement);
    const to = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: rows.length - 1 }[event.key];
    if (to === undefined || !rows.length) return;
    event.preventDefault();
    rows[(to + rows.length) % rows.length].focus();
  });
  //: The note's head X is the card's Close too: the card's own is folded away here (the 296px
  //: foot had no room for it beside Note | To-do, the picture and Save, so Save wrapped to a
  //: second line; wrapzoom 2026-11-11). It closes the card the card's way (the draft kept, a
  //: held picture dropped), and the capture listener below rests the window.
  for (const button of document.querySelectorAll("[data-desk-close]")) {
    button.addEventListener("click", () => {
      const cardClose = button.closest("#desk-note") && $("desk-capture").querySelector('#capture-card:not([hidden]) [data-cc="close"]');
      if (cardClose) cardClose.click();
      else rest();
    });
  }

  //: The card closes itself (Close, Escape); the panel goes with it. Capture phase: the card
  //: stops the Escape it handles, and keeps its draft either way.
  const capture = $("desk-capture");
  capture.addEventListener("click", (event) => event.target.closest('[data-cc="close"]') && rest(), true);
  capture.addEventListener("keydown", (event) => event.key === "Escape" && rest(), true);
  //: The card changes its own height (a to-do list, the tags): the window follows.
  document.addEventListener("mm:controls-changed", fit);
  $("desk-search-text").addEventListener("input", () => {
    enterAt = 0;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      searchTimer = 0;
      runSearch();
    }, 220);
  });
  //: Enter in the field: a pending search runs now; with the results in, it opens the first match.
  $("desk-search-text").addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      $("desk-search-hits").querySelector("button")?.focus();
    }
    if (event.key === "Enter" && !event.isComposing) {
      event.preventDefault();
      if (searchTimer) {
        clearTimeout(searchTimer);
        searchTimer = 0;
        runSearch();
        enterAt = searchSeq;
      } else if (searching) enterAt = searchSeq;
      else $("desk-search-hits").querySelector("button")?.click();
    }
  });
  //: The results are walked with the arrows; Up from the first goes back to the field.
  $("desk-search-hits").addEventListener("keydown", (event) => {
    const rows = [...$("desk-search-hits").querySelectorAll("button")];
    const at = rows.indexOf(document.activeElement);
    const to = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: rows.length - 1 }[event.key];
    if (to === undefined || at < 0) return;
    event.preventDefault();
    if (to < 0) $("desk-search-text").focus();
    else rows[Math.min(to, rows.length - 1)].focus();
  });

  //: Drawn at once as Atlas (the answer with no storage), then as who the
  //: notebook says; shown again to the person each time the window is: the
  //: lock may have changed while it was hidden.
  draw();
  show("rest");
  probe();
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) probe();
  });
  //: The overlay asks for the menu (left click) or the settings menu (right click)
  //: each time it shows this window, and the first time it opens on the menu.
  if (overlay) {
    window.addEventListener("desk-open", (event) => openMenu(event.detail === "context" ? "context" : "menu"));
    //: Python hides the window on a second click on the figure; what it showed is
    //: cleared first so the next open does not flash the last menu's size.
    window.addEventListener("desk-close", () => show("rest"));
    //: The first open: Python holds which click made this window, asked once
    //: when the bridge is ready; the quick menu if it never answers.
    let opened = false;
    const firstOpen = async () => {
      if (opened) return;
      opened = true;
      let kind = "menu";
      try {
        kind = (await ask("panel_kind")) === "context" ? "context" : "menu";
      } catch {
        kind = "menu";
      }
      openMenu(kind);
    };
    if (host()) firstOpen();
    else window.addEventListener("pywebviewready", firstOpen, { once: true });
    setTimeout(() => {
      if (!opened) {
        opened = true;
        openMenu("menu");
      }
    }, 2000);
    //: Click-away: the window reports losing focus to something else, but only
    //: after it has had focus (a window that opens unfocused is not "away").
    let focused = false;
    window.addEventListener("focus", () => {
      focused = true;
    });
    window.addEventListener("blur", () => {
      if (!focused) return;
      focused = false;
      show("rest");
      ask("panel_blur");
    });
  }
})();
