// quick-access.js: arranging the dashboard's Quick access row (INBOX 461).
//
// Lazy (app.js, `LAZY_MODULES.quickAccess`): the row itself, the stored list
// and the Customise and Reset menu are dashboard.js; this is the editing view
// and the picker, which only a person who customises ever needs. Entered
// through `quickAccessEdit`, a `LAZY_ENTRY_POINTS` stand-in, from
// `renderQuickLinks` while `quickEditing` is set.
//
// The view is the row itself with a ⋯ menu beside each tile (Move left, Move
// right, Remove: the keyboard's route to reordering, which is also what a
// phone uses) and the tiles draggable on a pointer, using the dashboard
// widgets' own `dashDragOverCard`. A tile's own press is switched off while
// editing: a tile that opens a feature when you meant to arrange it is the
// mistake this mode exists to avoid.
//
// Adding, removing and ordering several at once is the manager
// (`quickAccessManage`, below): every command the palette has that declares a
// place to go and says a line about itself, as one checkable list with what is
// already a tile checked and first, in order.

function quickAccessLeave() {
  quickEditing = false;
  renderQuickLinks();
}

//: Save, redraw, and put the focus back on the control that was used: the
//: redraw replaces every node, and a keyboard user who moved a tile would
//: otherwise land on the page's top.
async function quickAccessCommit(ids, focusId = "") {
  await saveQuickAccess(ids);
  await quickAccessEdit();
  const spot = focusId && $("dash-quicklinks")?.querySelector(`[data-id="${CSS.escape(focusId)}"] .menu-wrap button`);
  (spot || $("dash-quicklinks")?.querySelector(".quick-edit-add"))?.focus();
}

function quickAccessTile(link, index, ids, row) {
  const wrap = document.createElement("div");
  wrap.className = "quick-edit-tile";
  wrap.dataset.id = link.id;
  wrap.draggable = true;
  const tile = quickLinkButton({ ...link, run: () => {} }, quickTintKey(link.id, index, quickTints()));
  tile.tabIndex = -1;
  tile.setAttribute("aria-disabled", "true");
  const move = (by) => {
    const next = [...ids];
    const [taken] = next.splice(index, 1);
    next.splice(index + by, 0, taken);
    return quickAccessCommit(next, link.id);
  };
  const menu = kebabMenu(
    [
      { label: "ph:arrow-left Move left", title: `Move ${link.label} one place left`, group: "move", disabled: index === 0, run: () => index > 0 && move(-1) },
      { label: "ph:arrow-right Move right", title: `Move ${link.label} one place right`, group: "move", disabled: index === ids.length - 1, run: () => index < ids.length - 1 && move(1) },
      { label: "ph:palette Highlight", title: `Choose a colour for ${link.label}, or none`, group: "look", run: () => quickAccessPickTint(link, index) },
      { label: "ph:trash Remove", title: `Take ${link.label} off this row`, group: "remove", disabled: ids.length < 2, run: () => ids.length > 1 && quickAccessCommit(ids.filter((id) => id !== link.id)) },
    ],
    `${link.label}: arrange`,
  );
  wrap.append(tile, menu);
  wrap.addEventListener("dragstart", () => wrap.classList.add("dragging"));
  wrap.addEventListener("dragend", () => {
    wrap.classList.remove("dragging");
    const order = [...row.querySelectorAll(".quick-edit-tile")].map((el) => el.dataset.id);
    if (order.join() !== ids.join()) quickAccessCommit(order, link.id);
  });
  wrap.addEventListener("dragover", (event) => {
    event.preventDefault();
    const dragged = row.querySelector(".dragging");
    if (dragged && dragged !== wrap) dashDragOverCard(event, wrap, dragged, row);
  });
  return wrap;
}

