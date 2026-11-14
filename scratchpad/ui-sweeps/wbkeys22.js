// L-whiteboard-22: Alt+Shift+L, T, N and K on a real board; Ctrl+K still opens the app palette.
//   BASE=http://127.0.0.1:8899 node scratchpad/ui-sweeps/wbkeys22.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

(async () => {
  const { browser, page, board } = await openBoard({ title: "wbkeys22" });
  const ev = (fn, arg) => page.evaluate(fn, arg);
  const settle = (ms = 500) => page.waitForTimeout(ms);
  const s1 = await ev(async (bid) => {
    const id = (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: bid, x: 0, y: 0, z: 2,
      data: JSON.stringify({ d: "M 200 200 L 360 200 L 360 290 L 200 290 Z", shape: "rect", color: "#335599", width: 2, fill: "#ffcc00", label: "Alpha" }) }) })).id;
    await fetchWhiteboardState(); renderWhiteboardNow(); return id;
  }, board.id);
  await settle(800);
  const sel = async () => { await ev(() => { document.activeElement?.blur?.(); }); await ev((i) => { clearWbSelection(); selectWbItem("sketch", i); document.getElementById("whiteboard-container")?.focus(); }, s1); await settle(300); };
  const open = () => ev(() => [...document.querySelectorAll("[role=menu], [role=dialog], dialog[open], .modal-overlay")].filter((d) => !d.classList.contains("hidden") && d.getBoundingClientRect().width > 0 && /Link this|web page/.test(d.textContent)).map((d) => d.id || d.className).join(","));

  await sel(); await page.keyboard.press("Alt+Shift+T"); await settle(600);
  let r = await ev(() => ({ active: document.activeElement?.id, tab: document.querySelector('#wb-format [role=tab][aria-selected=true]')?.id }));
  check("Alt+Shift+T focuses the Tooltip field on the Data tab", r.active === "wb-fmt-tip" && /data/.test(r.tab || ""), r);
  await page.keyboard.press("Escape"); await settle(300);

  await sel(); await page.keyboard.press("Alt+Shift+L"); await settle(700);
  r = await open(); check("Alt+Shift+L opens the link dialog", r.length > 0, r);
  await page.keyboard.press("Escape"); await settle(400);

  await sel(); await page.keyboard.press("Alt+Shift+N"); await settle(700);
  r = await ev(() => ({ open: [...document.querySelectorAll("[id*=comment]")].filter((e) => e.offsetParent && e.getBoundingClientRect().width > 50).map((e) => e.id).slice(0, 3) }));
  check("Alt+Shift+N opens the comment thread", r.open.length > 0, r);
  await page.keyboard.press("Escape"); await settle(400);

  await sel(); await page.keyboard.press("Alt+Shift+K"); await settle(700);
  r = await ev(() => ({ active: document.activeElement?.id || document.activeElement?.className, tab: document.querySelector('#wb-format [role=tab][aria-selected=true]')?.id }));
  check("Alt+Shift+K goes to the tags", /tag/i.test(`${r.active}`) || /data/.test(r.tab || ""), r);
  await page.keyboard.press("Escape"); await settle(300);

  await sel(); await page.keyboard.press("Control+k"); await settle(700);
  r = await ev(() => { const p = document.getElementById("palette-overlay"); return { id: p?.id, shown: Boolean(p && !p.classList.contains("hidden") && p.getBoundingClientRect().width > 0) }; });
  check("Ctrl+K still opens the app's command palette", r.shown, r);
  summary(); await browser.close();
})();
