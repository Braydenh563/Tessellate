// L-whiteboard-36: pasting a file a board cannot hold says so.
//   BASE=http://127.0.0.1:8899 node scratchpad/ui-sweeps/wbl36.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, errors } = await openBoard({ title: "l36" });
  await page.waitForTimeout(1000);
  const n0 = await page.evaluate(() => wbState.objects.length);
  await page.evaluate(() => {
    document.activeElement?.blur();
    const dt = new DataTransfer();
    dt.items.add(new File(["hello"], "notes.txt", { type: "text/plain" }));
    document.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true }));
  });
  await page.waitForTimeout(800);
  const said = await page.evaluate(() => [...document.querySelectorAll(".toast")].map((t) => t.innerText).join(" | "));
  check("the paste says what a board takes", /pictures and PDFs/.test(said) && /notes\.txt/.test(said), said);
  check("nothing was placed", (await page.evaluate(() => wbState.objects.length)) === n0);
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