//: **A tile's highlight** (INBOX 589): DESIGN.md's swatch picker in a sheet,
//: under a preview that is the tile itself, repainted as the arrows move the
//: check. The accent first, then the twelve category hues, then "No
//: highlight". Checked is what the tile shows now, a stored choice or its
//: position's default; whatever is picked is stored, so the first tile set to
//: "No highlight" stays plain wherever it goes.
async function quickAccessPickTint(link, index) {
  //: The picker lives with the Manage categories panel (lazy).
  if (typeof swatchPicker !== "function" && !(await ensureModule("categories"))) return;
  const before = quickTintKey(link.id, index, quickTints());
  const palette = { accent: "var(--accent)", ...CATEGORY_PALETTE };
  openSheet({
    label: `Highlight for ${link.label}`,
    sub: "A colour for this tile. The first tile has the accent until you choose.",
    name: "quick-tint",
    build: (card, close) => {
      card.classList.add("swatch-card", "quick-tint-card");
      const slot = document.createElement("div");
      slot.className = "quick-tint-preview";
      const show = (key) => {
        const tile = quickLinkButton({ ...link, run: () => {} }, key || "");
        tile.tabIndex = -1;
        tile.setAttribute("aria-hidden", "true");
        slot.replaceChildren(tile);
      };
      const picker = swatchPicker({
        label: `Highlight for ${link.label}`,
        value: before || null,
        palette,
        none: "No highlight",
        onChange: show,
        onChoose: async (key) => {
          close();
          if ((key || "") === before) return;
          await saveQuickTint(link.id, key || "none");
          await quickAccessEdit();
          $("dash-quicklinks")?.querySelector(`[data-id="${CSS.escape(link.id)}"] .menu-wrap button`)?.focus();
        },
      });
      card.append(slot, picker);
      requestAnimationFrame(() => picker.querySelector('[tabindex="0"]')?.focus());
    },
  });
}

async function quickAccessEdit() {
  const box = $("dash-quicklinks");
  if (!box) return;
  const items = quickAccessCurrent();
  const ids = items.map((link) => link.id);
  const heading = document.createElement("p");
  heading.className = "launch-label";
  heading.textContent = "Quick access";
  const count = document.createElement("span");
  count.className = "muted launch-count";
  count.textContent = `${ids.length} of ${QUICK_ACCESS_MAX}`;
  const done = smallButton("ph:check Done", "Finish arranging", quickAccessLeave);
  done.classList.add("launch-done");
  const head = document.createElement("div");
  head.className = "launch-head";
  head.append(heading, count, done);

  const row = document.createElement("div");
  row.className = "launch-row launch-row-start quick-edit-row";
  items.forEach((link, index) => row.appendChild(quickAccessTile(link, index, ids, row)));
  //: Always offered, even with the row full: the manager is also where one
  //: tile is swapped for another.
  const add = quickLinkButton({ icon: "ph:squares-four", label: "Add or arrange", hint: "Check, drag and order every command", run: () => quickAccessManage(ids) });
  add.classList.add("quick-edit-add");
  row.appendChild(add);
  const group = document.createElement("div");
  group.className = "launch-group";
  group.append(head, row);
  box.replaceChildren(group);
}

//: **The manager** (INBOX 524: "it is hard to tell which ones are already added
//: and I can only add one at a time, I want it to have the ability to add or
//: remove or rearrange multiple of them"). One list, two groups: what is on the
//: dashboard (checked, in order, draggable) and every other command (unchecked).
//: A tick adds or removes in the draft and nothing is saved until Done, so
//: several can be changed in one visit; the search narrows both groups and
//: stays while you work. Reordering is by drag, by Alt+Up and Alt+Down on a
//: row, and by the two small buttons on it (a drag alone is not enough: WCAG
//: 2.5.7). The rows are the Attach picker's (`note-picker-*`: a check ring at
//: the right edge, the accent's soft fill on a row that is on) and the list is
//: one tab stop that the arrow keys walk.

//: `id` swapped with its neighbour `by` places away among the rows you can see
//: (`visible`, in order), in the full `draft`. A search that hides the tile
//: between two does not make the move do nothing.
function quickAccessMoved(draft, visible, id, by) {
  const at = visible.indexOf(id);
  const other = visible[at + by];
  if (at < 0 || other === undefined) return draft;
  const next = [...draft];
  const a = next.indexOf(id);
  const b = next.indexOf(other);
  [next[a], next[b]] = [next[b], next[a]];
  return next;
}

