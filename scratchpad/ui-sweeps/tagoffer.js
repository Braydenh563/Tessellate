// A note with no tags offers to have them written, where the tags would be.
//
// INBOX 292, the owner: "half the time when there are no tags on a note, i
// want the ai to generate them for me, so one of my most used features is the
// re-evaluate feature, but i feel like it is more than just re-evaluating, and
// it is hidden away and the user's probably wont know its a thing."
//
// The action already existed, one row deep in the note's own menu, named for
// the smallest part of what it does. This measures the two halves of the fix:
// the offer is on the card where a person is thinking about tags, and the menu
// row says what it does.
const { boot } = require("./lib.js");

let failures = 0;
function ok(label, pass, detail) {
  console.log(`${pass ? "PASS" : "FAIL"}  ${label}  — ${detail}`);
  if (!pass) failures += 1;
}

(async () => {
  const { page, browser } = await boot({ width: 1440, height: 900 });

  // A note with no tags of its own.
  await page.evaluate(async () => {
    const r = await api("/entries", {
      method: "POST",
      body: JSON.stringify({ content: "A note with nothing filed on it yet." }),
    });
    const made = await r.json();
    // Strip whatever the filing gave it, so the empty-tag path is the one
    // under test rather than whichever tags a model happened to add.
    await api(`/entries/${made.id}`, {
      method: "PUT",
      body: JSON.stringify({ content: made.content, tags: [] }),
    });
    switchTab("notes");
    await loadEntries();
  });
  await page.waitForTimeout(700);

  // **Both states, because the offer is conditional on one.** A chip is a
  // `<span role="button">` and `syncModelGatedControls` closes controls by
  // setting `disabled`, which does nothing to a span, so the offer is rendered
  // or not rather than shown disabled. This sandbox has no model, so without
  // driving the status the probe would only ever see the "no model" half and
  // would have reported the offer missing as a fault.
  const withoutModel = await page.evaluate(() => {
    modelStatus = { ollama_running: false };
    renderEntries();
    const li = [...document.querySelectorAll(".entry-list li")].find((el) =>
      el.textContent.includes("A note with nothing filed on it yet."),
    );
    return [...(li ? li.querySelectorAll(".chip") : [])].map((c) => c.textContent.trim());
  });
  ok(
    "with no model answering, nothing is offered that cannot be honoured",
    !withoutModel.some((t) => /tag with atlas/i.test(t)),
    JSON.stringify(withoutModel),
  );
  ok(
    "and the manual route is still there in that case",
    withoutModel.some((t) => /no tags yet|add tags/i.test(t)),
    JSON.stringify(withoutModel),
  );

  await page.evaluate(() => {
    modelStatus = { ollama_running: true };
    renderEntries();
  });
  await page.waitForTimeout(200);

  const row = await page.evaluate(() => {
    const li = [...document.querySelectorAll(".entry-list li")].find((el) =>
      el.textContent.includes("A note with nothing filed on it yet."),
    );
    if (!li) return { error: "the note is not on screen" };
    const chips = [...li.querySelectorAll(".chip")].map((c) => ({
      text: c.textContent.trim(),
      cls: c.className,
      role: c.getAttribute("role"),
      tabindex: c.getAttribute("tabindex"),
      title: c.title,
      box: (({ width, height }) => ({ w: +width.toFixed(1), h: +height.toFixed(1) }))(
        c.getBoundingClientRect(),
      ),
    }));
    return { chips };
  });

  ok("the note renders", !row.error, row.error || "on screen");
  const chips = row.chips || [];
  const offer = chips.find((c) => /tag with atlas/i.test(c.text));
  const flag = chips.find((c) => /no tags yet|add tags/i.test(c.text));

  ok("the empty tag row still flags itself", !!flag, JSON.stringify(flag && flag.text));
  ok("and it offers Atlas beside the flag", !!offer, JSON.stringify(offer && offer.text));
  ok(
    "the offer is a real control, not a label",
    offer && offer.role === "button" && offer.tabindex === "0",
    offer ? `role ${offer.role}, tabindex ${offer.tabindex}` : "absent",
  );
  ok(
    "the offer says what Atlas will do, and that you approve it",
    offer && /approve/i.test(offer.title),
    offer ? JSON.stringify(offer.title) : "absent",
  );
  ok(
    "and it is big enough to press",
    offer && offer.box.w > 40 && offer.box.h >= 18,
    offer ? JSON.stringify(offer.box) : "absent",
  );

  // The menu row: the same action, named for what it does. With no model
  // (this sandbox) the row drops "with Atlas" (entry-menu.js, aiIsOff).
  const menu = await page.evaluate(() => {
    const li = [...document.querySelectorAll(".entry-list li")].find((el) =>
      el.textContent.includes("A note with nothing filed on it yet."),
    );
    const more = li && li.querySelector(".entry-more, [data-kebab], button[aria-haspopup]");
    if (!more) return { error: "no menu button on the card" };
    more.click();
    return {};
  });
  await page.waitForTimeout(200);

  if (!menu.error) menu.items = await page.evaluate(() => {
    const li = [...document.querySelectorAll(".entry-list li")].find((el) =>
      el.textContent.includes("A note with nothing filed on it yet."),
    );
    const m = li && li.querySelector(".action-menu:not(.hidden)");
    return m ? [...m.querySelectorAll(".menu-item")].map((b) => b.textContent.trim()) : [];
  });
  if (menu.error) {
    ok("the note's menu opens", false, menu.error);
  } else {
    ok("the note's menu opens", true, `${menu.items.length} rows`);
    ok(
      "and the action is named for what it does",
      menu.items.some((t) => /tag and file( with atlas)?$/i.test(t)),
      JSON.stringify(menu.items.filter((t) => /atlas|evaluat|tag and file/i.test(t))),
    );
    ok(
      "with no row still called re-evaluate",
      !menu.items.some((t) => /^re-evaluate$/i.test(t)),
      JSON.stringify(menu.items.filter((t) => /evaluat/i.test(t))),
    );
  }

  await browser.close();
  console.log(failures ? `FAILURES: ${failures}` : "ALL PASS");
  process.exit(failures ? 1 : 0);
})();
