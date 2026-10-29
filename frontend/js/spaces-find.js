// spaces-find.js: the status bar's slots, spaces, the templates pane, Find
// anything, then the boot kick-offs. Moved out of app.js on 2026-09-26 as one
// contiguous range (INBOX 426 cc, docs/roadmap/agent-remaining/appjs-split.md).
// A classic script sharing app.js's globals, loaded in app.js's old order;
// nothing in an earlier file calls into it while the page loads
// (scratchpad/appjs-map.js --check).

// --- what shows in the status bar --------------------------------------------
//
// The list of slots and the Settings rows that edit it (`STATUS_SLOTS`,
// `renderStatusBarSettings`) are in settings-controls.js: only the Settings
// window draws them. What is hidden is stored, and applied here.

function hiddenStatusSlots() {
  // `prefsCache`, not `window.prefsCache`. It is declared with `let` at the
  // top level of a classic script, which puts it in the *global lexical*
  // scope, shared with every other script here, so a bare reference works , 
  // and explicitly NOT on `window`. Two existing call sites in this file get
  // that wrong and silently read `undefined` forever; this one measured as a
  // toggle that ticked and did nothing.
  const stored = typeof prefsCache === "object" && prefsCache ? prefsCache.status_bar_hidden : null;
  return new Set(Array.isArray(stored) ? stored : []);
}

function applyStatusBarSlots() {
  const hidden = hiddenStatusSlots();
  for (const element of document.querySelectorAll("[data-status-slot]")) {
    // `.hidden` rather than a style: everything else in this app that shows
    // and hides uses the class, and one of these slots (`status-task`) is
    // already driven by it from another code path.
    element.classList.toggle("status-slot-off", hidden.has(element.dataset.statusSlot));
  }
}

let statusClockTimer = null;

