// The Tesseract engine's one control (INBOX 443 (3), the owner: "using
// tesseract and how it operates in the ocr workspace is still annoying to use
// and manage").
//
// Measured before this existed: the engine's state was a tooltip on a disabled
// dropdown option, "Install the OCR extra in Settings, Optional extras" (a
// section that is named Packages now), with no install button in the
// workspace, no language choice anywhere, and a Packages row that showed a
// green tick for the Python half alone. This draws one status line, from the
// one status the server computes (`GET /ocr-readers` → `engine`, see
// core/ocr.py's `engine_status`), in the two places a person looks:
//
//  * the OCR workspace (`#ocr-engine`, mounted by library.js): can it read,
//    which language, and when it cannot, one Install button that follows the
//    install to the end;
//  * the Packages row for "Search inside images" (settings-packages.js `renderExtras`):
//    the language choice only, because that row already owns Install,
//    Reinstall, Remove and the progress bar, and a second set would be the
//    duplicate this was told not to build.
//
// A lazy piece (app.js `LAZY_MODULES.ocrEngine`, entry point `ocrEngineMount`):
// the boot scripts only carry the stand-in.

const ocrEngineHosts = new Set();
let ocrEngineLatest = null;
let ocrEngineTimer = null;
//: One install at a time, process-wide, like the server's: `running` follows
//: `GET /extras`, `failed` is the sentence to show until the next try.
//: `extra` is which one: "ocr" (Tesseract) or "rapidocr".
const ocrEngineInstall = { running: false, step: "", failed: "", extra: "ocr" };
const OCR_ENGINE_EXTRAS = {
  ocr: { name: "Tesseract", ask: "Install Tesseract OCR?\n\nAbout 10 MB is downloaded from PyPI, then your system's package manager (winget, Homebrew, apt) is asked for the Tesseract program. It reads text in images on this computer, and nothing is sent anywhere. No restart is needed." },
  rapidocr: { name: "RapidOCR", ask: "Install RapidOCR?\n\nAbout 60 MB is downloaded from PyPI, with no system program to fetch. It reads text in images on this computer (English and Chinese), and nothing is sent anywhere. No restart is needed." },
};

//: Mount the status line into `host` and keep it current. `readers` is the
//: `/ocr-readers` answer when the caller already has it (the workspace asked
//: just before); without it this asks. `settings` draws the Packages row's
//: smaller version. `onChange` runs after something here changed the engine
//: (an install finished, a language was chosen).
async function ocrEngineMount(host, { readers = null, settings = false, popover = false, onChange = null, onPaint = null } = {}) {
  if (!host) return null;
  host._ocrEngine = { settings, popover, onChange, onPaint };
  host.classList.add("ocr-engine");
  ocrEngineHosts.add(host);
  if (readers && readers.engine) {
    ocrEngineLatest = readers;
  } else {
    ocrEngineLatest = await apiJson("/ocr-readers", { silent: true }).catch(() => ocrEngineLatest);
  }
  ocrEnginePaintAll();
  //: An install started in Settings, or before this window was opened, is
  //: still running: pick it up rather than offering a second Install button.
  if (!settings && !ocrEngineInstall.running) {
    const body = await apiJson("/extras", { silent: true }).catch(() => null);
    if (body && body.running && OCR_ENGINE_EXTRAS[body.installing]) {
      ocrEngineInstall.extra = body.installing;
      ocrEngineInstall.running = true;
      ocrEngineInstall.failed = "";
      ocrEngineFollow();
    }
  }
  return ocrEngineLatest;
}

function ocrEnginePaintAll() {
  for (const host of [...ocrEngineHosts]) {
    if (!host.isConnected) {
      ocrEngineHosts.delete(host);
      continue;
    }
    ocrEnginePaint(host);
    host._ocrEngine?.onPaint?.({ installing: ocrEngineInstall.running });
  }
}

function ocrEngineLanguageName(engine) {
  const code = engine?.language || "";
  if (!code) return "";
  const known = (engine.languages || []).find((l) => l.code === code);
  return known ? known.name : code;
}

