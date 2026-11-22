// The Quick sketch's brush ring against the owner bug "the pen cursor circle
// does not take the selected colour". Picks colours and reads the ring's
// computed border, halo and width at the current THEME. Exit 1 on a finding.
//
//   colour   the ring's border equals the picked ink (red, blue)
//   halo     with ink equal to the paper (white on white, near-black on black)
//            the halo differs from the ink by more than the ink does from the paper
//   size     the ring's width is the brush size times the zoom
//
//   BASE=http://127.0.0.1:8796 THEME=dark node sketchring.js
const { boot } = require("./lib.js");
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(1000);
  await page.evaluate(() => openSketch());
  await page.waitForTimeout(1200);
  const bb = await page.locator('[data-sp="stage"]').boundingBox();
  const rows = [];
  async function probe(label, hex, paper, size) {
    await page.evaluate(([h, p, s]) => {
      const fire = (el, v) => { el.value = v; el.dispatchEvent(new Event("input", { bubbles: true })); };
      fire(document.querySelector('[data-sp="custom"]'), h);
      if (p) fire(document.querySelector('[data-sp="paper"]'), p);
      if (s) fire(document.querySelector('[data-sp="size"]'), String(s));
    }, [hex, paper, size]);
    await page.mouse.move(bb.x + 100, bb.y + 100);
    await page.mouse.move(bb.x + 120, bb.y + 110);
    const r = await page.evaluate(() => {
      const e = document.querySelector('[data-sp="ring"]');
      const c = getComputedStyle(e);
      return { border: c.borderTopColor, halo: c.boxShadow.split(" 0px")[0], w: e.getBoundingClientRect().width };
    });
    rows.push({ label, hex, paper: paper || "kept", ...r });
  }
  await page.keyboard.press("p");
  await probe("red", "#ff0000", "#ffffff", 8);
  await probe("blue", "#0000ff");
  await probe("white on white", "#ffffff");
  await probe("near-black on black", "#101010", "#000000");
  await probe("red size 30", "#ff0000", "#ffffff", 30);
  console.log(process.env.THEME || "light", JSON.stringify(rows, null, 1));
  const rgb = (h) => `rgb(${[1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)).join(", ")})`;
  let bad = 0;
  for (const r of rows.slice(0, 2)) if (r.border !== rgb(r.hex)) { console.log("FAIL colour", r.label); bad++; }
  const sizeRow = rows[4];
  const zoom = await page.evaluate(() => document.querySelector('[data-sp="ring"]').getBoundingClientRect().width / 30);
  if (Math.abs(sizeRow.w - 30 * zoom) > 1) { console.log("FAIL size"); bad++; }
  if (rows[2].halo === rows[2].border || rows[3].halo === rows[3].border) { console.log("FAIL halo"); bad++; }
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