// HH:MM, no seconds, repainted on the minute by `startMinuteTicker` (see it
// for why a clock without seconds is one wake a minute rather than sixty,
// or, as this one used to be, two).
function paintStatusClock() {
  const el = $("status-clock");
  if (!el) return;
  el.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// Reads prefsCache.status_bar_clock rather than taking an argument, the same
// convention applyStatusBarSlots() and applyAppearance() already use: one
// source of truth, called again after every write.
function applyStatusClock() {
  const el = $("status-clock");
  if (!el) return;
  const on = Boolean(prefsCache?.status_bar_clock);
  el.classList.toggle("hidden", !on);
  if (statusClockTimer) {
    statusClockTimer();
    statusClockTimer = null;
  }
  if (on) {
    //: Was `setInterval(..., 30000)`, which cost two wakes a minute to paint
    //: HH:MM *and* left the bar up to 30 seconds behind the minute it was
    //: showing. `startMinuteTicker` is one wake and never behind.
    statusClockTimer = startMinuteTicker(paintStatusClock);
  } else {
    closeStatusClockDetail();
  }
}

// **The detail popover.** Asked for directly: seconds, the date and the
// timezone, on click or hover, none of which belong in the bar's own
// HH:MM (the comment on paintStatusClock explains why: glanced at, not
// watched, so a 30s repaint is deliberate there). This is the opposite
// case, open only while someone is actually looking at it, so it gets
// its own 1s ticker, started on open and stopped on close rather than
// running unconditionally in the background the way the bar's clock does.
let statusClockDetailTimer = null;
let statusClockDetailPinned = false;

function paintStatusClockDetail() {
  if (document.hidden) return; // the next tick after the tab is back repaints
  const now = new Date();
  const dateEl = $("status-clock-detail-date");
  const timeEl = $("status-clock-detail-time");
  const zoneEl = $("status-clock-detail-zone");
  if (!dateEl || !timeEl || !zoneEl) return;
  dateEl.textContent = now.toLocaleDateString([], {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  timeEl.textContent = now.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  // Both the IANA name (what a person recognises, "Europe/London") and
  // the numeric offset (what actually explains a gap between two
  // people's clocks): a name alone doesn't say which side of UTC you're
  // on, and an offset alone doesn't say which timezone that even is.
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const offsetMatch = /GMT([+-]\d+(?::\d+)?)/.exec(
    now.toLocaleTimeString([], { timeZoneName: "shortOffset" })
  );
  zoneEl.textContent = offsetMatch ? `${zone} (UTC${offsetMatch[1]})` : zone;
}

function openStatusClockDetail(pin) {
  const panel = $("status-clock-detail");
  const btn = $("status-clock");
  if (!panel || !btn || !prefsCache?.status_bar_clock) return;
  if (pin) statusClockDetailPinned = true;
  panel.classList.remove("hidden");
  btn.setAttribute("aria-expanded", "true");
  paintStatusClockDetail();
  if (!statusClockDetailTimer) {
    statusClockDetailTimer = setInterval(paintStatusClockDetail, 1000);
  }
  // Positioned from the button's own rect, not a static CSS offset: the
  // clock's horizontal position among the bar's other optional slots
  // (STATUS_SLOTS) isn't fixed, so a hardcoded `right:` would drift out
  // from under the button the moment a neighbouring slot is toggled off.
  // Opens *upward*: the status bar is the bottom of the screen, so
  // "below the button" is off-window.
  const margin = 8;
  const anchor = btn.getBoundingClientRect();
  panel.style.left = "0px";
  const box = panel.getBoundingClientRect();
  let left = anchor.left;
  if (left + box.width > window.innerWidth - margin) {
    left = Math.max(margin, window.innerWidth - margin - box.width);
  }
  panel.style.left = `${Math.round(left)}px`;
  panel.style.bottom = `${Math.round(window.innerHeight - anchor.top + margin)}px`;
}

function closeStatusClockDetail(force) {
  // Hover-out shouldn't close a click-pinned popover, only Escape,
  // outside click, or the clock itself being turned off should.
  if (statusClockDetailPinned && !force) return;
  statusClockDetailPinned = false;
  $("status-clock-detail")?.classList.add("hidden");
  $("status-clock")?.setAttribute("aria-expanded", "false");
  if (statusClockDetailTimer) {
    clearInterval(statusClockDetailTimer);
    statusClockDetailTimer = null;
  }
}

(() => {
  const btn = $("status-clock");
  if (!btn) return;
  btn.addEventListener("mouseenter", () => openStatusClockDetail(false));
  btn.addEventListener("mouseleave", () => closeStatusClockDetail(false));
  btn.addEventListener("focus", () => openStatusClockDetail(false));
  btn.addEventListener("blur", () => closeStatusClockDetail(false));
  btn.addEventListener("click", () => {
    if (statusClockDetailPinned) closeStatusClockDetail(true);
    else openStatusClockDetail(true);
  });
})();
document.addEventListener("click", (e) => {
  if (
    statusClockDetailPinned &&
    !e.target.closest("#status-clock, #status-clock-detail")
  ) {
    closeStatusClockDetail(true);
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && statusClockDetailPinned) closeStatusClockDetail(true);
});

// --- Agent Activity: moved to agent-activity.js ---

// --- Global Command Palette (Ctrl+K): moved to palette.js ---
// Split out on 2026-09-24 when the gzipped app.js crossed
// test_static_compression.py's bound; see palette.js's header.

// --- spaces ------------------------------------------------------------------
//
// A space partitions notes, categories, links and documents. It is soft
// separation, not separate databases: every row carries a `workspace_id` and
// the server adds a loader criterion for the one named in `X-Workspace-ID`.
// That header is added in `api()` above, which is the only reason switching
// spaces changes what you see rather than just the label in the header.
//
// The id is kept in localStorage rather than on the server on purpose: which
// space you were last in is a property of this window, not of the notebook,
// and syncing it would mean two open windows fighting over one value.
//
// `SPACE_ALL` itself is declared up near `api()`, not here: see the comment
// there for why.

// The icons a space may be given. A closed set, because the value is
// interpolated into a class name, an arbitrary string there is CSS class
// injection, and it is also how you end up with a space whose icon is a
// typo that renders as an empty box.
const SPACE_ICONS = [
  "ph-folder", "ph-briefcase", "ph-house", "ph-user", "ph-kanban",
  "ph-code", "ph-flask", "ph-heart", "ph-book-open", "ph-graduation-cap",
  "ph-game-controller", "ph-terminal-window", "ph-camera", "ph-music-notes",
  "ph-airplane", "ph-shopping-cart", "ph-tree", "ph-lightbulb",
];

let spacesCache = [];

//: The two headers every hand-built request needs, for a call that has to
//: replace `api()`'s defaults (a FormData body must not carry its JSON
//: Content-Type). Passing a headers object holding only the token replaced
//: the space header too, so a document imported through the chat's paperclip
//: landed in the default space whatever space was open (audit 2026-10-05).
//: `tests/test_auth_headers_space.py` fails on a literal that drops it.
function authHeaders() {
  return {
    "X-Auth-Token": authToken(),
    "X-Workspace-ID": activeSpaceId(),
  };
}

function setActiveSpace(id) {
  prefs.set("spaceId", id);
  // A full reload rather than a re-fetch of everything on the page. Every list,
  // count, graph and sidebar in the app is scoped by the header, so a partial
  // refresh would leave whichever one we forgot showing the old space, and a
  // space that is half-switched is worse than one that took a second.
  window.location.reload();
}

function spaceIconPicker(container, hiddenInput) {
  container.replaceChildren();
  for (const name of SPACE_ICONS) {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", String(hiddenInput.value === name));
    button.setAttribute("aria-label", name.replace("ph-", "").replace(/-/g, " "));
    const icon = document.createElement("i");
    icon.className = `ph ${name}`;
    icon.setAttribute("aria-hidden", "true");
    button.appendChild(icon);
    button.addEventListener("click", () => {
      hiddenInput.value = name;
      for (const sibling of container.children) {
        sibling.setAttribute("aria-checked", String(sibling === button));
      }
    });
    container.appendChild(button);
  }
}

function spaceMenuOption({ id, name, icon, deletable, hiddenFromAll }) {
  const option = document.createElement("button");
  option.type = "button";
  option.className = "space-option";
  option.setAttribute("role", "option");
  option.dataset.spaceId = id;
  option.setAttribute("aria-selected", String(id === activeSpaceId()));
  // .space-option-name ellipsises with no other escape hatch for a long
  // board name.
  option.title = name;

  const glyph = document.createElement("i");
  glyph.className = `ph ${icon}`;
  glyph.setAttribute("aria-hidden", "true");

  const label = document.createElement("span");
  label.className = "space-option-name";
  label.textContent = name;

  option.append(glyph, label);
  option.addEventListener("click", () => setActiveSpace(id));

  if (deletable) {
    const actions = document.createElement("span");
    actions.className = "space-option-actions";

    // Nested <button> is invalid HTML, so these are spans with a button role.
    // The click handlers stop propagation: without it, "rename" would also
    // trip the row's own switch-to-this-space handler and reload the page out
    // from under the dialog that was about to open.
    for (const [glyphName, title, run] of [
      // Keep this space out of "All spaces", or put it back. Asked for
      // directly: "how do I hide a specific space's notes and
      // images/documents etc, all the content from the 'all spaces' space if
      // I wish??" It lives on the space's own row because that is where a
      // person is when they think it, not buried in Settings, which is the
      // other place it could have gone and a worse one.
      //
      // The glyph carries the state (an open eye means visible, a struck-out
      // one means hidden), and the title says what pressing it will do,
      // which is the pair every other toggle in this app uses.
      [
        hiddenFromAll ? "ph-eye-slash" : "ph-eye",
        hiddenFromAll
          ? "Hidden from All spaces, show it there again"
          : "Hide this space's contents from All spaces",
        () => toggleSpaceHidden(id, !hiddenFromAll),
      ],
      ["ph-pencil-simple", "Rename this space", () => openSpaceEdit(id, name, icon)],
      ["ph-trash", "Delete this space", () => openSpaceDelete(id)],
    ]) {
      const action = document.createElement("span");
      action.className = "ghost small";
      action.setAttribute("role", "button");
      action.tabIndex = 0;
      action.title = title;
      action.setAttribute("aria-label", title);
      const actionIcon = document.createElement("i");
      actionIcon.className = `ph ${glyphName}`;
      actionIcon.setAttribute("aria-hidden", "true");
      action.appendChild(actionIcon);
      const fire = (event) => {
        event.stopPropagation();
        event.preventDefault();
        closeSpaceMenu();
        run();
      };
      action.addEventListener("click", fire);
      action.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") fire(event);
      });
      actions.appendChild(action);
    }
    option.appendChild(actions);
  }
  return option;
}

// Flip a space in or out of the everything-view. A view filter, not a
// privacy boundary: the space stays completely usable when selected.
async function toggleSpaceHidden(id, hidden) {
  try {
    await apiJson(`/spaces/${id}`, {
      method: "PUT",
      body: JSON.stringify({ hidden_from_all: hidden }),
    });
    pushRequestUndo(
      hidden ? "Hid a space from All spaces" : "Showed a space in All spaces",
      `/spaces/${id}`,
      "PUT",
      { hidden_from_all: !hidden },
      { hidden_from_all: hidden },
      async () => {
        await loadSpaces();
        renderSpaceMenu();
        if (activeSpaceId() === SPACE_ALL) await loadEntries();
      }
    );
    await loadSpaces();
    renderSpaceMenu();
    toast(
      hidden
        ? "Hidden from All spaces. It still opens normally when you pick it."
        : "Showing in All spaces again."
    );
    // The everything-view's contents just changed under whatever is on
    // screen, so it has to be re-read rather than left stale.
    if (activeSpaceId() === SPACE_ALL) await loadEntries();
  } catch (error) {
    toast(error.message || "Couldn't change that space.", true);
  }
}

function renderSpaceMenu() {
  const menu = $("space-menu");
  if (!menu) return;
  menu.replaceChildren();

  menu.appendChild(spaceMenuOption({
    id: SPACE_ALL,
    name: "All spaces",
    icon: "ph-circles-four",
    deletable: false,
  }));
  for (const space of spacesCache) {
    menu.appendChild(spaceMenuOption({
      id: space.id,
      name: space.name,
      icon: space.icon,
      // "default" is where a deleted space's notes go, so it cannot itself be
      // deleted: the server refuses it too, but offering a button that always
      // errors is not a UI.
      hiddenFromAll: Boolean(space.hidden_from_all),
      deletable: space.id !== "default",
    }));
  }

  const divider = document.createElement("div");
  divider.className = "space-menu-divider";
  menu.appendChild(divider);

  const create = document.createElement("button");
  create.type = "button";
  create.className = "space-option";
  create.id = "space-create-open";
  const plus = document.createElement("i");
  plus.className = "ph ph-plus";
  plus.setAttribute("aria-hidden", "true");
  const createLabel = document.createElement("span");
  createLabel.className = "space-option-name";
  createLabel.textContent = "New space…";
  create.append(plus, createLabel);
  create.addEventListener("click", () => {
    closeSpaceMenu();
    openSpaceCreate();
  });
  menu.appendChild(create);

  // The button's own label follows whatever is selected.
  const current = spacesCache.find((space) => space.id === activeSpaceId());
  const nameEl = $("space-current-name");
  const iconEl = $("space-current-icon");
  if (nameEl) {
    nameEl.textContent = current ? current.name : "All spaces";
    nameEl.title = current ? current.name : "All spaces";
  }
  if (iconEl) iconEl.className = `ph ${current ? current.icon : "ph-circles-four"}`;
  //: Past twelve spaces the menu is typed to (row 1643, `listFilter`).
  listFilter(menu, { label: "Filter spaces", inside: true, rows: ":scope > .space-option:not(#space-create-open)" })?.refresh();
}

function closeSpaceMenu() {
  //: The same hand-back as `closeNavHistoryMenu`: Escape in the list left
  //: the focus on `body`.
  const held = $("space-menu")?.contains(document.activeElement);
  $("space-menu")?.classList.add("hidden");
  $("space-switcher-btn")?.setAttribute("aria-expanded", "false");
  if (held) $("space-switcher-btn")?.focus({ preventScroll: true });
}

function openSpaceCreate() {
  $("space-create-name").value = "";
  $("space-create-icon").value = "ph-folder";
  $("space-create-error").textContent = "";
  spaceIconPicker($("space-create-icon-picker"), $("space-create-icon"));
  $("space-create-dialog").showModal();
  $("space-create-name").focus();
}

function openSpaceEdit(id, name, icon) {
  $("space-edit-id").value = id;
  $("space-edit-name").value = name;
  $("space-edit-icon").value = icon;
  $("space-edit-dialog").dataset.was = JSON.stringify({ name, icon });
  $("space-edit-error").textContent = "";
  spaceIconPicker($("space-edit-icon-picker"), $("space-edit-icon"));
  $("space-edit-dialog").showModal();
  $("space-edit-name").focus();
}

function openSpaceDelete(id) {
  $("space-delete-id").value = id;
  $("space-delete-error").textContent = "";
  //: Delete everything, or move it all to another space first (owner,
  //: 0.3.31). Deleting is the first option because it is what the button
  //: has always done; every other space is offered as a move.
  const fate = $("space-delete-fate");
  fate.replaceChildren();
  const wipe = document.createElement("option");
  wipe.value = "";
  wipe.textContent = "Delete everything in it";
  fate.appendChild(wipe);
  for (const space of spacesCache) {
    if (space.id === id || space.id === "all") continue;
    const option = document.createElement("option");
    option.value = space.id;
    option.textContent = `Move everything to ${space.name}`;
    fate.appendChild(option);
  }
  const sync = () => {
    $("space-delete-submit").textContent = fate.value ? "Move and delete space" : "Delete space and contents";
  };
  fate.onchange = sync;
  sync();
  $("space-delete-dialog").showModal();
}

async function loadSpaces() {
  if (!$("space-switcher-btn")) return;
  const wasEmpty = !spacesCache.length;
  try {
    spacesCache = await apiJson("/spaces", { silent: true });
  } catch {
    // A notebook that has never had a space made still has to work. Failing to
    // list them leaves the switcher on "All spaces", which is exactly right.
    spacesCache = [];
  }
  renderSpaceMenu();
  updateCaptureSpaceLabel();
  //: The other half of the guard on the note card's space chip: the list is
  //: drawn before this request comes back, and every card that drew while the
  //: cache was empty is now missing the chip it should carry. Re-rendered only
  //: when there is something on screen to re-render and the cache actually has
  //: something in it, so this costs a fresh notebook nothing and cannot loop
  //: (nothing in `renderEntries` calls back into here).
  if (wasEmpty && spacesCache.length && $("entry-list")?.children.length) renderEntries();
}

//: INBOX 1a/38: says which space the capture form actually files into,
//: because the answer is not always the one picked at the top. Selecting
//: "All spaces" turns off the workspace filter for *reading*, but a new
//: note still has to land somewhere concrete, and `database.py`'s own
//: insert hook only stamps a workspace when one is actually selected: with
//: "all" sent, a fresh row keeps its column default, "default" (Default
//: Space). Read that off the same rule rather than re-deciding it here, so
//: this label and the server's own behaviour cannot drift apart.
function updateCaptureSpaceLabel() {
  const label = $("capture-space-hint");
  if (!label) return;
  const active = activeSpaceId();
  const filingId = active === SPACE_ALL ? "default" : active;
  const space = spacesCache.find((s) => s.id === filingId);
  const name = space ? space.name : "Default space";
  label.textContent =
    active === SPACE_ALL
      ? `Filing into ${name} (pick a space above to file there instead).`
      : `Filing into ${name}.`;
}

function initSpaceSwitcher() {
  const button = $("space-switcher-btn");
  const menu = $("space-menu");
  if (!button || !menu) return;

  button.addEventListener("click", (event) => {
    event.stopPropagation();
    const open = button.getAttribute("aria-expanded") === "true";
    button.setAttribute("aria-expanded", String(!open));
    menu.classList.toggle("hidden", open);
  });

  document.addEventListener("click", (event) => {
    if (!menu.contains(event.target) && !button.contains(event.target)) closeSpaceMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSpaceMenu();
  });

  // Cancel buttons. These were `onclick` attributes, which this app's CSP
  // refuses outright, so every one of them was dead markup.
  for (const closer of document.querySelectorAll("[data-close-dialog]")) {
    closer.addEventListener("click", () => {
      document.getElementById(closer.dataset.closeDialog)?.close();
    });
  }

  //: The forms are empty shells that give Enter something to submit; the click handlers below do the work.
  for (const id of ["space-create-form", "space-edit-form"]) $(id)?.addEventListener("submit", (event) => event.preventDefault());

  $("space-create-submit")?.addEventListener("click", async () => {
    const name = $("space-create-name").value.trim();
    const error = $("space-create-error");
    error.textContent = "";
    if (!name) {
      error.textContent = "Give the space a name.";
      return;
    }
    try {
      const space = await apiJson("/spaces", {
        method: "POST",
        body: JSON.stringify({ name, icon: $("space-create-icon").value }),
      });
      $("space-create-dialog").close();
      //: Made in place, with no reload: a reload empties the session's Undo.
      //: Undo moves anything put in it meanwhile to the default space, then
      //: removes it; Redo makes it again under the id the server gives next.
      const made = { name, icon: $("space-create-icon").value };
      let live = space;
      pushUndo(
        `Made the space “${name}”`,
        async () => {
          await api(`/spaces/${encodeURIComponent(live.id)}?move_to=default`, { method: "DELETE" });
          if (activeSpaceId() === live.id) setActiveSpace("all");
          else await loadSpaces();
        },
        async () => {
          live = await apiJson("/spaces", { method: "POST", body: JSON.stringify(made) });
          await loadSpaces();
        }
      );
      await loadSpaces();
      toastAction(`Made the space “${name}”.`, "Open it", () => setActiveSpace(live.id));
    } catch (err) {
      error.textContent = err.message;
    }
  });

  $("space-edit-submit")?.addEventListener("click", async () => {
    const id = $("space-edit-id").value;
    const name = $("space-edit-name").value.trim();
    const error = $("space-edit-error");
    error.textContent = "";
    if (!name) {
      error.textContent = "Give the space a name.";
      return;
    }
    try {
      const now = { name, icon: $("space-edit-icon").value };
      await apiJson(`/spaces/${encodeURIComponent(id)}`, {
        method: "PUT",
        body: JSON.stringify(now),
      });
      pushRequestUndo(`Renamed the space to “${name}”`, `/spaces/${encodeURIComponent(id)}`, "PUT", JSON.parse($("space-edit-dialog").dataset.was || "{}"), now, loadSpaces);
      $("space-edit-dialog").close();
      await loadSpaces();
      toast(`Renamed to “${name}”.`);
    } catch (err) {
      error.textContent = err.message;
    }
  });

  $("space-delete-submit")?.addEventListener("click", async () => {
    const id = $("space-delete-id").value;
    const error = $("space-delete-error");
    error.textContent = "";
    try {
      const moveTo = $("space-delete-fate").value;
      const query = moveTo ? `?move_to=${encodeURIComponent(moveTo)}` : "";
      const wasOpen = activeSpaceId() === id;
      const gone = await apiJson(`/spaces/${encodeURIComponent(id)}${query}`, { method: "DELETE" });
      //: The moved notes by id (`refreshEntries` reads the notebook whole
      //: if it cannot patch them in safely).
      if (moveTo) await refreshEntries(gone?.restore?.moved?.entries || []);
      $("space-delete-dialog").close();
      // Standing in the space you just deleted has to move you somewhere real,
      // and reload() alone would leave the header naming a space that is gone.
      if (activeSpaceId() === id) setActiveSpace("default");
      else await loadSpaces();
      //: Undo (undo-1005) when the delete lost nothing: an empty space, or one
      //: whose contents moved, which go back row by row. A delete that took
      //: the contents with it has no Undo (`restore` is null): its files are
      //: gone from the disk, which is why the dialog asks first. Deleting the
      //: open space reloads the page, which empties the stack, so none then.
      let restore = wasOpen ? null : gone?.restore;
      if (restore) {
        const remake = async () => {
          await apiJson("/spaces/restore", { method: "POST", body: JSON.stringify(restore) });
          await loadSpaces();
          if (moveTo) await refreshEntries(restore.moved?.entries || []);
        };
        const action = pushUndo(`Deleted the space “${gone.name}”`, remake, async () => {
          restore = (await apiJson(`/spaces/${encodeURIComponent(id)}${query}`, { method: "DELETE" })).restore || restore;
          await loadSpaces();
          if (moveTo) await refreshEntries(restore.moved?.entries || []);
        });
        toastAction(`Deleted “${gone.name}”.`, "Undo", async () => {
          settleUndoFromToast(action);
          await remake().catch((e) => toast(e.message, true));
        });
      }
    } catch (err) {
      error.textContent = err.message;
    }
  });

  // Deliberately NOT loading the list here, see the "load spaces" step in
  // startApp(), which runs once there is a token.
}

initSpaceSwitcher();

// --- capture templates, Settings pane (extends Wave B) ------------------------------
//
// Every template is editable, the built-ins included (INBOX 409, "templates
// cant be edited"): the persona pane's shape, where editing a built-in saves
// a copy under the same name into the same preference the person's own live
// in (`templateCatalogue`, near the Capture form, is where that copy wins),
// the row then says "Edited" and grows Reset, and Reset removes the copy.
// The server's only refusal is two saved templates with one name
// (routes_settings._validated_templates).

// Which template (by name) the editor is currently editing, if any,
// same tracking `editingSkillName` does, so Save updates in place on a
// rename instead of leaving a duplicate behind.
let editingTemplateName = null;

// The saved list as stored: the person's own templates and the edited
// built-ins together, which is what every PUT writes back.
function customTemplates() {
  return (prefsCache && prefsCache.custom_templates) || [];
}

function startEditingTemplate(template) {
  editingTemplateName = template.name;
  const name = $("template-name");
  name.value = template.name;
  //: A built-in's edit keeps the built-in's name: the name is what makes the
  //: saved copy an edit of it rather than a fifth template beside it, so the
  //: field is shown but not for typing. A person who wants a "Journal" of a
  //: different name adds their own.
  name.readOnly = Boolean(template.builtin);
  $("template-description").value = template.description || "";
  $("template-body").value = template.content;
  $("template-add").textContent = "Save changes";
  $("template-cancel").classList.remove("hidden");
  $("template-status").textContent = template.builtin
    ? `Editing the built-in “${template.name}”…`
    : `Editing “${template.name}”…`;
  (template.builtin ? $("template-body") : name).focus();
}

function stopEditingTemplate() {
  editingTemplateName = null;
  for (const id of ["template-name", "template-description", "template-body"]) {
    $(id).value = "";
  }
  $("template-name").readOnly = false;
  $("template-add").textContent = "Add template";
  $("template-cancel").classList.add("hidden");
  $("template-status").textContent = "";
}

async function saveTemplateList(templates) {
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ custom_templates: templates }),
  });
  await loadTemplates();
  renderTemplateSettings();
}

