// The editors' keyboard, as a student meets it in the first lecture (dogfood
// round 1, dog1-1025.md items 1 to 4 and 8): redo, bold with nothing selected,
// list typing and fences in the note box. Each test types the way a person
// does and reads the text back, because the faults lived between the keymap
// and the surface adapter, where a unit test cannot see them.
const { test, expect } = require("@playwright/test");
const { watchErrors, openApp, openTab, api } = require("../helpers");

async function openNewDoc(page, content = "Start.") {
  await openApp(page);
  const doc = await api(page, "/documents", { method: "POST", body: JSON.stringify({ title: `Keys ${Date.now() % 100000}`, content }) });
  await openApp(page, `/#/docs/${doc.id}`);
  const cm = page.locator('#tab-documents .cm-content[aria-label="Document text"]');
  await expect(cm).toBeVisible();
  await cm.click();
  await page.keyboard.press("Control+End");
  return cm;
}

const docText = (page) => page.evaluate(() => docText());

test("Ctrl+Shift+Z redoes in a document, as Ctrl+Y does", async ({ page }) => {
  const errors = watchErrors(page);
  await openNewDoc(page);
  await page.keyboard.insertText(" one");
  await page.waitForTimeout(600);
  // One insert, so one history step; the pause keeps it apart from " one".
  await page.keyboard.insertText("\ntwo");
  await page.waitForTimeout(600);
  expect(await docText(page)).toBe("Start. one\ntwo");
  await page.keyboard.press("Control+z");
  expect(await docText(page)).toBe("Start. one");
  await page.keyboard.press("Control+Shift+z");
  expect(await docText(page), "Ctrl+Shift+Z undid again instead of redoing").toBe("Start. one\ntwo");
  await page.keyboard.press("Control+z");
  await page.keyboard.press("Control+y");
  expect(await docText(page)).toBe("Start. one\ntwo");
  // The toolbar's Redo is clickable and does the same.
  await page.keyboard.press("Control+z");
  expect(await docText(page)).toBe("Start. one");
  // The formatting toolbar starts collapsed; Ctrl+Shift+X opens it.
  await page.keyboard.press("Control+Shift+X");
  await page.locator('#tab-documents [data-md="redo"]').first().click();
  expect(await docText(page), "the toolbar Redo did nothing").toBe("Start. one\ntwo");
  expect(errors).toEqual([]);
});

test("Ctrl+B with nothing selected leaves the placeholder selected, so typing replaces it whole", async ({ page }) => {
  const errors = watchErrors(page);
  await openNewDoc(page, "");
  await page.keyboard.press("Control+b");
  expect(await docText(page)).toBe("**bold text**");
  const sel = await page.evaluate(() => [docSurface().selectionStart, docSurface().selectionEnd]);
  expect(sel, "the selection should be the placeholder, not the opening markers").toEqual([2, 11]);
  await page.keyboard.insertText("very important");
  expect(await docText(page)).toBe("**very important**");
  expect(errors).toEqual([]);
});

async function openCaptureBox(page) {
  await openApp(page);
  await openTab(page, "notes");
  await page.click('#notes-subtabs [data-section="capture"]');
  const live = page.locator('.cm-content[aria-label="New note"]');
  await expect(page.locator("#entry-content")).toBeVisible();
  // A click upgrades the textarea to the live editor, as it does for a person.
  await page.locator("#entry-content").click();
  await expect(live).toBeVisible();
  await live.click();
  return page.locator("#entry-content");
}

test("note box: Enter continues a bullet, retyping '- ' does not nest, a blank bullet ends the list", async ({ page }) => {
  const errors = watchErrors(page);
  const box = await openCaptureBox(page);
  await page.keyboard.type("- one");
  await page.keyboard.press("Enter");
  await expect(box).toHaveValue("- one\n- ");
  await page.keyboard.type("- ");
  await expect(box, "typing '- ' on the auto-bullet nested it").toHaveValue("- one\n- ");
  await page.keyboard.type("two");
  await page.keyboard.press("Enter");
  await page.keyboard.press("Enter");
  await expect(box, "Enter on an empty bullet should end the list").toHaveValue("- one\n- two\n");
  await page.keyboard.type("done");
  await expect(box).toHaveValue("- one\n- two\ndone");
  expect(errors).toEqual([]);
});

test("note box: a closing fence goes back to the opening fence's indent", async ({ page }) => {
  const errors = watchErrors(page);
  const box = await openCaptureBox(page);
  await page.keyboard.type("```");
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await page.keyboard.type("code");
  await page.keyboard.press("Enter");
  await page.keyboard.type("```");
  await page.keyboard.press("Enter");
  await page.keyboard.type("after");
  await expect(box, "the fence and the line after it carried the code's indent").toHaveValue("```\n  code\n```\nafter");
  expect(errors).toEqual([]);
});

test("table cell: Tab moves to the next cell even while a word is offered", async ({ page }) => {
  const errors = watchErrors(page);
  const body = "algorithms are taught here\n\n| a | b |\n| --- | --- |\n|  | y |\n";
  await openNewDoc(page, body);
  await page.evaluate((at) => docSurface().setSelection(at), body.indexOf("|  | y") + 2);
  await page.keyboard.type("alg");
  await expect(page.locator("#doc-complete-list")).toBeVisible();
  await page.keyboard.press("Tab");
  const text = await docText(page);
  expect(text, "Tab took the offered word instead of leaving the cell").toBe(body.replace("|  | y", "| alg | y"));
  expect(await page.evaluate(() => { const s = docSurface(); return s.text.slice(s.selectionStart, s.selectionEnd); })).toBe("y");
  expect(errors).toEqual([]);
});
