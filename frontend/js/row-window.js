// row-window.js: `windowRows`, the one windowed list Notes and the Timeline both draw into.
// Moved out of notes-list.js whole (its size cap, L-world-class-873); a classic boot script
// loaded just before it, so every caller finds it.

(() => {
  //: **One windowed list, for Notes and the Timeline** (audit 1029 N9, audit 1028
  //: S16 and S53). `renderIncrementally` (library.js) only ever added: a list
  //: scrolled to its end held every card, 300 notes 12,126 elements, and the
  //: Timeline's own paging did the same with 8 elements a row, 27,500 nodes at
  //: 2,000 rows. Here every row is an empty `<li class="row-shell">` holding its
  //: place (its key, the height it last drew at), and only the rows within
  //: `ROW_WINDOW_MARGIN` of the scroller's window are built; a built row that is
  //: `ROW_WINDOW_FAR` past the window becomes a shell again once the scroll
  //: settles. A shell is one element, so a notebook costs one node a row plus
  //: the screenful. The keyboard builds the row it moves to (`fill`), the
  //: selection lives in `selectedIds` and not in the rows, and a row being
  //: edited, holding focus, open or with a menu open is never hollowed
  //: (`stays`), nor the one Tab stop. One instance serves any number of lists (the Timeline has a
  //: list a day) and `add` appends, which is how a page of the Timeline lands.
  //: **Runs** (`o.run`, L-world-class-873): a shell is still an element the browser
  //: styles and lays out on every show of the tab, 4,380 of them on a 4,628-note
  //: Notes switch (74 to 100ms of style). Rows that are not built land as one
  //: `row-run` spacer per `o.run` rows, as tall as the shells it stands for; a
  //: run that nears the window opens into its shells, and far shells fold back
  //: into runs once the scroll settles. A run has no key, so a lookup by key goes
  //: through `rowFor`, which opens the run holding it.
  const ROW_WINDOW_MARGIN = "1200px 0px";
  const ROW_WINDOW_BATCH = 6;
  const ROW_WINDOW_FAR = 3000;
  const ROW_WINDOW_CARRY = ["rail-subject", "flash"];

  //: A row's carried state (focus place, rail subject, flash) moves onto what replaces it.
  function rowWindowCarry(to, from) {
    if (!from) return to;
    to.tabIndex = from.tabIndex;
    for (const name of ROW_WINDOW_CARRY) if (from.classList.contains(name)) to.classList.add(name);
    return to;
  }

  //: `o.shell` names the shell's tag: a `<tbody>` takes `tr` (L491, the Timeline table).
  //: Hidden inline, not by a rule: the boot stylesheets are at their cap.
  function rowWindowShellEl(o, item) {
    const li = document.createElement(o.shell || "li");
    li.className = "row-shell";
    li.setAttribute("aria-hidden", "true");
    li.style.cssText = `visibility:hidden;height:${o.heights.get(o.keyOf(item)) || o.guess}px`;
    li.tabIndex = -1;
    o.tag(li, item);
    return li;
  }

  //: One spacer for rows `i` to `to - 1`, as tall as their shells would be.
  //: `o.gap` is the space between two rows (a margin, so not in their heights).
  function rowWindowRunEl(o, items, i, to) {
    const li = document.createElement(o.shell || "li");
    li.className = "row-shell row-run";
    li.setAttribute("aria-hidden", "true");
    let height = 0;
    for (let k = i; k < to; k++) height += o.heights.get(o.keyOf(items[k])) || o.guess;
    const gaps = o.gap && to - i > 1 ? ` + ${to - i - 1} * ${o.gap}` : "";
    li.style.cssText = `visibility:hidden;height:calc(${height}px${gaps})`;
    li.tabIndex = -1;
    li.dataset.run = to - i;
    return li;
  }

  //: The built rows over ROW_WINDOW_FAR from the window, with their heights (dropping the gone ones
  //: from `live`): all read before any is replaced.
  function rowWindowFarRows(live, box, stays) {
    const far = [];
    for (const li of live) {
      if (!li.isConnected) live.delete(li);
      else if (li.tabIndex !== 0 && !stays(li)) {
        const r = li.getBoundingClientRect();
        if (r.bottom < box.top - ROW_WINDOW_FAR || r.top > box.bottom + ROW_WINDOW_FAR) far.push([li, r.height]);
      }
    }
    return far;
  }

  //: Unbuilt rows `from` to `to - 1` as spacers of `size` rows: `spacer(k, end)` makes each.
  function rowWindowSpacers(size, from, to, spacer) {
    const out = [];
    for (let k = from; k < to; k += size) out.push(spacer(k, Math.min(k + size, to)));
    return out;
  }

  //: Far shells and runs side by side, in groups of two or more: the window folds each back into runs,
  //: so a list scrolled end to end goes back to a few dozen spacers. Positions first, one layout.
  function rowWindowFoldGroups(list, box, known) {
    const far = (el) => {
      const r = el.getBoundingClientRect();
      return r.bottom < box.top - ROW_WINDOW_FAR || r.top > box.bottom + ROW_WINDOW_FAR;
    };
    const free = (el) => el.classList.contains("row-shell") && el.tabIndex !== 0
      && !ROW_WINDOW_CARRY.some((name) => el.classList.contains(name)) && known(el);
    const groups = [];
    let group = [];
    for (const el of list.children) {
      if (free(el) && far(el)) group.push(el);
      else { if (group.length > 1) groups.push(group); group = []; }
    }
    if (group.length > 1) groups.push(group);
    return groups;
  }

  //: Inside `windowRows`: a run opens into its shells and the observer builds the ones in the window;
  //: `rowFor(key)` opens the run holding a row first. A shell is hidden, so it cannot take focus: the
  //: keyboard (Home, End, the arrows) has `fill` build the row it moves to first (a run's last when
  //: coming from below), and `fillRun` builds the few rows beyond it too (a few rows in one frame cost
  //: less than a row in every frame of a scroll). Rows are emptied once the scroll settles, never on
  //: the frame they left: a row read a moment ago and scrolled back to is kept, and every position is
  //: read before any row is replaced, so it is one layout. `add(list, more, now)`: `now(item, i)` says
  //: which rows are built as they land, the rest are shells, or runs of `o.run` (a lone row stays a shell).
  function windowRows(root, o) {
    const info = new WeakMap(); // row -> { items, i }
    const lists = new WeakMap(); // list -> its items
    const live = new Set(); // rows built now
    const runs = new Set(); // run spacers now
    const els = new Map(); // key -> its row or shell now
    const owned = new Set(); // lists this window serves
    let timer = 0;
    let off = false;
    const carry = rowWindowCarry;
    const shellFor = (items, i, from) => {
      const li = rowWindowShellEl(o, items[i]);
      info.set(li, { items, i });
      els.set(o.keyOf(items[i]), li);
      return carry(li, from);
    };
    const make = (items, i, from) => {
      const li = carry(o.build(items[i], i), from);
      info.set(li, { items, i });
      els.set(o.keyOf(items[i]), li);
      live.add(li);
      observer.observe(li);
      return li;
    };
    const runFor = (items, i, to) => {
      const li = rowWindowRunEl(o, items, i, to);
      info.set(li, { items, i, to });
      runs.add(li);
      observer.observe(li);
      return li;
    };
    function open(run) {
      const at = info.get(run);
      runs.delete(run);
      observer.unobserve(run);
      if (!at || !run.parentElement) return [];
      const shells = [];
      for (let k = at.i; k < at.to; k++) {
        const shell = shellFor(at.items, k);
        observer.observe(shell);
        shells.push(shell);
      }
      run.replaceWith(...shells);
      return shells;
    }
    function rowFor(key) {
      const el = els.get(key);
      if (el?.isConnected) return el;
      for (const run of runs) {
        const at = info.get(run);
        if (!run.isConnected) { runs.delete(run); continue; }
        for (let k = at.i; k < at.to; k++) if (o.keyOf(at.items[k]) === key) { open(run); return els.get(key) || null; }
      }
      return null;
    }
    const spacers = (items, from, to) => rowWindowSpacers(o.run, from, to, (k, end) => (end - k > 1 ? runFor(items, k, end) : observed(shellFor(items, k))));
    function fill(shell, last = false) {
      if (runs.has(shell)) {
        const opened = open(shell);
        if (!opened.length) return shell;
        shell = opened[last ? opened.length - 1 : 0];
      }
      const at = info.get(shell);
      if (!at || !shell.classList.contains("row-shell") || !shell.parentElement) return shell;
      const li = make(at.items, at.i, shell);
      shell.replaceWith(li);
      o.onFill?.(li);
      return li;
    }
    function fillRun(target, up) {
      const run = [target];
      const step = up ? "previousElementSibling" : "nextElementSibling";
      for (let el = target[step]; el?.classList.contains("row-shell") && !runs.has(el) && run.length < ROW_WINDOW_BATCH; el = el[step]) run.push(el);
      for (const shell of run) fill(shell);
    }
    function settle() {
      if (off) return;
      const box = root ? root.getBoundingClientRect() : { top: 0, bottom: innerHeight };
      for (const [li, height] of rowWindowFarRows(live, box, o.stays)) {
        const at = info.get(li);
        if (height) o.heights.set(o.keyOf(at.items[at.i]), height);
        const shell = shellFor(at.items, at.i, li);
        li.replaceWith(shell);
        live.delete(li);
        observer.observe(shell);
      }
      if (o.run) for (const list of owned) fold(list, box);
      o.onSettle?.();
    }
    function fold(list, box) {
      if (!list.isConnected) return owned.delete(list);
      for (const g of rowWindowFoldGroups(list, box, (el) => info.has(el))) {
        if (g.every((el) => runs.has(el)) && g.length <= Math.ceil(g.reduce((n, el) => n + Number(el.dataset.run), 0) / o.run)) continue;
        const first = info.get(g[0]);
        const last = info.get(g[g.length - 1]);
        for (const el of g) { runs.delete(el); observer.unobserve(el); }
        g[0].before(...spacers(first.items, first.i, last.to ?? last.i + 1));
        for (const el of g) el.remove();
      }
    }
    const observer = new IntersectionObserver((seen) => {
      if (off) return;
      for (const { target, isIntersecting, boundingClientRect, rootBounds } of seen) {
        const at = info.get(target);
        if (!at || !target.parentElement) continue;
        if (!target.classList.contains("row-shell")) {
          if (boundingClientRect.height) o.heights.set(o.keyOf(at.items[at.i]), boundingClientRect.height);
        } else if (isIntersecting && runs.has(target)) open(target);
        else if (isIntersecting) fillRun(target, rootBounds && boundingClientRect.top < rootBounds.top);
      }
      clearTimeout(timer);
      timer = setTimeout(settle, 300);
    }, { root, rootMargin: ROW_WINDOW_MARGIN });
    function add(list, more, now = () => false) {
      const items = lists.get(list) || [];
      lists.set(list, items);
      const from = items.length;
      for (const item of more) items.push(item);
      owned.add(list);
      const fragment = document.createDocumentFragment();
      let gap = -1; // first unbuilt row of the stretch being gathered
      const close = (to) => {
        if (gap < 0) return;
        if (o.run) fragment.append(...spacers(items, gap, to));
        else for (let k = gap; k < to; k++) fragment.appendChild(observed(shellFor(items, k)));
        gap = -1;
      };
      more.forEach((item, k) => {
        const i = from + k;
        if (!now(item, i)) { if (gap < 0) gap = i; return; }
        close(i);
        fragment.appendChild(make(items, i));
      });
      close(items.length);
      list.appendChild(fragment);
    }
    const observed = (el) => (observer.observe(el), el);
    function stop() {
      off = true;
      observer.disconnect();
      clearTimeout(timer);
      runs.clear();
      els.clear();
      owned.clear();
    }
    const keys = (list) => (lists.get(list) || []).map(o.keyOf);
    return { add, fill, rowFor, keys, stop };
  }

  Object.assign(window, { windowRows });
})();