function ocrEnginePaint(host) {
  const readers = ocrEngineLatest;
  const engine = readers?.engine;
  const opts = host._ocrEngine || {};
  host.replaceChildren();
  if (!engine || !Object.keys(engine).length) {
    host.hidden = true;
    return;
  }
  //: The Packages row already says "Not installed" and offers Install; this
  //: adds only what it could not say, so a missing engine paints nothing there.
  //: Settings mounts this under Tesseract's own row, so a ready RapidOCR
  //: (`engine.engine`, op4-1005) is that row's news only to the workspace.
  const local = engine.engine_name || "Tesseract";
  const isTesseract = !engine.engine || engine.engine === "tesseract";
  if (opts.settings && (!engine.ready || !isTesseract)) {
    host.hidden = true;
    return;
  }
  host.hidden = false;
  const line = document.createElement("div");
  line.className = "ocr-engine-line";

  if (ocrEngineInstall.running) {
    const installing = `Installing ${OCR_ENGINE_EXTRAS[ocrEngineInstall.extra].name}`;
    line.appendChild(
      opts.popover
        ? ocrEngineStatusLine(installing, "is-busy")
        : chip(`ph:spin ${installing}`, "item-label ocr-engine-chip")
    );
    const step = document.createElement("span");
    step.className = "muted ocr-engine-detail";
    step.textContent = ocrEngineInstall.step || "Starting…";
    const bar = document.createElement("progress");
    bar.className = "task-progress ocr-engine-progress";
    line.append(step, bar);
    host.appendChild(line);
    return;
  }

  if (engine.ready) {
    //: **In the workspace this is a popover now** (INBOX 717): the state is a
    //: dot on the reader button and a quiet line here, not a filled badge in a
    //: row of its own, and Manage is a row of the tool row's ⋯ menu.
    if (opts.popover) {
      line.appendChild(ocrEngineStatusLine(`${local}${isTesseract && engine.version ? ` ${engine.version}` : ""} is ready`, "is-ok"));
    } else if (!opts.settings) {
      line.appendChild(
        chip(`ph:check-circle ${local}${isTesseract && engine.version ? ` ${engine.version}` : ""} is ready`, "item-label is-ok ocr-engine-chip")
      );
    }
    //: The language is Tesseract's; RapidOCR's models read what they read.
    if (isTesseract) line.appendChild(ocrEngineLanguagePicker(engine, opts));
    host.appendChild(line);
    if (engine.language_note) {
      const note = document.createElement("p");
      note.className = "muted ocr-engine-note";
      note.textContent = engine.language_note;
      host.appendChild(note);
    }
    return;
  }

  //: **Nothing reads at all** (WORLD_CLASS_PLAN 28.4 row 5): no engine and
  //: no model. One line, RapidOCR first because it is pip alone with no
  //: system program to fetch (the half a Tesseract install most often fails
  //: on), each with its download size; Tesseract second. Not in Settings,
  //: whose Packages row already owns both installs.
  const noModel = !(readers.vision ? readers.vision_model : "");
  if (noModel && !engine.rapidocr && !opts.settings) {
    line.appendChild(
      opts.popover
        ? ocrEngineStatusLine("Nothing can read pages yet", "is-warn")
        : chip("ph:warning Nothing can read pages yet", "item-label is-warn ocr-engine-chip")
    );
    const offer = document.createElement("span");
    offer.className = "muted ocr-engine-detail";
    const rapidSize = engine.rapidocr_size ? `, ${engine.rapidocr_size}` : "";
    const tessSize = engine.tesseract_size ? `${engine.tesseract_size} plus a system program` : "plus a system program";
    offer.textContent = `Install RapidOCR (nothing else to install${rapidSize}) or Tesseract (${tessSize}) to read on this computer, or start an AI model in Settings.`;
    const again = (extra) => ocrEngineInstall.failed && ocrEngineInstall.extra === extra;
    line.append(
      offer,
      smallButton(
        again("rapidocr") ? "ph:arrow-clockwise Try RapidOCR again" : "ph:download-simple Install RapidOCR",
        "Install RapidOCR on this computer",
        () => ocrEngineStartInstall("rapidocr"),
        false
      ),
      smallButton(
        again("ocr") ? "ph:arrow-clockwise Try Tesseract again" : "ph:download-simple Install Tesseract",
        "Install Tesseract OCR on this computer",
        () => ocrEngineStartInstall("ocr"),
        false
      )
    );
    host.appendChild(line);
    ocrEnginePaintFailure(host);
    return;
  }

  //: Not ready: say which half is missing, what still works, and give the one
  //: action. The sentence about the AI reader is the fallback the owner asked
  //: for, stated before the failure rather than after it.
  line.appendChild(
    opts.popover
      ? ocrEngineStatusLine("Tesseract can't read yet", "is-warn")
      : chip("ph:warning Tesseract can't read yet", "item-label is-warn ocr-engine-chip")
  );
  const detail = document.createElement("span");
  detail.className = "muted ocr-engine-detail";
  const ai = readers.vision ? readers.vision_model : "";
  detail.textContent = ai
    ? `${engine.reason} ${shortModelName(ai)} reads pages until it is installed.`
    : `${engine.reason} Install it here, or start an AI model in Settings, to read pages.`;
  line.appendChild(detail);
  line.appendChild(
    smallButton(
      ocrEngineInstall.failed ? "ph:arrow-clockwise Try again" : "ph:download-simple Install Tesseract",
      "Install Tesseract OCR on this computer",
      () => ocrEngineStartInstall(),
      false
    )
  );
  host.appendChild(line);
  ocrEnginePaintFailure(host);
}

