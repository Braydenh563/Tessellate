// L-whiteboard-2: a PDF dropped on a board asks "Place as pages" or "Attach as one object"; pages are one image each,
// side by side, one Undo step; attach is one object that opens the file.
//   BASE=http://127.0.0.1:8893 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbpdf.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

// A hand-built PDF of `n` pages, offsets computed so no reader has to repair it.
function makePdf(n) {
  const objs = ["<< /Type /Catalog /Pages 2 0 R >>"];
  const kids = Array.from({ length: n }, (_, i) => `${3 + i} 0 R`).join(" ");
  objs.push(`<< /Type /Pages /Kids [${kids}] /Count ${n} >>`);
  for (let i = 0; i < n; i++) objs.push("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 400] >>");
  let out = "%PDF-1.4\n";
  const at = [];
  objs.forEach((o, i) => { at.push(out.length); out += `${i + 1} 0 obj\n${o}\nendobj\n`; });
  const xref = out.length;
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n` + at.map((p) => String(p).padStart(10, "0") + " 00000 n \n").join("");
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, "latin1").toString("base64");
}

(async () => {
  const { browser, page, errors } = await openBoard({ title: "wbpdf" });
  await page.evaluate(() => {
    window.__asked = [];
    window.confirmDialog = async (msg, opts) => { window.__asked.push({ msg, opts }); return /to the board/.test(msg) ? window.__answer : true; };
  });
  const drop = (b64, name) => page.evaluate(async ([data, fname]) => {
    const bytes = Uint8Array.from(atob(data), (c) => c.charCodeAt(0));
    const dt = new DataTransfer();
    dt.items.add(new File([bytes], fname, { type: "application/pdf" }));
    const box = document.getElementById("whiteboard-container");
    box.dispatchEvent(new DragEvent("drop", { dataTransfer: dt, bubbles: true, cancelable: true, clientX: 700, clientY: 450 }));
  }, [b64, name]);
  const objects = () => page.evaluate(() => (wbState.objects || []).map((o) => ({ id: o.id, kind: o.kind, x: o.x, y: o.y, w: o.width, h: o.height, d: o.data })));

  // 1. Place as pages.
  await page.evaluate(() => { window.__answer = true; });
  await drop(makePdf(3), "three.pdf");
  await page.waitForTimeout(3500);
  let objs = await objects();
  const asked = (await page.evaluate(() => window.__asked)).filter((a) => /to the board/.test(a.msg));
  check("the question names both choices", asked[0]?.opts?.confirmLabel === "Place as pages" && asked[0]?.opts?.cancelLabel === "Attach as one object", asked[0]?.opts);
  check("three pages make three image objects", objs.length === 3 && objs.every((o) => o.kind === "image"), objs.map((o) => o.kind));
  check("each page has its own url", new Set(objs.map((o) => o.d.url)).size === 3, objs.map((o) => o.d.url));
  check("side by side, same row", objs.every((o) => o.y === objs[0].y) && objs[0].x < objs[1].x && objs[1].x < objs[2].x, objs.map((o) => [o.x, o.y]));
  const imgs = await page.evaluate(() => [...document.querySelectorAll(".wb-object-image img")].map((i) => [i.naturalWidth, i.naturalHeight]));
  check("the page pictures load", imgs.length === 3 && imgs.every(([w, h]) => w > 0 && h > 0), imgs);
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(1200);
  check("one Undo takes all the pages back", (await objects()).length === 0, (await objects()).length);

  // 2. Attach as one object.
  await page.evaluate(() => { window.__answer = false; });
  await drop(makePdf(2), "two.pdf");
  await page.waitForTimeout(3000);
  objs = await objects();
  check("attach makes one image object showing page 1", objs.length === 1 && objs[0].kind === "image" && /\/0$/.test(objs[0].d.url) && !!objs[0].d.pdf, objs);
  await page.evaluate((id) => selectWbItem("object", id), objs[0].id);
  const before = await page.evaluate(() => (wbState.objects[0].width));
  await page.evaluate(async () => { const o = wbState.objects[0]; o.width += 100; await wbSaveObject(o); });
  check("it resizes like any image", (await page.evaluate(() => wbState.objects[0].width)) === before + 100);
  await page.dblclick(`.wb-object-image[data-id="${objs[0].id}"]`, { position: { x: 60, y: 60 } });
  await page.waitForTimeout(1500);
  check("double-click opens the file viewer", await page.evaluate(() => !!document.querySelector(".lightbox")));
  await page.keyboard.press("Escape");
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(1000);

  // 3. Backing out places nothing; over 20 pages is capped.
  const n = (await objects()).length;
  await page.evaluate(() => { window.__answer = undefined; });
  await drop(makePdf(2), "nope.pdf");
  await page.waitForTimeout(2500);
  check("Escape places nothing", (await objects()).length === n - (n ? 0 : 0) && (await objects()).length === n);
  await page.evaluate(() => { window.__answer = true; });
  await drop(makePdf(23), "long.pdf");
  await page.waitForTimeout(9000);
  const placed = (await objects()).length - n;
  check("a 23-page file places 20", placed === 20, placed);
  check("the question says only 20 are placed", /first 20 of 23/.test((await page.evaluate(() => window.__asked)).filter((a) => /to the board/.test(a.msg)).at(-1).msg));
  check("no console errors", errors.length === 0, errors);
  summary();
  await browser.close();
})();
