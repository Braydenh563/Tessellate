// INBOX 440 (2): the attachment cards. Seeds one note per file kind (an
// image, a PDF and a text file, attached and inline), then measures and
// shoots every surface that draws an attachment: a note card in the list,
// the note's edit form, and the Capture box.
//
//   BASE=http://127.0.0.1:8789 TAG=before node scratchpad/ui-sweeps/attachcards.js
//   THEME=dark W=390 TAG=after node scratchpad/ui-sweeps/attachcards.js
//
// Writes scratchpad/ui-sweeps/out/attach-<TAG>-<theme>-<width>-<surface>.png
// and prints one JSON line of measurements per surface.
const { boot } = require("./lib");
const path = require("path");
const OUTDIR = path.join(__dirname, "out");
require("fs").mkdirSync(OUTDIR, { recursive: true });
const W = Number(process.env.W || 1280);
const TAG = process.env.TAG || "after";
const THEME = process.env.THEME || "light";
const phone = W < 600;

(async () => {
  const { browser, page } = await boot({
    viewport: { width: W, height: phone ? 844 : 900 },
    ...(phone ? { hasTouch: true, isMobile: true } : {}),
  });
  const shot = (name) => path.join(OUTDIR, `attach-${TAG}-${THEME}-${W}-${name}.png`);

  // Seed once per data dir: the note carrying the marker is looked up first.
  const ids = await page.evaluate(async () => {
    const all = await apiJson("/entries?limit=200").catch(() => []);
    const list = Array.isArray(all) ? all : all.items || [];
    const found = list.find((e) => (e.content || "").startsWith("Gary The Moss Monster"));
    if (found) return { id: found.id };
    const canvas = document.createElement("canvas");
    canvas.width = 640; canvas.height = 480;
    const g = canvas.getContext("2d");
    g.fillStyle = "#fff"; g.fillRect(0, 0, 640, 480);
    g.strokeStyle = "#2e7d32"; g.lineWidth = 8;
    g.beginPath(); g.arc(320, 260, 140, 0, Math.PI * 2); g.stroke();
    g.fillStyle = "#222"; g.beginPath(); g.arc(270, 230, 14, 0, 7); g.arc(370, 230, 14, 0, 7); g.fill();
    const png = await new Promise((r) => canvas.toBlob(r, "image/png"));
    const headers = { "X-Auth-Token": authToken(), "X-Workspace-ID": activeSpaceId() };
    const up = async (blob, name) => {
      const form = new FormData();
      form.append("file", new File([blob], name, { type: blob.type }));
      return (await fetch("/media/upload", { method: "POST", headers, body: form })).json();
    };
    const pdfText = "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF";
    const img = await up(png, "Gary The Moss Monster drawing final v2.png");
    const pdf = await up(new Blob([pdfText], { type: "application/pdf" }), "CAB432 week 7 lecture slides on agents.pdf");
    const content = `Gary The Moss Monster :D\n\n![Gary The Moss Monster drawing final v2.png](${img.url})\n\n[CAB432 week 7 lecture slides on agents.pdf](${pdf.url})`;
    const e = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content, category: "Art", tags: [] }) });
    const attach = async (blob, name) => {
      const form = new FormData();
      form.append("file", new File([blob], name, { type: blob.type }));
      await fetch(`/entries/${e.id}/files`, { method: "POST", headers, body: form });
    };
    await attach(png, "Gary sketch attached.png");
    await attach(new Blob([pdfText], { type: "application/pdf" }), "Reading list for the semester.pdf");
    await attach(new Blob(["Some plain text notes.\nLine two.\n"], { type: "text/plain" }), "meeting-notes.txt");
    return { id: e.id, imgUrl: img.url };
  });

  // Surface 1: the note card in the list.
  await page.evaluate(() => { switchTab("notes"); window.showNotesSection && showNotesSection("browse"); notesViewMode = "cards"; loadEntries(); });
  await page.waitForTimeout(2500);
  const measure = (scope) => page.evaluate((scope) => {
    const host = document.querySelector(scope);
    if (!host) return { scope, missing: true };
    const cards = [...host.querySelectorAll(".att-card")];
    const old = host.querySelectorAll(".attachment-chip, .file-card, .thumb-wrap, .entry-links .chip").length;
    return {
      scope,
      oldShapes: old,
      cards: cards.map((c) => {
        const r = c.getBoundingClientRect();
        const name = c.querySelector(".att-card-name");
        const meta = c.querySelector(".att-card-meta");
        const open = c.querySelector(".att-card-open");
        const more = c.querySelector(".att-card-more");
        const mr = more?.getBoundingClientRect();
        const ns = name && getComputedStyle(name);
        return {
          kind: c.dataset.kind,
          w: Math.round(r.width), h: Math.round(r.height),
          name: name?.textContent, nameTitle: name?.title,
          nameClipped: name ? name.scrollHeight > name.clientHeight + 1 : null,
          nameLines: name ? Math.round(name.getBoundingClientRect().height / parseFloat(ns.lineHeight)) : null,
          meta: meta?.textContent,
          openTag: open?.tagName, openLabel: open?.getAttribute("aria-label"),
          more: more && { w: Math.round(mr.width), h: Math.round(mr.height), label: more.getAttribute("aria-label"), title: more.title },
          overflowX: c.scrollWidth > c.clientWidth + 1,
        };
      }),
    };
  }, scope);
  const card = `#entry-list > li[data-id="${ids.id}"]`;
  await page.locator(card).scrollIntoViewIfNeeded().catch(() => null);
  console.log(JSON.stringify({ surface: "note", ...(await measure(card)) }));
  await page.locator(card).screenshot({ path: shot("note") }).catch((e) => console.log("shot note", e.message));

  // The kebab menu, opened from the first card, and its rows.
  const moreBtn = page.locator(`${card} .att-card-more`).first();
  if (await moreBtn.count()) {
    await moreBtn.click();
    await page.waitForTimeout(400);
    const rows = await page.evaluate(() => {
      const menu = [...document.querySelectorAll('[role="menu"]')].find((m) => m.getClientRects().length);
      return menu ? [...menu.querySelectorAll('[role="menuitem"]')].map((b) => `${b.textContent.trim()}${b.disabled || b.getAttribute("aria-disabled") === "true" ? " (disabled)" : ""}`) : null;
    });
    console.log(JSON.stringify({ surface: "menu", rows }));
    await page.screenshot({ path: shot("menu") });
    await page.keyboard.press("Escape");
  }

  // Surface 2: the edit form of the same note.
  await page.evaluate((id) => { setEditingNote(id); renderEntries(); }, ids.id);
  await page.waitForTimeout(1500);
  const editHost = "#entry-edit-attachment-chips";
  console.log(JSON.stringify({ surface: "edit", ...(await measure(editHost)) }));
  await page.locator(editHost).screenshot({ path: shot("edit") }).catch((e) => console.log("shot edit", e.message));

  // Surface 3: the Capture box, holding the same two references.
  await page.evaluate(() => { switchTab("notes"); window.showNotesSection && showNotesSection("capture"); });
  await page.waitForTimeout(600);
  await page.evaluate((id) => {
    const note = document.querySelector(`#entry-list > li[data-id="${id}"] textarea`);
    const box = document.getElementById("entry-content");
    const src = note ? note.value : "";
    box.value = src.split("\n").slice(2).join("\n");
    box.dispatchEvent(new Event("input", { bubbles: true }));
  }, ids.id);
  await page.waitForTimeout(800);
  const capHost = "#entry-attachment-chips";
  console.log(JSON.stringify({ surface: "capture", ...(await measure(capHost)) }));
  await page.locator("#entry-content").scrollIntoViewIfNeeded().catch(() => null);
  const capArea = await page.evaluate(() => {
    const a = document.getElementById("entry-attachment-chips");
    const b = document.getElementById("entry-file-strip");
    const rs = [a, b].filter((x) => x && x.getClientRects().length).map((x) => x.getBoundingClientRect());
    if (!rs.length) return null;
    const top = Math.min(...rs.map((r) => r.top)), bottom = Math.max(...rs.map((r) => r.bottom));
    const left = Math.min(...rs.map((r) => r.left)), right = Math.max(...rs.map((r) => r.right));
    return { x: Math.max(0, left - 8), y: Math.max(0, top - 8), width: right - left + 16, height: bottom - top + 16 };
  });
  if (capArea) await page.screenshot({ path: shot("capture"), clip: capArea });
  // Clear the draft so the next run starts clean.
  await page.evaluate(() => { const box = document.getElementById("entry-content"); box.value = ""; box.dispatchEvent(new Event("input", { bubbles: true })); });
  await browser.close();
})();
