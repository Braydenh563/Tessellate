// perf2-1005 (audit FE-07): the emblem draws at three sizes without p5, and
// the boot's network list holds no p5 and no d3 before a tab asks for them.
//   BASE=http://127.0.0.1:8859 node perf2-1005-emblem.js
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, scale: 2 });
  const requested = [];
  page.on("request", (r) => requested.push(r.url()));
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);
  await page.fill("#lock-password", "testpassword123").catch(() => {});
  await page.click("#lock-submit").catch(() => {});
  await page.waitForTimeout(4000);
  const atBoot = requested.filter((u) => /p5\.min|d3\.v7/.test(u)).map((u) => u.split("/").pop());
  // The p5 sketch this was once compared against is gone: the emblem is the
  // favicon's SVG now (phone-shell.js emblemArt, from #emblem-template), so the
  // pixel diff had no seed to read. What is left to hold: it draws at each size
  // without p5, and the boot asks for neither p5 nor d3.
  const compare = await page.evaluate(() => [24, 52, 76].map((size) => {
    const holder = document.createElement("div");
    document.body.appendChild(holder);
    renderEmblem(holder, size, { animate: false });
    const art = holder.firstElementChild;
    const box = art?.getBoundingClientRect();
    const out = { size, tag: art?.tagName.toLowerCase() || null, w: box ? +box.width.toFixed(1) : 0, h: box ? +box.height.toFixed(1) : 0, p5: typeof window.p5 };
    holder.remove();
    return out;
  }));
  const fails = [];
  if (atBoot.length) fails.push(`boot asked for ${atBoot.join(", ")}`);
  for (const c of compare) if (!c.tag || c.w < 1 || c.h < 1) fails.push(`no emblem drawn at ${c.size}`);
  if (compare.some((c) => c.p5 !== "undefined")) fails.push("p5 loaded to draw the emblem");
  console.log(JSON.stringify({ atBoot, compare }, null, 1));
  for (const f of fails) console.log(`FAIL ${f}`);
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
