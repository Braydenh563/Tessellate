// The draw.io keys the board lacked (WHITEBOARD_PLAN section 11, 2026-11-12): each pressed on a real board,
// the effect measured. Ctrl+M, F2, Ctrl+Shift+A/I/E/U/Y/R, Ctrl+R, Ctrl+Alt+X, Ctrl+arrow resize, Alt+Shift+F/V/B/E/R,
// Ctrl+Shift+End/Home, Ctrl+Shift+Plus/Minus and /.
//   BASE=http://127.0.0.1:8884 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbkeys2.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

(async () => {
  const { browser, page, errors, board } = await openBoard({ title: "wbkeys2" });
  const ev = (fn, arg) => page.evaluate(fn, arg);
  const settle = (ms = 500) => page.waitForTimeout(ms);
  const press = async (k, ms = 450) => { await page.keyboard.press(k); await settle(ms); };

  const ids = await ev(async (bid) => {
    const box = async (x, y, words, extra = {}) => (await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({
      kind: "text", data: { content: words, ...(extra.data || {}) }, board_id: bid, x, y, z: 1, width: 140, height: 70, group_id: extra.group || null,
    }) })).id;
    const shape = async (x, y, label, props) => (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      board_id: bid, x: 0, y: 0, z: 2,
      data: JSON.stringify({ d: `M ${x} ${y} L ${x + 160} ${y} L ${x + 160} ${y + 90} L ${x} ${y + 90} Z`, shape: "rect", color: "#335599", width: 2, fill: "#ffcc00", label, ...(props ? { props } : {}) }),
    }) })).id;
    const s1 = await shape(200, 200, "Alpha", { owner: "Sam", tier: "gold" });
    const s2 = await shape(500, 200, "Beta");
    const s3 = await shape(200, 400, "A much longer label that will not fit in this small shape at all, really");
    const t1 = await box(700, 450, "Grouped A", { group: "g1" });
    const t2 = await box(900, 450, "Grouped B", { group: "g1" });
    const u1 = await box(700, 600, "Loose box");
    const link = (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      board_id: bid, x: 0, y: 0, z: 3,
      data: JSON.stringify({ type: "link-straight", sourceKind: "sketch", sourceId: s1, targetKind: "sketch", targetId: s2, color: "#445566", width: 3, endCap: "arrow", points: [{ x: 360, y: 150 }, { x: 440, y: 150 }] }),
    }) })).id;
    await fetchWhiteboardState();
    renderWhiteboardNow();
    return { s1, s2, s3, t1, t2, u1, link };
  }, board.id);
  await settle(900);
  await ev(() => { window.__t = []; const t = window.toast; window.toast = (...a) => { window.__t.push(String(a[0])); return t(...a); }; });
  const said = () => ev(() => window.__t.splice(0));

  const sel = (kind, id) => ev(([k, i]) => { clearWbSelection(); selectWbItem(k, i); }, [kind, id]);
  const selected = () => ev(() => [...wbMultiSelection].concat(wbSelectedItem ? [`${wbSelectedItem.kind}:${wbSelectedItem.id}`] : []));
  const depth = () => ev(() => wbUndoStack.length);
  const sketchData = (id) => ev((i) => JSON.parse(wbFindItem("sketch", i).data), id);
  const box = (id) => ev((i) => { const b = wbItemBBox("sketch", wbFindItem("sketch", i)); return { w: Math.round(b.maxX - b.minX), h: Math.round(b.maxY - b.minY) }; }, id);
  const objectBox = (id) => ev((i) => { const o = wbFindItem("object", i); return { w: o.width, h: o.height, r: o.rotation || 0 }; }, id);
  const reloads = () => ev(() => (window.__reloaded = window.__reloaded || 0));
  await ev(() => { window.addEventListener("beforeunload", () => { window.__reloaded = 1; }); });

  // --- Ctrl+M: the Data tab ---
  await sel("sketch", ids.s1);
  await press("Control+m", 600);
  let r = await ev(() => ({ panel: !document.getElementById("wb-format")?.classList.contains("hidden"), tab: document.querySelector('#wb-format [role=tab][aria-selected=true]')?.id }));
  check("Ctrl+M opens the Format panel on the Data tab", r.panel && /data/.test(r.tab || ""), r);
  
  const propsBefore = await sketchData(ids.s1);
  await press("Escape", 300);
  await ev(() => { document.activeElement?.blur?.(); });
  check("leaving the Data tab keeps the shape data", Boolean(propsBefore.props) && JSON.stringify((await sketchData(ids.s1)).props) === JSON.stringify(propsBefore.props), [propsBefore.props, (await sketchData(ids.s1)).props]);

  // --- Select none: a palette command; Ctrl+Shift+A stays the app's (Atlas from anywhere) ---
  await sel("sketch", ids.s1);
  await press("Control+Shift+A", 600);
  check("Ctrl+Shift+A leaves the board selection alone (the app's key)", (await selected()).length === 1, await selected());
  await press("Escape", 300);
  await ev(() => { document.activeElement?.blur?.(); });
  await sel("sketch", ids.s1);
  await ev(() => wbRunCommand("select-none"));
  await settle(300);
  check("Select none (palette) selects none", (await selected()).length === 0, await selected());

  // --- Ctrl+Shift+I / E: shapes, connectors ---
  await press("Control+Shift+I");
  let picked = await selected();
  check("Ctrl+Shift+I selects the shapes and no connector", picked.length >= 3 && !picked.includes(`sketch:${ids.link}`), picked);
  await ev(() => wbRunCommand("select-connectors"));
  await settle(300);
  picked = await selected();
  check("Select all connectors (palette) selects the connectors only", picked.length === 1 && picked[0] === `sketch:${ids.link}`, picked);
  check("still on the board", await ev(() => !document.getElementById("library-view-whiteboard").classList.contains("hidden")));

  // --- Alt+Shift+R: clear waypoints, one undo step ---
  await sel("sketch", ids.link);
  let d0 = await depth();
  await press("Alt+Shift+R", 700);
  let ld = await sketchData(ids.link);
  check("Alt+Shift+R clears the connector's bends", !ld.points || ld.points.length === 0, ld.points);
  check("...as one Undo step", (await depth()) === d0 + 1, [d0, await depth()]);

  // --- Alt+Shift+B / E: copy data, paste data ---
  await sel("sketch", ids.s1);
  await press("Alt+Shift+B", 300);
  await sel("sketch", ids.s2);
  d0 = await depth();
  await press("Alt+Shift+E", 800);
  let s2 = await sketchData(ids.s2);
  check("Alt+Shift+B then E copies the data onto another shape", s2.props?.owner === "Sam" && s2.props?.tier === "gold", { props: s2.props, said: await said(), clip: await ev(() => wbFmtState.dataClip), focus: await ev(() => document.activeElement?.tagName + "#" + document.activeElement?.id) });
  check("...as one Undo step", (await depth()) === d0 + 1, [d0, await depth()]);
  await ev(() => wbUndo());
  await settle(700);
  check("Undo takes the pasted data off again", !(await sketchData(ids.s2)).props);

  // --- Alt+Shift+F / V: copy size, paste size ---
  await sel("sketch", ids.s1);
  await press("Alt+Shift+F", 300);
  await sel("object", ids.u1);
  await press("Alt+Shift+V", 800);
  const tb = await objectBox(ids.u1);
  check("Alt+Shift+F then V sets the size (160 by 90)", tb.w === 160 && tb.h === 90, tb);

  // --- Ctrl+R: turn 90 (and the page does not reload) ---
  await sel("object", ids.t2);
  await press("Control+r", 800);
  check("Ctrl+R turns the selection 90 degrees", (await objectBox(ids.t2)).r === 90, await objectBox(ids.t2));
  check("...and the page did not reload", (await reloads()) === 0);

  // --- Ctrl+Shift+Y: autosize ---
  await sel("sketch", ids.s3);
  const before = await box(ids.s3);
  await ev(() => wbRunCommand("auto-size"));
  await settle(1500);
  const after = await box(ids.s3);
  check("Grow to fit (palette) grows a shape to its words", after.w > before.w || after.h > before.h, { before, after });

  // --- Ctrl+Shift+R: clear default style (no hard reload, no recording) ---
  await ev(() => { document.activeElement?.blur?.(); });
  await sel("sketch", ids.s1);
  await ev(() => wbFmtState.board?.setDefault());
  await settle(700);
  const hadDefault = await ev(() => JSON.stringify(wbBoardSettings?.() || {}).includes("default"));
  await ev(() => wbRunCommand("clear-default-style"));
  await settle(900);
  const gone = await ev(() => !JSON.stringify(wbBoardSettings?.() || {}).includes("default"));
  check("Clear the default style (palette) clears it", gone, { hadDefault });
  check("...and the page did not reload", (await reloads()) === 0 && (await ev(() => !document.querySelector(".recording-active, #meeting-recorder:not(.hidden)"))));

  // --- Ctrl+Alt+X: copy as image (the call is made; the permission may be denied in the sandbox) ---
  await ev(() => { window.__img = 0; window.__orig = wbCopyAsImage; });
  await sel("sketch", ids.s1);
  const called = await ev(async () => {
    let n = 0;
    const real = WB_COMMAND_BY_ID.get("copy-image").run;
    WB_COMMAND_BY_ID.get("copy-image").run = () => { n += 1; };
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "x", code: "KeyX", ctrlKey: true, altKey: true, bubbles: true, cancelable: true }));
    await new Promise((r) => setTimeout(r, 100));
    WB_COMMAND_BY_ID.get("copy-svg").run = () => { n += 10; };
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "X", code: "KeyX", ctrlKey: true, altKey: true, shiftKey: true, bubbles: true, cancelable: true }));
    await new Promise((r) => setTimeout(r, 100));
    WB_COMMAND_BY_ID.get("copy-image").run = real;
    return n;
  });
  check("Ctrl+Alt+X runs Copy as image and Ctrl+Alt+Shift+X Copy as SVG, once each", called === 11, called);

  // --- Ctrl+arrow resize ---
  await sel("sketch", ids.s2);
  const w0 = (await box(ids.s2)).w;
  const h0 = (await box(ids.s2)).h;
  d0 = await depth();
  for (let i = 0; i < 4; i += 1) await page.keyboard.press("Control+ArrowRight", { delay: 5 });
  await settle(900);
  const w1 = (await box(ids.s2)).w;
  check("Ctrl+Right four times widens by 4 px", w1 - w0 === 4, { w0, w1 });
  check("...in one Undo step for the burst", (await depth()) === d0 + 1, [d0, await depth()]);
  await press("Control+ArrowDown", 800);
  check("Ctrl+Down grows the height by 1 px", (await box(ids.s2)).h - h0 === 1, await box(ids.s2));
  await press("Control+Shift+ArrowRight", 800);
  const w2 = (await box(ids.s2)).w;
  check("Ctrl+Shift+Right grows by 10 px", w2 - w1 === 10, { w1, w2 });
  await ev(() => wbUndo());
  await settle(600);
  await ev(() => wbUndo());
  await settle(600);
  await ev(() => wbUndo());
  await settle(700);
  const back = await box(ids.s2);
  check("three Undos return the original size", back.w === w0 && back.h === h0, { back, w0, h0 });
  const rep = await ev(() => wbFmtState.keys.canRepeat());
  check("the resize is recorded for Repeat last", rep === true);

  // --- Ctrl+Shift+Plus / Minus: font size ---
  await sel("sketch", ids.s1);
  const fs = async () => ev((i) => { const p = JSON.parse(wbFindItem("sketch", i).data); return p.label_size || p.font_size || null; }, ids.s1);
  const f0 = (await fs()) ?? (await ev(() => wbFmtValue(wbFmtEntries()[0], "size")));
  await press("Control+Shift+Equal", 800);
  const f1 = await fs();
  await press("Control+Shift+Minus", 800);
  const f2 = await fs();
  check("Ctrl+Shift+Plus makes the text larger, Ctrl+Shift+Minus smaller again", f1 === f0 + 1 && f2 === f0, { f0, f1, f2 });

  // --- Ctrl+Shift+End / Home and Ctrl+Shift+U on a group ---
  await sel("object", ids.t1);
  await press("Control+Shift+End", 600);
  const inGroup = await ev(() => wbFmtState.isolate.active());
  check("Ctrl+Shift+End opens the group", inGroup === true);
  await press("Control+Shift+Home", 600);
  check("Ctrl+Shift+Home leaves it", (await ev(() => wbFmtState.isolate.active())) === false);
  await ev(([a, b]) => { wbMultiSelection.clear(); wbMultiSelection.add(wbMultiKey("object", a)); wbMultiSelection.add(wbMultiKey("object", b)); wbSelectedItem = null; wbUpdateContextBar(); }, [ids.t1, ids.t2]);
  d0 = await depth();
  await press("Control+Shift+U", 900);
  const groups = await ev(([a, b]) => [wbFindItem("object", a).group_id, wbFindItem("object", b).group_id], [ids.t1, ids.t2]);
  check("Ctrl+Shift+U ungroups", groups.every((g) => !g), groups);
  check("...and did not open anything of the app's", await ev(() => !document.getElementById("library-view-whiteboard").classList.contains("hidden")));

  // --- F2 writes like Enter ---
  await ev(() => clearWbSelection());
  await sel("sketch", ids.s2);
  await press("F2", 700);
  const editing = await ev(() => { const a = document.activeElement; return { tag: a?.tagName, editable: Boolean(a?.isContentEditable || a?.tagName === "TEXTAREA" || a?.tagName === "INPUT") }; });
  check("F2 on a selected shape starts editing its words", editing.editable, editing);
  await press("Escape", 400);

  // --- / goes to the Library search ---
  await ev(() => { document.activeElement?.blur?.(); clearWbSelection(); });
  await press("/", 400);
  await page.waitForFunction(() => document.activeElement?.id === "wb-lib-search", null, { timeout: 6000 }).catch(() => {});
  const lib = await ev(() => ({ focus: document.activeElement?.id, shown: !document.getElementById("wb-sidebar-panel").classList.contains("hidden") }));
  check("/ opens the Library and focuses its search", lib.focus === "wb-lib-search" && lib.shown, lib);
  await page.keyboard.type("a/b");
  check("a / typed in the search stays text", (await ev(() => document.getElementById("wb-lib-search").value)) === "a/b");
  await ev(() => { document.getElementById("wb-lib-search").value = ""; });

  // --- Keys list in the help sheet and the palette ---
  await ev(() => { document.activeElement?.blur?.(); wbOpenHelpSheet(); });
  await settle(500);
  const sheet = await ev(() => document.getElementById("wb-help-sections")?.textContent || "");
  const wanted = ["Ctrl+M", "Ctrl+Shift+I", "Ctrl+R", "Ctrl+Alt+X", "Alt+Shift+F", "Alt+Shift+B", "Alt+Shift+R", "Ctrl+Shift+End", "Ctrl+Shift+Home", "Ctrl+Shift+U", "F2", "Ctrl+Shift+Plus", "Ctrl+arrows"];
  const missing = wanted.filter((k) => !sheet.includes(k));
  check("the keys sheet lists all of them", missing.length === 0, missing);

  check("no page errors", errors.length === 0, errors.slice(0, 3));
  await browser.close();
  process.exit(summary() ? 0 : 1);
})().catch((e) => { console.error(e); process.exit(2); });
