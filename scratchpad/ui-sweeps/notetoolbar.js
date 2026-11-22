// The note Capture box's formatting toolbar is one row at the desktop
// window's 1184x760 (the owner's report: "Preview" wrapped alone onto a second
// row). Measured at 1184, and at 1440 and 820 either side, in whichever look
// LOOK names (unset: the app default, Quiet utilitarian; `default`: Classic).
//
// A row is the set of controls sharing a top edge; the toolbar is one row when
// every control's top is within 2px of the first's. Every control must keep an
// accessible name, since the fix hides words visually below a width.
//
// Usage: BASE=http://127.0.0.1:8793 [LOOK=default] node notetoolbar.js
const { boot } = require("./lib.js");

let bad = 0;
const ok = (n, c, d) => {
  if (!c) bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};

const WIDTHS = [
  [1184, 760],
  [1440, 900],
  [820, 1000],
];

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1184, height: 760 } });
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(1200);
  await page.evaluate(() => {
    if (typeof showNotesSection === "function") showNotesSection("capture");
  });
  await page.waitForTimeout(800);
  const look = await page.evaluate(() => ({
    palette: document.documentElement.dataset.palette || "default",
    density: document.documentElement.dataset.density,
  }));
  console.log("look:", JSON.stringify(look));

  for (const [w, h] of WIDTHS) {
    await page.setViewportSize({ width: w, height: h });
    await page.waitForTimeout(700);
    const m = await page.evaluate(() => {
      const bar = document.querySelector("#note-toolbar");
      if (!bar || !bar.offsetParent) return null;
      const kids = [...bar.children].filter((k) => k.offsetParent && !k.classList.contains("doc-toolbar-sep"));
      const tops = kids.map((k) => Math.round(k.getBoundingClientRect().top));
      const name = (el) => {
        const own = el.getAttribute("aria-label") || el.getAttribute("title") || "";
        return own || el.textContent.trim();
      };
      const r = bar.getBoundingClientRect();
      const last = kids[kids.length - 1].getBoundingClientRect();
      return {
        width: Math.round(r.width),
        height: Math.round(r.height),
        rows: new Set(tops.map((t) => Math.round((t - tops[0]) / 4))).size,
        overflow: bar.scrollWidth > bar.clientWidth + 1,
        lastRight: Math.round(r.right - last.right),
        kids: kids.map((k) => ({
          label: (k.textContent || "").trim().replace(/\s+/g, " ").slice(0, 16),
          top: Math.round(k.getBoundingClientRect().top - tops[0]),
          w: Math.round(k.getBoundingClientRect().width),
        })),
        unnamed: kids.flatMap((k) => (k.classList.contains("doc-toolbar-pair") ? [...k.children] : [k])).filter((k) => !name(k)).map((k) => k.outerHTML.slice(0, 60)),
      };
    });
    if (!m) {
      ok(`${w}: the toolbar is on screen`, false);
      continue;
    }
    console.log(`@${w}: ${m.width}x${m.height}, ${m.rows} row(s), room at the end ${m.lastRight}px`);
    console.log("   " + m.kids.map((k) => `${k.label || "(icon)"}:${k.w}${k.top ? "@" + k.top : ""}`).join("  "));
    if (w >= 1184) ok(`${w}: the formatting toolbar is one row`, m.rows === 1, `${m.rows} rows`);
    ok(`${w}: nothing scrolls or clips sideways`, !m.overflow);
    ok(`${w}: every control keeps a name`, m.unnamed.length === 0, m.unnamed.join(" | "));
  }
  // The icon picker still does its job: it opens its colours, and choosing
  // one writes the markdown into the note box.
  await page.setViewportSize({ width: 1184, height: 760 });
  await page.waitForTimeout(500);
  await page.evaluate(() => {
    const box = document.querySelector("#entry-content");
    box.value = "a word";
    box.focus();
    box.setSelectionRange(2, 6);
  });
  const opener = await page.$('#note-toolbar .select-shell:has(> [data-md-colour="highlight"]) .select-opener');
  const face = await opener.evaluate((el) => ({
    name: el.getAttribute("aria-label"),
    title: el.title,
    icon: !!el.querySelector(".select-icon"),
  }));
  ok("the highlight picker is an icon with a name and a title", face.icon && !!face.name && !!face.title,
    JSON.stringify(face));
  await opener.click();
  await page.waitForTimeout(400);
  const rows = await page.evaluate(() =>
    [...document.querySelectorAll(".select-menu:not(.hidden) [role='option']")].map((r) => r.textContent.trim())
  );
  ok("it opens its colours", rows.includes("Green"), JSON.stringify(rows));
  await page.evaluate(() => {
    const row = [...document.querySelectorAll(".select-menu:not(.hidden) [role='option']")].find(
      (r) => r.textContent.trim() === "Green"
    );
    row && row.click();
  });
  await page.waitForTimeout(300);
  const text = await page.evaluate(() => document.querySelector("#entry-content").value);
  ok("and choosing one writes it into the note", text === "a ==green|word==", JSON.stringify(text));

  console.log(`\n${bad ? bad + " FAIL" : "all pass"}`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
