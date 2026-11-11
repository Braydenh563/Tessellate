// documents-spell.js: the page's half of the spelling second opinion (INBOX 1731).
//
// The worker (`harper-worker.js`, `spell-second.js`) holds a Hunspell dictionary
// for the dialect and the person's own words. This file is what the page keeps
// for it: the words it sends, and the answers it remembers for the spelling
// check (`docSpellLookup`) and the suggestion menu (`docSuggestAlternatives`) to
// read. Loaded in the Library bundle before documents.js; one closure, and what
// other files call is the `Object.assign` at the foot.
(() => {
  //: `words`: root word to {known, suggestions}. `want`: asked for, not yet
  //: sent. `own`: the server's list (the words the notes use twice, never from a
  //: private note), fetched once per session.
  const second = { words: new Map(), want: new Set(), timer: 0, own: null };

  //: The person's own words to the worker: the notes' list plus the dictionary
  //: they added to. Sent whole, again whenever either changes.
  function docOwnWordsSend() {
    const send = () => docGrammarSend({ type: "own", words: [...(second.own || []), ...docDictionary()] }, false);
    if (second.own) return send();
    second.own = [];
    apiJson("/spelling/own-words", { silent: true })
      .then((body) => {
        second.own = (body && body.words) || [];
        send();
        //: What the worker answered before it had these words is asked again.
        docGrammarCache = { text: null, findings: [] };
        renderDocProse();
      })
      .catch(() => send());
  }

  //: The answer for a root word, or null until the worker has given one.
  function docSecondAnswer(root) {
    return second.words.get(root) || null;
  }

  //: Ask about a word the page's own list does not know; true when it will be
  //: answered. A batch a quarter of a second after the last word, so a pass over
  //: a document is one message.
  function docSecondWant(root) {
    if (second.words.has(root) || second.want.has(root) || !docGrammarEnabled()) return false;
    if (!/^[a-z]+(?:'[a-z]+)*$/.test(root)) return false;
    second.want.add(root);
    clearTimeout(second.timer);
    second.timer = setTimeout(flush, 250);
    return true;
  }

  async function flush() {
    const words = [...second.want].slice(0, 200);
    words.forEach((word) => second.want.delete(word));
    if (!words.length) return;
    const answers = await docGrammarSend({ type: "spell", words, dialect: docSpellingVariant() });
    //: No worker, or a failed one: the page's own list decides, as before.
    for (const word of words) {
      second.words.set(word, (answers && answers[word]) || { known: false, suggestions: [] });
    }
    if (second.want.size) flush();
    docSpellCache.clear();
    renderDocProse();
  }

  //: "Add to dictionary" as a row, for the document's menu and the note's alike.
  function dictionaryRow(word) {
    return {
      kind: "action",
      id: "dictionary",
      //: Short (INBOX 552): the word is the heading above it, and "Add
      //: \u201cword\u201d to dictionary" wrapped onto two lines in a narrow panel.
      label: "ph:book-open-text Add to dictionary",
      title: `Add \u201c${word}\u201d to the dictionary`,
      run: async (close = () => {}) => {
        close();
        await docDictionaryAdd(word);
      },
    };
  }

  //: **Spelling packs for other languages (D30).** French, German and Spanish word lists the
  //: person installed from Settings, Packages (`core/spellpacks.py`). One is read only when a
  //: document's `lang` names it: the page fetches its two Hunspell files once, the Harper
  //: worker builds the checker, and words are asked in batches like the English second
  //: opinion. Until it answers, and for a language with no pack, nothing is flagged.
  //: `list`: the server's packs (null until asked). `state`: lang to "loading", "ready" or
  //: "failed". `answers`: lang to word to {known, suggestions}. `version` moves with every
  //: answer, so the rule memo (`docProse.rules`) knows its findings are stale.
  const pack = { list: null, probed: 0, probing: false, state: new Map(), answers: new Map(), want: new Map(), timer: 0, version: 0 };
  const PACK_RECHECK_MS = 5000;
  const PACK_WORD = /\p{L}+(?:['’]\p{L}+)*/gu;

  function packRefresh() {
    pack.version += 1;
    docSpellCache.clear();
    renderDocProse();
  }

  //: Ask the server which packs are installed: once, then every few seconds while the document's
  //: language has none (an install in Settings needs no reload), and at once on `force`.
  function packProbe(force = false) {
    if (pack.probing || (!force && pack.list && Date.now() - pack.probed < PACK_RECHECK_MS)) return;
    pack.probing = true;
    apiJson("/spellpacks", { silent: true })
      .then((body) => {
        const before = JSON.stringify(pack.list);
        pack.list = (body && body.packs) || [];
        for (const [lang, state] of [...pack.state]) {
          if (state === "ready" && !pack.list.some((one) => one.lang === lang && one.installed)) pack.state.delete(lang);
        }
        if (before !== JSON.stringify(pack.list)) packRefresh();
      })
      .catch(() => {
        pack.list = pack.list || [];
      })
      .finally(() => {
        pack.probed = Date.now();
        pack.probing = false;
      });
  }

  async function packLoad(lang) {
    pack.state.set(lang, "loading");
    try {
      const [aff, dic] = await Promise.all(["aff", "dic"].map((kind) => api(`/spellpacks/${lang}/${kind}`, { silent: true }).then((response) => response.text())));
      const done = await docGrammarSend({ type: "packload", lang, aff, dic });
      pack.state.set(lang, done && done.loaded ? "ready" : "failed");
    } catch {
      pack.state.set(lang, "failed");
    }
    packRefresh();
  }

  //: "none" (no pack for this language, or the list has not arrived), "missing" (not installed),
  //: "loading", "ready" or "failed". Starts the probe and the load the first time it is asked.
  function packState(lang) {
    packProbe();
    const entry = pack.list && pack.list.find((one) => one.lang === lang);
    if (!entry) return "none";
    if (!entry.installed) return "missing";
    if (!pack.state.has(lang)) {
      //: The pack is read in the grammar worker, so it is off when that is.
      if (!docGrammarEnabled()) return "failed";
      packLoad(lang);
    }
    return pack.state.get(lang);
  }

  async function packFlush(lang) {
    const wanted = pack.want.get(lang) || new Set();
    const words = [...wanted].slice(0, 200);
    words.forEach((word) => wanted.delete(word));
    if (!words.length) return;
    const answers = await docGrammarSend({ type: "packspell", lang, words });
    const known = pack.answers.get(lang);
    //: No worker, or a failed one: the words are left alone.
    for (const word of words) known.set(word, (answers && answers[word]) || { known: true, suggestions: [] });
    if (wanted.size) packFlush(lang);
    packRefresh();
  }

  function packWant(lang, word) {
    if (!pack.want.has(lang)) pack.want.set(lang, new Set());
    pack.want.get(lang).add(word);
    clearTimeout(pack.timer);
    pack.timer = setTimeout(() => packFlush(lang), 250);
  }

  //: Spelling findings for a document in `lang`, from its pack. `skipped(at)` is the prose pass's
  //: mask (code, addresses). A word the pack has not answered yet is asked and not flagged.
  function packFindings(text, lang, skipped) {
    if (packState(lang) !== "ready") return [];
    if (!pack.answers.has(lang)) pack.answers.set(lang, new Map());
    const known = pack.answers.get(lang);
    const own = docDictionary();
    const found = [];
    const words = new RegExp(PACK_WORD.source, PACK_WORD.flags);
    let hit;
    while ((hit = words.exec(text)) !== null) {
      const word = hit[0];
      const end = hit.index + word.length;
      if (skipped(hit.index) || !docSpellable(text, word, hit.index, end)) continue;
      if (own.has(word.toLowerCase())) continue;
      //: A capitalised word inside a sentence is a name, as in English; German capitalises every
      //: noun, so there it is checked.
      if (lang !== "de" && docSpellNameKind(text, word, hit.index) === "name") continue;
      const answer = known.get(word);
      if (!answer) {
        packWant(lang, word);
        continue;
      }
      if (answer.known) continue;
      found.push({
        rule: "spelling",
        message: `“${word}” is not in the ${packName(lang)} dictionary`,
        start: hit.index,
        end,
        text: word,
        replacement: null,
        alternatives: answer.suggestions,
      });
    }
    return found;
  }

  function packName(lang) {
    const entry = pack.list && pack.list.find((one) => one.lang === lang);
    if (entry) return entry.name;
    try {
      return new Intl.DisplayNames(["en"], { type: "language" }).of(lang) || lang;
    } catch {
      return lang;
    }
  }

  //: The panel line for a document whose pack is working; "" otherwise, and the caller says why
  //: the checker is off (`docProse.langNote`).
  function packNote(lang) {
    const state = packState(lang);
    if (state !== "ready" && state !== "loading") return "";
    return `Spelling is checked in ${packName(lang)} from its installed pack. Grammar checks stay English.`;
  }

  //: The note under the panel's header for a non-English document, and for one whose pack is
  //: not installed the one-click install (`extraNoticeMount`, the notice every optional package
  //: uses). Null for English.
  function langRow(text) {
    const note = docProse.langNote(text);
    if (!note) return null;
    const row = document.createElement("div");
    row.className = "doc-prose-lang";
    const line = document.createElement("p");
    line.className = "muted";
    line.textContent = note;
    row.appendChild(line);
    const lang = docProse.langOf(text);
    if (packState(lang) === "missing") {
      const slot = document.createElement("div");
      row.appendChild(slot);
      //: Not `fresh`: this row is rebuilt on every panel redraw (every 400 ms while typing), and the
      //: pack list above already re-probes; the notice's shared 3 s cache answers before paint.
      extraNoticeMount(slot, `spell-${lang}`);
    }
    return row;
  }

  //: Settings, Packages or the notice installed or removed something: ask again now.
  window.addEventListener("tessellate:extras-changed", () => packProbe(true));

  window.docSpell = {
    ownWordsSend: docOwnWordsSend,
    answer: docSecondAnswer,
    want: docSecondWant,
    dictionaryRow,
    packFindings,
    packNote,
    packKey: () => pack.version,
    langName: packName,
    langRow,
  };
})();
