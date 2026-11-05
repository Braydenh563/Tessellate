// An empty slot always draws its box (INBOX 1584 d, the owner: "I can still deleted boxes and they wont reappear
// if I deletw ehat I wrote"). Every structure the Equation tab's palette inserts is put in the real MathLive field;
// each of its boxes is filled with a letter, the letter is deleted, and the box is drawn again: counted in the
// field's TeX (`\placeholder`) and in what it draws (the box glyph), because a count of one can pass while the
// other fails. The same walk ran under plain Playwright against the running app: 102 structures, 102 whole (it has not been run under @playwright/test: the harness has no node_modules for it).
const { test, expect } = require("@playwright/test");
const { watchErrors, openApp } = require("../helpers");

const FIELD = ".math-editor math-field";

async function openEquationTab(page) {
  await openApp(page);
  await page.evaluate(async () => {
    await ensureModule("replyKit");
    await ensureModule("mathEditor");
    openCalculator("", "equation");
  });
  await expect(page.locator(FIELD)).toBeVisible({ timeout: 20_000 });
}

//: The TeX's boxes and the boxes drawn, as the field has them now.
const boxes = (page) =>
  page.evaluate((selector) => {
    const field = document.querySelector(selector);
    const tex = field.getValue("latex");
    return { tex, inTex: (tex.match(/\\placeholder/g) || []).length, drawn: ((field.shadowRoot || field).textContent.match(/\u25a2/g) || []).length };
  }, FIELD);

//: In shards, each its own test and timeout: the whole walk (over 100 structures, about a second each on a
//: shared runner) outran one 240 s test on CI (run 41625361789). Every structure is still walked, by one shard.
const SHARDS = 4;
for (let shard = 0; shard < SHARDS; shard += 1) {
  test(`every structure the palette inserts keeps a box for each slot after what was typed in it is deleted (part ${shard + 1} of ${SHARDS})`, async ({ page }) => {
    test.setTimeout(240_000);
    const errors = watchErrors(page);
    await openEquationTab(page);
    const every = await page.evaluate(() =>
      mathEditorGroups()
        .filter((group) => group.structures)
        .flatMap((group) => group.items.filter((item) => /#[?@]/.test(item.tex)).map((item) => ({ name: item.name, slots: (item.tex.match(/#[?@]/g) || []).length })))
    );
    expect(every.length, "the palette has its structures").toBeGreaterThan(90);
    const structures = every.filter((_, i) => i % SHARDS === shard);
    const broken = [];
    for (const { name, slots } of structures) {
      // A clean field, the way a person clears one: select all, delete.
      await page.evaluate((selector) => {
        const field = document.querySelector(selector);
        field.focus();
        field.executeCommand("selectAll");
      }, FIELD);
      await page.keyboard.press("Backspace");
      await page.waitForTimeout(80);
      await page.evaluate((title) => [...document.querySelectorAll(".math-editor-tile")].find((tile) => tile.title === title).click(), name);
      await page.waitForTimeout(150);
      const first = await boxes(page);
      for (let slot = 0; slot < slots; slot += 1) {
        // Tab is the field's own way to the next box. A beat between the keys: the field settles an edit before the next.
        await page.keyboard.type("x");
        await page.waitForTimeout(50);
        await page.keyboard.press("Backspace");
        await page.waitForTimeout(50);
        // Not after the last box: MathLive's Tab past the end throws inside the field (its own, not the app's).
        if (slot < slots - 1) await page.keyboard.press("Tab");
      }
      const last = await boxes(page);
    if (last.inTex !== slots || last.drawn !== slots) broken.push(`${name}: ${first.inTex} boxes at first, ${last.inTex} in the TeX and ${last.drawn} drawn after, of ${slots}: ${last.tex}`);
  }
  expect(broken, "a structure lost a box").toEqual([]);
  expect(errors).toEqual([]);
});
}
