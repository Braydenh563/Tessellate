// whiteboard-map-more.js: two things a topic gains beyond its words, in one lazy
// file (a second file would cost the boot script's gzipped list another path).
//
// 1. The Gantt view: a Gantt view of a map's dated topics (MINDMAP_PLAN
// gap 3, XMind). A topic with both a start day and a due day (the Markers
// popover's Start and Due, `wbMapMarkerParts`) is drawn as a bar between them
// on one shared day scale, in start order. A topic with only one of the two
// has no length, so it is counted under the chart rather than drawn.
//
// The bars move the dates, not a copy of them: drag a bar, or press the left
// and right arrows on it (Shift for a week), and both days move together
// through `wbMapSetNodeStyle`, so each move is one Undo step on the board and
// the sheet's own Undo button is the board's Undo. Enter or a press without a
// drag shows the topic on the map.
//
// 2. An audio note on a topic (MINDMAP_PLAN gap 4, decided 2026-11-10): see
// "The audio note" below.
//
// Loaded in the Library bundle after whiteboard-map.js (`LAZY_MODULES`); the
// map calls both through `wbMapLazy`.

(() => {
  const WB_GANTT_DAY = 86400000;

  //: "2026-10-05" as a whole number of days since 1970, in UTC so a daylight
  //: saving change can never make a day 23 or 25 hours long.
  function wbGanttDayNumber(text) {
    const [y, m, d] = text.split("-").map(Number);
    return Date.UTC(y, m - 1, d) / WB_GANTT_DAY;
  }

  function wbGanttDayText(day) {
    return new Date(day * WB_GANTT_DAY).toISOString().slice(0, 10);
  }

  //: The patch that moves a topic's whole span by `days`.
  function wbGanttShift(data, days) {
    return {
      start: wbGanttDayText(wbGanttDayNumber(data.start) + days),
      due: wbGanttDayText(wbGanttDayNumber(data.due) + days),
    };
  }

  //: The bars, in start order (then due day, then id), and what was left out:
  //: `dueOnly` and `startOnly` topics have one day, `backwards` ones start
  //: after they are due. `from` and `to` are the first start and last due day.
  function wbGanttRows(nodes, labelOf) {
    const day = (value) => (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) ? wbGanttDayNumber(value) : null);
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const depthOf = (node) => {
      let depth = 0;
      for (let at = node; at.parent_id != null && byId.has(at.parent_id) && depth < 200; at = byId.get(at.parent_id)) depth += 1;
      return depth;
    };
    const rows = [];
    const out = { dueOnly: 0, startOnly: 0, backwards: 0 };
    for (const node of nodes) {
      const start = day(node.data?.start);
      const due = day(node.data?.due);
      if (start == null && due == null) continue;
      if (start == null) out.dueOnly += 1;
      else if (due == null) out.startOnly += 1;
      else if (start > due) out.backwards += 1;
      else rows.push({ id: node.id, label: labelOf(node), depth: depthOf(node), start, due });
    }
    rows.sort((a, b) => a.start - b.start || a.due - b.due || a.id - b.id);
    const from = rows.length ? Math.min(...rows.map((r) => r.start)) : 0;
    const to = rows.length ? Math.max(...rows.map((r) => r.due)) : 0;
    return { rows, from, to, ...out };
  }

  const wbGanttWords = (day) => wbMapDueWords(wbGanttDayText(day)).words;

  //: Where the scale is marked: every day for a fortnight, every week to ten
  //: weeks, the first of each month past that.
  function wbGanttTicks(from, to) {
    const total = to - from + 1;
    const ticks = [];
    if (total > 70) {
      for (let day = from; day <= to; day += 1) if (wbGanttDayText(day).endsWith("-01")) ticks.push(day);
      return ticks.length ? ticks : [from];
    }
    const step = total > 14 ? 7 : 1;
    for (let day = from; day <= to; day += step) ticks.push(day);
    return ticks;
  }

  const wbGanttNodes = () => (wbState.objects || []).filter((o) => WB_MAP_KINDS.has(o.kind));

  //: One row: the topic's name, and a track holding its bar.
  function wbGanttRowEl(row, range, ctx) {
    const total = range.to - range.from + 1;
    const line = document.createElement("li");
    line.className = "wb-gantt-row";
    const name = document.createElement("span");
    name.className = "wb-gantt-name";
    name.style.paddingLeft = `${Math.min(row.depth, 6) * 0.75}rem`;
    name.textContent = row.label || "Untitled topic";
    name.title = row.label || "";
    const track = document.createElement("div");
    track.className = "wb-gantt-track";
    const bar = document.createElement("button");
    bar.type = "button";
    bar.className = "wb-gantt-bar";
    bar.dataset.id = String(row.id);
    bar.style.left = `${((row.start - range.from) / total) * 100}%`;
    bar.style.width = `${((row.due - row.start + 1) / total) * 100}%`;
    const days = row.due - row.start + 1;
    bar.setAttribute("aria-label", `${row.label || "Untitled topic"}, ${wbGanttWords(row.start)} to ${wbGanttWords(row.due)}, ${days} ${days === 1 ? "day" : "days"}. Left and right arrows move it a day, Shift a week, Enter shows it on the map.`);
    bar.title = `${wbGanttWords(row.start)} to ${wbGanttWords(row.due)}`;
    bar.append(Object.assign(document.createElement("span"), { className: "wb-gantt-days", textContent: days > 1 ? `${days} d` : "" }));
    wbGanttWireBar(bar, row, track, total, ctx);
    track.append(bar);
    if (range.today != null) {
      const mark = document.createElement("span");
      mark.className = "wb-gantt-today";
      mark.style.left = `${((range.today - range.from + 0.5) / total) * 100}%`;
      track.append(mark);
    }
    line.append(name, track);
    return line;
  }

  //: Moves the topic's span, one Undo step, and draws the sheet again.
  async function wbGanttMove(id, days, ctx) {
    const live = (wbState.objects || []).find((o) => o.id === id);
    if (!live || !days) return;
    await wbMapSetNodeStyle(live, wbGanttShift(live.data, days));
    ctx.redraw(id);
  }

  function wbGanttShow(id, ctx) {
    ctx.close();
    selectWbItem("object", id);
    const live = (wbState.objects || []).find((o) => o.id === id);
    if (live) wbMapRevealTopic(live);
  }

  //: A drag shows the bar sliding and applies whole days on release; a press
  //: that did not travel shows the topic.
  function wbGanttWireBar(bar, row, track, total, ctx) {
    bar.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      const width = track.getBoundingClientRect().width || 1;
      const x0 = event.clientX;
      let days = 0;
      bar.setPointerCapture(event.pointerId);
      const move = (e) => {
        days = Math.round(((e.clientX - x0) / width) * total);
        bar.style.transform = `translateX(${e.clientX - x0}px)`;
        bar.classList.toggle("is-dragging", Math.abs(e.clientX - x0) > 3);
      };
      const up = () => {
        bar.removeEventListener("pointermove", move);
        bar.removeEventListener("pointerup", up);
        bar.removeEventListener("pointercancel", up);
        const dragged = bar.classList.contains("is-dragging");
        bar.classList.remove("is-dragging");
        bar.style.transform = "";
        bar.dataset.dragged = dragged ? "1" : "";
        if (days) wbGanttMove(row.id, days, ctx);
      };
      bar.addEventListener("pointermove", move);
      bar.addEventListener("pointerup", up);
      bar.addEventListener("pointercancel", up);
    });
    bar.addEventListener("click", () => {
      if (bar.dataset.dragged) {
        bar.dataset.dragged = "";
        return;
      }
      wbGanttShow(row.id, ctx);
    });
    bar.addEventListener("keydown", (event) => {
      const step = event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : 0;
      if (!step) return;
      event.preventDefault();
      wbGanttMove(row.id, step * (event.shiftKey ? 7 : 1), ctx);
    });
  }

  function wbGanttAxis(range) {
    const total = range.to - range.from + 1;
    const axis = document.createElement("div");
    axis.className = "wb-gantt-axis";
    axis.setAttribute("aria-hidden", "true");
    const ticks = document.createElement("div");
    ticks.className = "wb-gantt-ticks";
    for (const day of wbGanttTicks(range.from, range.to)) {
      const tick = document.createElement("span");
      tick.className = "wb-gantt-tick";
      tick.style.left = `${((day - range.from) / total) * 100}%`;
      tick.textContent = wbGanttWords(day);
      ticks.append(tick);
    }
    axis.append(document.createElement("span"), ticks);
    return axis;
  }

  //: Fills the sheet's body from the map as it is now. Keeps the focus on the
  //: bar that moved, so an arrow key can be pressed again.
  function wbGanttFill(body, sub, ctx, focusId = null) {
    const data = wbGanttRows(wbGanttNodes(), (n) => wbMapLabel(n));
    const left = [];
    if (data.dueOnly) left.push(`${data.dueOnly} with only a due day`);
    if (data.startOnly) left.push(`${data.startOnly} with only a start day`);
    if (data.backwards) left.push(`${data.backwards} starting after the due day`);
    sub.textContent = data.rows.length
      ? `${data.rows.length} dated ${data.rows.length === 1 ? "topic" : "topics"}, ${wbGanttWords(data.from)} to ${wbGanttWords(data.to)}.${left.length ? ` Not drawn: ${left.join(", ")}.` : ""}`
      : "No topic has both a start day and a due day yet.";
    if (!data.rows.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Give a topic a start and a due day in Markers, and its bar appears here.";
      body.replaceChildren(empty);
      return;
    }
    const list = document.createElement("ol");
    list.className = "wb-gantt-list";
    const today = Math.floor(Date.now() / WB_GANTT_DAY - new Date().getTimezoneOffset() / 1440);
    data.today = today >= data.from && today <= data.to ? today : null;
    list.append(...data.rows.map((row) => wbGanttRowEl(row, data, ctx)));
    body.replaceChildren(wbGanttAxis(data), list);
    if (focusId != null) body.querySelector(`.wb-gantt-bar[data-id="${focusId}"]`)?.focus();
  }

  function wbMapOpenGantt() {
    if (!wbIsMap()) return;
    openSheet({
      label: "Gantt chart",
      name: "map-gantt",
      sub: "Dated topics",
      build(card, close) {
        const sub = card.querySelector(".sheet-sub");
        const body = document.createElement("div");
        body.className = "wb-gantt";
        const foot = document.createElement("div");
        foot.className = "wb-gantt-foot";
        const undo = document.createElement("button");
        undo.type = "button";
        undo.className = "ghost small";
        undo.textContent = "Undo";
        undo.title = "Undo the last change on this board (Ctrl+Z)";
        const hint = document.createElement("span");
        hint.className = "muted";
        hint.textContent = "Drag a bar to move its dates.";
        foot.append(hint, undo);
        const ctx = {
          close,
          redraw: (id) => wbGanttFill(body, sub, ctx, id),
        };
        undo.addEventListener("click", async () => {
          await wbUndo();
          wbGanttFill(body, sub, ctx);
        });
        card.append(body, foot);
        wbGanttFill(body, sub, ctx);
      },
    });
  }


  //: **The audio note** (MINDMAP_PLAN gap 4, decided 2026-11-10). A recording
  //: is its own object in the notebook (WORLD_CLASS_PLAN, "Audio in the
  //: notebook", decision 2), so a topic does not keep audio: `data.recording`
  //: is the id of a recording picked from the Library's, and the topic shows a
  //: small microphone mark that plays it in a popover
  //: (`/media/recordings/<id>`, the file the Recordings list plays). No upload
  //: and no new media type; recording itself stays in Library, Recordings.
  //: Setting, replacing and removing the link go through `wbMapSetNodeStyle`,
  //: so each is one Undo step. A recording later put in the bin leaves the id
  //: behind; the popover then says so and offers to remove the mark.
  //: "1:12" or "1:02:05", whole seconds rounded down.
  function wbAudioLength(ms) {
    const total = Math.max(0, Math.floor((Number(ms) || 0) / 1000));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = String(total % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
  }

  //: The picker's rows: a recording's name and length, those whose name has
  //: the words typed, as `pickerListbox`'s `fill` takes them.
  function wbAudioRows(recordings, term) {
    const needle = String(term || "").trim().toLowerCase();
    return recordings
      .map((r) => ({ icon: "ph:microphone", label: r.title || "Untitled recording", about: r.duration_ms ? wbAudioLength(r.duration_ms) : "", value: r.id }))
      .filter((row) => !needle || row.label.toLowerCase().includes(needle));
  }

  const wbAudioLive = (id) => (wbState.objects || []).find((o) => o.id === id);

  //: The topic's microphone mark: made the first time a topic has a
  //: recording, hidden when it has none. A press plays; the id is read at the
  //: press, because the datum that drew the topic is replaced by every fetch.
  function wbAudioPaint(el, data) {
    const id = Number.isInteger(data?.recording) && data.recording > 0 ? data.recording : null;
    let mark = el.querySelector(".wb-map-audio");
    if (!id && !mark) return;
    if (!mark) {
      mark = document.createElement("button");
      mark.type = "button";
      mark.className = "wb-map-audio";
      mark.setAttribute("aria-haspopup", "dialog");
      mark.setAttribute("aria-expanded", "false");
      const glyph = document.createElement("i");
      glyph.className = "ph ph-microphone";
      glyph.setAttribute("aria-hidden", "true");
      mark.append(glyph);
      mark.addEventListener("pointerdown", (event) => event.stopPropagation());
      mark.addEventListener("dblclick", (event) => event.stopPropagation());
      mark.addEventListener("click", (event) => {
        event.stopPropagation();
        wbAudioPlay(Number(el.dataset.id), mark);
      });
      const after = el.querySelector(".wb-map-link");
      if (after) after.after(mark);
      else el.querySelector(".wb-map-body")?.append(mark);
    }
    mark.hidden = !id;
    if (id) {
      mark.title = "Audio note: play it";
      mark.setAttribute("aria-label", "Play the audio note on this topic");
    }
  }

  //: Pick a recording from the Library's and attach it to the topic.
  async function wbAudioPick(node) {
    let recordings;
    try {
      recordings = (await apiJson("/recordings?limit=500")).recordings || [];
    } catch (error) {
      toast(error.message || voiceLine("failed", { what: "read your recordings" }), true);
      return;
    }
    if (!recordings.length) {
      toast("No recordings yet. Record one in Library, Recordings, then attach it here.", "info");
      return;
    }
    const shell = pickerDialog({
      title: "Audio note",
      about: `Pick the recording to attach to "${wbMapLabel(node) || "this topic"}". The audio stays in Recordings.`,
      placeholder: "Search recordings…",
      searchLabel: "Search recordings",
    });
    const box = pickerListbox(shell, "Your recordings");
    const paint = () => {
      const term = shell.search.value.trim();
      box.fill(wbAudioRows(recordings, term), term.toLowerCase(), term ? "No recording has that name." : "No recordings yet.");
    };
    shell.search.addEventListener("input", paint);
    paint();
    const id = await new Promise((resolve) => shell.open(resolve));
    const live = wbAudioLive(node.id);
    if (id == null || !live) return;
    await wbMapSetNodeStyle(live, { recording: id });
    toast("Audio note attached. Ctrl+Z takes it off.", "info");
  }

  async function wbAudioRemove(node) {
    const live = wbAudioLive(node.id);
    if (!live?.data?.recording) return;
    await wbMapSetNodeStyle(live, { recording: null });
    toast("Audio note removed. Ctrl+Z puts it back.", "info");
  }

  let wbAudioPop = null;

  function wbAudioClose({ restoreFocus = false } = {}) {
    const state = wbAudioPop;
    if (!state) return;
    wbAudioPop = null;
    document.removeEventListener("pointerdown", state.outside, true);
    state.audio.pause();
    state.panel.remove();
    state.anchor.setAttribute("aria-expanded", "false");
    if (restoreFocus && state.anchor.isConnected) state.anchor.focus({ preventScroll: true });
  }

  //: The player: the browser's own audio controls, loaded only when it is
  //: opened (`preload = "none"`), under the recording's name and length.
  async function wbAudioPlay(nodeId, anchor) {
    const live = wbAudioLive(nodeId);
    const id = live?.data?.recording;
    if (!id) return;
    const reopen = wbAudioPop?.nodeId === nodeId;
    wbAudioClose();
    if (reopen) return;
    const panel = document.createElement("div");
    panel.className = "help-popover wb-map-audio-pop";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", `Audio note on ${wbMapLabel(live) || "this topic"}`);
    const title = document.createElement("p");
    title.className = "wb-map-audio-title";
    title.textContent = "Loading the recording…";
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.preload = "none";
    audio.src = `/media/recordings/${id}`;
    audio.setAttribute("aria-label", "Audio note");
    const foot = document.createElement("div");
    foot.className = "wb-map-audio-foot";
    const swap = document.createElement("button");
    swap.type = "button";
    swap.className = "ghost small";
    swap.textContent = "Choose another…";
    swap.addEventListener("click", () => {
      wbAudioClose();
      wbAudioPick(live);
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost small";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
      wbAudioClose();
      wbAudioRemove(live);
    });
    foot.append(swap, remove);
    panel.append(title, audio, foot);
    panel.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.key === "Escape") {
        event.preventDefault();
        wbAudioClose({ restoreFocus: true });
      }
    });
    const outside = (event) => {
      if (!panel.contains(event.target) && !anchor.contains(event.target)) wbAudioClose();
    };
    document.addEventListener("pointerdown", outside, true);
    document.body.append(panel);
    anchor.setAttribute("aria-expanded", "true");
    wbAudioPop = { nodeId, panel, audio, anchor, outside };
    placeHelpPopover(panel, anchor);
    audio.focus({ preventScroll: true });
    try {
      const rec = await apiJson(`/recordings/${id}`, { silent: true });
      title.textContent = `${rec.title || "Untitled recording"}${rec.duration_ms ? `, ${wbAudioLength(rec.duration_ms)}` : ""}`;
    } catch {
      title.textContent = "This recording is not in Recordings any more.";
      audio.hidden = true;
      swap.textContent = "Choose another…";
    }
  }

  //: The file's whole surface, one object, so the shared scope gains one name rather than one per entry point.
  const wbMapLazy = {
    openGantt: wbMapOpenGantt,
    paintAudio: wbAudioPaint,
    pickAudio: wbAudioPick,
    removeAudio: wbAudioRemove,
    playAudio: wbAudioPlay,
  };
  Object.assign(window, { wbMapLazy });
})();
