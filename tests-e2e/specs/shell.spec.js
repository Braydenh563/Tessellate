// The app around the notes: the command palette (commands and places, handing a
// search to Find anything) and the guided tour it opens,
// the companion shown and hidden, a template made in Settings and used in
// Capture, a space made and a note filed in it, and a setting that is still
// set after a reload.
const { test, expect } = require("@playwright/test");
const { openApp, openTab, api, captureNote, reloadApp } = require("../helpers");

async function palette(page, words) {
  await page.keyboard.press("Control+k");
  await expect(page.locator("#palette-input")).toBeFocused();
  await page.keyboard.type(words);
  await expect(page.locator("#palette-list > *").first()).toBeVisible();
}

test("Ctrl+K, Take the guided tour walks to its second step and closes", async ({ page }) => {
  await openApp(page);
  await palette(page, "Take the guided tour");
  await page.keyboard.press("Enter");
  await expect(page.locator("#tour-next")).toBeVisible();
  const first = await page.locator("#tour-card, .tour-card").first().innerText().catch(() => "");
  await page.click("#tour-next");
  await expect(page.locator("#tour-back")).toBeEnabled();
  const second = await page.locator("#tour-card, .tour-card").first().innerText().catch(() => "");
  expect(second).not.toBe(first);
  await page.click("#tour-close");
  await expect(page.locator("#tour-next")).toBeHidden();
});

test("Ctrl+K offers the matching note, and its last row hands the words to Find anything", async ({ page }) => {
  await openApp(page);
  await captureNote(page, "A note about zephyrquartz and sourdough.");
  await palette(page, "zephyrquartz");
  // Audit 1018 item 10: the top notes that match come under the commands; the
  // handoff to Find anything stays the last row.
  const rows = page.locator("#palette-list .rich-picker-row");
  await expect(rows).toHaveCount(2);
  await expect(rows.first()).toContainText("zephyrquartz");
  await expect(rows.last()).toContainText("Search everything for");
  await rows.last().click();
  await expect(page.locator("#finder-input")).toHaveValue("zephyrquartz");
  await expect(page.locator("#finder-results .finder-row").first()).toContainText("zephyrquartz");
});

test("the companion shows with Ctrl+Shift+Y, stays after a reload, and hides again", async ({ page }) => {
  await openApp(page);
  const buddy = page.locator("#nm-buddy");
  await expect(buddy).toHaveCount(0);
  await page.keyboard.press("Control+Shift+Y");
  await expect(buddy).toBeVisible();
  await reloadApp(page);
  await expect(buddy).toBeVisible();
  await page.keyboard.press("Control+Shift+Y");
  await expect(buddy).toHaveCount(0);
});

test("a template made in Settings fills the Capture box", async ({ page }) => {
  await openApp(page, "/#/settings/templates");
  const name = `Book notes ${Date.now() % 10000}`;
  await page.fill("#template-name", name);
  await page.fill("#template-body", "Book:\nAuthor:\nThoughts:");
  await page.click("#template-add");
  await expect(page.locator("#settings-templates")).toContainText(name);
  await page.keyboard.press("Escape");

  await openApp(page);
  await openTab(page, "notes");
  await page.click('#notes-subtabs [data-section="capture"]');
  await page.click("#entry-template");
  // Choosing is not making (INBOX 410): pick the row, then confirm.
  const picker = page.locator("#note-template-dialog");
  await picker.getByText(name, { exact: true }).click();
  await picker.getByRole("button", { name: "Use this template" }).click();
  await expect(page.locator("#entry-content")).toHaveValue(/Book:\nAuthor:\nThoughts:/);
});

test("a new space holds the note written in it, and All spaces still shows it", async ({ page }) => {
  await openApp(page);
  const name = `Garden ${Date.now() % 10000}`;
  await page.click("#space-switcher-btn");
  await page.click("#space-create-open");
  await page.fill("#space-create-name", name);
  await page.click("#space-create-submit");
  //: Making a space no longer reloads into it (so Undo survives): the toast offers "Open it".
  await page.locator(".toast", { hasText: `Made the space \u201c${name}\u201d` }).getByRole("button", { name: "Open it" }).click();
  await expect(page.locator("#space-current-name")).toHaveText(name);
  const id = await captureNote(page, "Sow the broad beans in November under fleece");
  const spaces = await api(page, "/spaces");
  const space = (spaces.spaces || spaces).find((s) => s.name === name);
  expect((await api(page, `/entries/${id}`)).workspace_id).toBe(space.id);

  await reloadApp(page);
  await expect(page.locator("#space-current-name")).toHaveText(name);
  await page.click("#space-switcher-btn");
  await page.locator("#space-menu").getByText("All spaces").click();
  await expect(page.locator("#space-current-name")).toHaveText("All spaces");
});

test("a setting changed in Settings is still set after a reload", async ({ page }) => {
  await openApp(page, "/#/settings/preferences");
  const name = `Robin ${Date.now() % 1000}`;
  await page.fill("#pref-display-name", name);
  await page.keyboard.press("Tab");
  await expect.poll(async () => (await api(page, "/preferences")).display_name).toBe(name);
  await openApp(page, "/#/settings/preferences");
  await expect(page.locator("#pref-display-name")).toHaveValue(name);
});

test("Ctrl+K types ahead while the palette's own script is still loading", async ({ page }) => {
  // The palette is fetched on its first open; a slow fetch (a cold CI runner)
  // used to lose the words typed at once and the Enter after them.
  await page.route(/app-palette\.js/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.continue();
  });
  await openApp(page);
  await page.keyboard.press("Control+k");
  await page.keyboard.type("Open the bin");
  await page.keyboard.press("Enter");
  await expect(page.locator("#tab-library")).toBeVisible();
  await expect(page.locator("#palette-overlay")).toBeHidden();
});

test("the Guide answers from the app's own help with no model", async ({ page }) => {
  // A received line shadowed the progress line in the stream reader, so the
  // first piece of every answer threw and the Guide said "Something went wrong".
  await openApp(page);
  await page.evaluate(() => openHelpChat());
  await page.fill("#help-chat-input", "how do I export documents?");
  await page.click("#help-chat-send");
  const reply = page.locator(".help-chat-msg.is-assistant:not(.is-pending)").last();
  await expect(reply).toContainText("Documents");
  await expect(reply).not.toContainText("Something went wrong");
});
