// date-field.js: the panel of a date or time field (UI_MODERNISATION_PLAN
// Phase 12 decision 5; DESIGN.md, "A date or a time in a form"). A lazy piece
// (app.js `LAZY_MODULES.dateField`): `enhanceDateField` in sheets-selects.js
// draws the face at boot and loads this on the first press. The panel is the
// help popover shell with the Timeline month pop's grid, or the day's times
// every 15 minutes in the person's clock; a typed phrase is read by
// `ai/when` (`POST /reminders/when`); Today or Now, and Clear.

(() => {
  const DATE_FIELD_DAY = 86400000;
  const dateFieldKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const dateFieldShift = (key, days) => dateFieldKey(new Date(new Date(`${key}T12:00:00`).getTime() + days * DATE_FIELD_DAY));

  function dateFieldWire(input, opener, panel, label, isTime) {
    const commit = (value) => {
      input.value = value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      closeHelpPopovers();
      opener.focus();
    };
    const button = (text, title, run, cls = "ghost small") => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = cls;
      setLabel(b, text);
      if (title) { b.title = title; b.setAttribute("aria-label", title); }
      b.addEventListener("click", run);
      return b;
    };
    const render = (month, focusKey) => {
      const today = dateFieldKey(new Date());
      const first = new Date(`${month}T00:00:00`);
      const count = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
      const title = document.createElement("span");
      title.className = "timeline-monthpop-title";
      title.setAttribute("role", "status");
      title.textContent = first.toLocaleDateString(undefined, { month: "long", year: "numeric" });
      const step = (n) => { const d = new Date(first.getFullYear(), first.getMonth() + n, 1); return dateFieldKey(d); };
      const head = document.createElement("div");
      head.className = "timeline-monthpop-head";
      head.append(
        button("ph:caret-left", "Earlier month", () => render(step(-1), null), "ghost small icon-only"),
        title,
        button("ph:caret-right", "Later month", () => render(step(1), null), "ghost small icon-only"),
      );
      const grid = document.createElement("div");
      grid.className = "timeline-monthpop-grid";
      grid.setAttribute("role", "group");
      grid.setAttribute("aria-label", title.textContent);
      for (let i = 0; i < 7; i += 1) {
        const name = document.createElement("span");
        name.className = "timeline-monthpop-dow";
        name.setAttribute("aria-hidden", "true");
        name.textContent = new Date(2024, 0, 1 + i).toLocaleDateString(undefined, { weekday: "narrow" });
        grid.appendChild(name);
      }
      for (let i = (first.getDay() + 6) % 7; i > 0; i -= 1) grid.appendChild(document.createElement("span"));
      const ym = month.slice(0, 7);
      const picked = input.value;
      const stop = focusKey?.startsWith(ym) ? focusKey : picked.startsWith(ym) ? picked : today.startsWith(ym) ? today : `${ym}-01`;
      for (let n = 0; n < count; n += 1) {
        const key = dateFieldShift(month, n);
        const day = button(String(n + 1), "", () => commit(key), "ghost small timeline-monthday");
        day.dataset.key = key;
        day.disabled = (input.min && key < input.min) || (input.max && key > input.max);
        day.classList.toggle("is-today", key === today);
        day.classList.toggle("is-in-strip", key === picked);
        day.setAttribute("aria-pressed", key === picked ? "true" : "false");
        day.setAttribute("aria-label", new Date(`${key}T00:00:00`).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" }));
        day.tabIndex = key === stop ? 0 : -1;
        grid.appendChild(day);
      }
      panel.replaceChildren(head, grid, foot());
      if (focusKey) grid.querySelector(`[data-key="${focusKey}"]`)?.focus({ preventScroll: true });
    };
    const renderTimes = () => {
      const grid = document.createElement("div");
      grid.className = "timeline-monthpop-grid";
      grid.setAttribute("role", "group");
      grid.setAttribute("aria-label", label);
      grid.style.gridTemplateColumns = "repeat(4, minmax(0, 1fr))";
      grid.style.overflowY = "auto";
      grid.style.maxHeight = "15rem";
      const picked = input.value.slice(0, 5);
      for (let minutes = 0; minutes < 1440; minutes += 15) {
        const value = `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
        const b = button(dateFieldFace(value, true), "", () => commit(value), "ghost small timeline-monthday");
        b.dataset.key = value;
        b.classList.toggle("is-in-strip", value === picked);
        b.setAttribute("aria-pressed", value === picked ? "true" : "false");
        grid.appendChild(b);
      }
      panel.replaceChildren(grid, foot());
    };
    const foot = () => {
      const typed = document.createElement("input");
      typed.type = "text";
      typed.placeholder = isTime ? "Type a time, like 3pm" : "Type a day, like next friday";
      typed.setAttribute("aria-label", typed.placeholder);
      const status = document.createElement("p");
      status.className = "status";
      status.setAttribute("role", "status");
      typed.addEventListener("keydown", async (event) => {
        if (event.key !== "Enter" || !typed.value.trim()) return;
        event.preventDefault();
        try {
          const at = await apiJson("/reminders/when", {
            method: "POST",
            body: JSON.stringify({ text: typed.value.trim(), tz_offset_minutes: -new Date().getTimezoneOffset() }),
          });
          commit(isTime ? at.time : at.date);
        } catch (error) {
          status.textContent = error.message || "I couldn't read a date or time from that.";
        }
      });
      const row = document.createElement("div");
      row.className = "timeline-monthpop-head";
      const now = new Date();
      row.append(
        button(isTime ? "Now" : "Today", "", () => commit(isTime ? `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}` : dateFieldKey(now))),
        button("Clear", "", () => commit("")),
      );
      const wrap = document.createElement("div");
      wrap.append(typed, status, row);
      return wrap;
    };
    wireHelpPopover(opener, panel);
    opener.addEventListener("click", () => {
      if (opener.getAttribute("aria-expanded") === "true") return;
      if (isTime) renderTimes();
      else render(`${(input.value || dateFieldKey(new Date())).slice(0, 7)}-01`, null);
      setTimeout(() => {
        const at = panel.querySelector('.timeline-monthday[tabindex="0"], .timeline-monthday[aria-pressed="true"]');
        if (at) { at.focus({ preventScroll: true }); at.scrollIntoView?.({ block: "nearest" }); }
        else panel.querySelector(".timeline-monthday")?.focus({ preventScroll: true });
      }, 0);
    }, true);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { opener.focus(); return; }
      const current = document.activeElement?.closest?.(".timeline-monthday");
      if (!current || !panel.contains(current)) return;
      const key = current.dataset.key;
      if (isTime) {
        const all = [...panel.querySelectorAll(".timeline-monthday")];
        const moves = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -4, ArrowDown: 4 };
        if (!(event.key in moves)) return;
        event.preventDefault();
        all[Math.max(0, Math.min(all.length - 1, all.indexOf(current) + moves[event.key]))].focus();
        return;
      }
      const weekday = (new Date(`${key}T00:00:00`).getDay() + 6) % 7;
      const moves = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7, Home: -weekday, End: 6 - weekday };
      let target = null;
      if (event.key in moves) target = dateFieldShift(key, moves[event.key]);
      else if (event.key === "PageUp" || event.key === "PageDown") {
        const d = new Date(`${key}T12:00:00`);
        d.setMonth(d.getMonth() + (event.key === "PageUp" ? -1 : 1));
        target = dateFieldKey(d);
      }
      if (!target) return;
      event.preventDefault();
      if (target.slice(0, 7) === key.slice(0, 7)) {
        for (const day of panel.querySelectorAll(".timeline-monthday")) day.tabIndex = day.dataset.key === target ? 0 : -1;
        panel.querySelector(`[data-key="${target}"]`)?.focus();
      } else render(`${target.slice(0, 7)}-01`, target);
    });
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { dateFieldWire });
})();