function ocrEnginePaintFailure(host) {
  if (!ocrEngineInstall.failed) return;
  const failed = document.createElement("p");
  failed.className = "ocr-engine-note is-error";
  failed.setAttribute("role", "alert");
  failed.textContent = `${ocrEngineInstall.failed} The install log is in Settings, Packages.`;
  host.appendChild(failed);
}

//: The popover's state, the reader button's dot repeated beside its words: a
//: quiet line, the size of a status rather than of a control.
function ocrEngineStatusLine(words, state) {
  const line = document.createElement("p");
  line.className = "ocr-engine-status";
  const dot = document.createElement("span");
  dot.className = `ocr-engine-dot ${state}`;
  dot.setAttribute("aria-hidden", "true");
  const text = document.createElement("span");
  text.textContent = words;
  line.append(dot, text);
  return line;
}

function ocrEngineLanguagePicker(engine, opts) {
  const wrap = document.createElement("label");
  //: In the popover the label stands over its select, the dock menu's own
  //: section recipe: "Reads in [Default]" side by side sat its words off the
  //: select's centre line (INBOX 717's screenshot).
  wrap.className = opts.popover ? "ocr-engine-lang-wrap is-stacked" : "ocr-engine-lang-wrap";
  const label = document.createElement("span");
  label.className = opts.popover ? "dock-menu-label ocr-engine-lang-label" : "muted ocr-engine-lang-label";
  label.textContent = opts.popover ? "Tesseract reads in" : "Reads in";
  const select = document.createElement("select");
  select.className = "ocr-engine-lang";
  select.setAttribute("aria-label", "Language Tesseract reads in");
  select.title =
    "The language Tesseract reads in. It applies to every read, here and in the background, and is remembered.";
  const options = [{ code: "", name: "Default" }, ...(engine.languages || [])];
  //: A saved combination such as "eng+deu" is not one pack, so it has no row
  //: of its own in the list; show it rather than silently showing "Default".
  if (engine.language && !options.some((o) => o.code === engine.language)) {
    options.push({ code: engine.language, name: engine.language });
  }
  for (const option of options) {
    const row = document.createElement("option");
    row.value = option.code;
    row.textContent = option.name;
    select.appendChild(row);
  }
  select.value = engine.language || "";
  select.addEventListener("change", async () => {
    select.disabled = true;
    try {
      const status = await apiJson("/ocr/language", {
        method: "POST",
        body: JSON.stringify({ language: select.value }),
      });
      if (ocrEngineLatest) ocrEngineLatest.engine = status;
      const name = ocrEngineLanguageName(status);
      toast(
        name
          ? `Tesseract reads in ${name} from now on. Read a page again to use it.`
          : "Tesseract is back to its default language. Read a page again to use it."
      );
      opts.onChange?.(status);
    } catch (error) {
      toast(error.message || "That language could not be set.", true);
    }
    ocrEnginePaintAll();
  });
  wrap.append(label, select);
  return wrap;
}

async function ocrEngineStartInstall(extra = "ocr") {
  const ok = await confirmDialog(OCR_ENGINE_EXTRAS[extra].ask);
  if (!ok) return;
  ocrEngineInstall.failed = "";
  ocrEngineInstall.extra = extra;
  const result = await apiJson(`/extras/${extra}/install`, { method: "POST" }).catch((error) => ({
    started: false,
    message: error.message,
  }));
  if (!result.started) {
    ocrEngineInstall.failed = result.message || "The install could not start.";
    ocrEnginePaintAll();
    return;
  }
  ocrEngineInstall.running = true;
  ocrEngineInstall.step = "Starting…";
  ocrEnginePaintAll();
  ocrEngineFollow();
}

//: Follow the install to its end, from `GET /extras` (the one source the
//: Packages panel reads too), then ask the engine again: the server's own
//: answer, never the installer's exit code, decides whether it worked.
async function ocrEngineFollow() {
  clearTimeout(ocrEngineTimer);
  const body = await apiJson("/extras", { silent: true }).catch(() => null);
  if (body && body.running && body.installing === ocrEngineInstall.extra) {
    ocrEngineInstall.step = body.step || "Installing…";
    ocrEnginePaintAll();
    ocrEngineTimer = setTimeout(ocrEngineFollow, 1200);
    return;
  }
  ocrEngineInstall.running = false;
  ocrEngineLatest = await apiJson("/ocr-readers", { silent: true }).catch(() => ocrEngineLatest);
  const rapid = ocrEngineInstall.extra === "rapidocr";
  if (rapid ? ocrEngineLatest?.engine?.rapidocr : ocrEngineLatest?.engine?.ready) {
    ocrEngineInstall.failed = "";
    toast(`${OCR_ENGINE_EXTRAS[ocrEngineInstall.extra].name} is ready.`);
  } else {
    ocrEngineInstall.failed = (body?.step || ocrEngineLatest?.engine?.reason || "The install did not finish.").trim();
  }
  ocrEnginePaintAll();
  for (const host of ocrEngineHosts) host._ocrEngine?.onChange?.(ocrEngineLatest?.engine);
}
