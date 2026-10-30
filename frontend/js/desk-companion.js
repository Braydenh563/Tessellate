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
    menu: [208, 312],
    context: [208, 268],
    note: [320, 376],
    search: [340, 440],
  };
  const PANELS = { menu: "desk-menu", context: "desk-menu", note: "desk-note", search: "desk-search" };
  let state = "rest";
  let locked = true;
  let seedShown = "";

  const card = new URLSearchParams(location.search).has("card");
  document.body.classList.toggle("desk-card", card);

  //: What the app's window saved in this browser's storage (the window shares it).
  const token = () => prefs.get("token", "");

  //: The window's one kind of request: signed in, in the space open in the app.
  const call = (path, method = "GET", body = null) =>
    fetch(path, {
      method,
      headers: { "Content-Type": "application/json", "X-Auth-Token": token(), "X-Workspace-ID": prefs.get("spaceId", "") || "all" },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });

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
    if (name === seedShown) return;
    seedShown = name;
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
    state = next;
    document.body.dataset.state = next;
    document.body.dataset.size = SIZES[next].join("x");
    for (const id of new Set(Object.values(PANELS))) $(id).classList.toggle("hidden", PANELS[next] !== id);
    $("desk-pet").setAttribute("aria-expanded", String(next === "menu" || next === "context"));
    ask("set_size", SIZES[next][0], SIZES[next][1]);
  }

  function item(label, icon, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost desk-item";
    button.setAttribute("role", "menuitem");
    const mark = document.createElement("i");
    mark.className = `ph ph-${icon}`;
    mark.setAttribute("aria-hidden", "true");
    button.append(mark, document.createTextNode(label));
    button.addEventListener("click", onClick);
    return button;
  }

  async function openMenu(kind) {
    await probe();
    const menu = $("desk-menu");
    const rows = [];
    if (kind === "context") {
      rows.push(item("Settings", "gear", () => leave(() => ask("open_app", "settings"))));
      rows.push(item("Hide", "eye-slash", () => ask("hide_companion")));
    } else if (locked) {
      const note = document.createElement("p");
      note.className = "muted desk-note";
      note.textContent = "Tessellate is locked. Open it to unlock.";
      rows.push(note, item("Open Tessellate", "arrow-square-out", () => leave(() => ask("open_app"))));
    } else {
      rows.push(
        item("Quick note", "note-pencil", () => openPanel("note")),
        item("Quick search", "magnifying-glass", () => openPanel("search")),
        item("Open Tessellate", "arrow-square-out", () => leave(() => ask("open_app")))
      );
    }
    menu.replaceChildren(...rows);
    show(kind);
    rows.find((row) => row.tagName === "BUTTON")?.focus();
  }

  //: Run `action`, then rest: the window is about to be hidden by the app's own
  //: coming forward, and a panel left open would be there when it returns.
  function leave(action) {
    show("rest");
    action();
  }

  async function openPanel(kind) {
    if (!(await probe())) return openMenu("menu");
    show(kind);
    $(kind === "note" ? "desk-note-text" : "desk-search-text").focus();
  }

  function rest() {
    show("rest");
    $("desk-pet").focus();
  }

  // --- Quick note --------------------------------------------------------------
  const noteStatus = (text, isError = false) => {
    $("desk-note-status").textContent = text;
    $("desk-note-status").classList.toggle("error", isError);
  };
  let saving = false;

  async function saveNote() {
    const content = $("desk-note-text").value.trim();
    if (!content || saving) return;
    saving = true;
    $("desk-note-save").disabled = true;
    noteStatus("Saving...");
    try {
      const response = await call("/entries", "POST", { content });
      if (response.status === 401) {
        await probe();
        return openMenu("menu");
      }
      if (!response.ok) throw new Error("Couldn't save that note.");
      const made = await response.json().catch(() => null);
      $("desk-note-text").value = "";
      noteStatus("Saved and being filed.");
      //: The app's window puts it on its Undo stack when it answers; with no
      //: answer this window offers the Undo itself.
      const taken = made?.id != null && (await window.standaloneUndo.announce(made, "Captured a note"));
      if (taken || made?.id == null) setTimeout(() => state === "note" && rest(), 900);
      else window.standaloneUndo.offer({ id: made.id, send: call, status: noteStatus, row: document.querySelector(".desk-actions") });
    } catch (error) {
      noteStatus(error.message || "Couldn't save that note.", true);
    } finally {
      saving = false;
      $("desk-note-save").disabled = false;
    }
  }

  // --- Quick search ------------------------------------------------------------
  let searchTimer = 0;
  let searchSeq = 0;
  const plain = (text) => String(text || "").replace(/<[^>]*>/g, "").trim();

  function hitRow(hit) {
    const row = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost desk-hit";
    const title = document.createElement("span");
    title.className = "desk-hit-title";
    title.textContent = plain(hit.title) || "Untitled";
    const kind = document.createElement("span");
    kind.className = "muted desk-hit-kind";
    kind.textContent = hit.kind;
    button.append(title, kind);
    if (hit.snippet) {
      const snippet = document.createElement("span");
      snippet.className = "muted desk-hit-snippet";
      snippet.textContent = plain(hit.snippet).slice(0, 140);
      button.append(snippet);
    }
    button.addEventListener("click", () => leave(() => ask("open_hit", hit.kind, hit.id)));
    row.append(button);
    return row;
  }

  async function runSearch() {
    const q = $("desk-search-text").value.trim();
    const mine = ++searchSeq;
    const list = $("desk-search-hits");
    if (!q) {
      list.replaceChildren();
      $("desk-search-status").textContent = "";
      return;
    }
    try {
      const response = await call(`/search?q=${encodeURIComponent(q)}&limit=6`);
      if (mine !== searchSeq) return;
      if (response.status === 401) {
        list.replaceChildren();
        await probe();
        return openMenu("menu");
      }
      if (!response.ok) throw new Error("Search is not available right now.");
      const body = await response.json();
      list.replaceChildren(...(body.hits || []).map(hitRow));
      $("desk-search-status").textContent = body.hits?.length ? "" : "Nothing found.";
    } catch (error) {
      if (mine === searchSeq) $("desk-search-status").textContent = error.message || "Search is not available right now.";
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
  for (const button of document.querySelectorAll("[data-desk-close]")) button.addEventListener("click", rest);

  $("desk-note-save").addEventListener("click", saveNote);
  $("desk-note-text").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      saveNote();
    }
  });
  $("desk-search-text").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(runSearch, 220);
  });
  $("desk-search-text").addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") $("desk-search-hits").querySelector("button")?.focus();
    if (event.key === "Enter") {
      clearTimeout(searchTimer);
      runSearch();
    }
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
})();
