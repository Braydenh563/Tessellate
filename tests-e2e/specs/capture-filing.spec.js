// Capture and filing, end to end: the app's core flow, and the strictest
// spec here. The owner, 2026-10-05: "for who knows how long, the actual
// creating and filing of a note was severely broken which is the main
// feature of the app". Thousands of Python tests passed through all of it,
// because none of them typed into the composer and looked at the result.
//
// Every test writes through the real UI, reloads, and asserts what a person
// sees: the note is there, in a category that makes sense, with its tags,
// findable by search, on the timeline and on the graph. No model: the seeded
// notebook (global-setup.js) is what the no-model filing path learns from.
const { test, expect } = require("@playwright/test");
const { watchErrors, openApp, openTab, api, captureNote, waitFiled, noteExists, reloadApp } = require("../helpers");

// One note per seeded category, each written the way a person writes one,
// sharing words with that category's notes but copying none of them.
const NOTES = [
  { text: "Booked the night train from Lisbon to Porto and a hotel near Ribeira #bookings", category: "Travel", tag: "bookings" },
  { text: "Tried a sourdough focaccia: 75% hydration, olive oil, rosemary, baked hot", category: "Cooking" },
  { text: "Harbor launch: the store listing copy and the pricing page are still not signed off", category: "Work" },
  { text: "Long run of 16 km today, the knee held up after the physio exercises", category: "Health" },
];

// WORLD_CLASS_PLAN 23, decision 6: a note that reads as health, money,
// relationships, the law or identity is suggested, not filed, unless the
// Settings switch is on. The first test turns it on so the Health note
// files like the others; the last test leaves it off and checks the hold.
function setAutoFileSensitive(page, on) {
  return api(page, "/preferences", { method: "PUT", body: JSON.stringify({ auto_file_sensitive: on }) });
}

