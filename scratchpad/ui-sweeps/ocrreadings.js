// **The lightbox and the OCR workspace show, and delete, the same readings**
// (INBOX 421 e, the owner: "I cant delete the ocr entry in the workspace or
// the lightbox and the text in the lightbox doesnt even appear in the ocr
// workspace").
//
// One picture with both stored readings, the vision model's and Tesseract's.
//   1. The lightbox (Library, Images) shows both, each with a delete; a real
//      click on the Tesseract one's delete, confirmed, clears that field only.
//   2. The workspace, with its reader on the AI model (the owner's setting,
//      no Tesseract run), shows the vision reading as its sections and the
//      Tesseract one beside them, labelled; its delete clears that field.
//
//   BASE=http://127.0.0.1:8793 SCRATCH=/tmp/mm PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/ocrreadings.js
const { boot } = require("./lib.js");

let failures = 0;
function check(label, ok, detail) {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}

const VISION = "Goal\n\nPeople and tests, read by the model.";
const TESS = "Goal People tests (Tesseract)";

async function seed(page) {
  return page.evaluate(async ({ VISION, TESS }) => {
    const c = document.createElement("canvas");
    c.width = 80; c.height = 60;
    const g = c.getContext("2d");
    g.fillStyle = "#246"; g.fillRect(0, 0, 80, 60);
    const blob = await new Promise((r) => c.toBlob(r, "image/png"));
    const fd = new FormData();
    fd.append("file", new File([blob], `readings-${Date.now()}.png`, { type: "image/png" }));
    fd.append("direct", "true");
    const r = await fetch("/media/upload", { method: "POST", body: fd, headers: { "X-Auth-Token": authToken(), "X-Workspace-ID": activeSpaceId() } });
    const media = await r.json();
    await apiJson(`/media/${media.id}/vision-ocr`, { method: "POST", body: JSON.stringify({ text: VISION }) });
    await apiJson(`/media/${media.id}/ocr`, { method: "POST", body: JSON.stringify({ text: TESS }) });
    return media;
  }, { VISION, TESS });
}

async function fields(page, media) {
  return page.evaluate(async (m) => {
    const row = await apiJson(`/media/meta/${encodeURIComponent(m.url.split("/").pop())}`);
    return { vision: row.vision_ocr_text || "", tess: row.ocr_text || "" };
  }, media);
}

