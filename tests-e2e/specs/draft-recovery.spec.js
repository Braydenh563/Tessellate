// A killed server loses no typed draft (WORLD_CLASS 25e, Brief 51 step 4).
//
// The three boxes people type into keep their words on this device as they
// type, not on the server: Capture (`captureDraft` and its title and tags,
// settings-wiring.js), Quick note (`quickNoteDraft`, quick-note.js) and the
// open edit form (`note-edit-draft`, note-edit-panels.js), all through the
// prefs store (browser storage). This spec runs its own server, because it
// kills it: SIGKILL to the server's own process group (spawned detached, the
// setsid shape), so no shutdown hook runs, then starts it again on the same
// data dir and reloads the page.
const { test, expect } = require("@playwright/test");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const config = require("../playwright.config.js");
const { signIn } = require("../global-setup.js");
const { openApp, reloadApp, api, noteRow } = require("../helpers");

const PORT = config.PORT + 7;
const URL = `http://127.0.0.1:${PORT}`;
const DIR = path.join(config.DATA_ROOT, "draft-recovery");

function startServer() {
  const child = spawn(
    config.PYTHON,
    ["-m", "uvicorn", "tessellate.api.app:create_app", "--factory", "--port", String(PORT)],
    {
      cwd: path.join(__dirname, "..", ".."),
      detached: true,
      stdio: "ignore",
      env: {
        ...process.env,
        PYTHONPATH: "src",
        TESSELLATE_DATA_DIR: DIR,
        TESSELLATE_NO_AUTO_INSTALL: "1",
        HF_HUB_OFFLINE: "1",
        TRANSFORMERS_OFFLINE: "1",
      },
    }
  );
  return child;
}

async function serverAnswers() {
  try {
    return (await fetch(`${URL}/health`)).ok;
  } catch {
    return false;
  }
}

async function waitFor(check, want, ms = 60_000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if ((await check()) === want) return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`the server did not ${want ? "start" : "stop"} in time`);
}

//: A new notebook asks once about update checks, over everything; answered
//: the way global-setup.js answers it, touching no network.
async function answerFirstStartQuestions(page) {
  const dontCheck = page.locator(".confirm-overlay button", { hasText: "Don't check" });
  await dontCheck.waitFor({ state: "visible", timeout: 3_000 }).catch(() => {});
  if (await dontCheck.isVisible().catch(() => false)) {
    await dontCheck.click();
    await dontCheck.waitFor({ state: "hidden", timeout: 5_000 }).catch(() => {});
  }
}

test("typed drafts in Capture, Quick note and the edit form survive a killed server and a reload", async ({ browser }) => {
  test.setTimeout(180_000);
  fs.rmSync(DIR, { recursive: true, force: true });
  fs.mkdirSync(DIR, { recursive: true });
  let server = startServer();
  try {
    await waitFor(serverAnswers, true);
    const state = path.join(DIR, "..", ".auth-draft-recovery.json");
    await signIn(URL, state);
    const context = await browser.newContext({ baseURL: URL, storageState: state });
    const page = await context.newPage();
    await openApp(page);
    await answerFirstStartQuestions(page);

    const made = await api(page, "/entries", { method: "POST", body: JSON.stringify({ content: "The ferry leaves at nine" }) });
    const words = {
      capture: `capture draft ${Date.now() % 100000}: the tide turns at four`,
      title: "Harbour notes",
      quick: "quick note draft: bring the spare oar",
      edit: " and the last one back is at six",
    };

    // Capture: title, body and tags, typed.
    await page.evaluate(() => switchTab("notes"));
    await page.click('#notes-subtabs [data-section="capture"]');
    await page.fill("#entry-title", words.title);
    const live = page.locator('.cm-content[aria-label="New note"]');
    await ((await live.count()) ? live : page.locator("#entry-content")).click();
    await page.keyboard.insertText(words.capture);
    await expect(page.locator("#entry-content")).toHaveValue(words.capture);

    // Quick note: opened, typed, closed with Escape (which keeps the words).
    await page.evaluate(() => openQuickNote());
    await page.locator("#quick-note-text").click();
    await page.keyboard.insertText(words.quick);
    await page.keyboard.press("Escape");

    // The edit form: opened on the note, a line added, not saved.
    await page.evaluate(() => loadEntries());
    const row = await noteRow(page, made.id);
    await row.locator('button[aria-label^="Edit this entry"]').click();
    const body = row.locator('.cm-content[aria-label="Note text"]');
    await body.click();
    await page.keyboard.press("Control+End");
    await page.keyboard.insertText(words.edit);
    // Kept on this device as typed, before anything else happens.
    await expect.poll(() => page.evaluate(() => prefs.json("note-edit-draft", {}).content || "")).toContain(words.edit.trim());

    // The server dies without a word: SIGKILL to its whole process group.
    process.kill(-server.pid, "SIGKILL");
    await waitFor(serverAnswers, false, 15_000);
    server = startServer();
    await waitFor(serverAnswers, true);

    page.once("dialog", (dialog) => dialog.accept());
    await reloadApp(page);
    await answerFirstStartQuestions(page);

    // The edit form's offer first: it is a toast, so it is read before it times out.
    const offer = page.locator(".toast", { hasText: "unsaved changes" });
    await expect(offer).toBeVisible({ timeout: 15_000 });
    await offer.getByRole("button", { name: "Open them" }).click();
    const form = page.locator(`#entry-list > li[data-id="${made.id}"] textarea.note-edit-box`);
    await expect(form).toHaveValue(/The ferry leaves at nine and the last one back is at six/);

    await page.evaluate(() => switchTab("notes"));
    await page.click('#notes-subtabs [data-section="capture"]');
    await expect(page.locator("#entry-content")).toHaveValue(words.capture);
    await expect(page.locator("#entry-title")).toHaveValue(words.title);

    await page.evaluate(() => openQuickNote());
    await expect(page.locator("#quick-note-text")).toHaveValue(words.quick);
    await page.keyboard.press("Escape");

    await context.close();
  } finally {
    try {
      process.kill(-server.pid, "SIGKILL");
    } catch {
      // already gone
    }
  }
});
