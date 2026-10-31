// Word-style equations (INBOX 1473 a): click a drawn equation in a document,
// fill the empty box, and what is stored is TeX between dollar signs, replaced
// at the exact source range, in one undo step; Escape leaves the text as it
// was. MathLive (vendored, loaded on the first edit) runs under the page's real
// policy here, so a style attribute it wrote that the policy refused would show
// as a console error and fail the last assertion.
const { test, expect } = require("@playwright/test");
const { watchErrors, openApp, api } = require("../helpers");

const BODY = "Maths field\n\nA fraction $\\frac{67}{}$ in text.\n\nA block $$\\sqrt{x}+\\int_{0}^{1}f(x)dx$$ here.\n\nTail line.\n";

async function openMaths(page) {
  await openApp(page);
  const made = await api(page, "/documents", { method: "POST", body: JSON.stringify({ title: `Maths field ${Date.now() % 100000}`, content: BODY }) });
  await openApp(page, `/#/docs/${made.id}`);
  await page.waitForFunction(() => typeof docCmView !== "undefined" && docCmView.state.doc.length > 20);
  await page.evaluate(() => {
    if (typeof setDocView === "function") setDocView("live");
    docCmView.focus();
    docCmView.dispatch({ selection: { anchor: docCmView.state.doc.length } });
  });
  return made;
}

const source = (page) => page.evaluate(() => docCmView.state.doc.toString());

test("clicking a drawn fraction opens a field; filling its empty box writes the TeX back to the exact range", async ({ page }) => {
  const errors = watchErrors(page);
  await openMaths(page);
  const before = await source(page);
  await page.locator(".cm-md-math").first().click();
  const field = page.locator(".math-field-pop math-field");
  await expect(field).toBeVisible({ timeout: 20_000 });
  expect(await source(page), "opening the field must not touch the text").toBe(before);
  // The empty box is a dotted placeholder; clicking it and typing fills it.
  await field.locator(".ML__latex span", { hasText: "▢" }).first().click();
  await page.keyboard.type("89");
  await page.keyboard.press("Enter");
  await expect(page.locator(".math-field-pop")).toHaveCount(0);
  const after = await source(page);
  expect(after).toBe(before.replace("$\\frac{67}{}$", () => "$\\frac{67}{89}$"));
  // One undo step puts it back byte for byte.
  await page.evaluate(() => docCmView.focus());
  await page.keyboard.press("Control+z");
  expect(await source(page)).toBe(before);
  expect(errors).toEqual([]);
});

test("Escape leaves the text byte for byte as it was, and the LaTeX box edits the same equation", async ({ page }) => {
  const errors = watchErrors(page);
  await openMaths(page);
  const before = await source(page);
  await page.locator(".cm-md-math-block").click();
  const pop = page.locator(".math-field-pop");
  await expect(pop.locator("math-field")).toBeVisible({ timeout: 20_000 });
  await page.keyboard.type("+7");
  await page.keyboard.press("Escape");
  await expect(pop).toHaveCount(0);
  expect(await source(page)).toBe(before);

  await page.locator(".cm-md-math-block").click();
  await expect(pop.locator("math-field")).toBeVisible();
  await pop.getByRole("button", { name: "LaTeX" }).click();
  await pop.locator(".math-field-latex").fill("\\sqrt{y}+1");
  expect(await pop.locator("math-field").evaluate((el) => el.getValue("latex"))).toBe("\\sqrt{y}+1");
  await pop.getByRole("button", { name: "Done" }).click();
  expect(await source(page)).toBe(before.replace("$$\\sqrt{x}+\\int_{0}^{1}f(x)dx$$", () => "$$\\sqrt{y}+1$$"));
  expect(errors).toEqual([]);
});