// One row in the Settings list, deliberately the same shape as `skillRow`
// (same classes, same chip-then-blurb-then-actions layout) so the two panes
// that manage a "named, user-editable list of markdown" read as one pattern
// rather than two. `textContent` throughout: template bodies are untrusted
// user text and are never rendered as HTML.
function templateRow(template) {
  const li = document.createElement("li");
  const row = document.createElement("div");
  row.className = "entry-meta skill-row";
  row.appendChild(chip(template.name, "item-title"));
  //: The persona row's two words: a shipped template that has been edited
  //: says so, and the word is what tells the reader the Reset beside it
  //: has something to restore.
  if (template.builtin) {
    row.appendChild(chip(template.overridden ? "Edited" : "Built-in", "item-label"));
  }
  const note = document.createElement("span");
  note.className = "muted skill-blurb";
  note.textContent = template.description || template.content;
  row.appendChild(note);
  const actions = document.createElement("span");
  actions.className = "entry-actions";
  actions.appendChild(
    smallButton("Edit", "Edit this template", () => startEditingTemplate(template))
  );
  if (template.builtin && template.overridden) {
    actions.appendChild(
      smallButton("Reset", "Restore the original template", async () => {
        if (editingTemplateName === template.name) stopEditingTemplate();
        await saveTemplateList(customTemplates().filter((t) => t.name !== template.name));
      })
    );
  }
  if (!template.builtin) {
    actions.appendChild(
      smallButton("Delete", "Remove this template", async () => {
        if (!(await confirmDialog(`Delete the “${template.name}” template?`))) return;
        if (editingTemplateName === template.name) stopEditingTemplate();
        await saveTemplateList(customTemplates().filter((t) => t.name !== template.name));
      })
    );
  }
  li.append(row, actions);
  return li;
}

