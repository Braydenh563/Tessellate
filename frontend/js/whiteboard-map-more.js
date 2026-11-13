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
// 3. Harper on topic labels (MINDMAP_PLAN VC12): see "Grammar on labels" below.
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
      wbMapCache.part(el, "link")?.after(mark);
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

  // ---------------------------------------------------------------------------
  // The gap audit's topic tools (MINDMAP_PLAN "Placed from INBOX, 2026-10-19",
  // rows 5 to 8 and 12; XMind and MindNode do each of them). Kept together and
  // in this lazy file so the main map file stays free for other work.
  // ---------------------------------------------------------------------------

  //: **Brainstorm timer** (row 5; XMind's brainstorm mode): a countdown chip
  //: over the map. The clock is passed in, so a test never reads the real one.
  function wbBrainstormLeft(startedAt, minutes, now) {
    return Math.max(0, Math.ceil((startedAt + minutes * 60000 - now) / 1000));
  }

  function wbBrainstormClock(seconds) {
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  }

  let wbBrainstormTimer = null;

  function wbBrainstormStop() {
    if (wbBrainstormTimer) clearTimeout(wbBrainstormTimer.tick);
    wbBrainstormTimer?.chip.remove();
    wbBrainstormTimer = null;
  }

  function wbBrainstormStart(minutes = 5) {
    wbBrainstormStop();
    const host = document.getElementById("whiteboard-container");
    if (!host) return;
    const chip = document.createElement("div");
    chip.className = "wb-map-brainstorm dock";
    chip.setAttribute("role", "timer");
    const clock = document.createElement("span");
    clock.className = "wb-map-brainstorm-clock";
    const stop = document.createElement("button");
    stop.type = "button";
    stop.className = "btn btn-ghost btn-sm";
    stop.textContent = "Stop the timer";
    stop.addEventListener("click", wbBrainstormStop);
    chip.append(clock, stop);
    host.append(chip);
    const startedAt = Date.now();
    const paint = () => {
      const left = wbBrainstormLeft(startedAt, minutes, Date.now());
      clock.textContent = left ? `Brainstorm ${wbBrainstormClock(left)}` : "Time is up";
      if (!left) {
        wbAnnounce("The brainstorm time is up.");
        toast("The brainstorm time is up.");
      } else if (wbBrainstormTimer) {
        wbBrainstormTimer.tick = setTimeout(paint, 1000);
      }
    };
    wbBrainstormTimer = { chip, tick: 0 };
    paint();
    wbAnnounce(`A ${minutes} minute brainstorm timer started.`);
  }

  //: **Copy the shape of a branch** (row 6; MindNode's Copy style): the
  //: topic's look and its branch layout, pasted onto another topic as one Undo
  //: step. A key the source lacks clears the target's, so the two match.
  function wbShapePatch(data, keys) {
    const patch = {};
    for (const key of [...keys, "branch_layout"]) patch[key] = data?.[key] ?? null;
    return patch;
  }

  let wbShapeCopied = null;

  function wbShapeCopy(node) {
    if (!node) return;
    wbShapeCopied = wbShapePatch(node.data, WB_MAP_STYLE_KEYS);
    toast("Copied this topic's shape. Choose another topic and paste it.");
  }

  async function wbShapePaste(node) {
    if (!node || !wbShapeCopied) {
      toast("Copy a topic's shape first.", "info");
      return;
    }
    await wbRecordGesture(async () => {
      await wbMapSetNodeStyle(node, { ...wbShapeCopied });
      renderWhiteboardNow();
    });
    wbAnnounce("Pasted the shape. Ctrl+Z takes it back.");
  }

  //: **Topic templates** (row 7; XMind's templates for one topic): a ready
  //: set of children, chosen in the ghost picker and added by the outline
  //: reader as one Undo step.
  const WB_TOPIC_TEMPLATES = Object.freeze({
    pros: ["Pros and cons", ["Pros", "Cons"]],
    swot: ["SWOT", ["Strengths", "Weaknesses", "Opportunities", "Threats"]],
    five: ["Who, what, when, where, why", ["Who", "What", "When", "Where", "Why"]],
    agenda: ["Meeting agenda", ["Goal", "Attendees", "Discussion", "Decisions", "Actions"]],
  });

  function wbTemplateOutline(key) {
    const parts = WB_TOPIC_TEMPLATES[key]?.[1];
    return parts ? parts.join("\n") : "";
  }

  async function wbTemplatePick(node) {
    if (!node) return;
    const rows = Object.entries(WB_TOPIC_TEMPLATES).map(([key, [name, parts]], id) => ({ id, key, text: name, parts }));
    const chosen = await wbMapBranchPicker(rows, {
      title: "Templates for this topic",
      about: "Each one adds its branches under the topic.",
      node,
      meta: (row) => [row.parts.join(", ")],
    });
    for (const pick of chosen || []) {
      const row = rows.find((r) => r.text === pick.text);
      if (row) await wbTemplateAdd(node, row.key);
    }
  }

  async function wbTemplateAdd(node, key) {
    const text = wbTemplateOutline(key);
    if (!node || !text) return 0;
    selectWbItem("object", node.id);
    return wbRecordGesture(wbMapPasteText, [text]);
  }

  //: **A picture from a link** (row 8; XMind's Insert image from URL): the
  //: server fetches it (`/links/image`, public addresses only, pictures only)
  //: and keeps it as a board picture, then it is the topic's picture.
  async function wbTopicImageFromLink(node) {
    if (!node) return;
    const url = String(await promptDialog("The address of the picture. An http or https link to an image.", "", { confirmLabel: "Fetch the picture" }) ?? "").trim();
    if (!url) return;
    wbAnnounce("Fetching the picture.");
    try {
      const uploaded = await apiJson("/links/image", { method: "POST", body: JSON.stringify({ url }) });
      //: The fetched file is kept like any board picture; setting it on the
      //: topic is the write, one Undo step like every topic look.
      await wbRecordGesture(wbMapSetNodeStyle, [node, { image: uploaded.url }]);
      renderWhiteboardNow();
    } catch (err) {
      toast(err.message || "That picture could not be fetched.", true);
    }
  }

  //: **A second central topic** (row 12; XMind's multiple roots): a new root
  //: beside the chosen topic, joined to it by a link that may carry words.
  //: OPML and FreeMind keep the link and its label; Markdown cannot (decision 12).
  async function wbSecondRoot(from) {
    const name = String(await promptDialog("Name the second central topic.", "", { confirmLabel: "Add the topic" }) ?? "").trim();
    if (!name) return;
    const label = String(await promptDialog("What joins the two? A few words, or leave it empty.", "", { confirmLabel: "Join them" }) ?? "").trim();
    await wbRecordGesture(async () => {
      const root = await wbMapCreateNode({ parentId: null, text: name });
      if (!root) return;
      if (from) {
        root.x = Math.round((from.x || 0) + (from.width || 160) + 160);
        root.y = Math.round(from.y || 0);
        await wbSaveObject(root);
        const link = await apiJson("/whiteboard/sketches", {
          method: "POST",
          body: JSON.stringify({
            data: JSON.stringify({ type: "link-straight", sourceId: from.id, sourceKind: "object", targetId: root.id, targetKind: "object", label }),
            x: 0, y: 0, z: 1, board_id: window.currentBoardId ?? null,
          }),
        });
        wbState.sketches = [...(wbState.sketches || []), link];
      }
      selectWbItem("object", root.id);
      renderWhiteboardNow();
    });
    wbAnnounce(`Added ${name} as a second central topic.`);
  }

  //: **Save a branch as Markdown** (row 9): the same outline Copy as text
  //: writes, as a file.
  async function wbBranchSaveMarkdown(node) {
    const boardId = window.currentBoardId;
    if (!node || !boardId) return;
    let tree;
    try {
      tree = await apiJson(`/whiteboard/boards/${boardId}/tree`);
    } catch (err) {
      toast(err.message || "This map could not be read.", true);
      return;
    }
    const find = (list) => {
      for (const n of list || []) {
        if (n.id === node.id) return n;
        const hit = find(n.children);
        if (hit) return hit;
      }
      return null;
    };
    const found = find(tree.roots);
    if (!found) return;
    const { title, body } = wbMapTreeMarkdown([found]);
    const name = `${(title || "branch").replace(/[^\w\- ]+/g, "").trim().slice(0, 60) || "branch"}.md`;
    downloadBlob(new Blob([body ? `# ${title}\n\n${body}\n` : `# ${title}\n`], { type: "text/markdown" }), name);
    toast(`Saved “${title}” as ${name}.`);
  }


  // --- Grammar on labels (VC12) --------------------------------------------
  //
  //: The documents' Harper worker (`docGrammarAsk`, documents-prose.js) takes
  //: any string, so a topic's label is asked once per distinct text and the
  //: answer is kept by text (a bounded map). Only agreement lints are kept: a
  //: label is a fragment, and Harper's capital-letter and sentence rules would
  //: flag nearly every one. The ask is made after a quiet pause and never
  //: while a pointer is down, so a drag, which repaints every frame, costs no
  //: lint call; the paint itself only reads the kept answers. A flagged label
  //: wears a double line and the topic menu offers each suggestion, applied
  //: through `wbMapSetNodeStyle` as one Undo step.
  const WB_GRAMMAR_QUIET_MS = 900;
  const WB_GRAMMAR_KEPT = 400;
  const WB_GRAMMAR_PER_PASS = 24;
  const wbGrammar = { found: new Map(), queue: new Set(), timer: 0, down: false, asks: 0 };
  document.addEventListener("pointerdown", () => { wbGrammar.down = true; }, true);
  document.addEventListener("pointerup", () => { wbGrammar.down = false; }, true);
  document.addEventListener("pointercancel", () => { wbGrammar.down = false; }, true);

  function wbGrammarAvailable() {
    //: documents-prose.js is in the `library` files this bundle starts with, so no guard.
    return docGrammarEnabled();
  }

  async function wbGrammarRun() {
    wbGrammar.timer = 0;
    if (wbGrammar.down) return wbGrammarSoon();
    if (!wbGrammarAvailable()) return wbGrammar.queue.clear();
    const texts = [...wbGrammar.queue].slice(0, WB_GRAMMAR_PER_PASS);
    for (const text of texts) wbGrammar.queue.delete(text);
    if (wbGrammar.found.size > WB_GRAMMAR_KEPT) wbGrammar.found.clear();
    for (const text of texts) {
      wbGrammar.asks += 1;
      const lints = await docGrammarAsk(text).catch(() => null);
      //: No answer (the worker is off or failed): leave the text unasked so a later pass can try.
      if (lints === null) continue;
      const hits = docGrammarFindings(lints, text).filter((f) => f.harperKind === "Agreement" && f.alternatives.length);
      wbGrammar.found.set(text, hits[0] || null);
    }
    wbGrammarRepaint();
    if (wbGrammar.queue.size) wbGrammarSoon();
  }

  function wbGrammarSoon() {
    clearTimeout(wbGrammar.timer);
    wbGrammar.timer = setTimeout(wbGrammarRun, WB_GRAMMAR_QUIET_MS);
  }

  //: Wear (or drop) the mark on one drawn label from the kept answer; a text
  //: with no answer yet is queued, and nothing else is done here.
  function wbGrammarPaint(node, datum) {
    const el = node.querySelector(".wb-map-text");
    if (!el || datum.kind !== "topic") return;
    const text = String(datum.data?.content || "").trim();
    const hit = text.length > 3 && !el.isContentEditable ? wbGrammar.found.get(text) : null;
    if (hit) {
      el.dataset.grammar = hit.message;
      return;
    }
    if (el.dataset.grammar) delete el.dataset.grammar;
    if (text.length > 3 && !wbGrammar.found.has(text) && wbGrammarAvailable()) {
      wbGrammar.queue.add(text);
      if (!wbGrammar.timer) wbGrammarSoon();
    }
  }

  function wbGrammarRepaint() {
    for (const el of document.querySelectorAll(".wb-map-node")) {
      const datum = (wbState.objects || []).find((o) => String(o.id) === el.dataset.id);
      if (datum) wbGrammarPaint(el, datum);
    }
  }

  //: The menu rows for one topic: a suggestion each, "Use “has”" style.
  function wbGrammarFixes(node) {
    const text = String(node?.data?.content || "").trim();
    const hit = node?.kind === "topic" ? wbGrammar.found.get(text) : null;
    if (!hit) return [];
    return hit.alternatives.slice(0, 3).map((option) => ({
      label: option === "" ? `Remove “${hit.text}”` : `Use “${text.slice(0, hit.start) + option + text.slice(hit.end)}”`,
      title: hit.message,
      run: () => wbGrammarApply(node, hit, option),
    }));
  }

  async function wbGrammarApply(node, hit, option) {
    const live = (wbState.objects || []).find((o) => o.id === node.id) || node;
    const text = String(live.data?.content || "").trim();
    if (text.slice(hit.start, hit.end) !== hit.text) return toast("That label has changed since it was checked.", "info");
    await wbMapSetNodeStyle(live, { content: text.slice(0, hit.start) + option + text.slice(hit.end) });
    renderWhiteboardNow();
    wbAnnounce("Label corrected.");
  }


  // --- Stamps on board items ----------------------------------------------
  //
  //: The topic's reaction stamps (`WB_MAP_STAMPS`, `wbMapStampPatch`,
  //: whiteboard-map.js) on any other item the vote dots take: the same
  //: toggle per person, the same data (`stamps`, `stamped`), a row of chips
  //: under the item's bottom edge. A press on a chip is one Undo step.
  async function wbStampSet(entries, name, how) {
    const said = [];
    await wbRecordGesture(async () => {
      for (const e of entries) {
        const patch = wbMapStampPatch(e.item.data, name, how);
        if (!patch) continue;
        const data = { ...e.item.data };
        for (const key of ["stamps", "stamped"]) {
          if (patch[key]) data[key] = patch[key];
          else delete data[key];
        }
        e.item.data = data;
        said.push(patch.said);
      }
      if (said.length) await wbSaveMany(entries.map((e) => ({ kind: "object", item: e.item })));
    });
    wbScheduleRender();
    if (said.length) wbAnnounce(said[0]);
  }

  async function wbStampPress(id, name, how) {
    const item = (wbState.objects || []).find((o) => o.id === id);
    if (item && !wbIsLocked("object", item)) await wbStampSet([{ kind: "object", item }], name, how);
  }

  function wbStampPaint(el, d) {
    const held = WB_MAP_STAMPS.filter(([name]) => d.data?.stamps?.[name] > 0);
    let row = el.querySelector(":scope > .wb-stamps");
    if (!held.length) {
      row?.remove();
      return;
    }
    const mine = Array.isArray(d.data.stamped) ? d.data.stamped : [];
    const key = held.map(([name]) => `${name}${d.data.stamps[name]}${mine.includes(name) ? "m" : ""}`).join(",");
    if (!row) {
      row = document.createElement("div");
      row.className = "wb-stamps";
      //: A chip is a button on a draggable item: its presses stay its own.
      for (const type of ["pointerdown", "dblclick", "contextmenu"]) row.addEventListener(type, (event) => event.stopPropagation());
      el.appendChild(row);
    }
    if (row.dataset.key === key) return;
    row.dataset.key = key;
    row.replaceChildren(...held.map(([name, glyph, said]) => {
      const yours = mine.includes(name);
      const wrap = document.createElement("span");
      wrap.className = "wb-map-stamp-wrap";
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "wb-map-stamp";
      chip.dataset.stamp = name;
      chip.setAttribute("aria-pressed", String(yours));
      chip.title = `${said}: ${yours ? "press to take yours back" : "press to add yours"}`;
      chip.setAttribute("aria-label", `${said}, ${d.data.stamps[name]}${yours ? ", yours included" : ""}. ${yours ? "Press to take yours back." : "Press to add yours."}`);
      const icon = document.createElement("i");
      icon.className = `ph ph-${glyph}`;
      icon.setAttribute("aria-hidden", "true");
      chip.append(icon, String(d.data.stamps[name]));
      chip.addEventListener("click", () => wbStampPress(d.id, name, "toggle"));
      wrap.append(chip, kebabMenu([
        { label: "Remove one", title: "Takes one off the count", run: () => wbStampPress(d.id, name, "one") },
        { label: "Clear all", title: "Every count of this stamp; Ctrl+Z brings them back", danger: true, run: () => wbStampPress(d.id, name, "all") },
      ], `${said} stamp options`));
      return wrap;
    }));
  }

  //: "React with a stamp": a menu of the six, applied to the whole selection.
  function wbStampMenu() {
    const targets = wbVoteTargets();
    if (!targets.length) return toast("Select a note, text box, picture or frame to react to.");
    const box = (document.querySelector("#wb-html-layer .wb-object.wb-selected") || document.body).getBoundingClientRect();
    openMenuAtPoint(WB_MAP_STAMPS.map(([name, , said]) => makeMenuItem(said, `Add or take back your ${said.toLowerCase()} stamp`,
      () => wbStampSet(targets, name, "toggle"))), "Reaction stamps", box.left, box.bottom);
  }

  async function wbStampClear() {
    const held = (wbState.objects || []).filter((o) => !WB_MAP_KINDS.has(o.kind) && o.data?.stamps && !wbIsLocked("object", o));
    if (!held.length) return toast("No item on this board has a stamp.");
    await wbRecordGesture(async () => {
      for (const item of held) {
        const data = { ...item.data };
        delete data.stamps;
        delete data.stamped;
        item.data = data;
      }
      await wbSaveMany(held.map((item) => ({ kind: "object", item })));
    });
    wbScheduleRender();
    wbAnnounce(`Stamps cleared from ${nounCount(held.length, "item")}.`);
  }

  //: The chips in an SVG export: a small pill per stamp under the item (the
  //: live chip's glyph is a font, which an export lacks, so the words stand in).
  function wbStampSvg(obj) {
    let x = 0;
    return WB_MAP_STAMPS.filter(([name]) => obj.data?.stamps?.[name] > 0).map(([name, , said]) => {
      const text = `${said} ${obj.data.stamps[name]}`;
      const w = 12 + text.length * 6.5;
      const out = `<rect x="${x}" y="${obj.height + 4}" width="${w}" height="16" rx="8" fill="#eef1fb" stroke="#2f5bd3" />` +
        `<text x="${x + w / 2}" y="${obj.height + 12}" font-size="10" font-weight="600" text-anchor="middle" dominant-baseline="central" fill="#1d2433">${wbSvgEscape(text)}</text>`;
      x += w + 4;
      return out;
    }).join("");
  }


  // --- Linked stickers ------------------------------------------------------
  //
  //: MINDMAP_PLAN 14.4 (WHITEBOARD_PLAN decision 25 no longer holds for stickers):
  //: a placed icon follows by its `library_ref` (`icons/<name>`, which is also
  //: its `data.icon`) and an emoji by its glyph, since a duplicate drops the
  //: ref. An edit to the selected one is carried to every copy in one Undo step.
  function wbStickerKey(kind, item) {
    if (kind === "sketch") return wbSketchData(item)?.icon ? `icon:${wbSketchData(item).icon}` : null;
    if (kind === "object" && item?.kind === "text" && item.data?.sticker) return `emoji:${item.data.content}`;
    return null;
  }

  function wbStickerCopiesOf(key, state) {
    if (!key) return [];
    const out = [];
    for (const item of state.sketches || []) if (wbStickerKey("sketch", item) === key) out.push({ kind: "sketch", item });
    for (const item of state.objects || []) if (wbStickerKey("object", item) === key) out.push({ kind: "object", item });
    return out;
  }

  //: The selected sticker and every copy of it (itself included), or [].
  function wbStickerCopies() {
    if (wbMultiSelection.size > 1 || !wbSelectedItem) return [];
    const item = wbFindItem(wbSelectedItem.kind, wbSelectedItem.id);
    return wbStickerCopiesOf(wbStickerKey(wbSelectedItem.kind, item), wbState);
  }

  //: Make every copy look like the selected one: an icon's colour and opacity, an emoji's
  //: size and turn (kept about each copy's own centre).
  async function wbStickerMatch() {
    const copies = wbStickerCopies();
    const from = copies.find((e) => e.item.id === wbSelectedItem?.id && e.kind === wbSelectedItem?.kind);
    if (copies.length < 2 || !from) return toast("Select a placed icon or emoji that has copies first.");
    const others = copies.filter((e) => e !== from);
    await wbRecordGesture(async () => {
      for (const e of others) {
        if (e.kind === "sketch") {
          const data = wbSketchData(e.item) || {};
          const source = wbSketchData(from.item) || {};
          for (const key of ["fill", "color", "fillOpacity", "opacity"]) {
            if (source[key] === undefined) delete data[key];
            else data[key] = source[key];
          }
          e.item.data = JSON.stringify(data);
        } else {
          const cx = e.item.x + e.item.width / 2;
          const cy = e.item.y + e.item.height / 2;
          e.item.width = from.item.width;
          e.item.height = from.item.height;
          e.item.x = cx - from.item.width / 2;
          e.item.y = cy - from.item.height / 2;
          e.item.rotation = from.item.rotation ?? null;
        }
      }
      await wbSaveMany(others.map((e) => ({ kind: e.kind, item: e.item })));
    });
    wbScheduleRender();
    wbAnnounce(`${nounCount(others.length, "copy", "copies")} matched.`);
  }

  //: Swap a sticker for another everywhere it is placed. An emoji is a glyph; an
  //: icon is a path scaled to each copy, so the chosen icon's path is fitted into
  //: each copy's own box (centred, uniform) and keeps its colour and opacity.
  async function wbStickerSwap() {
    const copies = wbStickerCopies();
    if (!copies.length) return toast("Select a placed icon or emoji that has copies first.");
    const icons = copies[0].kind === "sketch";
    const choice = await pickIconOrEmoji({ anchor: document.querySelector('[aria-controls="wb-insert-menu"]'), title: icons ? "Swap this icon everywhere" : "Swap this emoji everywhere" });
    if (!choice || !choice.value) return;
    if ((choice.kind === "icon") !== icons) return toast(icons ? "Pick an icon to swap an icon." : "Pick an emoji to swap an emoji.");
    let fresh = null;
    if (icons) {
      const d = (await wbLoadIcons())[choice.value];
      const to = d && wbPathBBox(d);
      if (!to || !(to.maxX > to.minX) || !(to.maxY > to.minY)) return toast("That icon is not in the library's set.", "info");
      fresh = { d, to };
    }
    await wbRecordGesture(async () => {
      for (const e of copies) {
        if (!icons) {
          e.item.data = { ...e.item.data, content: choice.value };
          continue;
        }
        const data = wbSketchData(e.item) || {};
        const from = wbPathBBox(data.d || "");
        if (!from) continue;
        const k = Math.min((from.maxX - from.minX) / (fresh.to.maxX - fresh.to.minX), (from.maxY - from.minY) / (fresh.to.maxY - fresh.to.minY));
        const cx = (from.minX + from.maxX) / 2;
        const cy = (from.minY + from.maxY) / 2;
        const nx = (fresh.to.minX + fresh.to.maxX) / 2;
        const ny = (fresh.to.minY + fresh.to.maxY) / 2;
        data.d = wbTransformPathD(fresh.d, { sx: k, sy: k, anchorX: nx, anchorY: ny, dx: cx - nx, dy: cy - ny });
        data.icon = choice.value;
        if (data.library_ref) data.library_ref = `icons/${choice.value}`;
        e.item.data = JSON.stringify(data);
      }
      await wbSaveMany(copies.map((e) => ({ kind: e.kind, item: e.item })));
    });
    wbScheduleRender();
    wbAnnounce(`${nounCount(copies.length, "copy", "copies")} swapped.`);
  }


  // --- The affinity sort ----------------------------------------------------
  //
  //: MINDMAP_PLAN Phase G: the selected stickies, grouped by theme by
  //: `/affinity` (a model's groups, else the words they share), each sticky
  //: shown with the notes that back its place. The person ticks the groups to
  //: keep (and may rename them); each ticked one becomes a frame with its
  //: stickies laid out inside it, all in one `wbRecordGesture`, so one Undo
  //: takes the lot back. Frames go to the right of the selection, which stays
  //: where it was for the groups left unticked.
  const WB_AFFINITY_GAP = 16;
  const WB_AFFINITY_HEAD = 44;

  function wbAffinityStickies() {
    const out = [];
    for (const key of wbMultiSelection) {
      const [kind, id] = key.split(":");
      const item = kind === "object" ? wbFindItem("object", Number(id)) : null;
      if (item && item.kind === "text" && wbIsSticky(item) && String(item.data?.content || "").trim()) out.push(item);
    }
    return out;
  }

  function wbAffinityDialog(got) {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay confirm-overlay";
      overlay.setAttribute("role", "dialog");
      overlay.setAttribute("aria-modal", "true");
      overlay.setAttribute("aria-label", "Group these stickies by theme");
      const card = document.createElement("div");
      card.className = "card modal-card confirm-card wb-affinity-card";
      const about = document.createElement("p");
      about.className = "confirm-text";
      about.textContent = got.source === "model"
        ? `${nounCount(got.count, "sticky", "stickies")} in ${nounCount(got.groups.length, "theme")}. Tick the ones to make into frames.`
        : `${nounCount(got.count, "sticky", "stickies")} grouped by the words they share${got.reason === "offline" ? " (no model is running)" : ""}. Tick the ones to make into frames.`;
      const list = document.createElement("div");
      list.className = "wb-affinity-list";
      const picks = got.groups.map((group) => {
        const box = document.createElement("section");
        box.className = "wb-affinity-group";
        const head = document.createElement("label");
        head.className = "setting-check wb-affinity-head";
        const tick = document.createElement("input");
        tick.type = "checkbox";
        tick.checked = group.name !== "Other";
        const name = document.createElement("input");
        name.type = "text";
        name.value = group.name;
        name.maxLength = 120;
        name.setAttribute("aria-label", `Frame name for ${group.name}`);
        const count = document.createElement("span");
        count.className = "wb-affinity-count";
        count.textContent = nounCount(group.items.length, "sticky", "stickies");
        head.append(tick, name, count);
        const items = document.createElement("ul");
        items.className = "wb-affinity-items";
        for (const item of group.items) {
          const li = document.createElement("li");
          const text = document.createElement("span");
          text.textContent = item.text;
          const backed = document.createElement("span");
          backed.className = "wb-affinity-backed";
          backed.textContent = item.notes.length ? `Backed by ${item.notes.map((n) => `"${n.title}"`).join(", ")}` : "No note backs this";
          li.append(text, backed);
          items.append(li);
        }
        box.append(head, items);
        list.append(box);
        return { group, tick, name };
      });
      const close = (chosen) => {
        document.removeEventListener("keydown", onKey, true);
        overlay.remove();
        resolve(chosen);
      };
      const onKey = (event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          close(null);
        }
      };
      const go = smallButton("Make frames", "Make a frame for each ticked theme", () => {
        const chosen = picks.filter((p) => p.tick.checked).map((p) => ({ name: p.name.value.trim() || p.group.name, items: p.group.items }));
        close(chosen.length ? chosen : null);
      }, false);
      const row = document.createElement("div");
      row.className = "row confirm-actions";
      row.append(smallButton("Cancel", "Cancel", () => close(null)), go);
      card.append(dialogHead("Group by theme", () => close(null)), about, list, row);
      overlay.append(card);
      wireBackdropClose(overlay, () => close(null));
      document.addEventListener("keydown", onKey, true);
      document.body.append(overlay);
      go.focus();
    });
  }

  async function wbAffinityRun() {
    const boardId = window.currentBoardId;
    const stickies = wbAffinityStickies();
    if (!boardId || stickies.length < 2) return toast("Select two or more stickies with words on them first.");
    wbAnnounce("Grouping the stickies by theme.");
    let got = null;
    try {
      got = await apiJson(`/whiteboard/boards/${boardId}/affinity`, { method: "POST", body: JSON.stringify({ ids: stickies.map((s) => s.id).slice(0, 60) }) });
    } catch (err) {
      return toast(err.message || "These stickies could not be grouped.", true);
    }
    const chosen = await wbAffinityDialog(got);
    if (!chosen || window.currentBoardId !== boardId) return;
    const byId = new Map(stickies.map((s) => [s.id, s]));
    const box = stickies.reduce((b, s) => ({ x: Math.max(b.x, s.x + s.width), y: Math.min(b.y, s.y) }), { x: -Infinity, y: Infinity });
    let left = box.x + 80;
    let made = 0;
    await wbRecordGesture(async () => {
      for (const group of chosen) {
        const members = group.items.map((i) => byId.get(i.id)).filter(Boolean);
        const cell = { w: Math.max(...members.map((m) => m.width)), h: Math.max(...members.map((m) => m.height)) };
        const cols = Math.min(4, Math.ceil(Math.sqrt(members.length)));
        const rows = Math.ceil(members.length / cols);
        const width = cols * (cell.w + WB_AFFINITY_GAP) + WB_AFFINITY_GAP;
        const height = WB_AFFINITY_HEAD + rows * (cell.h + WB_AFFINITY_GAP) + WB_AFFINITY_GAP;
        const frame = await wbCreateObject("frame", { content: group.name.slice(0, 120) }, Math.round(left), Math.round(box.y), width, height);
        if (!frame) continue;
        members.forEach((m, i) => {
          m.x = left + WB_AFFINITY_GAP + (i % cols) * (cell.w + WB_AFFINITY_GAP);
          m.y = box.y + WB_AFFINITY_HEAD + WB_AFFINITY_GAP + Math.floor(i / cols) * (cell.h + WB_AFFINITY_GAP);
        });
        await wbSaveMany(members.map((item) => ({ kind: "object", item })));
        left += width + 40;
        made += 1;
      }
    });
    wbScheduleRender();
    wbAnnounce(`${nounCount(made, "frame")} made. Ctrl+Z takes them back.`);
  }


  // --- A boundary round a lasso'd set ---------------------------------------
  //
  //: MINDMAP_PLAN 12.2 item 1 (decision 19 extended): `boundary_set` on the
  //: first selected topic lists the ids; the shape is the union of those that
  //: are showing, so it follows them as they move or fold, and a deleted
  //: member just drops out. The same `boundary`, label, styles and removal.
  function wbBoundarySetBox(index, hidden, ids) {
    let box = null;
    for (const id of ids) {
      const node = index.byId.get(id);
      if (!node || hidden.has(id)) continue;
      const size = wbMapNodeSize(node);
      const r = { minX: node.x, minY: node.y, maxX: node.x + size.w, maxY: node.y + size.h };
      box = box
        ? { minX: Math.min(box.minX, r.minX), minY: Math.min(box.minY, r.minY), maxX: Math.max(box.maxX, r.maxX), maxY: Math.max(box.maxY, r.maxY) }
        : r;
    }
    return box;
  }

  //: The selected topics, lowest id first (the lead keeps the boundary).
  function wbBoundaryTargets() {
    if (!wbIsMap()) return [];
    const out = [];
    for (const key of wbMultiSelection) {
      const [kind, id] = key.split(":");
      const item = kind === "object" ? wbFindItem("object", Number(id)) : null;
      if (item && item.kind === "topic") out.push(item);
    }
    return out.sort((a, b) => a.id - b.id);
  }

  async function wbBoundaryDraw() {
    const topics = wbBoundaryTargets();
    if (topics.length < 2) return toast("Select two or more topics first.");
    await wbMapSetStructure(topics[0], { boundary: "rounded", boundary_set: topics.map((t) => t.id) },
      `Boundary drawn round ${nounCount(topics.length, "topic")}.`);
  }

  //: The file's whole surface, one object, so the shared scope gains one name rather than one per entry point.
  const wbMapLazy = {
    openGantt: wbMapOpenGantt,
    paintAudio: wbAudioPaint,
    pickAudio: wbAudioPick,
    removeAudio: wbAudioRemove,
    playAudio: wbAudioPlay,
    startTimer: wbBrainstormStart,
    stopTimer: wbBrainstormStop,
    timerOn: () => Boolean(wbBrainstormTimer),
    copyShape: wbShapeCopy,
    pasteShape: wbShapePaste,
    pickTemplate: wbTemplatePick,
    imageFromLink: wbTopicImageFromLink,
    secondRoot: wbSecondRoot,
    saveBranch: wbBranchSaveMarkdown,
    setBox: wbBoundarySetBox,
    boundaryTargets: wbBoundaryTargets,
    boundaryDraw: wbBoundaryDraw,
    stickerCopies: wbStickerCopies,
    stickerMatch: wbStickerMatch,
    stickerSwap: wbStickerSwap,
    affinitySort: wbAffinityRun,
    affinityTargets: wbAffinityStickies,
    paintStamps: wbStampPaint,
    stampMenu: wbStampMenu,
    clearStamps: wbStampClear,
    svgStamps: wbStampSvg,
    paintGrammar: wbGrammarPaint,
    grammarFixes: wbGrammarFixes,
    grammarState: wbGrammar,
  };
  Object.assign(window, { wbMapLazy });
})();
