// Run by tests/test_goals_focus_98.py: goals-view.js in a bare page with stubbed helpers.
const { chromium } = require("/opt/node22/lib/node_modules/playwright");
const fs = require("fs");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent(`<section id="goals"><select id="goals-show"><option value="" data-label="All">All</option><option value="goal" data-label="Goals">Goals</option><option value="list" data-label="Lists">Lists</option><option value="done" data-label="Finished">Finished</option></select><button id="goals-new-goal"></button><button id="goals-new-list"></button><ul id="goals-list"></ul></section>`);
  await page.evaluate(() => {
    window.$ = (id) => document.getElementById(id);
    const goal = { id: 1, title: "Pack", kind: "list", target_date: "", done_at: null, items: [{ id: 1, text: "socks", done: false }, { id: 2, text: "shoes", done: false }] };
    const shape = () => {
      const done = goal.items.filter((i) => i.done).length;
      return { ...goal, progress: { total: goal.items.length, done, percent: Math.round((done * 100) / goal.items.length) } };
    };
    window.apiJson = async (path, opts = {}) => {
      if (opts.method === "PATCH") {
        const m = path.match(/items\/(\d+)/);
        goal.items.find((i) => i.id == m[1]).done = JSON.parse(opts.body).done;
        return {};
      }
      if (opts.method === "POST") {
        goal.items.push({ id: 9, text: JSON.parse(opts.body).text, done: false });
        return {};
      }
      return { goals: [shape()], counts: { goal: 0, list: 1 } };
    };
    window.toast = () => {};
    window.voiceLine = (k, w) => w;
    window.kebabMenu = () => document.createElement("button");
    window.smallButton = (l, t, f) => {
      const b = document.createElement("button");
      b.onclick = f;
      return b;
    };
    window.evidenceSpan = (c, t = "", tag = "span") => {
      const e = document.createElement(tag);
      e.className = c;
      e.textContent = t;
      return e;
    };
    window.surfaceFailed = () => {};
    window.promptDialog = async () => null;
    window.offerUndo = () => {};
  });
  await page.addScriptTag({ content: fs.readFileSync(process.argv[2], "utf8") });
  await page.evaluate(() => document.dispatchEvent(new Event("goals:show")));
  await page.waitForSelector(".goal-item input");
  const out = {};
  await page.focus('[data-item="2"] input');
  await page.keyboard.press("Space");
  await page.waitForFunction(() => document.querySelector('[data-item="2"] input')?.checked);
  out.tick = await page.evaluate(() => ({
    checked: document.querySelector('[data-item="2"] input').checked,
    active: document.activeElement.closest("[data-item]")?.dataset.item,
    tag: document.activeElement.tagName,
    progress: document.querySelector(".goal-bar").value,
  }));
  await page.focus(".goal-add input");
  await page.keyboard.type("hat");
  await page.keyboard.press("Enter");
  await page.waitForSelector('[data-item="9"]');
  out.add = await page.evaluate(() => ({
    active: document.activeElement.closest(".goal-add") ? "add-line" : document.activeElement.tagName,
    items: document.querySelectorAll(".goal-item").length,
  }));
  console.log(JSON.stringify(out));
  await browser.close();
})();
