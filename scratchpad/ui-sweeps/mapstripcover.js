// MINDMAP_PLAN §13b's remainder: does the topic strip still cover the handle
// of the line into its own topic?
//
// §12.1 found it once: the strip opened 44px above the selected topic, several
// hundred pixels wide, and for a child laid out a little below its parent it
// landed on the middle of the line into it (`elementFromPoint` at the handle's
// centre returned the strip). §13b took the strip to a third of the width
// without measuring this again. Here, for every non-root topic of a map in
// each layout, the topic is selected and `elementFromPoint` is read at the
// centre of the waypoint handle of the line into it (`.wb-map-edge-handle`,
// shown for the selected topic): a hit inside `#wb-map-strip` is a covered
// handle. A handle off screen is skipped, not counted.
//
//   BASE=http://127.0.0.1:8794 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     WIDTHS=1440,1024,820,390 node scratchpad/ui-sweeps/mapstripcover.js
const { boot } = require("./lib.js");

const WIDTHS = (process.env.WIDTHS || "1440,1024,820,390").split(",").map(Number);
const LAYOUTS = (process.env.LAYOUTS || "tree-right,tree-down,radial,tree-both").split(",");

(async () => {
  let covered = 0;
  let checked = 0;
  for (const width of WIDTHS) {
    const height = width <= 600 ? 844 : 900;
    const { browser, page } = await boot({ viewport: { width, height } });
    await page.click('[data-tab="library"]');
    await page.waitForTimeout(700);
    await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
    await page.waitForTimeout(1000);
    await page.evaluate(async () => {
      const v = document.getElementById("library-view-whiteboard");
      for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v);
      await initWhiteboard();
    });
    for (const layout of LAYOUTS) {
      const out = await page.evaluate(async (lay) => {
        const content = ["# Cover", "- Trunk"];
        for (let b = 1; b <= 4; b++) {
          content.push(`  - Branch ${b}`);
          for (let l = 1; l <= 2; l++) content.push(`    - Leaf ${b}${l}`);
        }
        const board = await apiJson("/whiteboard/boards/import", {
          method: "POST",
          body: JSON.stringify({ format: "markdown", content: content.join("\n"), name: `Cover ${lay}` }),
        });
        await apiJson(`/whiteboard/boards/${board.id}`, { method: "PUT", body: JSON.stringify({ layout: lay }) });
        await openWhiteboardBoard(board.id);
        await new Promise((r) => setTimeout(r, 1500));
        await wbMapTidy({ quiet: true });
        await new Promise((r) => setTimeout(r, 800));
        const results = [];
        const idx = wbMapIndex();
        for (const node of idx.nodes) {
          if (node.parent_id == null) continue;
          const el = document.querySelector(`.wb-object[data-id="${node.id}"]`);
          if (!el) continue;
          //: Centred on the topic first, as a person looking at it would be.
          if (typeof wbCenterOnObject === "function") wbCenterOnObject(node.id);
          selectWbItem("object", node.id);
          await new Promise((r) => setTimeout(r, 250));
          const handle = document.querySelector(`.wb-map-edge-handle[data-child="${node.id}"]`);
          const strip = document.getElementById("wb-map-strip");
          if (!handle || !strip) continue;
          const hb = handle.getBoundingClientRect();
          const x = hb.left + hb.width / 2;
          const y = hb.top + hb.height / 2;
          if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
          const hit = document.elementFromPoint(x, y);
          const sb = strip.getBoundingClientRect();
          const tb = el.getBoundingClientRect();
          //: And never onto the topic it styles, which is what moving it off
          //: the handle must not trade for.
          const onTopic = sb.left < tb.right && sb.right > tb.left && sb.top < tb.bottom && sb.bottom > tb.top;
          results.push({
            onTopic,
            label: node.data?.content || "",
            covered: Boolean(hit && hit.closest("#wb-map-strip")),
            hit: hit ? (hit.getAttribute("class") || hit.tagName).split(" ")[0] : null,
            strip: `${Math.round(sb.width)}x${Math.round(sb.height)}`,
            rects: { strip: [sb.left, sb.top, sb.right, sb.bottom].map(Math.round), topic: [tb.left, tb.top, tb.right, tb.bottom].map(Math.round), handle: [hb.left, hb.top, hb.right, hb.bottom].map(Math.round) },
          });
        }
        return results;
      }, layout);
      const bad = out.filter((r) => r.covered || r.onTopic);
      checked += out.length;
      covered += bad.length;
      for (const r of bad) console.log("   ", r.label, JSON.stringify(r.rects));
      console.log(`== ${width} ${layout}: ${out.length} handles, ${bad.length} under the strip or the strip on its topic`
        + (bad.length ? `  ${bad.map((r) => r.label).join(", ")}` : "")
        + (out[0] ? `  strip ${out[0].strip}` : ""));
    }
    await browser.close();
  }
  console.log(`${covered ? "FAIL" : "PASS"}: ${covered} of ${checked} handles covered by the strip`);
  process.exit(covered ? 1 : 0);
})();
