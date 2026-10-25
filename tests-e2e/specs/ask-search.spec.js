// Finding things with no model: search by words and by meaning, Ask with
// its numbered citations, and Chat saying plainly that it needs a model
// rather than offering a Send that does nothing. The seeded notebook is the
// source (global-setup.js); a model, when there is one, is covered by the
// evals (`pytest -m evals`), never here.
const { test, expect } = require("@playwright/test");
const { watchErrors, openApp, openTab, api } = require("../helpers");

async function browse(page) {
  await openTab(page, "notes");
  await page.click('#notes-subtabs [data-section="browse"]');
}

test("keyword search finds the seeded note by a word in its body", async ({ page }) => {
  await openApp(page);
  await browse(page);
  await page.fill("#note-search", "Pendular");
  await page.keyboard.press("Enter");
  const list = page.locator("#entry-list");
  await expect(list).toContainText("Lisbon to Porto on the Alfa Pendular");
  await expect.poll(() => list.locator(":scope > li").count()).toBeLessThan(5);
});

test("meaning search answers a question that shares few words with the note", async ({ page }) => {
  await openApp(page);
  await browse(page);
  // The toggle lives in the search box's own menu.
  const toggle = page.locator("#semantic-search-toggle");
  if (!(await toggle.isVisible())) await page.click("#notes-filter-menu > summary");
  await toggle.check();
  await page.fill("#note-search", "bread baking log");
  await page.keyboard.press("Enter");
  // With no embedding model this is keyword search with stemming (the
  // documented fallback); either way the sourdough log is the answer.
  await expect(page.locator("#entry-list")).toContainText("Sourdough log");
});

test("Ask with no model answers from the notes, with numbered citations that open them", async ({ page }) => {
  const errors = watchErrors(page);
  await openApp(page);
  await openTab(page, "notes");
  await page.click('#notes-subtabs [data-section="ask"]');
  await page.fill("#question", "How long is the train from Lisbon to Porto?");
  await page.click("#ask-btn");
  const answer = page.locator("#ai-answer");
  // With no model the answer is composed from the notes (INBOX 688): marked
  // as such, every sentence the notes' own.
  await expect(answer).toHaveClass(/answer-composed/);
  // The chip over the answer says where it came from (CHAT_PLAN decision 36).
  await expect(page.locator("#answered-by")).toHaveText("From your notes");
  await expect(answer).toContainText("2h50");
  // Numbered citations in the answer, and the numbered sources under it.
  const cites = answer.locator(".answer-citation-link");
  await expect.poll(() => cites.count()).toBeGreaterThan(1);
  await expect(page.locator("#raw-results .chat-source-index").first()).toBeVisible();
  // A citation opens a look at the note it stands for.
  const first = cites.first();
  await first.click();
  await expect(first).toHaveAttribute("aria-expanded", "true");
  const label = (await first.getAttribute("aria-label")).replace(/^Source \d+: /, "").slice(0, 20);
  await expect(page.locator("[role=dialog]:visible", { hasText: label }).first()).toBeVisible();
  expect(errors).toEqual([]);
});

test("Ask's own suggestion, Summarise my notes in Health, answers from Health only", async ({ page }) => {
  await openApp(page);
  await openTab(page, "notes");
  await page.click('#notes-subtabs [data-section="ask"]');
  await page.fill("#question", "Summarise my notes in Health.");
  await page.click("#ask-btn");
  const sources = page.locator("#raw-results > li");
  await expect.poll(() => sources.count()).toBeGreaterThan(2);
  const ids = await sources.evaluateAll((rows) => rows.map((r) => Number(r.dataset.id)));
  for (const id of ids) {
    const note = await api(page, `/entries/${id}`);
    expect(note.category, `source ${id} is not a Health note`).toBe("Health");
  }
});

test("Chat with no model answers from the notes and says what a model adds", async ({ page }) => {
  await openApp(page);
  await openTab(page, "chat");
  // INBOX 725: with no model Chat is answered by the composer, so Send works,
  // the banner says so, and Agent mode is greyed with its reason.
  const send = page.locator("#chat-send");
  await expect(send).toBeEnabled();
  await expect(page.locator("#tab-chat")).toContainText("Chat answers from your notes");
  await expect(page.locator('#chat-mode-seg [data-chat-mode="agent"]')).toBeDisabled();
  // And the empty state points at what does work without one.
  await expect(page.locator("#chat-messages")).toContainText("Try in Ask");
});
