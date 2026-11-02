// Bringing notes in: Markdown files through Settings, Data (their
// `[[wiki links]]` joined up, and a second import of the same files adding
// nothing), and a Notion export zip.
const { test, expect } = require("@playwright/test");
const { openApp, api, makeZip } = require("../helpers");

// Choosing files shows the preview first (INBOX 1520, S36): every note a
// tick, and its Import press runs it.
async function confirmPreview(page, count) {
  const sheet = page.locator('[data-sheet="import-preview"]');
  await expect(sheet).toContainText(`${count} notes will be imported`, { timeout: 20_000 });
  // Diagnostic only (CI-only failure, five fixes): what the toast yield sees. Asserts nothing.
  console.log("toast-yield probe", JSON.stringify(await page.evaluate(() => {
    const box = document.getElementById("toast-box");
    const a = document.activeElement;
    const area = a && a.closest && a.closest("form, section, [role=dialog]");
    const r = (el) => { const b = el.getBoundingClientRect(); return [b.x, b.y, b.width, b.height].map(Math.round); };
    let err = null;
    try { toastYield(); } catch (e) { err = String(e); }
    return { active: a && `${a.tagName}#${a.id}.${a.className}`, area: area && `${area.tagName}.${area.className}[${area.getAttribute("role")}] role=${area.role}`,
      work: area ? [...area.querySelectorAll("button:not(.panel-grip)")].map((b) => [b.textContent.trim().slice(0, 12), b.checkVisibility({ contentVisibilityAuto: true }), r(b)]) : null,
      toasts: [...box.children].map((t) => [t.className, !!t.toastTimer, r(t)]), cls: box.className, err, ua: navigator.userAgent.slice(-30) };
  })));
  await sheet.getByRole("button", { name: `Import ${count}` }).click();
}

async function findNotes(page, word) {
  const found = await api(page, `/search?q=${encodeURIComponent(word)}&hybrid=false`);
  return found.hits.filter((h) => h.kind === "note");
}

test("Markdown files import as notes with their links, and importing them again adds nothing", async ({ page }) => {
  await openApp(page, "/#/settings/data");
  const tag = `kestrel${Date.now() % 100000}`;
  const files = [
    { name: "Birdwatching.md", mimeType: "text/markdown", buffer: Buffer.from(`# Birdwatching\n\nSaw a ${tag} over the marsh. See [[Binoculars]].\n`) },
    { name: "Binoculars.md", mimeType: "text/markdown", buffer: Buffer.from(`# Binoculars\n\n8x42 for the ${tag} season.\n`) },
  ];
  await page.setInputFiles("#import-md-files", files);
  await confirmPreview(page, 2);
  await expect(page.locator("#import-md-status")).toContainText("Imported 2 notes", { timeout: 20_000 });
  await expect.poll(async () => (await findNotes(page, tag)).length).toBe(2);

  const bird = (await findNotes(page, "Birdwatching"))[0];
  const { links } = await api(page, `/entries/${bird.id}`);
  const targets = JSON.stringify(links);
  expect(targets, "the [[Binoculars]] link was not joined").toContain("Binoculars");

  // The same two files again: nothing new.
  await page.setInputFiles("#import-md-files", files);
  await confirmPreview(page, 2);
  await expect(page.locator("#import-md-status")).toContainText("2 already in your notebook", { timeout: 20_000 });
  expect((await findNotes(page, tag)).length).toBe(2);
});

test("a Notion export zip imports its pages as notes", async ({ page }) => {
  await openApp(page, "/#/settings/data");
  const tag = `ptarmigan${Date.now() % 100000}`;
  const zip = makeZip({
    "Export/Trip ideas 0123456789abcdef0123456789abcdef.md": `# Trip ideas\n\nA ${tag} walk in the Cairngorms.\n`,
    "Export/Reading list fedcba9876543210fedcba9876543210.md": `# Reading list\n\nThe ${tag} chapter of the field guide.\n`,
  });
  await page.setInputFiles("#import-notion-file", { name: "notion-export.zip", mimeType: "application/zip", buffer: zip });
  await confirmPreview(page, 2);
  await expect.poll(async () => (await findNotes(page, tag)).length, { timeout: 20_000 }).toBe(2);
  await expect(page.locator("#import-app-status")).not.toBeEmpty();
});
