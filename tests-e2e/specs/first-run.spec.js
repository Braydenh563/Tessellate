// A brand-new notebook (the "first-run" project's own server and data dir):
// what a first note does with no model and nothing to learn from, what the
// empty screens say, and a full backup, sealed with a password, taken and
// restored through Settings. Restore replaces the notebook, which is why it
// runs here and not on the shared seeded one.
const fs = require("fs");
const { test, expect } = require("@playwright/test");
const { watchErrors, openApp, openTab, api, captureNote, waitFiled, noteExists, noteRow, menuItem, confirm, reloadApp } = require("../helpers");

test.describe.configure({ mode: "serial" });

// First, while the notebook is new (WORLD_CLASS_PLAN 25c): the dashboard's
// three steps, ticked as each is done; the sample notebook, offered once,
// answered from with no model, and taken away again to the bin.
test("a new notebook starts in three steps, and the sample notebook comes and goes", async ({ page }) => {
  const errors = watchErrors(page);
  await openApp(page);
  // A new notebook asks once whether to check for updates: this walk says no.
  await page.locator(".confirm-overlay button", { hasText: "Don't check" }).click({ timeout: 10_000 }).catch(() => {});
  await openTab(page, "dashboard");
  const steps = page.locator(".first-steps");
  // The one-row head since INBOX 1301 D2: "Get started", "0 of 3 done".
  await expect(steps.locator("#first-steps-title")).toHaveText("Get started");
  await expect(steps.locator(".first-steps-count")).toHaveText("0 of 3 done");
  await expect(steps.locator(".start-step.is-done")).toHaveCount(0);

  // Step one is typed where it is asked.
  await page.fill("#first-steps-name", "Robin");
  await page.press("#first-steps-name", "Enter");
  await expect(steps.locator(".start-step.is-done")).toHaveCount(1);

  // The sample's door is in the card's menu since D2 (it was a row of buttons
  // that changed the card's height).
  const firstStepsMenu = async (name) => {
    await steps.locator('button[aria-label="More about the first steps"]').click();
    return page.locator(".action-menu:not(.hidden) [role=menuitem]", { hasText: name });
  };
  await (await firstStepsMenu("Try a sample notebook")).click();
  // Eight saves, the first loading the search model: allowed a minute.
  await expect.poll(async () => (await api(page, "/help/sample-notebook")).live, { timeout: 60_000 }).toBe(8);

  // Step three with no model: the answer is the sample's own sentence.
  await steps.locator(".start-step").nth(2).click();
  await page.fill("#question", "where is the spare key?");
  await page.press("#question", "Enter");
  await expect(page.locator("#tab-notes")).toContainText("blue flowerpot");

  await openTab(page, "dashboard");
  // Your name and an answer; the sample notes are not your first note.
  await expect(steps.locator(".start-step.is-done")).toHaveCount(2);
  await (await firstStepsMenu("Remove the sample notes")).click();
  await expect.poll(async () => (await api(page, "/help/sample-notebook")).live).toBe(0);
  // Offered once: not again on this notebook.
  await expect(await firstStepsMenu("Try a sample notebook")).toHaveCount(0);
  await page.keyboard.press("Escape");
  const categories = (await api(page, "/categories")).map((c) => c.name);
  expect(categories, "the sample's categories went with it").not.toContain("Recipes");
  expect(errors).toEqual([]);
});

test("the empty notebook says what to do, and a first note is saved and says why it is Uncategorised", async ({ page }) => {
  const errors = watchErrors(page);
  await openApp(page);
  await openTab(page, "notes");
  await page.click('#notes-subtabs [data-section="browse"]');
  // An empty list is a sentence with a next step, not a blank.
  await expect(page.getByText("Your notebook is empty")).toBeVisible();
  await expect(page.getByText("Type a thought and Atlas files it for you.")).toBeVisible();

  const id = await captureNote(page, "First note: the spare key is under the blue pot");
  await waitFiled(page, id);
  // No model and nothing filed yet: it says so, and offers the choice.
  await expect(page.locator("#save-status")).toContainText("no AI model is running");
  await reloadApp(page);
  const saved = await api(page, `/entries/${id}`);
  expect(saved.category).toBe("Uncategorised");
  expect(errors).toEqual([]);
});

test("a sealed full backup restores the notebook as it was", async ({ page }) => {
  await openApp(page);
  const kept = await captureNote(page, `Kept by the backup ${Date.now() % 100000}`);

  await openApp(page, "/#/settings/data");
  await page.fill("#export-backup-password", "backup-pass-1234");
  const [download] = await Promise.all([page.waitForEvent("download"), page.click("#export-backup-zip")]);
  expect(download.suggestedFilename()).toMatch(/\.mmenc$/);
  const sealed = fs.readFileSync(await download.path());
  expect(sealed.subarray(0, 2).toString("latin1"), "a sealed backup is not a plain zip").not.toBe("PK");

  await page.keyboard.press("Escape");
  const lost = await captureNote(page, `Written after the backup ${Date.now() % 100000}`);

  await openApp(page, "/#/settings/data");
  await page.fill("#restore-bundle-password", "backup-pass-1234");
  await page.setInputFiles("#restore-bundle-file", {
    name: "memorymap-backup.mmenc",
    mimeType: "application/octet-stream",
    buffer: sealed,
  });
  // It says Restored, then reloads itself to the lock screen 1.2 s later
  // (settings-controls.js); wait for that navigation, not for a guess at it,
  // so openApp cannot start signing in on the page that is about to go.
  const reloaded = page.waitForEvent("domcontentloaded", { timeout: 30_000 });
  await page.locator(".confirm-overlay button:not(:has-text('Cancel'))").last().click();
  await expect(page.locator("#restore-bundle-status")).toContainText("Restored");
  await reloaded;
  await openApp(page);
  expect(await noteExists(page, kept), "the note in the backup came back").toBe(true);
  expect(await noteExists(page, lost), "the note written after the backup is gone").toBe(false);
});

test("a plain full backup is a zip", async ({ page }) => {
  await openApp(page, "/#/settings/data");
  const [download] = await Promise.all([page.waitForEvent("download"), page.click("#export-backup-zip")]);
  expect(download.suggestedFilename()).toMatch(/\.zip$/);
  const bytes = fs.readFileSync(await download.path());
  expect(bytes.subarray(0, 2).toString("latin1")).toBe("PK");
});

// Here, not on the shared notebook: locking ends every session the other
// specs saved, and each of them would then meet the lock screen.
test("a private note is encrypted, kept out of search, and readable again after lock and unlock", async ({ page }) => {
  await openApp(page);
  const word = `quokkaberry${Date.now() % 100000}`;
  const id = await captureNote(page, `My locker code is 4417, the ${word} one`);
  const row = await noteRow(page, id);
  await menuItem(page, row, "Make private");
  await confirm(page);
  await expect.poll(async () => (await api(page, `/entries/${id}`)).is_private).toBe(true);

  const found = await api(page, `/search?q=${word}`);
  const hits = found.hits.filter((h) => h.kind === "note").map((h) => h.id);
  expect(hits, "a private note was returned by search").not.toContain(id);

  // Lock the app and come back in with the password.
  await page.click("#lock-btn");
  await expect(page.locator("#lock-password")).toBeVisible();
  await openApp(page);
  const back = await api(page, `/entries/${id}`);
  expect(back.content).toContain("locker code is 4417");
});
