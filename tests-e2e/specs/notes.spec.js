// A note after it is written: edit it in its form and save, bin it and
// restore it from the Library, and an edit left unsaved kept across a
// reload. (Private notes and the lock are in first-run.spec.js.) Each test
// writes its own note through the real composer.
const { test, expect } = require("@playwright/test");
const { watchErrors, openApp, api, captureNote, noteExists, noteRow, menuItem, reloadApp } = require("../helpers");

test("the edit form saves a new title, body and tag, and they survive a reload", async ({ page }) => {
  const errors = watchErrors(page);
  await openApp(page);
  const id = await captureNote(page, "Draft agenda for the offsite: roadmap in the afternoon");
  const row = await noteRow(page, id);
  await row.locator('button[aria-label="Edit this entry"]').click();
  const title = row.locator(".note-edit-title");
  await expect(title).toBeVisible();
  await title.fill("Offsite agenda");
  const body = row.locator('.cm-content[aria-label="Note text"]');
  await body.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.insertText("\n\nDinner somewhere with a long table.");
  await row.locator(".note-edit-tag-input").fill("offsite");
  await page.keyboard.press("Enter");
  await row.locator("button", { hasText: "Save changes" }).click();
  await expect(row.locator(".note-edit-title")).toHaveCount(0);

  await reloadApp(page);
  const saved = await api(page, `/entries/${id}`);
  expect(saved.title).toBe("Offsite agenda");
  expect(saved.content).toContain("roadmap in the afternoon");
  expect(saved.content).toContain("Dinner somewhere with a long table.");
  expect(saved.tags).toContain("offsite");
  // And the card the list draws says so.
  await expect(await noteRow(page, id)).toContainText("Offsite agenda");
  expect(errors).toEqual([]);
});

test("Move to bin, then Restore from the Library's bin, brings the note back", async ({ page }) => {
  await openApp(page);
  const text = `Bin check ${Date.now()}: renew the passport before March`;
  const id = await captureNote(page, text);
  const row = await noteRow(page, id);
  await menuItem(page, row, "Move to bin");
  await expect.poll(() => noteExists(page, id)).toBe(false);
  await expect(page.locator(`#entry-list > li[data-id="${id}"]`)).toHaveCount(0);

  // The bin, the way the Guide says to reach it: Ctrl+K, "Open the bin".
  await page.keyboard.press("Control+k");
  await page.keyboard.type("Open the bin");
  await page.keyboard.press("Enter");
  await expect(page.locator("#tab-library")).toBeVisible();
  const binned = page.locator("#library-grid .library-card", { hasText: text });
  await expect(binned).toBeVisible();
  await binned.locator("button[aria-label^=\"Actions for\"]").click();
  await page.locator(".action-menu:not(.hidden) [role=menuitem]", { hasText: "Restore" }).click();
  await expect.poll(() => noteExists(page, id)).toBe(true);

  await reloadApp(page);
  await expect(await noteRow(page, id)).toContainText("renew the passport");
});

test("an edit left unsaved in the form survives a reload and can be reopened", async ({ page }) => {
  await openApp(page);
  const id = await captureNote(page, `Reload check ${Date.now() % 100000}: the bike lock code`);
  const row = await noteRow(page, id);
  await row.locator('button[aria-label="Edit this entry"]').click();
  const body = row.locator('.cm-content[aria-label="Note text"]');
  await body.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.insertText(" is 2210, not 2201");
  // The browser asks before leaving; this run says Leave, the way a person
  // in a hurry does, and the edit must still be there to come back to.
  page.once("dialog", (dialog) => dialog.accept());
  await reloadApp(page);
  const offer = page.locator(".toast", { hasText: "unsaved changes" });
  await expect(offer).toBeVisible({ timeout: 15_000 });
  await offer.getByRole("button", { name: "Open them" }).click();
  const form = page.locator(`#entry-list > li[data-id="${id}"] textarea.note-edit-box`);
  await expect(form).toHaveValue(/is 2210, not 2201/);
  await page.locator(`#entry-list > li[data-id="${id}"]`).locator("button", { hasText: "Save changes" }).click();
  await expect.poll(async () => (await api(page, `/entries/${id}`)).content).toContain("is 2210, not 2201");
});