//: A drag puts the visible tiles in `order` into the slots the visible tiles
//: held, so the tiles a search is hiding keep their places.
function quickAccessReslotted(draft, order) {
  const slots = draft.map((id, i) => (order.includes(id) ? i : -1)).filter((i) => i >= 0);
  const next = [...draft];
  slots.forEach((slot, i) => {
    next[slot] = order[i];
  });
  return next;
}

function quickAccessManage(ids) {
  const current = quickAccessCurrent();
  const catalogue = quickCatalogue();
  const known = new Map([...current.map((link) => [link.id, link]), ...catalogue]);
  //: What can be added: the five defaults (so a removed one can come back) and
  //: the catalogue, one row per name, so New note is not offered twice.
  const offered = [];
  const seen = new Set();
  for (const link of [...QUICK_START, ...catalogue.values()]) {
    const name = link.label.toLowerCase();
    if (seen.has(name)) continue;
    seen.add(name);
    offered.push(link);
  }
  let draft = [...ids];
  const names = () => new Set(draft.map((id) => known.get(id)?.label.toLowerCase()).filter(Boolean));
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay confirm-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", "Quick access");
  const card = document.createElement("div");
  card.className = "card modal-card space-dialog library-create-picker quick-pick";
  const head = document.createElement("div");
  head.className = "dialog-head";
  const title = document.createElement("h2");
  title.className = "dialog-head-title";
  title.textContent = "Quick access";
  const actions = document.createElement("span");
  actions.className = "dialog-head-actions";
  const returnFocus = document.activeElement;
  const close = () => {
    document.removeEventListener("keydown", onKey, true);
    overlay.remove();
    returnFocus?.isConnected && returnFocus.focus?.();
  };
  const onKey = (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      close();
    }
  };
  const x = smallButton("ph:x", "Close", close);
  x.classList.add("icon-only", "dialog-head-btn");
  actions.appendChild(x);
  head.append(title, actions);
  const about = document.createElement("p");
  about.className = "muted quick-manage-about";
  about.textContent = `Check the commands you want on your dashboard, up to ${QUICK_ACCESS_MAX}. Drag a row, or press Alt with Up or Down, to put them in order.`;
  const search = document.createElement("input");
  search.type = "search";
  search.className = "quick-pick-search";
  search.placeholder = "Search commands";
  search.setAttribute("aria-label", "Search commands");
  const live = document.createElement("div");
  live.className = "visually-hidden";
  live.setAttribute("aria-live", "polite");
  const scroll = document.createElement("div");
  scroll.className = "quick-manage-scroll";
  const onHead = document.createElement("p");
  onHead.className = "quick-manage-group";
  const onList = document.createElement("ul");
  onList.className = "quick-manage-list";
  onList.setAttribute("role", "list");
  onList.setAttribute("aria-label", "On your dashboard");
  const moreHead = document.createElement("p");
  moreHead.className = "quick-manage-group";
  moreHead.textContent = "More commands";
  const moreList = document.createElement("ul");
  moreList.className = "quick-manage-list";
  moreList.setAttribute("role", "list");
  moreList.setAttribute("aria-label", "More commands");
  const none = document.createElement("p");
  none.className = "muted quick-pick-empty";
  none.textContent = "No command matches that.";
  scroll.append(onHead, onList, moreHead, moreList, none);
  const caution = document.createElement("p");
  caution.className = "notice notice-warn quick-manage-warn";
  caution.setAttribute("role", "status");
  caution.hidden = true;
  const warn = (text) => {
    caution.textContent = text;
    caution.hidden = !text;
  };
  const foot = document.createElement("div");
  foot.className = "row space-dialog-actions quick-manage-foot";
  const count = document.createElement("span");
  count.className = "muted quick-manage-count";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "ghost small";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", close);
  const done = document.createElement("button");
  done.type = "button";
  done.className = "accent small";
  done.textContent = "Done";
  done.addEventListener("click", () => {
    close();
    if (draft.join() !== ids.join()) quickAccessCommit(draft);
  });
  foot.append(count, cancel, done);

  const visibleOn = () => [...onList.children].map((li) => li.dataset.id);
  const boxOf = (id) => overlay.querySelector(`[data-id="${CSS.escape(id)}"] .note-picker-box`);
  const restFocus = () => {
    const boxes = [...scroll.querySelectorAll(".note-picker-box")];
    const lit = boxes.find((box) => box === document.activeElement) || boxes[0];
    boxes.forEach((box) => (box.tabIndex = box === lit ? 0 : -1));
  };
  const tell = (text) => {
    live.textContent = "";
    live.textContent = text;
  };
  const move = (id, by) => {
    const next = quickAccessMoved(draft, visibleOn(), id, by);
    if (next.join() === draft.join()) return;
    draft = next;
    draw();
    boxOf(id)?.focus();
    tell(`${known.get(id).label}: ${draft.indexOf(id) + 1} of ${draft.length}`);
  };
  const row = (link, on, index, total, needle) => {
    const li = document.createElement("li");
    li.className = "quick-manage-item";
    li.dataset.id = link.id;
    const label = document.createElement("label");
    label.className = "note-picker-row";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.className = "visually-hidden note-picker-box";
    box.checked = on;
    box.addEventListener("change", () => {
      //: A refusal is the form saying what it can hold, not a fault: a line
      //: in the dialog (a `.notice-warn`), never an error toast with Report this.
      if (box.checked && draft.length >= QUICK_ACCESS_MAX) {
        box.checked = false;
        warn(`Quick access holds ${QUICK_ACCESS_MAX}. Uncheck one first.`);
        return;
      }
      if (!box.checked && draft.length < 2) {
        box.checked = true;
        warn("Quick access keeps at least one.");
        return;
      }
      warn("");
      draft = box.checked ? [...draft, link.id] : draft.filter((id) => id !== link.id);
      //: The row changes lists, so it lands far from where it was; the list
      //: stays where it is (INBOX 904 B13: focusing it scrolled to it, and a
      //: second untick meant scrolling back up).
      const top = scroll.scrollTop;
      draw();
      boxOf(link.id)?.focus({ preventScroll: true });
      scroll.scrollTop = top;
      tell(`${link.label}: ${box.checked ? "added" : "removed"}, ${draft.length} of ${QUICK_ACCESS_MAX}`);
    });
    const lines = document.createElement("span");
    lines.className = "note-picker-lines";
    const name = document.createElement("span");
    name.className = "note-picker-text";
    richPickerFillLabel(name, link.label, needle);
    const meta = document.createElement("span");
    meta.className = "note-picker-meta";
    meta.textContent = link.hint || "";
    lines.append(name, meta);
    const check = document.createElement("span");
    check.className = "note-picker-check";
    check.setAttribute("aria-hidden", "true");
    const tick = document.createElement("i");
    tick.className = "ph ph-check";
    check.appendChild(tick);
    label.append(box, richPickerTile({ icon: link.icon }), lines, check);
    //: Every row carries the grip and move lanes, empty on a row that is not
    //: on the dashboard, so both groups end at the same right edge.
    li.draggable = on;
    const grip = document.createElement("span");
    grip.className = "quick-manage-grip";
    grip.setAttribute("aria-hidden", "true");
    const dots = document.createElement("i");
    dots.className = "ph ph-dots-six-vertical";
    grip.appendChild(dots);
    const moves = document.createElement("span");
    moves.className = "quick-manage-moves";
    if (!on) {
      grip.classList.add("is-idle");
      moves.setAttribute("aria-hidden", "true");
      li.append(grip, label, moves);
      return li;
    }
    for (const [by, icon, word] of [[-1, "ph:caret-up", "up"], [1, "ph:caret-down", "down"]]) {
      const button = smallButton(icon, `Move ${link.label} ${word}`, () => move(link.id, by));
      button.classList.add("icon-only", "quick-manage-move");
      button.tabIndex = -1;
      button.disabled = by < 0 ? index === 0 : index === total - 1;
      moves.appendChild(button);
    }
    li.append(grip, label, moves);
    li.addEventListener("dragstart", (event) => {
      li.classList.add("dragging");
      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", link.label);
      }
    });
    li.addEventListener("dragend", () => {
      li.classList.remove("dragging");
      const next = quickAccessReslotted(draft, visibleOn());
      if (next.join() !== draft.join()) {
        draft = next;
        tell(`${link.label}: ${draft.indexOf(link.id) + 1} of ${draft.length}`);
      }
      draw();
      boxOf(link.id)?.focus();
    });
    return li;
  };
  onList.addEventListener("dragover", (event) => {
    event.preventDefault();
    const dragged = onList.querySelector(".dragging");
    const over = event.target.closest?.(".quick-manage-item");
    if (!dragged || !over || over === dragged) return;
    const box = over.getBoundingClientRect();
    onList.insertBefore(dragged, event.clientY < box.top + box.height / 2 ? over : over.nextSibling);
  });
  const draw = () => {
    const needle = search.value.trim().toLowerCase();
    const fits = (link) => !needle || `${link.label} ${link.hint || ""}`.toLowerCase().includes(needle);
    const on = draft.map((id) => known.get(id)).filter((link) => link && fits(link));
    const taken = names();
    const more = offered.filter((link) => !draft.includes(link.id) && !taken.has(link.label.toLowerCase()) && fits(link));
    onList.replaceChildren(...on.map((link, i) => row(link, true, i, on.length, needle)));
    moreList.replaceChildren(...more.map((link) => row(link, false, 0, 0, needle)));
    onHead.textContent = `On your dashboard · ${draft.length} of ${QUICK_ACCESS_MAX}`;
    onHead.hidden = onList.hidden = !on.length;
    moreHead.hidden = moreList.hidden = !more.length;
    none.hidden = Boolean(on.length || more.length);
    count.textContent = draft.join() === ids.join() ? "No changes" : `${draft.length} of ${QUICK_ACCESS_MAX} on your dashboard`;
    restFocus();
  };
  search.addEventListener("input", () => {
    warn("");
    draw();
  });
  search.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      scroll.querySelector(".note-picker-box")?.focus();
    }
  });
  scroll.addEventListener("keydown", (event) => {
    const boxes = [...scroll.querySelectorAll(".note-picker-box")];
    const at = boxes.indexOf(document.activeElement);
    if (at < 0) return;
    const id = document.activeElement.closest(".quick-manage-item")?.dataset.id;
    if ((event.key === "ArrowUp" || event.key === "ArrowDown") && event.altKey) {
      event.preventDefault();
      if (draft.includes(id)) move(id, event.key === "ArrowUp" ? -1 : 1);
      return;
    }
    const to = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: boxes.length - 1 }[event.key];
    if (to === undefined) {
      if (event.key === "Enter") {
        event.preventDefault();
        done.click();
      }
      return;
    }
    event.preventDefault();
    if (to < 0) return search.focus();
    boxes[Math.min(to, boxes.length - 1)]?.focus();
  });
  scroll.addEventListener("focusin", restFocus);
  draw();
  card.append(head, about, search, live, scroll, caution, foot);
  overlay.appendChild(card);
  wireBackdropClose(overlay, close);
  document.addEventListener("keydown", onKey, true);
  document.body.appendChild(overlay);
  search.focus();
}

//: One tile's highlight, saved; `""` forgets the choice (the position's
//: default again). Ids no longer on the row are pruned on the way, so the
//: stored map never outlives the tiles it was for.
async function saveQuickTint(id, key) {
  const on = new Set(quickAccessCurrent().map((link) => link.id));
  const next = Object.fromEntries(Object.entries(quickTints()).filter(([tile]) => on.has(tile) && tile !== id));
  if (key) next[id] = key;
  await saveQuickTints(next);
}
