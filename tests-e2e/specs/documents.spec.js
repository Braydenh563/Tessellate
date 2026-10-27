// Documents: make one from the Library's Create, write in it, and find it
// whole after a reload with the seeded documents untouched; download it as
// Markdown; bring a Markdown file in as a document.
const { test, expect } = require("@playwright/test");
const { watchErrors, openApp, openTab, api, reloadApp } = require("../helpers");

async function documentList(page) {
  const body = await api(page, "/documents?limit=100");
  return Array.isArray(body) ? body : body.items;
}

test("Library, Create, New document makes a new document, not the last one opened", async ({ page }) => {
  const errors = watchErrors(page);
  await openApp(page);
  const before = await documentList(page);
  // The oldest is the fixture's own: the three workers share one notebook, and
  // the newest can be another spec's document, written to while this one runs.
  const seeded = await api(page, `/documents/${before[before.length - 1].id}`);

  await openTab(page, "library");
  await page.click("#library-new-doc");
  await page.locator(".rich-picker-row", { hasText: "New document" }).click();
  await expect(page.locator("#tab-documents")).toBeVisible();
  const title = `Packing plan ${Date.now() % 100000}`;
  // The title box is focused and empty: a new document is only made on its
  // first edit (dogfood 1025 item 16), so a cancelled one leaves no row.
  await expect(page.locator("#doc-title")).toBeFocused();
  await expect(page.locator("#doc-title")).toHaveValue("");
  await page.keyboard.insertText(title);
  await page.locator('#tab-documents .cm-content[aria-label="Document text"]').click();
  await page.keyboard.insertText("Passports, chargers, the rail pass.");
  await expect(page.locator("#doc-saved")).toHaveText("Saved", { timeout: 15_000 });

  const after = await documentList(page);
  // Counted by title and id, not as before.length + 1: another worker's spec
  // makes documents in the same notebook while this one runs.
  const known = new Set(before.map((d) => d.id));
  const named = after.filter((d) => d.title === title);
  expect(named.length, "the new title went to another document").toBe(1);
  const made = named[0];
  expect(known.has(made.id), "New document made no document").toBe(false);
  const untouched = await api(page, `/documents/${seeded.id}`);
  expect(untouched.title).toBe(seeded.title);
  expect(untouched.content).toBe(seeded.content);

  await openApp(page, `/#/docs/${made.id}`);
  await expect(page.locator("#doc-title")).toHaveValue(title);
  await expect(page.locator("#tab-documents .cm-content")).toContainText("the rail pass");
  expect(errors).toEqual([]);
});

test("a link to an older document opens that document, not the newest", async ({ page }) => {
  await openApp(page);
  const docs = await documentList(page);
  const older = docs[docs.length - 1];
  expect(older.id).not.toBe(docs[0].id);
  await openApp(page, `/#/docs/${older.id}`);
  await expect(page.locator("#doc-title")).toHaveValue(older.title);
  // And it stays: the tab's own first load does not replace it.
  await page.waitForTimeout(1500);
  await expect(page.locator("#doc-title")).toHaveValue(older.title);
});

test("a document downloads as Markdown with its text", async ({ page }) => {
  await openApp(page);
  // The newest document with a line worth checking (an empty one left by an
  // earlier test has none).
  const docs = await documentList(page);
  const doc = docs.find((d) => (d.content || "").split("\n").some((l) => l.trim().length > 20)) || docs[0];
  await openApp(page, `/#/docs/${doc.id}`);
  await expect(page.locator("#doc-title")).toHaveValue(doc.title);
  await page.click("#doc-dock-menu > summary");
  // Download sits in its own submenu (Export ›).
  await page.locator(".menu-group:has(#doc-export-md) > button").first().click();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.click("#doc-export-md"),
  ]);
  const path = await download.path();
  const text = require("fs").readFileSync(path, "utf8");
  const full = await api(page, `/documents/${doc.id}`);
  expect(text).toContain(full.content.split("\n").find((l) => l.trim().length > 20).trim());
});

test("a Markdown file imported from the Library becomes a document", async ({ page }) => {
  await openApp(page);
  //: The documents that existed, by id, not their count: other specs in the
  //: same notebook make documents at the same time (budgets.spec.js's 50,000
  //: word one), so "one more than before" was true only when none landed
  //: in between.
  const before = new Set((await documentList(page)).map((d) => d.id));
  await openTab(page, "library");
  await page.click('#library-subtabs button[data-target="library-view-docs"]');
  const marker = `Imported ${Date.now() % 100000}`;
  await page.setInputFiles("#library-docs-import-input", {
    name: "garden-plan.md",
    mimeType: "text/markdown",
    buffer: Buffer.from(`# Garden plan\n\n${marker}: raised beds along the south fence.\n`),
  });
  await expect
    .poll(async () => {
      const fresh = (await documentList(page)).filter((d) => !before.has(d.id) && /Garden plan|garden-plan/.test(d.title));
      for (const d of fresh) {
        if ((await api(page, `/documents/${d.id}`)).content.includes(marker)) return true;
      }
      return false;
    })
    .toBe(true);
});

// INBOX 648: no unrecoverable loss. A document saves itself 1.2 s after the
// typing stops, and the browser asks before a reload while a save is due;
// a Leave inside that pause (or a desktop window closed, which asks nothing)
// lost the last words for good. They are kept on this device and offered back.
test("words typed just before a reload are kept and put back", async ({ page }) => {
  await openApp(page);
  const made = await api(page, "/documents", {
    method: "POST",
    body: JSON.stringify({ title: `Packing list ${Date.now() % 100000}`, content: "Passport and tickets." }),
  });
  await openApp(page, `/#/docs/${made.id}`);
  await expect(page.locator("#doc-title")).toHaveValue(made.title);
  // The save is held, never answered, so the reload lands inside the pause
  // whatever the load: under CI settings the 1.2 s autosave sometimes landed
  // first and there was nothing left to keep.
  const saveUrl = new RegExp(`/documents/${made.id}$`);
  const held = [];
  await page.route(saveUrl, (route) => (route.request().method() === "PUT" ? held.push(route) : route.continue()));
  const editor = page.locator("#tab-documents .cm-content");
  await editor.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.insertText(" Charger for the camera.");
  await expect(page.locator("#doc-saved")).toContainText("Unsaved");

  page.once("dialog", (dialog) => dialog.accept());
  await reloadApp(page);
  await page.unroute(saveUrl);
  for (const route of held) await route.abort().catch(() => {});
  const offer = page.locator(".toast", { hasText: "unsaved changes" });
  await expect(offer).toBeVisible({ timeout: 15_000 });
  await offer.getByRole("button", { name: "Put them back" }).click();
  await expect(editor).toContainText("Charger for the camera.");
  await expect
    .poll(async () => (await api(page, `/documents/${made.id}`)).content, { message: "the kept words were not saved" })
    .toContain("Charger for the camera.");
});
