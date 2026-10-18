// Shared steps for the flow specs. Each helper drives the real UI the way a
// person would, or reads back through the app's own `apiJson` (the same
// authenticated helper the page uses) when the outcome is data rather than
// pixels. Asserting on what a person sees after a reload is the point of
// these specs (see playwright.config.js), so the helpers wait for the app to
// be really up, not for a request to return.
const { expect } = require("@playwright/test");
const { E2E_PASSWORD: PASSWORD } = require("./playwright.config.js");

// Every uncaught exception and console.error on the page, for the specs that
// end with "and nothing threw". Attach before the first goto.
function watchErrors(page) {
  const errors = [];
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    // A 4xx the app asked for on purpose (a probe for an optional extra) is
    // logged by the browser itself, not by the app's code.
    if (/Failed to load resource/.test(text)) return;
    errors.push(`console: ${text}`);
  });
  return errors;
}

// The app is up: the boot splash and the opening curtain are gone and the
// tab bar answers. `networkidle` never settles here (the app polls).
async function openApp(page, route = "/") {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await waitForApp(page);
}

// A reload the way a person presses F5, then the app up again. One
// navigation: a reload followed by a second `goto` hung now and then in
// Chromium (the second navigation never committed), so the specs that check
// "still there after a reload" use this.
async function reloadApp(page) {
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForApp(page);
}

async function waitForApp(page) {
  // A spec that locks the app (notes.spec.js) ends every saved session, so
  // a later spec may meet the lock screen: sign in the way a person would.
  const locked = await page
    .waitForFunction(
      () => {
        const field = document.getElementById("lock-password");
        const overlay = document.getElementById("lock-overlay");
        if (field && overlay && !overlay.classList.contains("hidden") && field.offsetParent !== null) return "lock";
        return overlay && overlay.classList.contains("hidden") && localStorage.getItem("token") ? "app" : false;
      },
      null,
      { timeout: 20_000 }
    )
    .then((handle) => handle.jsonValue());
  if (locked === "lock") {
    await page.fill("#lock-password", PASSWORD);
    await page.click("#lock-submit");
  }
  await page.waitForFunction(
    () => {
      const splash = document.getElementById("boot-splash");
      const lock = document.getElementById("lock-overlay");
      return (
        (!splash || splash.classList.contains("hidden")) &&
        lock && lock.classList.contains("hidden") &&
        !document.documentElement.classList.contains("shell-curtain") &&
        typeof window.apiJson === "function"
      );
    },
    null,
    { timeout: 20_000 }
  );
}

async function openTab(page, tab) {
  // A tab that no longer exists fails in 15 s, not after the whole test's timeout.
  await page.click(`#tab-btn-${tab}`, { timeout: 15_000 });
  await expect(page.locator(`#tab-${tab}`)).toBeVisible();
}

// The app's own authenticated fetch, from inside the page.
function api(page, route, options) {
  return page.evaluate(([r, o]) => apiJson(r, o), [route, options || {}]);
}

// Notes, Capture: type into the composer and press Save. Returns the new
// note's id, read from the status line the composer writes it to.
async function captureNote(page, text, { title, tags, category } = {}) {
  await openTab(page, "notes");
  await page.click('#notes-subtabs [data-section="capture"]');
  const box = page.locator("#entry-content");
  await expect(box).toBeVisible();
  if (title !== undefined) await page.fill("#entry-title", title);
  if (tags !== undefined) await page.fill("#entry-tags", tags);
  if (category !== undefined) await page.selectOption("#entry-category", { label: category });
  // Clicked and typed, not filled: a click upgrades the textarea to the live
  // editor (CodeMirror) the way it does for a person, and the save must read
  // what was typed there.
  const live = page.locator('.cm-content[aria-label="New note"]');
  await ((await live.count()) ? live : box).click();
  await page.keyboard.insertText(text);
  await expect(box).toHaveValue(text);
  const status = page.locator("#save-status");
  const before = await status.getAttribute("data-entry-id");
  await page.click("#save-btn");
  // The status line names the new note's id; a build without that (v0.3.32,
  // driven for the comparison in e2e-1005.md) is read from the list instead.
  let id = 0;
  await expect
    .poll(async () => {
      const shown = await status.getAttribute("data-entry-id");
      if (shown && shown !== before) id = Number(shown);
      else {
        const latest = await api(page, "/entries?limit=5");
        id = (latest.find((e) => e.content.endsWith(text)) || {}).id || 0;
      }
      return id;
    }, { message: "Save made no note" })
    .toBeGreaterThan(0);
  expect(id, "the composer wrote no note id after Save").toBeGreaterThan(0);
  return id;
}

// Background filing settles: the note leaves "pending".
async function waitFiled(page, id) {
  let note;
  await expect
    .poll(
      async () => {
        note = await api(page, `/entries/${id}`);
        return note.filing_state;
      },
      { timeout: 20_000, message: `note ${id} never left the filing queue` }
    )
    .not.toBe("pending");
  return note;
}

// A note in the bin answers 404 to a plain read, so "is it there" is whether
// the read succeeds.
function noteExists(page, id) {
  return page.evaluate((nid) => apiJson(`/entries/${nid}`).then(() => true, () => false), id);
}

// A zip of `{name: text}` files, stored (no compression), for the import
// specs: Node has no zip writer and the suite takes no dependency for one.
// The format is the local headers, then the central directory, then its end
// record; CRC-32 is the standard reflected polynomial.
function makeZip(files) {
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc32 = (buf) => {
    let c = 0xffffffff;
    for (const byte of buf) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const locals = [];
  const centrals = [];
  let offset = 0;
  for (const [name, text] of Object.entries(files)) {
    const nameBuf = Buffer.from(name, "utf8");
    const data = Buffer.from(text, "utf8");
    const crc = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0x0800, 6); // UTF-8 names
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(data.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(0x0800, 8);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(data.length, 20);
    central.writeUInt32LE(data.length, 24);
    central.writeUInt16LE(nameBuf.length, 28);
    central.writeUInt32LE(offset, 42);
    locals.push(local, nameBuf, data);
    centrals.push(central, nameBuf);
    offset += 30 + nameBuf.length + data.length;
  }
  const dir = Buffer.concat(centrals);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(Object.keys(files).length, 8);
  end.writeUInt16LE(Object.keys(files).length, 10);
  end.writeUInt32LE(dir.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, dir, end]);
}

// A note's row in Notes, Your notes; one of its ⋯ menu's items; and the
// confirm card's filled button, whatever verb it reads (`confirmVerb`).
async function noteRow(page, id) {
  await openTab(page, "notes");
  await page.click('#notes-subtabs [data-section="browse"]');
  const row = page.locator(`#entry-list > li[data-id="${id}"]`);
  await expect(row).toBeVisible();
  return row;
}

async function menuItem(page, row, label) {
  await row.locator('button[aria-label="More actions"]').click();
  await page.locator(".action-menu:not(.hidden)").getByText(label, { exact: true }).click();
}

async function confirm(page) {
  const button = page.locator(".confirm-overlay button:not(:has-text('Cancel'))").last();
  await expect(button).toBeVisible();
  await button.click();
}

module.exports = { reloadApp, noteRow, menuItem, confirm, makeZip, watchErrors, openApp, openTab, api, captureNote, waitFiled, noteExists };
