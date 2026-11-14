// translate.js: Translate this, the offline translator's sheet (WORLD_CLASS_PLAN
// 28.5 row 10, Brief 83). The owner, 2026-10-10: "What about ai free
// translations?" Loaded on first use by `LAZY_MODULES.translate` (app.js) from
// the palette row "Translate this" (settings-panes.js).
//
// The passage is what was selected when the palette opened (a note, a
// document, a reading), else the whole editor that had the focus; it is
// translated in `translate-worker.js` on this computer and never reaches the
// server. With the package not installed the row opens its row in Settings,
// Packages instead: one line said, nothing dead.

//: The longest passage taken in one go: about 3,000 words, some 15 s on the
//: measured machine, in the worker so the page never waits on it.
(() => {
  const TRANSLATE_MAX_CHARS = 20000;

  //: Five minutes with nothing asked and the worker goes, with the model it
  //: holds in memory; the next ask loads it again (about a second and a half).
  const TRANSLATE_IDLE_MS = 5 * 60 * 1000;

  const translateUi = { worker: null, next: 1, waiting: new Map(), idle: null };

  function translateWorker() {
    if (!translateUi.worker) {
      const url = "/js/translate-worker.js";
      translateUi.worker = new Worker(`${url}${lazyAssetStamp(url)}`);
      translateUi.worker.addEventListener("message", (event) => {
        const data = event.data || {};
        const settle = translateUi.waiting.get(data.id);
        translateUi.waiting.delete(data.id);
        settle?.(data);
      });
      //: A worker whose script fails to load says so here and nowhere else.
      translateUi.worker.addEventListener("error", (event) => {
        event.preventDefault?.();
        translateStopWorker(event.message || "The translator did not start.");
      });
    }
    clearTimeout(translateUi.idle);
    translateUi.idle = setTimeout(() => translateStopWorker("Stopped while idle."), TRANSLATE_IDLE_MS);
    return translateUi.worker;
  }

  function translateStopWorker(reason) {
    clearTimeout(translateUi.idle);
    translateUi.worker?.terminate();
    translateUi.worker = null;
    for (const settle of translateUi.waiting.values()) settle({ ok: false, error: reason });
    translateUi.waiting.clear();
  }

  function translateAsk(pair, text) {
    const worker = translateWorker();
    const id = translateUi.next++;
    return new Promise((resolve) => {
      translateUi.waiting.set(id, resolve);
      worker.postMessage({ id, pair, text });
    });
  }

  //: Put the translation where the passage was: a text box through
  //: `setRangeText` and an `input` event (so its draft and rendering follow), a
  //: rich editor through the browser's own insert at the range it held, the
  //: same two paths Insert template takes (utility-tools.js).
  function translateReplace(caught, text) {
    const { target, start, end, range } = caught;
    target.focus();
    if (target.isContentEditable) {
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      document.execCommand("insertText", false, text);
    } else {
      target.setRangeText(text, start, end, "select");
      target.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }

  //: Whether the passage can be written back: a selection inside a box the
  //: person can edit, not a reading pane.
  function translateCanReplace(caught, whole) {
    const { target } = caught;
    if (whole || !target) return false;
    if (typeof target.setRangeText === "function" && !target.readOnly && !target.disabled) return caught.end > caught.start;
    return Boolean(target.isContentEditable && caught.range && target.contains(caught.range.commonAncestorContainer));
  }

  async function translateCaught(caught) {
    await ensureModule("utilities");
    const { text, whole } = utilitySelectedText(caught);
    if (!text.trim()) {
      toast("Select a passage in a note, a document or a reading, then choose Translate this.", "info");
      return;
    }
    if (text.length > TRANSLATE_MAX_CHARS) {
      toast(`That is ${text.length.toLocaleString()} characters. Select up to ${TRANSLATE_MAX_CHARS.toLocaleString()} and try again.`, "info");
      return;
    }
    const status = await apiJson("/translate/status", { silent: true }).catch(() => null);
    if (!status?.installed || !status.pairs?.length) {
      //: Not installed: a sheet with the one optional-package notice, whose Install is the way on.
      openSheet({
        label: "Translate this",
        sub: status?.hint || "Translating needs the offline translator.",
        name: "translate",
        build: (card) => {
          const slot = document.createElement("div");
          card.append(slot);
          extraNoticeMount(slot, "translate", { fresh: true });
        },
      });
      return;
    }
    const pair = status.pairs.find((p) => `${p.from}-${p.to}` === prefs.get("translate-pair")) || status.pairs[0];
    const replaceable = translateCanReplace(caught, whole);
    openSheet({
      label: "Translate this",
      sub: `${status.pairs.length > 1 ? "Choose the languages below. On this computer" : `${pair.label}, on this computer`}. A small model: good for the gist, check what matters.`,
      name: "translate",
      build: (card, close) => {
        card.classList.add("inbox-card", "translate-card");
        const body = document.createElement("div");
        body.className = "inbox-body translate-body";
        const source = document.createElement("p");
        source.className = "muted translate-text translate-source";
        source.textContent = text;
        const result = document.createElement("p");
        result.className = "translate-text translate-result";
        result.id = "translate-result";
        result.setAttribute("aria-live", "polite");
        result.textContent = "Translating…";
        const line = document.createElement("p");
        line.className = "status translate-status";
        line.setAttribute("role", "status");
        //: The translation first, the passage under it: on a phone the sheet's
        //: body scrolls, and what was asked for should not be below the fold.
        body.append(result, line, source);

        const actions = document.createElement("div");
        actions.className = "row right space-dialog-actions";
        const copy = document.createElement("button");
        copy.type = "button";
        copy.id = "translate-copy";
        copy.className = replaceable ? "ghost small" : "accent small";
        setLabel(copy, "ph:copy Copy");
        copy.disabled = true;
        actions.append(copy);
        let replace = null;
        if (replaceable) {
          replace = document.createElement("button");
          replace.type = "button";
          replace.id = "translate-replace";
          replace.className = "accent small";
          setLabel(replace, "ph:swap Replace the selection");
          replace.disabled = true;
          actions.append(replace);
        }
        card.append(body, actions);

        //: One handler each, reading the latest answer, so choosing another pair
        //: asks again without stacking listeners.
        let latest = "";
        copy.addEventListener("click", () => copyToClipboard(latest, copy));
        replace?.addEventListener("click", () => {
          close();
          translateReplace(caught, latest);
          toast("Replaced the selection with its translation. Ctrl+Z puts it back.");
        });
        let asked = 0;
        const run = (chosen) => {
          const mine = ++asked;
          latest = "";
          copy.disabled = true;
          if (replace) replace.disabled = true;
          result.textContent = "Translating…";
          result.lang = chosen.to;
          line.textContent = "";
          line.classList.remove("error");
          translateAsk(chosen, text).then((answer) => {
            if (mine !== asked) return;
            if (!answer.ok) {
              result.textContent = "";
              line.textContent = `Couldn't translate it. ${answer.error || ""}`.trim();
              line.classList.add("error");
              return;
            }
            latest = answer.text;
            result.textContent = answer.text;
            const seconds = (answer.ms / 1000).toFixed(1);
            line.textContent = answer.loadMs > 200
              ? `Translated in ${seconds} s, after ${(answer.loadMs / 1000).toFixed(1)} s loading the translator.`
              : `Translated in ${seconds} s.`;
            copy.disabled = false;
            if (replace) replace.disabled = false;
          });
        };
        //: Two or more installed pairs: a select, not a pill well (DESIGN.md `.seg`
        //: is for two or three short choices), the last pick kept on this device.
        if (status.pairs.length > 1) {
          const pick = document.createElement("select");
          pick.id = "translate-pair";
          pick.className = "translate-pair";
          pick.setAttribute("aria-label", "Language pair");
          pick.title = "Language pair";
          for (const option of status.pairs) pick.add(new Option(option.label, `${option.from}-${option.to}`));
          pick.value = `${pair.from}-${pair.to}`;
          pick.addEventListener("change", () => {
            const chosen = status.pairs.find((p) => `${p.from}-${p.to}` === pick.value) || status.pairs[0];
            prefs.set("translate-pair", pick.value);
            run(chosen);
          });
          body.prepend(pick);
        }
        run(pair);
      },
    });
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { translateAsk, translateCaught });
})();
