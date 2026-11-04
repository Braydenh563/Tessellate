// diagram-edges.js: connect by dragging, and rename in place (INBOX 1621, DOCUMENTS_PLAN 22.4 R8c). Lazy:
// `LAZY_MODULES.diagramEdges`, registered at the foot of documents-mermaid.js and asked for by diagram-builder.js's `show` for
// a flowchart, after the canvas (diagram-canvas.js). Two things, both on the overlay and neither asking for a picture before
// the change is made:
//  - an edge handle (`.dgm-handle`) at the right edge of the block under the pointer, or of the one picked: drag it to a
//    block or a group to connect, or to empty space to add a block there that is already connected. A press with no drag (or
//    Enter on it) arms it: the next click on the picture is the target, Escape puts it back;
//  - a double click on a block, an arrow or a group's title opens one input over it (`.dgm-rename`): Enter commits, Escape
//    puts it back. A new block, and the words on a second branch off a decision, are asked the same way once the picture
//    shows them (`want`), so a flowchart is built without leaving the picture.
(() => {
  const overlay = () => diagramModel.overlay.math;
  const REACH = 16;
  const STRIP = 32;
  const math = {
    //: The id Mermaid gives an arrow: `L_<from>_<to>_<n>`, n counting the arrows with the same two ends.
    edgeId: (m, edge) => `L_${edge.from}_${edge.to}_${m.edges.filter((e) => e.from === edge.from && e.to === edge.to).indexOf(edge)}`,
    //: The arrow whose midpoint is within `reach` client pixels of a point, or "".
    edgeAt: (hit, img, px, py, reach = REACH) => {
      let best = "";
      let far = reach;
      for (const p of overlay().place(hit, img, { left: 0, top: 0 }, hit?.edges)) {
        const d = Math.hypot(p.x - px, p.y - py);
        if (d <= far) (far = d), (best = p.id);
      }
      return best;
    },
  };

  function wire(S, h) {
    const fig = S?.fig;
    const stage = fig?.parentElement;
    const layer = stage?.querySelector(".dgm-overlay");
    if (!layer || S.k || fig.dataset.edges) return;
    fig.dataset.edges = "1";
    const img = () => fig.querySelector(".md-mermaid-img");
    const rect = () => img()?.getBoundingClientRect();
    const place = (list) => (S.hit && rect() ? overlay().place(S.hit, rect(), layer.getBoundingClientRect(), list) : []);
    const nodeAt = (x, y) => (S.hit && rect() ? overlay().at(S.hit, rect(), x, y) : "");
    const groupAt = (x, y) => (S.hit && rect() ? overlay().clusterAt(S.hit, rect(), x, y) : "");

    //: Four handles, one a side, so a connection can leave any edge and the picked block reads as connectable (INBOX 1679).
    const handles = ["top", "right", "bottom", "left"].map((side) => {
      const b = smallButton("ph:arrow-bend-down-right", "Connect to another block. Drag it to a block, or press it and click one", () => {});
      b.className = "dgm-handle ghost small hidden";
      b.dataset.side = side;
      b.type = "button";
      layer.append(b);
      return b;
    });
    let hover = "";
    let hideTimer = 0;
    let conn = null;
    let armed = "";
    let armedSide = "right";
    let editing = null;
    //: What to ask next, once the picture shows it: `{ node: id }` or `{ edge }` (the model's arrow).
    const want = [];

    const sole = () => {
      const on = layer.querySelectorAll(".dgm-box.on:not(.dgm-cluster)");
      return on.length === 1 ? on[0].dataset.node : "";
    };
    const current = () => conn?.from || armed || hover || sole();
    //: Where a side's handle sits on a placed block, and where its arrow leaves from.
    const anchor = (at, side) => [at.x + (side === "left" ? 0 : side === "right" ? at.w : at.w / 2), at.y + (side === "top" ? 0 : side === "bottom" ? at.h : at.h / 2)];
    const showHandle = () => {
      const id = current();
      const at = id && place().find((b) => b.id === id);
      const only = conn?.side || (armed && armedSide);
      for (const handle of handles) handle.classList.toggle("hidden", !at || Boolean(editing) || Boolean(only && only !== handle.dataset.side));
      if (!at) return;
      //: Shown first, measured once, then placed: a read between writes would lay the page out four times.
      const size = handles[0].offsetWidth || 24;
      for (const handle of handles) {
        const [x, y] = anchor(at, handle.dataset.side);
        handle.style.transform = `translate(${x - size / 2}px, ${y - size / 2}px)`;
      }
    };
    const leave = () => {
      clearTimeout(hideTimer);
      hideTimer = setTimeout(() => ((hover = ""), showHandle()), 350);
    };

    //: One input over a box, a title or an arrow's middle.
    function open(at, was, done, wide = 0) {
      editing?.cancel();
      const input = document.createElement("input");
      input.className = "dgm-rename";
      input.value = was;
      input.setAttribute("aria-label", "Name");
      const width = Math.max(120, wide);
      input.style.width = `${width}px`;
      input.style.transform = `translate(${at.x + at.w / 2 - width / 2}px, ${at.y + at.h / 2 - 16}px)`;
      layer.append(input);
      let over = false;
      const end = (keep) => {
        if (over) return;
        over = true;
        editing = null;
        input.remove();
        if (!keep) want.length = 0;
        else done(input.value.trim());
        showHandle();
      };
      editing = { cancel: () => end(false) };
      input.addEventListener("keydown", (event) => {
        event.stopPropagation();
        if (event.key === "Enter" || event.key === "Escape") event.preventDefault(), end(event.key === "Enter");
      });
      input.addEventListener("blur", () => end(true));
      showHandle();
      input.focus();
      input.select();
    }

    const renameNode = (id) => {
      const at = place().find((b) => b.id === id);
      const key = h.ops.key("n", id);
      const node = h.ops.node(S.m, id);
      if (!at || !node) return false;
      open(at, node.text, (text) => text && text !== node.text && h.ops.relabel(S.m, key, text) && h.commit(S, `Renamed to ${text}.`), at.w);
      return true;
    };
    const renameGroup = (id) => {
      const at = place(S.hit.clusters).find((b) => b.id === id);
      const group = h.ops.group(S.m, id);
      if (!at || !group) return false;
      open({ x: at.x, y: at.y, w: at.w, h: 0 }, group.title, (text) => text && text !== group.title && h.ops.relabel(S.m, h.ops.key("g", id), text) && h.commit(S, `Renamed to ${text}.`), Math.min(at.w, 220));
      return true;
    };
    const renameEdge = (edge) => {
      const at = place(S.hit.edges).find((b) => b.id === math.edgeId(S.m, edge));
      if (!at) return false;
      open({ ...at, w: 0, h: 0 }, edge.label, (text) => text !== edge.label && ((edge.label = text), h.commit(S, text ? `Labelled the connector ${text}.` : "Cleared the connector label.")));
      return true;
    };

    fig.addEventListener("dblclick", (event) => {
      if (!S.hit || !rect() || event.target.closest(".dock, .dgm-handle, .dgm-rename")) return;
      const node = nodeAt(event.clientX, event.clientY);
      const arrow = !node && math.edgeAt(S.hit, rect(), event.clientX, event.clientY);
      const edge = arrow && S.m.edges.find((e) => math.edgeId(S.m, e) === arrow);
      const group = !node && !edge && groupAt(event.clientX, event.clientY);
      const top = group && place(S.hit.clusters).find((b) => b.id === group);
      const y = event.clientY - layer.getBoundingClientRect().top;
      event.preventDefault();
      if (node) renameNode(node);
      else if (edge) renameEdge(edge);
      else if (top && y - top.y <= STRIP) renameGroup(group);
    });

    //: The next thing asked for, once the new picture has a size to place it by (an image decodes after the draw); dropped after 4 s.
    const ask = () => {
      while (want.length && want[0].until < Date.now()) want.shift();
      const next = want[0];
      if (!next || editing) return;
      if (next.node ? renameNode(next.node) : renameEdge(next.edge)) want.shift();
    };
    const settle = () => (ask(), showHandle());
    (fig.onpaint ||= []).push(settle);
    (fig.onzoom ||= []).push(settle);
    fig.addEventListener("load", settle, true);
    fig.addEventListener("scroll", showHandle, { passive: true });
    for (const type of ["click", "keyup", "focusin"]) S.root.addEventListener(type, () => queueMicrotask(showHandle));

    fig.addEventListener("pointermove", (event) => {
      if (event.pointerType === "touch" || event.buttons || conn) return;
      const id = nodeAt(event.clientX, event.clientY);
      if (id) (hover = id), clearTimeout(hideTimer), showHandle();
      else if (hover) leave();
    });
    fig.addEventListener("pointerleave", (event) => !handles.includes(event.relatedTarget) && hover && leave());

    //: Connects `from` to what is at the point: a block or a group, or (nothing there) a new block, in the group under it.
    function connect(from, x, y) {
      const to = nodeAt(x, y) || groupAt(x, y);
      const name = (id) => h.ops.node(S.m, id)?.text || h.ops.group(S.m, id)?.title || id;
      if (!to) {
        const group = groupAt(x, y);
        const key = h.add(S, { shape: "rect", after: null, into: group ? h.ops.key("g", group) : null, before: null, from, edit: false });
        const edge = key && S.m.edges.find((e) => e.from === from && e.to === key.slice(2));
        if (key) want.push({ node: key.slice(2), until: Date.now() + 4000 });
        if (edge && h.ops.needsLabel(S.m, edge)) want.push({ edge, until: Date.now() + 4000 });
        return key;
      }
      if (to === from) return;
      const edge = h.ops.join(S.m, from, to);
      if (!edge) return h.say(S, `${name(from)} is already connected to ${name(to)}.`);
      if (h.ops.needsLabel(S.m, edge)) want.push({ edge, until: Date.now() + 4000 });
      h.commit(S, `Connected ${name(from)} to ${name(to)}.`);
    }

    const line = document.createElement("span");
    line.className = "dgm-rubber hidden";
    layer.append(line);
    const aim = (x, y) => {
      const home = layer.getBoundingClientRect();
      const at = place().find((b) => b.id === conn.from);
      if (!at) return;
      const [x0, y0] = anchor(at, conn.side);
      const dx = x - home.left - x0;
      const dy = y - home.top - y0;
      line.style.width = `${Math.hypot(dx, dy)}px`;
      line.style.transform = `translate(${x0}px, ${y0}px) rotate(${Math.atan2(dy, dx)}rad)`;
      const to = nodeAt(x, y) || groupAt(x, y);
      for (const box of layer.querySelectorAll(".dgm-box.dgm-target")) box.classList.remove("dgm-target");
      if (to && to !== conn.from) [...layer.querySelectorAll(".dgm-box")].find((b) => (b.dataset.node || b.dataset.group) === to && (b.dataset.node ? !b.classList.contains("dgm-cluster") : true))?.classList.add("dgm-target");
    };
    const finish = () => {
      line.classList.add("hidden");
      for (const box of layer.querySelectorAll(".dgm-box.dgm-target")) box.classList.remove("dgm-target");
      conn = null;
      showHandle();
    };
    for (const handle of handles) {
      const side = handle.dataset.side;
      handle.addEventListener("pointerenter", () => clearTimeout(hideTimer));
      handle.addEventListener("pointerleave", () => !conn && hover && leave());
      handle.addEventListener("pointerdown", (event) => {
        const from = current();
        if (event.button || !from) return;
        event.preventDefault();
        handle.setPointerCapture?.(event.pointerId);
        conn = { id: event.pointerId, from, side, x: event.clientX, y: event.clientY, moved: false };
      });
      handle.addEventListener("pointermove", (event) => {
        if (!conn || event.pointerId !== conn.id) return;
        if (!conn.moved && Math.hypot(event.clientX - conn.x, event.clientY - conn.y) < 6) return;
        conn.moved = true;
        line.classList.remove("hidden");
        aim(event.clientX, event.clientY);
        showHandle();
      });
      handle.addEventListener("pointerup", (event) => {
        if (!conn || event.pointerId !== conn.id) return;
        const { from, moved } = conn;
        finish();
        if (moved) connect(from, event.clientX, event.clientY);
        else arm(from, side);
      });
      handle.addEventListener("pointercancel", finish);
      //: Enter or Space on the handle (a click with no pointer) arms it too.
      handle.addEventListener("click", (event) => event.detail === 0 && arm(current(), side));
    }

    function arm(from, side) {
      armed = from;
      armedSide = side;
      for (const handle of handles) {
        if (handle.dataset.side === side) handle.setAttribute("aria-pressed", "true");
        else handle.removeAttribute("aria-pressed");
      }
      showHandle();
      h.say(S, "Click the block to connect to, or empty space for a new one. Escape cancels.");
    }
    const disarm = () => {
      armed = "";
      for (const handle of handles) handle.removeAttribute("aria-pressed");
      showHandle();
    };
    fig.addEventListener("click", (event) => {
      if (!armed || event.target.closest(".dock, .dgm-handle")) return;
      const from = armed;
      disarm();
      connect(from, event.clientX, event.clientY);
    }, true);
    window.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && armed) disarm();
    });
  }

  diagramModel.edges = { wire, math };
})();