async function renderTemplateSettings() {
  await loadTemplates();
  const list = $("template-list");
  list.replaceChildren();
  const { builtin, custom } = await templateCatalogue();
  for (const template of [...custom, ...builtin]) list.appendChild(templateRow(template));
}


// Upgrade every dropdown in the app, and keep upgrading the ones that
// appear later. Last line of the file on purpose: by here every panel this
// script builds up front exists, and the observer inside covers the rest.
watchForSelects();

//: Clicking it does the one thing its name promises, and hands the pane back
//: to the follow logic by landing at the bottom, the next `scroll` event sets
//: `data-stuck` to "1" and the stream resumes carrying the view with it.
$("chat-jump-latest")?.addEventListener("click", () => {
  const pane = $("chat-messages");
  if (!pane) return;
  pane.scrollTo({ top: pane.scrollHeight, behavior: reducedMotionWanted() ? "auto" : "smooth" });
  pane.dataset.stuck = "1";
  syncChatJumpLatest();
});

//: The panel-wide half of "mark as unread": one gesture that puts every row
//: back to read, overrides included. See `forcedUnreadIds`.
$("notif-mark-all-read")?.addEventListener("click", () => {
  prefs.set(NOTIFICATIONS_READ_KEY, String(Date.now()));
  setForcedUnreadIds(new Set());
  setForcedReadIds(new Set());
  openNotifications();
  toast("All notifications marked as read.");
});

// --- Find anything ------------------------------------------------------------
//
//: Moved to search.js, lazy (WORLD_CLASS_PLAN decision 46, Brief 47): the box
//: is fetched with its first use or a few seconds after boot (app.js
//: `LAZY_MODULES.search`), and `openFinder` is its stand-in until then.


// --- the boot kick-offs, last ------------------------------------------------
//
//: These two calls ran from the middle of app.js while it was one file
//: (initNotesSubtabs from the notification controls' wiring, initAuth after
//: the Wave F wiring), where every function they reach was already hoisted.
//: Split into files, that is no longer true: initNotesSubtabs reaches
//: activeSpaceId and loadSpaces (this file) and maybeShowOnboarding
//: (settings-wiring.js) synchronously, and initAuth's answer from
//: /auth/status can arrive between two script executions and run startApp,
//: which calls loadSpaces. So they are the last thing the last file does, when
//: every piece has been declared (appjs-split.md hazard 1). What ran after
//: them in the old order is declarations and listeners, none of which read
//: what they set up.
initNotesSubtabs();
initAuth();