test.describe("capture and filing with no model", () => {
  test("notes written in Capture are filed by meaning, tagged, and still there after a reload", async ({ page }) => {
    const errors = watchErrors(page);
    await openApp(page);
    await setAutoFileSensitive(page, true);
    const ids = [];
    for (const note of NOTES) ids.push(await captureNote(page, note.text));

    // The composer is clear and ready for the next thought.
    await expect(page.locator("#entry-content")).toHaveValue("");
    const shown = await page.evaluate(() => {
      const live = document.querySelector('.cm-content[aria-label="New note"]');
      if (!live) return "";
      const copy = live.cloneNode(true);
      copy.querySelectorAll(".cm-placeholder").forEach((p) => p.remove());
      return copy.textContent.trim();
    });
    expect(shown, "the composer still shows the saved text").toBe("");

    for (const id of ids) await waitFiled(page, id);
    await reloadApp(page);

    for (const [i, note] of NOTES.entries()) {
      const saved = await api(page, `/entries/${ids[i]}`);
      expect(saved.content, "the saved text is the typed text").toBe(note.text);
      expect(saved.category, `"${note.text}" was filed under ${saved.category}`).toBe(note.category);
      expect(saved.is_deleted ?? false).toBe(false);
      if (note.tag) expect(saved.tags, "an inline #tag becomes a tag").toContain(note.tag);
    }

    // The Notes list shows each one, under its category.
    await openTab(page, "notes");
    await page.click('#notes-subtabs [data-section="browse"]');
    const list = page.locator("#entry-list");
    for (const note of NOTES) await expect(list).toContainText(note.text.replace(/ #\w+$/, ""));
    expect(errors).toEqual([]);
    await setAutoFileSensitive(page, false);
  });

  test("a health note is held with its category suggested until the switch is on", async ({ page }) => {
    await openApp(page);
    await setAutoFileSensitive(page, false);
    const id = await captureNote(page, "The physio exercises are working: the knee held up on the 16 km run tonight");
    await waitFiled(page, id);
    const saved = await api(page, `/entries/${id}`);
    expect(saved.category, "a health note is not filed on its own").toBe("Uncategorised");
    const filing = await api(page, `/entries/${id}/filing`);
    expect(filing.held_sensitive?.category, "the hold names the category it would have filed under").toBe("Health");
  });

  test("a full note: title, tags field and a category picked by hand", async ({ page }) => {
    const errors = watchErrors(page);
    await openApp(page);
    const id = await captureNote(page, "Ask the landlord about the damp patch in the back bedroom before winter.", {
      title: "Damp in the back bedroom",
      tags: "landlord, repairs",
      category: "Home",
    });
    await reloadApp(page);
    const saved = await api(page, `/entries/${id}`);
    expect(saved.category).toBe("Home");
    expect(saved.tags).toEqual(expect.arrayContaining(["landlord", "repairs"]));
    expect(saved.title).toBe("Damp in the back bedroom");
    expect(saved.content.startsWith("# Damp in the back bedroom")).toBe(true);
    expect(errors).toEqual([]);
  });

  test("a captured note is findable by keyword search", async ({ page }) => {
    await openApp(page);
    const word = `zanzibarite${Date.now() % 100000}`;
    const id = await captureNote(page, `Found a ${word} sample at the flea market, looks like a geode`);
    await waitFiled(page, id);
    await openTab(page, "notes");
    await page.click('#notes-subtabs [data-section="browse"]');
    await page.fill("#note-search", word);
    await page.keyboard.press("Enter");
    const list = page.locator("#entry-list");
    await expect(list).toContainText(word);
    // Only the match, not the whole notebook.
    await expect.poll(() => list.locator(":scope > li").count()).toBe(1);
  });

  test("a captured note is on the timeline and the graph", async ({ page }) => {
    await openApp(page);
    const text = `Timeline check ${Date.now()}: repotted the fig and moved it to the south window`;
    const id = await captureNote(page, text);
    await waitFiled(page, id);

    await openTab(page, "timeline");
    await expect(page.locator("#tab-timeline .timeline-row").first()).toBeVisible();
    await expect(page.locator("#tab-timeline")).toContainText(text.slice(0, 40));

    await openTab(page, "graph");
    // The Graph tab is a lazy bundle: its lookup does not exist until it has loaded.
    await expect
      .poll(() => page.evaluate((nid) => typeof graphNodeById === "function" && !!graphNodeById(nid), id), {
        message: "the new note is not a node on the graph",
      })
      .toBe(true);
  });

  test("Undo takes a new note back and Redo returns it", async ({ page }) => {
    await openApp(page);
    const text = `Undo check ${Date.now()}: return the library books on Friday`;
    const id = await captureNote(page, text);
    // Out of the composer, so Ctrl+Z is the app's undo, not the editor's
    // own (a text field keeps Ctrl+Z, by design: settings-wiring.js).
    await page.evaluate(() => document.activeElement.blur());
    await page.keyboard.press("Control+z");
    await expect.poll(() => noteExists(page, id), { message: "Undo left the note in place" }).toBe(false);
    await page.keyboard.press("Control+Shift+z");
    await expect.poll(() => noteExists(page, id), { message: "Redo did not bring it back" }).toBe(true);
    await reloadApp(page);
    expect(await noteExists(page, id)).toBe(true);
  });
});

test.describe("other ways in", () => {
  test("Quick note (Alt+N) saves from any tab and is filed", async ({ page }) => {
    await openApp(page);
    await openTab(page, "dashboard");
    await page.keyboard.press("Alt+n");
    const dialog = page.locator("#quick-note");
    await expect(dialog).toBeVisible();
    const text = "Pack the rail pass printout and the plug adapter for the Porto trip";
    await page.fill("#quick-note-text", text);
    await page.click("#quick-note-save");
    await expect(dialog).toBeHidden();
    let note;
    await expect
      .poll(async () => {
        const list = await api(page, "/entries?limit=5");
        note = list.find((e) => e.content === text);
        return !!note;
      })
      .toBe(true);
    note = await waitFiled(page, note.id);
    await reloadApp(page);
    const saved = await api(page, `/entries/${note.id}`);
    expect(saved.content).toBe(text);
    expect(saved.category).toBe("Travel");
  });

  // INBOX 1592: the dashboard's Quick capture is the Notes tab's composer, not a second one.
  test("the dashboard's Quick capture opens the Notes composer and saves a to-do", async ({ page }) => {
    await openApp(page);
    await openTab(page, "dashboard");
    const bar = page.locator(".dash-widget .capture-bar");
    await expect(bar.locator(".capture-bar-input")).toBeVisible();
    await bar.locator(".capture-bar-todo").click();
    const card = bar.locator("#capture-card");
    await expect(card).toBeVisible();
    await expect(card.locator('[data-cc="draw"]')).toBeVisible();
    await expect(card.locator('[data-cc="picture"]')).toBeVisible();
    const title = "Dashboard list for the Porto trip";
    await card.locator('[data-cc="title"]').fill(title);
    await card.locator(".capture-card-item-text").first().fill("rail pass printout");
    await page.keyboard.press("Enter");
    await page.keyboard.type("plug adapter");
    await page.keyboard.press("Control+Enter");
    await expect(card).toBeHidden();
    let note;
    await expect
      .poll(async () => {
        const list = await api(page, "/entries?limit=5");
        note = list.find((e) => e.content.includes(title));
        return !!note;
      })
      .toBe(true);
    expect(note.content).toContain("- [ ] rail pass printout");
    expect(note.content).toContain("- [ ] plug adapter");
  });

  test("pasted text saves exactly as pasted", async ({ page }) => {
    await openApp(page);
    await openTab(page, "notes");
    await page.click('#notes-subtabs [data-section="capture"]');
    const pasted = "Shopping list\n\n- oat milk\n- rye bread\n- lemons";
    await page.evaluate((t) => navigator.clipboard.writeText(t), pasted);
    await page.click("#entry-content");
    await page.keyboard.press("Control+v");
    await expect(page.locator("#entry-content")).toHaveValue(pasted);
    const status = page.locator("#save-status");
    const before = await status.getAttribute("data-entry-id");
    await page.click("#save-btn");
    await expect.poll(() => status.getAttribute("data-entry-id")).not.toBe(before);
    const id = Number(await status.getAttribute("data-entry-id"));
    const saved = await api(page, `/entries/${id}`);
    expect(saved.content).toBe(pasted);
  });
});
