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
  // What the toast stack measured when the press is tried: CI's toast stays
  // un-yielded over Import (2026-11-02, three fixes in), and no local run
  // reproduces it, so the run prints the numbers instead of a guess.
  console.log("import-preview yield", JSON.stringify(await page.evaluate(() => {
    const box = document.getElementById("toast-box");
    const r = (el) => el && [...["x", "y", "width", "height"].map((k) => Math.round(el.getBoundingClientRect()[k]))];
    const press = [...document.querySelectorAll('[data-sheet="import-preview"] button')].find((b) => /Import \d/.test(b.textContent));
    const active = document.activeElement;
    return { yielding: box.className, press: r(press), active: `${active?.tagName}.${active?.type || ""} in sheet ${!!active?.closest("[data-sheet]")}`, area: active?.closest("form, section, [role=dialog]")?.tagName, toasts: [...box.children].map((t) => [t.className, ...r(t), !!t.toastTimer]) };
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
