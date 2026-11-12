// X16: how much of the boot CSS (00 to 10, the sheets index.html links) does the
// app use? Chromium's rule-usage tracking is switched on before a reload, so it
// sees the boot itself; then each tab is visited and the delta is read, at a
// desktop and a phone width (a rule inside a media query that does not match is
// "unused" at one width and used at the other, so the two are united).
// Output: per sheet, bytes and the share used at boot, after the tabs, and never;
// plus the largest runs of consecutive never-used rules, which are the only
// honest candidates for a lazy sheet (each is a cascade-order risk to move).
//   LIB=$PWD/scratchpad/ui-sweeps/lib.js BASE=http://127.0.0.1:8793 node scratchpad/ui-sweeps/bootcsscov.js [out.json]
const fs = require("fs");
const zlib = require("zlib");
const { boot } = require(process.env.LIB || "./lib.js");

const TABS = ["notes", "chat", "docs", "library", "graph", "timeline", "reminders", "dashboard"];
const BOOT = /\/css\/(0\d|10)-[a-z-]+\.css/;

async function run(vp) {
  const { page, browser } = await boot({ viewport: vp, isMobile: vp.width < 500 });
  const cdp = await page.context().newCDPSession(page);
  const sheets = new Map();
  cdp.on("CSS.styleSheetAdded", (e) => sheets.set(e.header.styleSheetId, e.header));
  await cdp.send("DOM.enable");
  await cdp.send("CSS.enable");
  await cdp.send("CSS.startRuleUsageTracking");
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(5000);
  const take = async () => (await cdp.send("CSS.takeCoverageDelta")).coverage;
  const phases = { boot: await take() };
  for (const t of TABS) {
    await page.evaluate((t) => { location.hash = `#/${t}`; }, t);
    await page.waitForTimeout(1800);
    phases[t] = await take();
  }
  await page.evaluate(() => (typeof openSettingsModal === "function" ? openSettingsModal("general") : null));
  await page.waitForTimeout(1500);
  phases.settings = await take();
  const out = { width: vp.width, sheets: [] };
  for (const [id, h] of sheets) {
    if (!BOOT.test(h.sourceURL)) continue;
    // Ids from before the reload are gone; the live ones answer.
    const text = (await cdp.send("CSS.getStyleSheetText", { styleSheetId: id }).catch(() => null))?.text;
    if (!text) continue;
    const used = {};
    for (const [phase, rules] of Object.entries(phases)) {
      used[phase] = rules.filter((r) => r.styleSheetId === id && r.used).map((r) => [r.startOffset, r.endOffset]);
    }
    out.sheets.push({ url: h.sourceURL.replace(/^.*\/css\//, ""), text, used });
  }
  await browser.close();
  return out;
}

//: Bytes of `text` covered by a list of [start, end) ranges, merged first.
function merged(ranges) {
  const r = [...ranges].sort((a, b) => a[0] - b[0]);
  const m = [];
  for (const [s, e] of r) {
    if (m.length && s <= m[m.length - 1][1]) m[m.length - 1][1] = Math.max(m[m.length - 1][1], e);
    else m.push([s, e]);
  }
  return m;
}
const total = (rs) => rs.reduce((n, [s, e]) => n + (e - s), 0);

(async () => {
  const runs = [await run({ width: 1440, height: 900 }), await run({ width: 390, height: 844 })];
  const names = [...new Set(runs.flatMap((r) => r.sheets.map((s) => s.url)))].sort();
  const report = [];
  for (const name of names) {
    const per = runs.map((r) => r.sheets.find((s) => s.url === name)).filter(Boolean);
    const text = per[0].text;
    const all = (phases) => merged(per.flatMap((s) => phases.flatMap((p) => s.used[p] || [])));
    const bootUsed = all(["boot"]);
    const tabsUsed = all(["boot", ...TABS, "settings"]);
    // A top-level rule is "used" when any phase touched an offset inside it; the
    // tracker reports rule ranges, so a never-used rule is one with no hit at all.
    const hit = new Set(tabsUsed.map((r) => r[0]));
    const gz = (s) => zlib.gzipSync(Buffer.from(s)).length;
    // Never-used runs: gaps between used ranges that are at least 2 KB of source.
    const gaps = [];
    let at = 0;
    for (const [s, e] of tabsUsed) {
      if (s - at >= 2048) gaps.push([at, s]);
      at = Math.max(at, e);
    }
    if (text.length - at >= 2048) gaps.push([at, text.length]);
    const line = (off) => text.slice(0, off).split("\n").length;
    report.push({
      file: name,
      bytes: text.length,
      gz: gz(text),
      usedAtBoot: total(bootUsed),
      usedAfterTabs: total(tabsUsed),
      neverUsed: text.length - total(tabsUsed),
      neverUsedGz: gz(text) - Math.round((gz(text) * total(tabsUsed)) / text.length),
      runs: gaps.map(([s, e]) => ({ lines: `${line(s)}-${line(e)}`, bytes: e - s, gz: gz(text.slice(s, e)) })).sort((a, b) => b.bytes - a.bytes).slice(0, 5),
    });
    void hit;
  }
  for (const r of report) {
    const pct = (n) => ((100 * n) / r.bytes).toFixed(1) + "%";
    console.log(`${r.file.padEnd(28)} ${String(r.bytes).padStart(7)} B  gz ${String(r.gz).padStart(6)}  boot ${pct(r.usedAtBoot).padStart(6)}  +tabs ${pct(r.usedAfterTabs).padStart(6)}  never ${pct(r.neverUsed).padStart(6)} (~${r.neverUsedGz} gz)`);
    for (const g of r.runs) console.log(`    run lines ${g.lines}: ${g.bytes} B, ${g.gz} gz`);
  }
  const t = report.reduce((a, r) => ({ bytes: a.bytes + r.bytes, gz: a.gz + r.gz, never: a.never + r.neverUsed, neverGz: a.neverGz + r.neverUsedGz }), { bytes: 0, gz: 0, never: 0, neverGz: 0 });
  console.log(`TOTAL ${t.bytes} B, gz ${t.gz}, never used ${t.never} B (${((100 * t.never) / t.bytes).toFixed(1)}%), ~${t.neverGz} gz`);
  if (process.argv[2]) fs.writeFileSync(process.argv[2], JSON.stringify(report, null, 1));
})();