// Found by this suite flaking on CI settings: the tag list is fetched on the
// field's first focus, and when that answer came after the tag was typed and
// Enter pressed, the list opened then, every tag in it, over Save changes; a
// press meant for Save took a tag nobody chose. The answer is held back here
// so the order is certain, not a matter of load.
// Twice: once with the tags slow to come, once with the list's own file
// (tag-suggest.js, loaded on the first focus) slow to come.
// The page's service worker answers its own scripts from the shell cache, and
// `page.route` never sees a request a service worker answered: the list's file
// was not held at all, the tags were fetched before the spec's wait began, and
// the spec waited for a response that had already come. Blocked here, the
// holds are real again.
test.describe("held answers", () => {
  test.use({ serviceWorkers: "block" });
for (const [slow, url] of [["the tags arrive", /\/tags(\?|$)/], ["the list's code arrives", /tag-suggest\.js/]]) test(`a tag typed and entered before ${slow} does not open the list over Save`, async ({ page }) => {
  await openApp(page);
  const id = await captureNote(page, `Tag race ${Date.now()}: call the plumber about the boiler`);
  const row = await noteRow(page, id);
  await row.locator('button[aria-label="Edit this entry"]').click();
  let release;
  const held = new Promise((resolve) => (release = resolve));
  await page.route(url, async (route) => {
    await held;
    await route.continue();
  });
  const input = row.locator(".note-edit-tag-input");
  await input.click();
  await page.keyboard.insertText("plumbing");
  await page.keyboard.press("Enter");
  await expect(row.locator(".note-edit-tags")).toContainText("plumbing");
  // Listening before the release, so a quick answer is not missed.
  const answered = page.waitForResponse(/\/tags(\?|$)/);
  release();
  await answered;
  // The list's own work after the answer is one render; give it that frame.
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  await expect(page.locator(".tag-suggest:not(.hidden)")).toHaveCount(0);
  await row.locator("button", { hasText: "Save changes" }).click();
  await expect.poll(async () => (await api(page, `/entries/${id}`)).tags).toEqual(["plumbing"]);
});
});

// The third late arrival (BACKLOG 1682): not an answer but the keyboard. A
// change poll redraws the list, the form's row is carried through it and the
// tags field loses the keyboard with the move. Two things followed under load:
// keys typed before the next frame went to the page, not the field, and the
// focus the app then gave back took the "a tag was just entered" flag away and
// opened the list over Save. The redraw is the app's own (`renderEntries` with
// the `loadEntries` hold and restore), not a hand-made blur.
test("a redraw of the list leaves the tags field focused at once and its list shut", async ({ page }) => {
  await openApp(page);
  const id = await captureNote(page, `Tag restore ${Date.now()}: ring the plumber about the boiler`);
  const row = await noteRow(page, id);
  await row.locator('button[aria-label="Edit this entry"]').click();
  const input = row.locator(".note-edit-tag-input");
  await input.click();
  await expect(page.locator(".tag-suggest:not(.hidden)")).toHaveCount(1);
  await page.keyboard.press("Escape");
  await page.keyboard.insertText("zzqqnomatch");
  await page.keyboard.press("Enter");
  await expect(row.locator(".note-edit-tags")).toContainText("zzqqnomatch");
  await expect(page.locator(".tag-suggest:not(.hidden)")).toHaveCount(0);
  const heldAfterRedraw = await page.evaluate(async () => {
    const held = heldNoteControl();
    await renderEntries();
    restoreNoteControl(held);
    // No frame waited: a key typed now must land in the field.
    return document.activeElement?.classList.contains("note-edit-tag-input") ?? false;
  });
  expect(heldAfterRedraw).toBe(true);
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  await expect(page.locator(".tag-suggest:not(.hidden)")).toHaveCount(0);
  // A person's press in the same field still opens it.
  await page.locator(".note-edit-tag-input").click();
  await expect(page.locator(".tag-suggest:not(.hidden)")).toHaveCount(1);
});

// And the guard above keeps the list itself: a press in an empty tags field,
// with the tags slow to come, still opens it once they do.
test("a press in an empty tags field shows the tags already used", async ({ page }) => {
  await openApp(page);
  const id = await captureNote(page, `Tag list ${Date.now()}: the sourdough starter needs feeding`);
  const row = await noteRow(page, id);
  await row.locator('button[aria-label="Edit this entry"]').click();
  let release;
  const held = new Promise((resolve) => (release = resolve));
  await page.route(/\/tags(\?|$)/, async (route) => {
    await held;
    await route.continue();
  });
  await row.locator(".note-edit-tag-input").click();
  release();
  await expect(page.locator(".tag-suggest:not(.hidden) [role=option]").first()).toBeVisible();
});
