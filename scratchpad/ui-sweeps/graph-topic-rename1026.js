// The note panel's topic rename: field and Save/Cancel on one row, one height
// (the owner, 2026-10-26: "those buttons on the edit tags on the graph popup
// arent spaced or aligned").
const { boot } = require("./lib");
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1280, height: 800 } });
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(2500);
  await page.evaluate(async () => { await ensureModule("graph"); });
  const made = await page.evaluate(async () => (await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "Topic row probe" }) })).id);
  await page.evaluate(async (id) => { await openGraphPopup({ stopPropagation() {}, preventDefault() {}, clientX: 600, clientY: 400 }, { id }); }, made);
  await page.waitForTimeout(800);
  const out = await page.evaluate(() => {
    const box = document.getElementById("graph-popup-topic");
    box.replaceChildren();
    const mark = chip("ph:circles-three #idea", "tag", () => {});
    const rename = smallButton("ph:pencil-simple", "Rename the topic", () => {});
    rename.classList.add("icon-only");
    box.append(mark, rename);
    box.classList.remove("hidden");
    if (typeof gcRenameTopicInline !== "function") return { error: "no gcRenameTopicInline" };
    gcRenameTopicInline({ id: 1, name: "#idea" }, mark, rename);
    const r = (el) => { const b = el.getBoundingClientRect(); return { top: Math.round(b.top), h: Math.round(b.height), w: Math.round(b.width), cy: Math.round(b.top + b.height / 2), left: Math.round(b.left), right: Math.round(b.right) }; };
    let hid = null; for (let el = box; el; el = el.parentElement) if (getComputedStyle(el).display === "none") { hid = el.id || el.className; break; }
    if (hid) return { hid };
    const field = box.querySelector(".graph-topic-rename");
    const btns = [...box.querySelectorAll(".graph-topic-tools button")];
    const row = r(box);
    return { row, field: r(field), buttons: btns.map(r), gap: btns.length === 2 ? r(btns[1]).left - r(btns[0]).right : null, fieldToButton: btns.length ? r(btns[0]).left - r(field).right : null, bg: btns.map((b) => getComputedStyle(b).backgroundColor) };
  });
  console.log(JSON.stringify(out));
  await browser.close();
})();