// A delete that bins with Undo asks nothing, so only a real confirm dialog
// is answered: matching any open overlay's buttons pressed the workspace's
// own "Delete this reading" (the vision reading) after the Tesseract one.
async function confirmYes(page) {
  await page.waitForTimeout(300);
  const asked = await page.evaluate(() => {
    const b = [...document.querySelectorAll(".confirm-overlay:not(.hidden) button")]
      .find((x) => /delete|ok|yes|confirm/i.test(x.textContent || ""));
    b?.click();
    return Boolean(b);
  });
  await page.waitForTimeout(700);
  return asked;
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  try {
    let media = await seed(page);
    // 1. The lightbox.
    await page.evaluate(() => switchTab("library"));
    await page.waitForTimeout(800);
    await page.evaluate(() => [...document.querySelectorAll("#library-subtabs button")].find((b) => /image/i.test(b.textContent || ""))?.click());
    await page.waitForTimeout(2000);
    const at = await page.evaluate((file) => {
      const el = [...document.querySelectorAll("img")].find((i) => i.getBoundingClientRect().width
        && (i.closest("[data-id], li, article, .card")?.textContent || "").includes(file));
      if (!el) return null;
      el.scrollIntoView({ block: "center" });
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    }, media.original_name || media.filename);
    if (!at) {
      check("the Library shows the picture", false);
    } else {
      await page.mouse.click(at.x, at.y);
      await page.waitForTimeout(1200);
      const lb = await page.evaluate(() => {
        const box = [...document.querySelectorAll(".lightbox")].pop();
        const texts = [...box.querySelectorAll(".lightbox-text:not(.hidden)")].map((p) => p.textContent);
        const dels = [...box.querySelectorAll(".lightbox-reading-delete:not(.hidden)")].map((b) => {
          const r = b.getBoundingClientRect();
          return { x: r.left + r.width / 2, y: r.top + r.height / 2, byline: b.previousElementSibling?.textContent || "" };
        });
        return { texts, dels };
      });
      await page.screenshot({ path: `${process.env.SCRATCH || "."}/shots/ocrreadings-lightbox-${process.env.THEME || "light"}.png` });
      check("lightbox: both readings shown", lb.texts.length === 2, lb.texts.map((t) => t.slice(0, 30)).join(" | "));
      check("lightbox: each reading has a delete", lb.dels.length === 2, lb.dels.map((d) => d.byline).join(" | "));
      const tess = lb.dels.find((d) => /tesseract/i.test(d.byline));
      if (tess) {
        await page.mouse.click(tess.x, tess.y);
        const confirmed = await confirmYes(page);
        const f = await fields(page, media);
        const after = await page.evaluate(() => [...[...document.querySelectorAll(".lightbox")].pop().querySelectorAll(".lightbox-text:not(.hidden)")].length);
        check("lightbox: deleting the Tesseract reading clears that field only", confirmed && !f.tess && f.vision.startsWith("Goal") && after === 1,
          `confirmed ${confirmed}, vision ${Boolean(f.vision)}, tesseract ${Boolean(f.tess)}, readings on screen ${after}`);
      }
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
    }
    // 2. The workspace, reader on the AI model.
    media = await seed(page);
    await page.evaluate(async (m) => {
      const row = await apiJson(`/media/meta/${encodeURIComponent(m.url.split("/").pop())}`);
      const sel = document.getElementById("ocr-reader");
      const model = [...(sel?.options || [])].find((o) => o.value !== "tesseract");
      if (sel && model) sel.value = model.value;
      openOcrWorkspace({ ...row, _isImage: true }, [{ ...row, _isImage: true }]);
    }, media);
    await page.waitForTimeout(2000);
    const ws = await page.evaluate(() => {
      const regions = [...document.querySelectorAll("#ocr-region-list .ocr-region")].map((r) => r.textContent);
      const others = [...document.querySelectorAll("#ocr-other-readings:not(.hidden) .ocr-other-reading")].map((r) => ({
        label: r.querySelector(".ocr-other-reading-label")?.textContent || "", text: r.querySelector(".ocr-other-reading-text")?.textContent || "",
      }));
      return { reader: document.getElementById("ocr-reader")?.value, regions, others };
    });
    check("workspace (reader on the model): the vision reading is its sections", ws.regions.join(" ").includes("Goal") && ws.regions.join(" ").includes("People and tests"),
      `reader ${ws.reader}, ${ws.regions.length} sections`);
    check("workspace: the Tesseract reading is listed beside them, labelled", ws.others.length === 1 && /tesseract/i.test(ws.others[0].label) && ws.others[0].text.includes("Tesseract"),
      ws.others.map((o) => `${o.label}: ${o.text.slice(0, 30)}`).join(" | ") || "none");
    const del = await page.evaluate(() => {
      const b = document.querySelector("#ocr-other-readings .ocr-other-reading-delete");
      if (!b) return null;
      const r = b.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    });
    if (del) {
      await page.mouse.click(del.x, del.y);
      await confirmYes(page);
      const f = await fields(page, media);
      const left = await page.evaluate(() => document.querySelectorAll("#ocr-other-readings:not(.hidden) .ocr-other-reading").length);
      check("workspace: its delete clears the Tesseract field only", !f.tess && Boolean(f.vision) && left === 0,
        `vision ${Boolean(f.vision)}, tesseract ${Boolean(f.tess)}, listed ${left}`);
    }
    await page.screenshot({ path: `${process.env.SCRATCH || "."}/shots/ocrreadings-${process.env.THEME || "light"}.png` });
  } finally {
    await browser.close();
  }
  console.log(failures ? `${failures} failed` : "all passed");
  process.exit(failures ? 1 : 0);
})();
