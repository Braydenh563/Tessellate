// documents-suggest-panel.js: the spelling variants, the dictionary reads, and where the suggestions panel sits.
// Moved out of documents.js whole (L335) and wrapped: only what other files call goes on `window`; nothing here runs at load.
(() => {
  function renderDocTools() {
    docCompleteWords = null;
    renderDocStatusBar();
    renderDocProse();
  }
  const DOC_SPELLING_PAIRS = [
    ["colour", "color"], ["colours", "colors"], ["coloured", "colored"],
    ["favourite", "favorite"], ["favourites", "favorites"], ["favour", "favor"],
    ["behaviour", "behavior"], ["behaviours", "behaviors"],
    ["honour", "honor"], ["labour", "labor"], ["neighbour", "neighbor"],
    ["humour", "humor"], ["rumour", "rumor"], ["flavour", "flavor"],
    ["harbour", "harbor"], ["endeavour", "endeavor"], ["armour", "armor"],
    ["centre", "center"], ["centres", "centers"], ["metre", "meter"],
    ["metres", "meters"], ["litre", "liter"], ["litres", "liters"],
    ["theatre", "theater"], ["fibre", "fiber"], ["calibre", "caliber"],
    ["organise", "organize"], ["organised", "organized"], ["organising", "organizing"],
    ["organisation", "organization"], ["organisations", "organizations"],
    ["recognise", "recognize"], ["recognised", "recognized"],
    ["realise", "realize"], ["realised", "realized"],
    ["apologise", "apologize"], ["analyse", "analyze"], ["analysed", "analyzed"],
    ["prioritise", "prioritize"], ["summarise", "summarize"],
    ["specialise", "specialize"], ["categorise", "categorize"],
    ["catalogue", "catalog"], ["dialogue", "dialog"], ["programme", "program"],
    ["licence", "license"], ["defence", "defense"], ["offence", "offense"],
    ["practise", "practice"], ["grey", "gray"], ["cheque", "check"],
    ["travelling", "traveling"], ["travelled", "traveled"], ["traveller", "traveler"],
    ["cancelled", "canceled"], ["cancelling", "canceling"], ["modelling", "modeling"],
    ["labelled", "labeled"], ["fulfil", "fulfill"], ["enrol", "enroll"],
    ["storey", "story"], ["tyre", "tire"], ["kerb", "curb"], ["plough", "plow"],
    ["aluminium", "aluminum"], ["sceptical", "skeptical"], ["moustache", "mustache"],
    ["draught", "draft"], ["pyjamas", "pajamas"], ["jewellery", "jewelry"],
    ["marvellous", "marvelous"], ["towards", "toward"],
  ];
  const DOC_VARIANT_FAMILY = { us: "us", uk: "uk", au: "uk", in: "uk", ca: "ca" };
  const DOC_VARIANT_LABEL = { us: "US", uk: "UK", au: "Australian", ca: "Canadian", in: "Indian" };
  const DOC_CA_KEEPS_UK =
    /^(?!tyre$)([a-z]*(our(s|ed|ite|ites)?|re|res|ce|ces|ll(ed|ing|er))|grey|cheque|jewellery|marvellous|catalogue)$/;
  let docVariantMap = null;
  function docSpellingVariant() {
    const set = (prefsCache && prefsCache.spelling_variant) || "auto";
    if (set !== "auto") return set;
    const tag = String((typeof navigator === "object" && navigator && navigator.language) || "").toLowerCase();
    const byTag = { "en-au": "au", "en-nz": "au", "en-gb": "uk", "en-us": "us", "en-ca": "ca", "en-in": "in" };
    return byTag[tag] || (/^en-(ie|za|sg|my)$/.test(tag) ? "uk" : "off");
  }
  function docVariantLookup() {
    const variant = docSpellingVariant();
    if (docVariantFor === variant && docVariantMap) return docVariantMap;
    docVariantFor = variant;
    docVariantMap = new Map();
    const family = DOC_VARIANT_FAMILY[variant];
    if (!family) return docVariantMap;
    for (const [uk, us] of DOC_SPELLING_PAIRS) {
      //: Canada keeps some of each side: -our, -re, -ce and the doubled l from
      //: the left, -ize and the rest from the right.
      const british = family === "uk" || (family === "ca" && DOC_CA_KEEPS_UK.test(uk));
      if (british) docVariantMap.set(us, uk);
      else docVariantMap.set(uk, us);
    }
    return docVariantMap;
  }
  let docDictionarySet = null;
  let docDictionarySource = null;
  function docDictionary() {
    const source = (prefsCache && prefsCache.writing_dictionary) || null;
    if (!docDictionarySet || docDictionarySource !== source) {
      docDictionarySource = source;
      docDictionarySet = new Set((source || []).map((word) => String(word).toLowerCase()));
      //: A rebuilt dictionary means every cached per-word answer was answered
      //: against the old one, including the "not a word" answers that put the
      //: underlines on screen.
      docKnownWordsCache = null;
      docSpellCache = new Map();
    }
    return docDictionarySet;
  }
  async function docDictionaryWrite(words) {
    docDictionarySet = new Set(words.map((word) => word.toLowerCase()));
    //: Pinned to the preferences this set now speaks for, so the optimistic add
    //: above survives any read between here and the response: without it, the
    //: next `docDictionary()` would see the old array still on `prefsCache`,
    //: decide the set was stale and rebuild it without the word just added. When
    //: the PUT below replaces `prefsCache`, the identity changes and the set is
    //: rebuilt from what the server actually stored, which is the right answer.
    docDictionarySource = (prefsCache && prefsCache.writing_dictionary) || null;
    //: The ranked suggestions are drawn from this list, so a word added here has
    //: to be offerable on the very next menu rather than after a reload, and
    //: the per-word answers have to forget the word that has just been accepted.
    docKnownWordsCache = null;
    docSpellCache = new Map();
    prefsCache = await apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify({ writing_dictionary: [...docDictionarySet].sort() }),
    }).catch(() => prefsCache);
    docSpell.ownWordsSend();
    renderDocProse();
  }
  async function docDictionaryAdd(word) {
    const clean = String(word || "").trim();
    if (!clean) return;
    const lower = clean.toLowerCase();
    const without = () => docDictionaryWrite([...docDictionary()].filter((other) => other !== lower));
    const add = () => docDictionaryWrite([...docDictionary(), lower]);
    await add();
    offerUndo(`Added “${clean}” to the dictionary`, `“${clean}” added to your dictionary.`, without, add);
  }
  const docProseIgnored = new Set();
  function docProseKey(finding) {
    //: Scoped to the document, because the row says "in this document" and a
    //: dismissal that silently applied to the next document you opened would be
    //: the checker turning itself off with no way to see that it had.
    const scope = currentDoc && currentDoc.id ? currentDoc.id : "unsaved";
    return `${scope}:${finding.rule}:${finding.text.toLowerCase()}`;
  }
  function closeDocSuggest() {
    const menu = $("doc-suggest-menu");
    menu?.classList.add("hidden");
    docReturnFromViewport(menu);
    docSuggestOpenFor = null;
  }
  const DOC_SUGGEST_MAX = 5;
  const DOC_SUGGEST_DISTANCE = 2;
  const DOC_SUGGEST_CANDIDATES = 3000;
  function docEditDistance(a, b, cap) {
    if (Math.abs(a.length - b.length) > cap) return cap + 1;
    if (a === b) return 0;
    let previous = Array.from({ length: b.length + 1 }, (_, i) => i);
    let beforePrevious = null;
    for (let i = 1; i <= a.length; i += 1) {
      const row = new Array(b.length + 1);
      row[0] = i;
      let best = row[0];
      for (let j = 1; j <= b.length; j += 1) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        let value = Math.min(row[j - 1] + 1, previous[j] + 1, previous[j - 1] + cost);
        if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
          value = Math.min(value, beforePrevious[j - 2] + 1);
        }
        row[j] = value;
        if (value < best) best = value;
      }
      if (best > cap) return cap + 1;
      beforePrevious = previous;
      previous = row;
    }
    return previous[b.length];
  }
  function docKnownWords() {
    if (docKnownWordsCache) return docKnownWordsCache;
    const pool = new Set(docDictionary());
    for (const correction of Object.values(DOC_AUTOCORRECT)) pool.add(correction.toLowerCase());
    for (const [uk, us] of DOC_SPELLING_PAIRS) {
      pool.add(uk);
      pool.add(us);
    }
    docKnownWordsCache = [...pool];
    return docKnownWordsCache;
  }
  function docMatchCase(sample, word) {
    if (!sample || !word) return word;
    if (sample[0] !== sample[0].toUpperCase()) return word;
    return word[0].toUpperCase() + word.slice(1);
  }
  function docNearestWords(word, candidates, limit, skip) {
    const lower = word.toLowerCase();
    const scored = [];
    let scanned = 0;
    for (const candidate of candidates) {
      if (scanned >= DOC_SUGGEST_CANDIDATES) break;
      scanned += 1;
      const clean = String(candidate).toLowerCase();
      if (clean === lower || skip.has(clean)) continue;
      if (Math.abs(clean.length - lower.length) > DOC_SUGGEST_DISTANCE) continue;
      const distance = docEditDistance(lower, clean, DOC_SUGGEST_DISTANCE);
      if (distance <= DOC_SUGGEST_DISTANCE) scored.push([clean, distance]);
    }
    //: Distance first, then alphabetically, so the same word always sorts to
    //: the same place. A menu whose rows move between two openings of the same
    //: word is one nobody learns the shape of.
    scored.sort((a, b) => a[1] - b[1] || (a[0] < b[0] ? -1 : 1));
    return scored.slice(0, limit).map(([candidate]) => candidate);
  }
  const DOC_WORD_RULES = new Set(["spelling", "variant"]);
  function docFindingLabel(finding) {
    const text = finding.text || "";
    if (text.trim()) return text.replace(/\s+/g, " ").slice(0, 48);
    if (/^\n+$/.test(text)) return `${text.length} blank line${text.length === 1 ? "" : "s"}`;
    return nounCount(text.length, "space");
  }
  function docSuggestAlternatives(finding) {
    //: More than one plausible answer, where there is one. A single suggestion
    //: presented as *the* answer is how a checker quietly rewrites someone's
    //: voice; two or three make it a choice.
    const out = [];
    const seen = new Set();
    const push = (word) => {
      const clean = String(word);
      const key = clean.toLowerCase();
      if (!clean || seen.has(key) || key === finding.text.toLowerCase()) return;
      seen.add(key);
      out.push(clean);
    };
    if (finding.replacement !== null && finding.replacement !== undefined) {
      push(finding.replacement);
    }
    //: A grammar finding carries its checker's own answers, in its order. An
    //: empty one means "remove it", which `push` would drop as blank.
    if (Array.isArray(finding.alternatives)) {
      for (const option of finding.alternatives) {
        if (out.length >= DOC_SUGGEST_MAX) break;
        if (option === "") {
          if (!out.includes("")) out.push("");
        } else {
          push(option);
        }
      }
    }
    if (DOC_WORD_RULES.has(finding.rule)) {
      const lower = finding.text.toLowerCase();
      //: The other direction of the variant table, so a document set to UK still
      //: offers the US spelling as the second option rather than pretending it
      //: does not exist.
      for (const [uk, us] of DOC_SPELLING_PAIRS) {
        if (uk === lower) push(docMatchCase(finding.text, us));
        if (us === lower) push(docMatchCase(finding.text, uk));
      }
      //: **The dictionary's own answer, first.** These are real words one or
      //: two edits from what was typed, which is what a person means by "what
      //: did I mean to write". The two pools below stay underneath it because
      //: they still answer the cases it cannot: a word the reader added, and a
      //: word that appears in their own notes and in no dictionary.
      //: **The dictionary's answers, most common first** (INBOX 1731): the
      //: worker's, already ranked by how common the word is. Every pool here
      //: drops a suggestion that changes more than a third of a short word.
      const second = docSpell.answer(docSpellRoot(finding.text));
      for (const word of second ? second.suggestions : []) push(docMatchCase(finding.text, word));
      const near = (word) => docEditDistance(docSpellRoot(finding.text), word.toLowerCase(), 99) <= Math.max(1, Math.floor(finding.text.length / 3));
      if (out.length < DOC_SUGGEST_MAX) {
        const guesses = finding.guesses || docSpellGuesses(finding.text, DOC_SUGGEST_MAX);
        for (const word of guesses) {
          if (out.length >= DOC_SUGGEST_MAX) break;
          if (near(word)) push(docMatchCase(finding.text, word));
        }
      }
      if (out.length < DOC_SUGGEST_MAX) {
        for (const word of docNearestWords(finding.text, docKnownWords(), DOC_SUGGEST_MAX - out.length, seen)) {
          if (near(word)) push(docMatchCase(finding.text, word));
        }
      }
      if (out.length < DOC_SUGGEST_MAX) {
        //: Built on demand rather than kept warm: this is the only caller that
        //: needs it before the first completion popup, and building it walks the
        //: document and four hundred notes.
        if (!docCompleteWords) docBuildVocabulary();
        const vocabulary = (docCompleteWords || []).map(([word]) => word);
        for (const word of docNearestWords(finding.text, vocabulary, DOC_SUGGEST_MAX - out.length, seen)) {
          if (near(word)) push(docMatchCase(finding.text, word));
        }
      }
    }
    return out.slice(0, DOC_SUGGEST_MAX);
  }
  function docFindingLine(finding, variant = "row") {
    const line = document.createElement("span");
    line.className = `doc-finding-line doc-finding-line-${variant}`;
    const dot = document.createElement("span");
    dot.className = `doc-finding-dot doc-finding-dot-${docFindingKind(finding)}`;
    dot.setAttribute("aria-hidden", "true");
    const words = document.createElement("span");
    words.className = "doc-finding-words";
    //: A spacing finding's text *is* whitespace, so a heading built from it
    //: rendered as an empty bold nothing. Said in words instead: "three spaces"
    //: is a thing you can look for in the line, an empty heading is not.
    words.textContent = docFindingLabel(finding);
    const why = document.createElement("span");
    why.className = "doc-finding-why";
    const hint = variant === "row" ? docSpellGuesses.hint(finding) : "";
    why.textContent = hint ? `Did you mean \u201c${hint}\u201d?` : finding.message;
    //: Both halves ellipsise in a narrow panel (INBOX 426 b), so each carries
    //: its whole text as a title: the nearest title is the one the pointer
    //: shows, so these win over the row button's "show me this" hint only
    //: where the words themselves are under it.
    words.title = words.textContent;
    why.title = why.textContent;
    line.append(dot, words, why);
    return line;
  }
  function docFindingIsPassage(finding) {
    //: A link offer's answer is the link; asking a model to reword a title
    //: would be a different question.
    return finding.rule !== "link-offer" && /\s/.test(String(finding.text || "").trim());
  }
  async function docFindingAnswerRows(...args) {
    if (!(await lazyScript("/js/documents-suggest.js"))) return toast("The suggestions could not be loaded.", true, { action: ["Try again", () => docFindingAnswerRows(...args)] }), [];
    return docSuggestPiece.docFindingAnswerRows(...args);
  }
  async function docSuggestAnswers(...args) {
    if (!(await lazyScript("/js/documents-suggest.js"))) return toast("The suggestions could not be loaded.", true, { action: ["Try again", () => docSuggestAnswers(...args)] }), document.createDocumentFragment();
    return docSuggestPiece.docSuggestAnswers(...args);
  }
  async function openDocSuggest(...args) {
    if (!(await lazyScript("/js/documents-suggest.js"))) return toast("The suggestions could not be loaded.", true, { action: ["Try again", () => openDocSuggest(...args)] });
    return docSuggestPiece.openDocSuggest(...args);
  }
  async function docTranslatePassage(...args) {
    if (!(await lazyScript("/js/documents-suggest.js"))) return toast("The suggestions could not be loaded.", true, { action: ["Try again", () => docTranslatePassage(...args)] });
    return docSuggestPiece.docTranslatePassage(...args);
  }
  async function docAiDiscussInChat(...args) {
    if (!(await lazyScript("/js/documents-suggest.js"))) return toast("The suggestions could not be loaded.", true, { action: ["Try again", () => docAiDiscussInChat(...args)] });
    return docSuggestPiece.docAiDiscussInChat(...args);
  }
  async function docAiReview(...args) {
    if (!(await lazyScript("/js/documents-suggest.js"))) return toast("The suggestions could not be loaded.", true, { action: ["Try again", () => docAiReview(...args)] });
    return docSuggestPiece.docAiReview(...args);
  }
  const docLiftedHome = new WeakMap();
  function docLiftToViewport(el) {
    if (!el || el.parentElement === document.body) return el;
    const home = document.createComment(`${el.id || "popup"} while it is open`);
    el.replaceWith(home);
    docLiftedHome.set(el, home);
    document.body.appendChild(el);
    return el;
  }
  function docReturnFromViewport(el) {
    const home = el && docLiftedHome.get(el);
    if (!home || !home.parentNode) return;
    home.replaceWith(el);
    docLiftedHome.delete(el);
  }
  function docPlaceFixed(el, left, top) {
    el.style.left = `${Math.round(left)}px`;
    el.style.top = `${Math.round(top)}px`;
    const at = el.getBoundingClientRect();
    const dx = left - at.left;
    const dy = top - at.top;
    if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) {
      el.style.left = `${Math.round(left + dx)}px`;
      el.style.top = `${Math.round(top + dy)}px`;
    }
  }
  const DOC_SUGGEST_GAP = 4;
  const DOC_SUGGEST_EDGE = 8;
  function docSuggestBand(width) {
    const band = {
      min: DOC_SUGGEST_EDGE,
      max: window.innerWidth - DOC_SUGGEST_EDGE,
    };
    const host = docCmView ? docCmView.dom.getBoundingClientRect() : docSurface()?.rect?.();
    if (host && host.right - host.left >= width + 2) {
      band.min = Math.max(band.min, host.left);
      band.max = Math.min(band.max, host.right);
    }
    return band;
  }
  function placeDocSuggest() {
    const menu = $("doc-suggest-menu");
    if (!menu || !docSuggestAnchor || menu.classList.contains("hidden")) return;
    //: Measured after it is visible, because a hidden element measures zero and
    //: a menu positioned against zero opens in the corner. And measured parked
    //: at the window's left edge, not wherever the last open left it: a fixed
    //: box with `left` and no `right` is shrink-to-fit against the room to its
    //: right, so a short menu left near the right edge and then filled with a
    //: long candidate measured 256px of its 316 at 390 wide and was placed
    //: from that, its right edge on the window's (`wordmenuwidth.js`).
    docPlaceFixed(menu, DOC_SUGGEST_EDGE, DOC_SUGGEST_EDGE);
    const width = menu.offsetWidth;
    const height = menu.offsetHeight;
    const band = docSuggestBand(width);

    //: Left edge against the word's left edge, which is where a menu about a word
    //: reads from. When that would cross the band's right edge the menu is
    //: *right-aligned to the word* instead of slid back along it: the two boxes
    //: then share an edge, which still reads as "this belongs to that word", and
    //: the menu ends up beside the word rather than hanging off the card.
    let left = docSuggestAnchor.left;
    if (left + width > band.max) left = (docSuggestAnchor.right ?? docSuggestAnchor.left) - width;
    left = Math.max(band.min, Math.min(left, band.max - width));

    //: Below the word, above it when there is no room below, and clamped to the
    //: window in both directions. The old version clamped the *top* only, so an
    //: anchor low in a short window flipped to a negative top, was pulled back to
    //: 8, and drew its bottom rows off the end of the screen.
    let top = docSuggestAnchor.bottom + DOC_SUGGEST_GAP;
    if (top + height > window.innerHeight - DOC_SUGGEST_EDGE) {
      const above = docSuggestAnchor.top - height - DOC_SUGGEST_GAP;
      top = above >= DOC_SUGGEST_EDGE ? above : top;
    }
    top = Math.max(
      DOC_SUGGEST_EDGE,
      Math.min(top, window.innerHeight - DOC_SUGGEST_EDGE - height)
    );

    docPlaceFixed(menu, left, top);
  }
  function docSuggestFollowAnchor(event) {
    const menu = $("doc-suggest-menu");
    if (!menu || menu.classList.contains("hidden") || !docSuggestOpenFor) return;
    //: The menu scrolls its own overflow, and that scroll reaches this listener
    //: in the capture phase like any other. Following the word because someone
    //: is reading the last row of the menu would be absurd.
    if (event && event.target instanceof Node && menu.contains(event.target)) return;
    const rect = docFindingAnchor(docSuggestOpenFor, null);
    const host = docCmView ? docCmView.dom.getBoundingClientRect() : docSurface()?.rect?.();
    if (!rect || (host && (rect.bottom <= host.top + 1 || rect.top >= host.bottom - 1))) {
      return closeDocSuggest();
    }
    docSuggestAnchor = {
      left: rect.left,
      right: rect.right ?? rect.left,
      top: rect.top,
      bottom: rect.bottom,
    };
    placeDocSuggest();
  }
  let docSuggestFollowFrame = 0;
  function docScheduleSuggestFollow() {
    if (docSuggestFollowFrame) return;
    docSuggestFollowFrame = requestAnimationFrame(() => {
      docSuggestFollowFrame = 0;
      docSuggestFollowAnchor(null);
    });
  }

  //: The file's surface: what other files call (L335).
  Object.assign(window, { renderDocTools, DOC_VARIANT_LABEL, docSpellingVariant, docVariantLookup, docDictionary, docDictionaryWrite, docDictionaryAdd, docProseIgnored, docProseKey, closeDocSuggest, DOC_SUGGEST_MAX, docMatchCase, docSuggestAlternatives, docFindingLine, docFindingIsPassage, docFindingAnswerRows, docSuggestAnswers, openDocSuggest, docTranslatePassage, docAiDiscussInChat, docAiReview, docLiftToViewport, docReturnFromViewport, docPlaceFixed, placeDocSuggest, docSuggestFollowAnchor, docScheduleSuggestFollow });
})();
