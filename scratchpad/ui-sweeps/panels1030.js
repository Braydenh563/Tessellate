// Movable panels, measured (INBOX 1454): the grip never covers a control, a
// double-click on the grip resets the size, a stored entry that no longer fits
// opens at the default, and the drag, resize and dock feel.
//
//   BASE=http://127.0.0.1:8784 W=1440 H=900 THEME=dark \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/panels1030.js
//
// MODE=overlap (default): force-open every static panel in index.html plus the
//   real OCR workspace, Settings and Appearance, and count the panels whose
//   grip sits on a control (elementFromPoint under every grip pixel on a 3px
//   grid, grip hidden for the probe).
// MODE=stored: OCR workspace with a stale, tiny and offscreen entry.
// MODE=feel: drag, resize, dock and double-click on Settings.
// Prints PASS/FAIL lines and the numbers; exits 1 on a FAIL.
const { boot } = require("./lib.js");

const W = Number(process.env.W || 1440);
const H = Number(process.env.H || 900);
const MODE = process.env.MODE || "overlap";
let failures = 0;
function check(label, ok, detail) {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail !== undefined ? `  ${detail}` : ""}`);
}

//: Runs in the page: what sits under the grip's pixels. `ring` is how far past
//: the grip the probe also looks (the neighbourhood the owner's eye reads).
const PROBE = `(panel, ring) => {
  const grip = panel.querySelector(":scope > .panel-grip");
  if (!grip) return { grip: false };
  const g = grip.getBoundingClientRect();
  if (!g.width) return { grip: false, why: "grip not shown" };
  const old = grip.style.visibility;
  grip.style.visibility = "hidden";
  const hits = new Set();
  const ctl = "button, a, input, select, textarea, summary, [role=button], [role=menuitem], [role=tab], .select-opener, [contenteditable]";
  let covered = 0;
  const pr = panel.getBoundingClientRect();
  for (let x = g.left - ring + 1.5; x <= g.right + ring - 0.5; x += 3) {
    for (let y = g.top - ring + 1.5; y <= g.bottom + ring - 0.5; y += 3) {
      if (x < pr.left || x > pr.right || y < pr.top || y > pr.bottom) continue;
      const el = document.elementFromPoint(x, y);
      const c = el && panel.contains(el) ? el.closest(ctl) : null;
      if (c && c !== grip) {
        const inside = x >= g.left && x <= g.right && y >= g.top && y <= g.bottom;
        if (inside || ring) { hits.add((c.id ? "#" + c.id : c.tagName.toLowerCase() + "." + String(c.className).split(" ")[0])); }
        if (inside) covered += 1;
      }
    }
  }
  grip.style.visibility = old;
  //: The room above the grip: from the lowest control that shares its columns.
  let gap = null;
  for (const c of panel.querySelectorAll(ctl)) {
    if (c === grip || !c.getClientRects().length) continue;
    const b = c.getBoundingClientRect();
    if (b.right <= g.left || b.left >= g.right || b.height === 0 || b.bottom > g.top + 1) continue;
    gap = gap === null ? g.top - b.bottom : Math.min(gap, g.top - b.bottom);
  }
  return { gap: gap === null ? null : Math.round(gap * 10) / 10, grip: true, rect: [Math.round(g.left), Math.round(g.top), Math.round(g.width), Math.round(g.height)], hits: [...hits], covered };
}`;

async function ensureReady(page) { await page.evaluate(() => ensureModule("panelMovable")); await page.waitForTimeout(300); }
async function openStatic(page, id) {
  return page.evaluate(async (hostId) => {
    const host = document.getElementById(hostId);
    if (!host) return null;
    await ensureModule("panelMovable");
    host.classList.remove("hidden");
    host.hidden = false;
    if (host.tagName === "DIALOG" && !host.open) { try { host.showModal(); } catch (_) { host.show(); } }
    const head = host.querySelector(".dialog-head");
    if (!head) return null;
    const panel = panelOf(head);
    if (!panel || !panel.getClientRects().length) return null;
    panelAdopt(panel);
    return true;
  }, id);
}
async function closeStatic(page, id) {
  await page.evaluate((hostId) => {
    const host = document.getElementById(hostId);
    if (!host) return;
    if (host.tagName === "DIALOG" && host.open) host.close();
    else host.classList.add("hidden");
  }, id);
}

async function overlap(page) {
  await page.evaluate(() => ensureModule("panelMovable"));
  await page.waitForTimeout(300);
  const ids = await page.evaluate(() => [...document.querySelectorAll('dialog, [role="dialog"]')]
    .filter((h) => h.id && h.querySelector(".dialog-head")).map((h) => h.id));
  const rows = [];
  for (const id of ids) {
    const ok = await openStatic(page, id).catch(() => null);
    if (!ok) { await closeStatic(page, id).catch(() => {}); continue; }
    await page.waitForTimeout(80);
    const r = await page.evaluate(`(async () => {
      const probe = ${PROBE};
      const host = document.getElementById(${JSON.stringify(id)});
      const panel = panelOf(host.querySelector(".dialog-head"));
      const a = probe(panel, 0);
      const b = probe(panel, 0);
      return { a, b, size: [Math.round(panel.getBoundingClientRect().width), Math.round(panel.getBoundingClientRect().height)] };
    })()`);
    rows.push({ id, ...r });
    await closeStatic(page, id).catch(() => {});
  }
  return rows;
}


//: The real OCR workspace on an uploaded PDF (ocr717.js does the same), with a
//: faked reading so the foot has its Ask and Save as note buttons.
async function openOcr(page, browser) {
  await page.route("**/ocr-readers*", async (route) => {
    const json = await (await route.fetch()).json();
    json.tesseract = true;
    json.engine = { ...json.engine, ready: true, binary: true, package: true, version: "5.5.3", reason: "", fix: "", languages: [{ code: "eng", name: "English" }], language: "eng", engine: "tesseract", engine_name: "Tesseract", rapidocr: false };
    route.fulfill({ json });
  });
  await page.route("**/ocr-page-read*", (route) => route.fulfill({ json: { text: "Page one. Project kickoff.\n\nScope: capture and search.", model: "test-reader" } }));
  const make = await (await browser.newContext()).newPage();
  await make.setContent("<style>div{page-break-after:always;font:28px Georgia;padding:60px}</style><div>Page one. Project kickoff.</div><div>Page two.</div>");
  const pdf = (await make.pdf({ format: "A4" })).toString("base64");
  const media = await page.evaluate(async (b64) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const fd = new FormData();
    fd.append("file", new File([bytes], `scan-${Date.now()}.pdf`, { type: "application/pdf" }));
    fd.append("direct", "true");
    const r = await fetch("/media/upload", { method: "POST", body: fd, headers: { "X-Auth-Token": authToken(), "X-Workspace-ID": activeSpaceId() } });
    return r.json();
  }, pdf);
  await page.evaluate(() => switchTab("library"));
  await page.waitForTimeout(1200);
  await page.evaluate(async (m) => {
    const row = await apiJson(`/media/meta/${encodeURIComponent(m.url.split("/").pop())}`);
    openOcrWorkspace({ ...row, _isImage: true }, [{ ...row, _isImage: true }]);
  }, media);
  await page.waitForTimeout(2200);
  await page.evaluate(() => {
    const skip = [...document.querySelectorAll("button")].find((b) => /Skip for now/.test(b.textContent) && b.offsetParent);
    skip?.click();
  });
  await page.waitForTimeout(300);
}
async function probeOpen(page, id) {
  return page.evaluate(`(async () => {
    const probe = ${PROBE};
    const host = document.getElementById(${JSON.stringify(id)});
    const panel = panelOf(host.querySelector(".dialog-head"));
    panelAdopt(panel);
    await new Promise((r) => setTimeout(r, 100));
    return { a: probe(panel, 0), b: probe(panel, 6), size: [Math.round(panel.getBoundingClientRect().width), Math.round(panel.getBoundingClientRect().height)] };
  })()`);
}

//: Drag, resize and dock with a real mouse on one open panel: the numbers the
//: owner feels. `target` says how to open it; `label` names it in the output.
async function feel(page, label, sel, openFn) {
  await openFn();
  await page.waitForTimeout(600);
  const q = (fn, arg) => page.evaluate(fn, arg);
  const info = () => page.evaluate((hostId) => {
    const host = document.getElementById(hostId);
    const panel = panelOf(host.querySelector(".dialog-head"));
    const head = panelHeadOf(panel);
    const grip = panel.querySelector(":scope > .panel-grip");
    const r = (el) => { const b = el.getBoundingClientRect(); return { l: b.left, t: b.top, w: b.width, h: b.height, r: b.right, b: b.bottom }; };
    const reset = panel.querySelector(".panel-reset");
    return { panel: r(panel), head: r(head), grip: grip ? r(grip) : null, resetShown: reset ? !reset.hidden && reset.getClientRects().length > 0 : null, cursorHead: getComputedStyle(head).cursor, cursorGrip: grip ? getComputedStyle(grip).cursor : null, userSelect: getComputedStyle(head).userSelect, moving: panel.classList.contains("panel-moving"), cursorMoving: getComputedStyle(head).cursor, active: document.activeElement ? (panel.contains(document.activeElement) ? "inside" : document.activeElement.tagName) : "none", sel: String(getSelection()), scrim: panel.closest("[data-panel-moved]") !== null };
  }, sel);
  const tag = (s) => `${label}: ${s}`;
  //: A point on the head that is not a control (the middle of the title bar can be one).
  const headPoint = () => page.evaluate((hostId) => {
    const panel = panelOf(document.getElementById(hostId).querySelector(".dialog-head"));
    const hh = panelHeadOf(panel).getBoundingClientRect();
    //: From the middle outward, so the grab leaves room to drag either way.
    const mid = hh.left + hh.width / 2;
    for (let d = 0; d < hh.width / 2 - 16; d += 6) {
      for (const x of [mid + d, mid - d]) {
        const e = document.elementFromPoint(x, hh.top + hh.height / 2);
        if (e && e.closest(".dialog-head") && !e.closest("button, a, input, select, textarea, summary")) return [x, hh.top + hh.height / 2];
      }
    }
    return null;
  }, sel);
  // Adoption: hover the head, the panel must not shift.
  const pre = await info();
  await page.mouse.move(pre.head.l + pre.head.w / 2, pre.head.t + pre.head.h / 2);
  await page.waitForTimeout(150);
  const hov = await info();
  check(tag("adopting the panel (hover) does not move or resize it"), Math.abs(hov.panel.t - pre.panel.t) <= 0.5 && Math.abs(hov.panel.h - pre.panel.h) <= 0.5, `top ${pre.panel.t} to ${hov.panel.t}, height ${pre.panel.h} to ${hov.panel.h}`);
  check(tag("the head shows a grab cursor"), hov.cursorHead === "grab", hov.cursorHead);
  check(tag("the grip shows a resize cursor"), hov.cursorGrip === "nwse-resize", hov.cursorGrip);
  check(tag("reset button hidden at the default place"), hov.resetShown === false, hov.resetShown);
  // Focus kept: focus a control, drag the head by 60px, focus must stay inside.
  await page.evaluate((hostId) => { const p = panelOf(document.getElementById(hostId).querySelector(".dialog-head")); (p.querySelector("input, select, textarea, button:not(.panel-grip):not(.panel-reset)"))?.focus(); }, sel);
  const f0 = (await info()).active;
  // Head drag: pointer down, 1px, then 120px.
  const hp0 = await headPoint();
  if (!hp0) { check(tag("a free spot on the head to grab"), false, JSON.stringify(hov.head) + " " + JSON.stringify(await page.evaluate(([x, y]) => { const e = document.elementFromPoint(x, y); return e && e.tagName + "." + String(e.className).slice(0, 40) + " in " + (e.closest("[id]") || {}).id; }, [hov.head.l + hov.head.w / 2, hov.head.t + hov.head.h / 2]))); return; }
  const [hx, hy] = hp0;
  //: Move toward the side with room, so the grip stays on screen for the resize.
  const sx = hov.panel.r + 70 > W ? -1 : 1;
  const sy = hov.panel.b + 50 > H ? -1 : 1;
  await page.mouse.move(hx, hy);
  await page.mouse.down();
  const down = await info();
  check(tag("no jump at pointer-down on the head"), Math.abs(down.panel.l - hov.panel.l) <= 0.5 && Math.abs(down.panel.t - hov.panel.t) <= 0.5, `${down.panel.l - hov.panel.l},${down.panel.t - hov.panel.t}`);
  await page.mouse.move(hx + sx, hy + sy);
  const one = await info();
  check(tag("one pixel of pointer is one pixel of panel"), Math.abs(one.panel.l - hov.panel.l - sx) <= 0.6 && Math.abs(one.panel.t - hov.panel.t - sy) <= 0.6, `${one.panel.l - hov.panel.l},${one.panel.t - hov.panel.t}`);
  await page.evaluate(() => { window.__rects = 0; const o = Element.prototype.getBoundingClientRect; window.__orig = o; Element.prototype.getBoundingClientRect = function () { if (new Error().stack.includes('panel-movable')) if (new Error().stack.includes('panel-movable')) window.__rects += 1; return o.call(this); }; });
  await page.mouse.move(hx + 60 * sx, hy + 40 * sy, { steps: 12 });
  const reads = await page.evaluate(() => { Element.prototype.getBoundingClientRect = window.__orig; return window.__rects; });
  const mid = await info();
  check(tag("a head drag reads no layout per move"), reads === 0, `${reads} panel-movable rect reads over 13 moves`);
  check(tag("grabbing cursor while moving"), mid.moving && mid.cursorMoving === "grabbing", `${mid.moving} ${mid.cursorMoving}`);
  check(tag("no text selected during a drag"), mid.sel === "", JSON.stringify(mid.sel.slice(0, 30)));
  const dimmed = await page.evaluate((hostId) => { const h = document.getElementById(hostId); return h.matches("dialog, .modal-overlay, [id$='-overlay']"); }, sel);
  if (dimmed) check(tag("the dim lifts as the drag starts, not on release"), mid.scrim === true, mid.scrim);
  await page.mouse.up();
  const after = await info();
  check(tag("focus kept inside the panel through a head drag"), f0 === "inside" ? after.active === "inside" : true, `${f0} then ${after.active}`);
  check(tag("reset button shown once moved"), after.resetShown === true, after.resetShown);
  check(tag("the panel followed the pointer by 60,40"), Math.abs(after.panel.l - hov.panel.l - 60 * sx) <= 1 && Math.abs(after.panel.t - hov.panel.t - 40 * sy) <= 1, `${after.panel.l - hov.panel.l},${after.panel.t - hov.panel.t}`);
  // Grip resize: the corner follows the pointer.
  const g = after.grip;
  const gx = g.l + g.w / 2;
  const gy = g.t + g.h / 2;
  await page.mouse.move(gx, gy);
  await page.mouse.down();
  const gd = await info();
  check(tag("no jump at pointer-down on the grip"), Math.abs(gd.panel.w - after.panel.w) <= 0.5 && Math.abs(gd.panel.h - after.panel.h) <= 0.5 && Math.abs(gd.panel.l - after.panel.l) <= 0.5, `${gd.panel.w - after.panel.w},${gd.panel.h - after.panel.h}`);
  await page.evaluate(() => { window.__rects = 0; const o = Element.prototype.getBoundingClientRect; window.__orig = o; Element.prototype.getBoundingClientRect = function () { if (new Error().stack.includes('panel-movable')) window.__rects += 1; return o.call(this); }; });
  await page.mouse.move(gx - 80, gy - 50, { steps: 16 });
  const greads = await page.evaluate(() => { Element.prototype.getBoundingClientRect = window.__orig; return window.__rects; });
  const gm = await info();
  check(tag("a resize reads layout at most twice"), greads <= 2, `${greads} panel-movable rect reads over 16 moves`);
  check(tag("the corner follows the pointer (right edge)"), Math.abs(gm.panel.r - after.panel.r + 80) <= 1.5 && Math.abs(gm.panel.b - after.panel.b + 50) <= 1.5, `dRight ${gm.panel.r - after.panel.r}, dBottom ${gm.panel.b - after.panel.b}`);
  check(tag("the top-left corner holds still"), Math.abs(gm.panel.l - after.panel.l) <= 1.5 && Math.abs(gm.panel.t - after.panel.t) <= 1.5, `${gm.panel.l - after.panel.l},${gm.panel.t - after.panel.t}`);
  check(tag("no text selected during a resize"), gm.sel === "", JSON.stringify(gm.sel.slice(0, 30)));
  await page.mouse.up();
  // Double-click on the grip puts the size back (INBOX 1454).
  const rz = await info();
  await page.mouse.dblclick(rz.grip.l + rz.grip.w / 2, rz.grip.t + rz.grip.h / 2);
  await page.waitForTimeout(150);
  const dz = await info();
  check(tag("double-click on the grip resets the size"), Math.abs(dz.panel.w - pre.panel.w) <= 1 && Math.abs(dz.panel.h - pre.panel.h) <= 1, `${Math.round(rz.panel.w)}x${Math.round(rz.panel.h)} to ${Math.round(dz.panel.w)}x${Math.round(dz.panel.h)}, default ${Math.round(pre.panel.w)}x${Math.round(pre.panel.h)}`);
  // Dock: drag the head to the left edge; preview shows, release fills the zone.
  const hd = dz.head;
  const hp = await headPoint();
  await page.mouse.move(hp[0], hp[1]);
  await page.mouse.down();
  if (process.env.DEBUG) console.log("dock down", JSON.stringify(await page.evaluate(([x, y]) => { const e = document.elementFromPoint(x, y); return { at: e && (e.id || e.className.toString().slice(0, 40)), moving: Boolean(document.querySelector(".panel-moving")) }; }, [hd.l + hd.w / 2 - 40, hd.t + hd.h / 2])), JSON.stringify(hd));
  await page.mouse.move(60, 400, { steps: 8 });
  await page.mouse.move(4, 400, { steps: 4 });
  const prev = await page.evaluate(() => { const el = document.querySelector(".panel-snap-preview"); if (!el) return null; const b = el.getBoundingClientRect(); return { open: el.matches(":popover-open"), l: b.left, t: b.top, w: b.width, h: b.height, events: getComputedStyle(el).pointerEvents }; });
  check(tag("the dock preview shows at the left edge"), Boolean(prev && prev.open), JSON.stringify(prev));
  await page.mouse.up();
  await page.waitForTimeout(100);
  const dk = await info();
  check(tag("release fills the previewed zone"), Boolean(prev) && [dk.panel.l - prev.l, dk.panel.t - prev.t, dk.panel.w - prev.w, dk.panel.h - prev.h].every((d) => Math.abs(d) <= 1.5), `panel ${Math.round(dk.panel.l)},${Math.round(dk.panel.t)} ${Math.round(dk.panel.w)}x${Math.round(dk.panel.h)} preview ${prev && [prev.l, prev.t, prev.w, prev.h].map(Math.round)}`);
  const hidden = await page.evaluate(() => { const el = document.querySelector(".panel-snap-preview"); return !el || !el.matches(":popover-open"); });
  check(tag("the preview is gone after the drop"), hidden);
  check(tag("reset button shown while docked"), dk.resetShown === true, dk.resetShown);
  await page.evaluate((hostId) => { const p = panelOf(document.getElementById(hostId).querySelector(".dialog-head")); panelReset(p); }, sel);
  const back = await info();
  check(tag("reset puts it back where it opened"), Math.abs(back.panel.l - pre.panel.l) <= 1 && Math.abs(back.panel.t - pre.panel.t) <= 1 && Math.abs(back.panel.w - pre.panel.w) <= 1, `${back.panel.l - pre.panel.l},${back.panel.t - pre.panel.t},${back.panel.w - pre.panel.w}`);
  check(tag("reset button hidden again"), back.resetShown === false, back.resetShown);
  // A docked panel dragged out comes back to its own size, under the pointer.
  const hp1 = await headPoint();
  await page.mouse.move(hp1[0], hp1[1]);
  await page.mouse.down();
  await page.mouse.move(4, 400, { steps: 6 });
  await page.mouse.up();
  const dk2 = await info();
  const hp2 = await headPoint();
  await page.mouse.move(hp2[0], hp2[1]);
  await page.mouse.down();
  await page.mouse.move(hp2[0] + 300, hp2[1] + 120, { steps: 10 });
  const out = await info();
  const under = out.head.l - 1 <= hp2[0] + 300 && hp2[0] + 300 <= out.head.r + 1 && out.head.t - 1 <= hp2[1] + 120 && hp2[1] + 120 <= out.head.b + 1;
  await page.mouse.up();
  check(tag("dragging a docked panel out restores its size"), Math.abs(out.panel.w - pre.panel.w) <= 1.5 && Math.abs(out.panel.h - pre.panel.h) <= 1.5, `${Math.round(dk2.panel.w)}x${Math.round(dk2.panel.h)} docked, ${Math.round(out.panel.w)}x${Math.round(out.panel.h)} out, default ${Math.round(pre.panel.w)}x${Math.round(pre.panel.h)}`);
  check(tag("and the pointer stays on the head"), under, `pointer ${hp2[0] + 300},${hp2[1] + 120} head ${Math.round(out.head.l)}-${Math.round(out.head.r)} x ${Math.round(out.head.t)}-${Math.round(out.head.b)}`);
  // A smaller window pulls a far-parked panel back inside.
  await page.evaluate((hostId) => { const p = panelOf(document.getElementById(hostId).querySelector(".dialog-head")); panelReset(p); }, sel);
  const hp3 = await headPoint();
  await page.mouse.move(hp3[0], hp3[1]);
  await page.mouse.down();
  await page.mouse.move(Math.min(W - 40, hp3[0] + 500), Math.min(H - 40, hp3[1] + 400), { steps: 10 });
  await page.mouse.up();
  const parked = await info();
  await page.setViewportSize({ width: 1024, height: 700 });
  await page.waitForTimeout(400);
  const small = await info();
  check(tag("a smaller window brings the panel back inside it"), small.panel.r <= 1024.5 && small.panel.b <= 700.5 && small.head.t >= -0.5, `was ${Math.round(parked.panel.r)}x${Math.round(parked.panel.b)}, now right ${Math.round(small.panel.r)} bottom ${Math.round(small.panel.b)} in 1024x700`);
  await page.setViewportSize({ width: W, height: H });
  await page.waitForTimeout(300);
  // Keyboard: the grip moves, resizes and resets.
  await page.evaluate((hostId) => { const p = panelOf(document.getElementById(hostId).querySelector(".dialog-head")); panelReset(p); p.querySelector(":scope > .panel-grip").focus(); }, sel);
  const k0 = await info();
  const ring = await page.evaluate(() => { const g = document.activeElement; const c = getComputedStyle(g); return { cls: g.className, w: parseFloat(c.outlineWidth), style: c.outlineStyle, shadow: c.boxShadow !== "none", op: c.opacity }; });
  check(tag("the focused grip shows a ring"), ring.cls.includes("panel-grip") && ((ring.w > 0 && ring.style !== "none") || ring.shadow), JSON.stringify(ring));
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  const k1 = await info();
  check(tag("two arrow keys move the panel 32px"), Math.abs(k1.panel.l - k0.panel.l + 32) <= 1, `${k1.panel.l - k0.panel.l}`);
  await page.keyboard.press("Shift+ArrowDown");
  const k2 = await info();
  check(tag("Shift and an arrow resize 16px with the top-left held"), Math.abs(k2.panel.h - k1.panel.h - 16) <= 1.5 && Math.abs(k2.panel.t - k1.panel.t) <= 1.5, `h ${k2.panel.h - k1.panel.h}, top ${k2.panel.t - k1.panel.t}`);
  await page.keyboard.press("Home");
  const k3 = await info();
  check(tag("Home puts it back"), Math.abs(k3.panel.l - k0.panel.l) <= 1 && Math.abs(k3.panel.h - k0.panel.h) <= 1, `${k3.panel.l - k0.panel.l},${k3.panel.h - k0.panel.h}`);
}

async function main() {
  const { browser, page } = await boot({ viewport: { width: W, height: H } });
  await page.evaluate(() => {
    const skip = [...document.querySelectorAll("button")].find((b) => /Skip for now/.test(b.textContent));
    skip?.click();
  });
  if (MODE === "overlap") {
    const rows = await overlap(page);
    await openOcr(page, browser);
    rows.push({ id: "REAL ocr-workspace", ...(await probeOpen(page, "ocr-workspace")) });
    await page.evaluate(() => closeOcrWorkspace());
    await page.evaluate(() => openSettingsModal("models"));
    await page.waitForTimeout(1200);
    rows.push({ id: "REAL settings-modal", ...(await probeOpen(page, "settings-modal")) });
    const shown = rows.filter((r) => r.a && r.a.grip);
    const bad = shown.filter((r) => r.a.hits.length);
    const near = shown.filter((r) => r.b.hits.length);
    for (const r of shown) console.log(`  ${r.id.padEnd(34)} ${r.size.join("x").padEnd(9)} grip ${r.a.rect.join(",")}  on [${r.a.hits.join(" ")}]  gap ${r.a.gap}`);
    check(`${W}x${H}: panels opened`, shown.length > 0, shown.length);
    check(`${W}x${H}: panels whose grip is over a control`, bad.length === 0, `${bad.length} of ${shown.length}  ${bad.map((r) => r.id).join(",")}`);
    const gaps = shown.map((r) => r.a.gap).filter((g) => g !== null);
    console.log(`  smallest gap between a control and the grip row: ${Math.min(...gaps)}px over ${gaps.length} panels`);
  }
  if (MODE === "stored") {
    //: The OCR workspace with an entry that no longer fits: what it opens at.
    const cases = {
      none: null,
      tiny: [40, 20, 120, 60],
      squashedByTheOldHeadBug: [0, 0, 1340, 87],
      offscreen: [5000, -4000, null, null],
      positionOnlyFromOldLayout: [-310, 200, null, null],
      biggerThanTheWindow: [0, 0, 3000, 2000],
      badDock: [0, 0, 500, 400, "sideways"],
      good: [0, 0, 900, 600],
      unversionedFromBeforeTheFix: [-310, 200, null, null],
    };
    //: VER=2 (default) stamps the entries with the OCR workspace's layout
    //: version; VER=0 writes them bare, as the old build did.
    const VER = Number(process.env.VER ?? 2);
    const stamp = (e, name) => (e && VER && name !== "unversionedFromBeforeTheFix" ? [e[0], e[1], e[2], e[3], e[4] || "", VER] : e);
    const read = () => page.evaluate(() => { const c = document.querySelector("#ocr-workspace > .card").getBoundingClientRect(); return [Math.round(c.left), Math.round(c.top), Math.round(c.width), Math.round(c.height)]; });
    const base = {};
    for (const [name, raw] of Object.entries(cases)) {
      const entry = stamp(raw, name);
      await page.evaluate(([e]) => { try { localStorage.removeItem("tessellate.panels"); if (e) localStorage.setItem("tessellate.panels", JSON.stringify({ "ocr-workspace": e })); } catch (_) {} }, [entry]);
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.waitForTimeout(1500);
      await page.evaluate(() => { const b = [...document.querySelectorAll("button")].find((x) => /Skip for now/.test(x.textContent) && x.offsetParent); b?.click(); });
      await openOcr(page, browser);
      await page.evaluate(() => { document.querySelector("#ocr-workspace .dialog-head")?.dispatchEvent(new Event("pointerover", { bubbles: true })); });
      await page.waitForTimeout(400);
      const rect = await read();
      const saved = await page.evaluate(() => localStorage.getItem("tessellate.panels"));
      if (name === "none") base.rect = rect;
      const same = JSON.stringify(rect) === JSON.stringify(base.rect);
      const inside = rect[0] >= 0 && rect[1] >= 0 && rect[0] + rect[2] <= W && rect[1] + rect[3] <= H;
      console.log(`  ${name.padEnd(28)} opens ${rect.join("x")}  default ${same}  inside ${inside}  stored ${saved}`);
      if (name === "good" && VER) check("a good entry is kept", rect[2] === 900 && rect[3] === 600, rect.join("x"));
      else if (name === "good") check("a good entry is kept (bare, old build)", rect[2] === 900 && rect[3] === 600, rect.join("x"));
      else if (name === "positionOnlyFromOldLayout" && VER) check(`${name}: a current entry is kept and pulled inside the window`, inside && !same, rect.join(","));
      else if (name === "badDock" && VER) check(`${name}: the garbage dock is dropped, the size kept`, inside && rect[2] === 500, rect.join(","));
      else if (name !== "none") check(`${name}: opens at the default`, same, rect.join(","));
    }
  }
  if (MODE === "feel") {
    const which = (process.env.PANELS || "settings,ocr,shortcuts,widgets,space,appearance").split(",");
    const close = async () => { await page.keyboard.press("Escape"); await page.waitForTimeout(300); };
    for (const name of which) {
      if (name === "settings") await feel(page, name, "settings-modal", async () => { await page.evaluate(() => openSettingsModal("models")); });
      if (name === "ocr") { await close(); await feel(page, name, "ocr-workspace", () => openOcr(page, browser)); await page.evaluate(() => closeOcrWorkspace()); }
      if (name === "appearance") await feel(page, name, "appearance-panel", async () => { await page.evaluate(() => openAppearancePanel()); });
      if (name === "shortcuts") await feel(page, name, "shortcuts-overlay", async () => { await page.evaluate(() => openShortcuts()); });
      if (name === "widgets") await feel(page, name, "dash-widgets-dialog", async () => { await page.evaluate(() => { switchTab("dashboard"); }); await page.waitForTimeout(800); await page.evaluate(() => { document.getElementById("dash-widgets-dialog").showModal(); }); });
      if (name === "space") await feel(page, name, "space-create-dialog", async () => { await page.evaluate(() => { document.getElementById("space-create-dialog").showModal(); }); });
      await close();
    }
  }
  if (MODE === "one") {
    const id = process.env.ID;
    await ensureReady(page);
    await openStatic(page, id);
    await page.waitForTimeout(150);
    console.log(JSON.stringify(await page.evaluate((hid) => {
      const host = document.getElementById(hid);
      const panel = panelOf(host.querySelector(".dialog-head"));
      const r = (el) => { const b = el.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.right), Math.round(b.bottom)]; };
      return { clear: (document.getElementById("notif-clear") || panel).getBoundingClientRect().toJSON(), panel: r(panel), kids: [...panel.children].map((k) => k.tagName + "." + String(k.className).split(" ")[0] + " " + r(k).join(",")), grip: r(panel.querySelector(":scope > .panel-grip")), cs: getComputedStyle(panel).overflowY, gripCs: (() => { const c = getComputedStyle(panel.querySelector(":scope > .panel-grip")); return [c.height, c.minHeight, c.boxSizing, c.display, c.padding, c.lineHeight, c.marginTop, c.marginBottom].join(" "); })() };
    }, id), null, 1));
  }
  if (MODE === "shot") {
    await openOcr(page, browser);
    await page.evaluate(() => document.querySelector("#ocr-workspace .dialog-head")?.dispatchEvent(new Event("pointerover", { bubbles: true })));
    await page.waitForTimeout(300);
    const c = await page.evaluate(() => { const b = document.querySelector("#ocr-workspace > .card").getBoundingClientRect(); return { x: b.right - 420, y: b.bottom - 110, width: 430, height: 120 }; });
    await page.screenshot({ path: `${process.env.SCRATCH || "."}/ocr-foot.png`, clip: c });
  }
  if (MODE === "geo") {
    await openOcr(page, browser);
    const g = await page.evaluate(() => {
      const card = document.querySelector("#ocr-workspace > .card");
      const r = (el) => { const b = el.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.right), Math.round(b.bottom)]; };
      const cs = getComputedStyle(card);
      const note = document.getElementById("ocr-to-note");
      const chain = []; for (let e = note; e && e !== card; e = e.parentElement) chain.push(e.tagName + "." + String(e.className).split(" ")[0] + " " + r(e).join(","));
      return { card: r(card), pad: [cs.paddingRight, cs.paddingBottom], chain, grip: card.querySelector(":scope > .panel-grip") && r(card.querySelector(":scope > .panel-grip")), kids: [...card.children].map((k) => k.tagName + "." + String(k.className).split(" ")[0] + " " + r(k).join(",")) };
    });
    console.log(JSON.stringify(g, null, 1));
    const exp = await page.evaluate(() => {
      const card = document.querySelector("#ocr-workspace > .card");
      const grip = card.querySelector(":scope > .panel-grip");
      const out = {};
      for (const b of ["0px", "8px", "16px", "-16px"]) { grip.style.bottom = b; out[b] = Math.round(grip.getBoundingClientRect().bottom); }
      out.mb = getComputedStyle(grip).marginBottom; out.pb = card.style.getPropertyValue("--grip-pb"); out.scroll = [card.scrollHeight, card.clientHeight];
      return out;
    });
    console.log(JSON.stringify(exp));
  }
  await browser.close();
  process.exit(failures ? 1 : 0);
}
main().catch((e) => { console.error(e); process.exit(1); });
