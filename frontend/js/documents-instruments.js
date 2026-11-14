// documents-instruments.js: the editor's instruments: counts, completion, prose checks and autocorrect.
// Moved out of documents.js whole (L-documents-117) and wrapped: only what other files call goes on `window`.
(() => {
  //: State that moved here from documents.js (L-documents-118).
  let docWordlist = null;
  //: One answer per word rather than per occurrence. A document says the same
  //: word many times, the answers cannot change between two of them inside one
  //: pass, and the generation above is the most expensive thing the checker
  //: does. Cleared when the dictionary changes, which is the only thing that
  //: can change an answer.
  let docSpellCache = new Map();
  //: The words this app can say it knows, as opposed to the words it has seen.
  //: Rebuilt when the dictionary changes, which is the only thing that can add
  //: to it.
  let docKnownWordsCache = null;
  // =============================================================================
  // The editor's own instruments: counts, completion, prose checks, autocorrect
  // =============================================================================
  //
  // Asked for directly: *"improve and expand on some features in the document
  // editor, take inspo from vs code and word with options to view more info like
  // character count, inline auto fill suggestions, grammar checker + auto correct
  // etc."*
  //
  // **Everything below is local arithmetic over the text in the box.** No model,
  // no network, no service, which is not a limitation here, it is the
  // requirement: this app's whole claim is that it works with the plug pulled,
  // and a grammar checker that phones a server would be the first thing in it
  // that does not. It also means every one of these is instant, which is what
  // makes them usable while typing at all.
  //
  // What that rules out is honest to state: this cannot judge *meaning*. It will
  // not know that a sentence is wrong, only that it repeats a word, runs long,
  // or contains a spelling this list is sure about. Rules that would need
  // judgement (its/it's, their/there in context) are deliberately absent, 
  // a checker that is wrong a third of the time teaches people to ignore it,
  // and then the two thirds it is right about go unread too.

  //: The one surface each instrument acts on: whichever box the caret is in.
  //: There is one editor now, in every view, so this is almost always the
  //: document's own surface; the check survives because the fallback textarea
  //: is still a real box when the engine is unavailable.
  function docActiveBox() {
    const active = document.activeElement;
    if (active instanceof HTMLTextAreaElement && active.id === "doc-content") {
      return textareaSurface(active);
    }
    //: CodeMirror's editable is a `div`, not a textarea, so the check above
    //: cannot see it. `asSurface` maps any node inside the view onto the
    //: document's surface, which is what makes the caret-following instruments
    //: (the status bar, the completion popup, the findings menu) keep working
    //: once the engine is under them.
    return asSurface(active) || docSurface();
  }

  //: **Where the caret is, in pixels.** The standard mirror technique: a hidden
  //: div that copies every property that affects text layout, holds the text up
  //: to the caret, and reports where a marker span lands. There is no API for
  //: this: `selectionStart` is an index, and a popup has to go somewhere on
  //: screen.
  //:
  //: The property list is the part that has to be right: miss `font-family` or
  //: `padding` and the popup drifts further from the caret the further down the
  //: document you are, which reads as a positioning bug rather than a missing
  //: line of CSS.
  const DOC_MIRROR_PROPS = [
    "boxSizing", "width", "borderLeftWidth", "borderRightWidth", "borderTopWidth",
    "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
    "fontFamily", "fontSize", "fontWeight", "fontStyle", "letterSpacing",
    "lineHeight", "textTransform", "textIndent", "whiteSpace", "wordSpacing",
    "tabSize",
  ];

  let docMirror = null;

  //: The mirror itself, over a real textarea and an offset in its value. Split
  //: out of `docCaretPoint` because it is the *textarea's* answer to the
  //: question: CodeMirror has `coordsAtPos` and needs none of this, so the
  //: adapter routes each surface to whichever one is right for it.
  function docMirrorPoint(el, pos) {
    if (!docMirror) {
      docMirror = document.createElement("div");
      docMirror.className = "doc-caret-mirror";
      document.body.appendChild(docMirror);
    }
    const style = getComputedStyle(el);
    for (const prop of DOC_MIRROR_PROPS) docMirror.style[prop] = style[prop];
    //: `pre-wrap`, always: a textarea wraps and preserves whitespace, and a
    //: mirror that collapsed spaces would put the caret a word early on every
    //: line that has two of them.
    docMirror.style.whiteSpace = "pre-wrap";
    docMirror.style.overflowWrap = "break-word";
    docMirror.textContent = el.value.slice(0, pos);
    const marker = document.createElement("span");
    //: A zero-width space rather than nothing: an empty span has no box, so it
    //: reports the wrong position at the end of a line.
    marker.textContent = "​";
    docMirror.appendChild(marker);
    const boxRect = el.getBoundingClientRect();
    const markRect = marker.getBoundingClientRect();
    const mirrorRect = docMirror.getBoundingClientRect();
    const lineHeight = Number.parseFloat(style.lineHeight) || 18;
    const top = boxRect.top + (markRect.top - mirrorRect.top) - el.scrollTop;
    return {
      left: boxRect.left + (markRect.left - mirrorRect.left) - el.scrollLeft,
      top,
      bottom: top + lineHeight,
      lineHeight,
    };
  }

  //: **Where the caret is, in pixels, for whichever surface holds it.** The
  //: shape the plan names (`coordsAt(pos) -> {left, top, bottom}`), with the
  //: line height carried alongside because every caller here places a popup
  //: *under* the line and needs to know how tall it is.
  function docCaretPoint(box) {
    return box.coordsAt(box.selection().from);
  }


  // --- the prose check ----------------------------------------------------------
  //
  // **Rules, not judgement.** Each one has to be something a regular expression
  // can be *sure* about, because a checker that is wrong a third of the time
  // teaches people to ignore it, and then the two thirds it is right about go
  // unread too. That is why there is no its/it's rule here: telling those apart
  // needs the sentence's meaning, and this has none.
  //
  // `fix` is optional. A rule that can state the problem but not the answer
  // ("this sentence is 47 words long") still earns its row: knowing where to look
  // is most of the work. Only rules with a `fix` get a button.
  const DOC_PROSE_RULES = [
    {
      id: "repeat",
      english: true,
      //: The classic, and the one nobody catches by re-reading: the eye supplies
      //: the missing word. Case-insensitive, and only for words worth repeating
      //: by accident: `\b(\w+)\s+\1\b` alone flags "had had" and "that that",
      //: which are both real English.
      test: /\b(the|a|an|and|to|of|in|is|it|that|for|on|with|as|at|be)\s+\1\b/gi,
      message: "The same word twice in a row",
      fix: (match) => match.split(/\s+/)[0],
    },
    {
      id: "double-space",
      test: /(?<=\S) {2,}(?=\S)/g,
      message: "More than one space between words",
      fix: () => " ",
    },
    {
      id: "space-before-punctuation",
      //: Not before `![[embed]]`: that `!` is the embed's own, not punctuation.
      //: Nor before a dotfile or an extension (" .gitignore", " .env"): the dot
      //: opens a name there (INBOX 1407). Nor the `!` of an image, `![alt](src)`
      //: (audit 1102 DX19): markdown syntax, not punctuation.
      test: /\s+([,.;:!?])(?!\[\[)(?!(?<=!)\[)(?!(?<=\.)[A-Za-z0-9])/g,
      message: "A space before punctuation",
      fix: (match) => match.trim(),
    },
    {
      id: "missing-space",
      //: After a full stop and before a capital, not after every full stop,
      //: because `3.5`, `file.md` and `e.g.` are all correct and common.
      test: /[a-z]{2}[.!?](?=[A-Z])/g,
      message: "No space after the full stop",
      fix: (match) => `${match} `,
    },
    {
      id: "missing-space-comma",
      //: Only before a letter. `1,000` and `a[1,2]` are both correct and common,
      //: and a rule that reformatted numbers would be worse than no rule.
      test: /,(?=[A-Za-z])/g,
      message: "No space after the comma",
      fix: () => ", ",
    },
    {
      id: "double-punctuation",
      test: /([,;:])\1+/g,
      message: "Punctuation repeated",
      fix: (match) => match[0],
    },
    {
      id: "confusion",
      english: true,
      //: your/you're, the one confusion Harper let through on the fixture
      //: (`tests/fixtures/grammar/grammar_fixture_1026.json`): "Your going to love it", "your
      //: not late", "your welcome". Only the forms that cannot be possessive
      //: ("your going to", "your not", "your welcome." closing a clause),
      //: because "your welcome mat" and "your right to vote" are fine. No `fix`:
      //: the answer is offered and never applied by Fix all.
      test: /\b[Yy]our(?= (?:going to|gonna|not|supposed to|able to|ready to)\b| welcome(?:[.,!?]|\s*$| to\b))/gm,
      message: "“your” here is probably “you’re”",
      alternatives: (match) => [match[0] === "Y" ? "You’re" : "you’re"],
    },
    {
      id: "spelling",
      //: The same list autocorrect uses, so a document written with autocorrect
      //: off can still be cleaned up in one pass afterwards. Built below from
      //: `DOC_AUTOCORRECT` rather than typed twice.
      test: null,
      message: "A likely typo",
    },
    {
      id: "long-sentence",
      //: 45 words is not wrong, and this does not say it is, it says look here.
      //: No `fix`, because splitting a sentence is a decision about meaning and
      //: this knows none.
      test: null,
      message: "A very long sentence, worth a full stop somewhere",
    },
  ];

  //: One table for the notes and the documents (audit 1031 N42): `AUTOCORRECT_TYPOS`, autocorrect.js,
  //: which this bundle loads first. Two copies had drifted, 42 rows against 89.
  const DOC_AUTOCORRECT = AUTOCORRECT_TYPOS;

  const DOC_LONG_SENTENCE_WORDS = 45;

  // --- the dictionary the spelling check actually reads -------------------------
  //
  // **What was wrong, and it was the whole check.** Until 2026-09-12 the
  // spelling rule looked each word up in `DOC_AUTOCORRECT`, a hand-written table
  // of 42 typos, and treated every word that was not in it as correctly spelled.
  // That is not a spell checker, it is a list of 42 strings: "tets" was never
  // flagged, and neither was anything else a person actually mistypes. The
  // owner's two reports are the same cause seen from two sides. "Spelling errors
  // and grammar arent picked up all the time" is the table being 42 entries
  // long. "No edit suggestions popup panel appears when I click on underlined
  // words" is subtler and worse: the underline being clicked was not this app's,
  // it was the *browser's* native squiggle, drawn because the editor carries
  // `spellcheck="true"`. The app had no finding at that word, so it had nothing
  // to open a menu about, and the click did nothing.
  //
  // So the fix has to be a real dictionary, and the browser's squiggle has to
  // go once there is one, or every misspelling carries two underlines and only
  // one of them answers a click. `docBrowserSpellcheck` is that switch, and it
  // is deliberately conditional rather than deleted: if the word list fails to
  // load, the browser's checker is better than nothing and comes straight back.
  //
  // **Why it is a fetch and not a script.** 871KB of words parsed into a Set is
  // work the first paint should never wait for, and most sessions never open a
  // document at all. It loads on the first prose pass, which is 150ms after the
  // first keystroke in a document at the earliest, and the pass re-runs itself
  // when it arrives.

  const DOC_WORDLIST_URL = "/vendor/wordlist/en.txt";

  //: The words this app and the notes people keep in it are written in, that a
  //: general English list does not carry. Kept here rather than appended to the
  //: vendored file, so that file stays exactly what its build.sh produces and
  //: the licence notice beside it keeps describing its contents.
  const DOC_EXTRA_WORDS = [
    "apis", "async", "auth", "autocomplete", "autosave", "autosaved",
    "backend", "callout", "callouts", "changelog", "chatbot", "config", "configs",
    "csv", "dockerfile",
    "downvote", "dropdown", "dropdowns", "embeddings", "enum", "filepath",
    "frontend", "fullstack", "gitlab", "golang", "https", "iterable", "json",
    "kanban", "kubernetes", "linter", "localhost", "memorymap", "mindmap",
    "namespace", "navbar", "nodejs", "npm", "oauth", "onboarding", "passwordless",
    "pypi", "readme", "realtime", "rebase", "regexes", "retagging", "roadmap",
    "rustc", "scrollbar", "sdk", "signup", "standup", "struct", "subfolder",
    "subfolders", "todo", "todos", "tokenizer", "toml", "tooltip", "tooltips",
    "tsv", "ui", "uncached", "untagged", "upvote", "uri", "utf", "uuid", "ux",
    "viewport", "webapp", "webhook", "webhooks", "wireframe", "yaml", "yml",
    //: Found by running the app's own visible text past the list: 34 words in
    //: the whole of index.html were missing, and these are the ones a person
    //: would also write in a note. The rest were fragments ("ve", "nbsp") or
    //: real misspellings ("isnt"), which is the answer that check was for.
    "ctrl", "esc", "bundler", "dev", "embedder", "frontmatter", "minimap",
    "mistyped", "multiline", "outdent", "rebindable", "resizer", "stylesheet",
    "subtree", "uncategorised", "uncategorized", "unlinked", "unticked",
    //: The tools this app talks to by name. They appear in its own screens, so
    //: they will appear in notes about them.
    "gmail", "markitdown", "nomic", "ollama", "qwen", "searxng", "tesseract",
    //: INBOX 1407: the words an interface note uses (a draggable, resizable
    //: panel with scrollbars and a debounce) and the file names' own parts,
    //: found by the false-positive fixture `tests/fixtures/grammar/grammar_fixture_1407.json`.
    "backoff", "clickable", "cron", "debounce", "draggable", "gitignore",
    "hoverable", "makefile", "pytest", "resizable", "scrollbars", "searchable",
    "sortable", "txt", "md", "bat",
  ];

  //: One object, not two top-level lets (the global-scope ratchet).
  const docWordlistState = { loading: false, failed: false };

  //: Until this is true the checker makes no claim about whether a word is
  //: spelled correctly, which is why every caller asks rather than assuming.
  function docWordlistReady() {
    return docWordlist !== null;
  }

  function docLoadWordlist() {
    if (docWordlist || docWordlistState.loading || docWordlistState.failed) return;
    docWordlistState.loading = true;
    api(DOC_WORDLIST_URL, { silent: true })
      .then((response) => response.text())
      .then((text) => {
        const words = new Set(DOC_EXTRA_WORDS);
        //: **`trim()`, and it is the whole bug report.** Reported with a
        //: screenshot of 268 suggestions on a 298-word document, every one of
        //: them a real English word: "litterally everything isnt in the
        //: dictionary". The list loads, so the no-dictionary guard in
        //: `docWordKnown` never fires; it just matches nothing.
        //:
        //: The file is committed with unix line endings and this sandbox reads
        //: it that way, which is why `docs-spell.js` measured six findings over
        //: 8,000 characters with no false positives. Git on Windows checks text
        //: out with CRLF by default, so every entry arrives as `"offline\r"`,
        //: and `Set.has("offline")` is false for all 92,972 of them. One
        //: checkout on one platform turns the checker into a machine that flags
        //: the entire language.
        //:
        //: Trimming here rather than only pinning the file in `.gitattributes`
        //: (which this commit does as well): the attribute fixes the checkout,
        //: and this fixes every copy that already exists, plus any future list
        //: that arrives with trailing whitespace from wherever it was built.
        for (const line of text.split("\n")) {
          const word = line.trim();
          if (word) words.add(word);
        }
        docWordlist = words;
        docWordlistState.loading = false;
        //: The ranked suggestions are drawn from the same pool, so it has to be
        //: rebuilt, and the pass that ran without a dictionary has to run again
        //: now that there is one.
        docKnownWordsCache = null;
        docSpellCache = new Map();
        docCmApplySpellcheck();
        renderDocProse();
      })
      .catch(() => {
        //: Once, not on a loop: a failed fetch here means the file is missing
        //: from the build, and retrying on every keystroke would turn one
        //: mistake into a request storm. The browser's own checker stays on.
        docWordlistState.loading = false;
        docWordlistState.failed = true;
      });
  }

  //: A word the checker is willing to have an opinion about. Everything refused
  //: here is refused because flagging it would be wrong far more often than it
  //: would be right, and a checker that cries wolf is one that gets turned off.
  function docSpellable(text, word, start, end) {
    //: Nor a run of more than 40 letters: that is a pasted token or a hash, and
    //: generating its one-edit neighbours aborted node on a 100,000-letter run.
    if (word.length < 2 || word.length > 40) return false;
    //: An acronym (API, HTTP, NASA) is not in any word list and is not a typo.
    if (word === word.toUpperCase()) return false;
    //: An internal capital means an identifier or a product name: Tessellate,
    //: docSurface, YouTube. Splitting and checking the halves would flag half
    //: the identifiers in any technical note.
    if (/[A-Z]/.test(word.slice(1))) return false;
    //: A letter run touching a digit, a path separator, an @ or a dot before
    //: more letters is part of something that is not prose: utf-8, app.js,
    //: me@example.com, C:\\Users. The word regex stops at those characters, so
    //: the only way to see them is to look at what is on either side.
    //: A suggestion's marker is a boundary, not a symbol (OPEN 1088): `{++`
    //: before and `++}` after (and the other CriticMarkup pairs) left
    //: `{++faque++}` with no finding while `{++the faque ++}` had one.
    const opened = /(?:\{\+\+|\{--|\{~~|\{==|\{>>|~>)$/.test(text.slice(Math.max(0, start - 3), start));
    const closed = /^(?:\+\+\}|--\}|~~\}|==\}|<<\}|~>)/.test(text.slice(end, end + 3));
    const before = start > 0 && !opened ? text[start - 1] : "";
    const after = end < text.length && !closed ? text[end] : "";
    if (/[0-9_/@\\#$%&*+=<>~]/.test(before) || /[0-9_/@\\#$%&*+=<>~]/.test(after)) return false;
    //: Next to é, ï, ß: a piece of a longer word (audit 1028 D8).
    if (/\p{L}/u.test(before) || /\p{L}/u.test(after)) return false;
    if (after === "." && /[A-Za-z]/.test(text[end + 1] || "")) return false;
    if (before === "." && /[A-Za-z]/.test(text[start - 2] || "")) return false;
    //: A dotfile (" .gitignore", ".env"): a dot that opens a name, with nothing
    //: but space or the line's start before it (INBOX 1407).
    if (before === "." && (start < 2 || /\s/.test(text[start - 2]))) return false;
    //: A short piece of a hyphenated word is a fragment of a compound that the
    //: word list holds whole or not at all: the "Fi" of Wi-Fi, the "x" of x-ray.
    //: Longer pieces ("anti-inflamatory") are still checked.
    if (word.length <= 3 && ((before === "-" && /[A-Za-z]/.test(text[start - 2] || "")) || (after === "-" && /[A-Za-z]/.test(text[end + 1] || "")))) {
      return false;
    }
    return true;
  }

  //: **A name is not a misspelling.** A capitalised word that is not the first
  //: of its sentence is a person, a place or a product ("Okafor", "Priya",
  //: "Aroha", "Zeynep", "Siobhan": 8 of the 13 false spelling marks on the
  //: fixture), and no word list holds them. The first word of a sentence, a list
  //: item, a heading or a table cell is capitalised whatever it is, so it keeps
  //: the check but only where the checker has one confident correction
  //: (`docSpellConfident`): "Recieve the report" is still caught, "Priya will
  //: send" is not. What this gives up: a typo in a capitalised word in the
  //: middle of a sentence ("Reveiw" in a title-case line) is not marked; adding
  //: names to the dictionary was the only other answer and it never ends.
  //: The exception is a swap of two letters that makes exactly one real word
  //: ("Reveiw" is "Review", no name is spelled by swapping two letters of a
  //: common word), which `docSpellTransposed` answers.
  //: Returns "" for a word that is not capitalised.
  function docSpellNameKind(text, word, start) {
    if (!/^[A-Z]/.test(word)) return "";
    //: Only the last 120 characters are read: a one-line document of 100,000
    //: characters made `lastIndexOf("\n")` scan back to its start for every
    //: capitalised word (measured: 24 ms became 277 ms).
    const window = text.slice(Math.max(0, start - 120), start);
    const newline = window.lastIndexOf("\n");
    const lead = newline >= 0 ? window.slice(newline + 1) : window;
    const atLineHead = newline >= 0 || start <= 120;
    const opens = atLineHead && /^[ \t]*(?:(?:[#>*+|-]+|\d+[.)]|\[[ xX]\])[ \t]*)*["'“‘(*_]*$/.test(lead);
    const afterStop = /[.!?]["')”’*_\]]*[ \t]+["'“‘(*_]*$/.test(lead);
    return opens || afterStop ? "initial" : "name";
  }

  //: Is this a word? Asked only of things `docSpellable` has already allowed.
  //: A trailing possessive is stripped rather than listed: the vendored file
  //: drops its 18,579 "word's" forms because this is cheaper and cannot get out
  //: of step with the nouns it is built from.
  function docWordKnown(word) {
    if (!docWordlist) return true;
    const bare = word.replace(/['’]s$/i, "").replace(/['’]+$/, "");
    if (!bare) return true;
    const lower = bare.toLowerCase();
    return docWordlist.has(lower) || docDictionary().has(lower);
  }

  //: The strings one edit away from a word, each tagged with *which* edit, and
  //: the tag is the point. Norvig's shape for the generation, and the reason it
  //: is this rather than a scan of the dictionary is arithmetic: a scan is
  //: 93,000 edit-distance computations, this is a few hundred Set lookups, and
  //: the two return the same answer for distance one.
  //:
  //: The tag ranks the answers, and ranking by *how specific the edit is* is
  //: what makes the top row the word the writer meant. There are only n-1
  //: transpositions of a word and n deletions, against 26n insertions and 25n
  //: substitutions: so a candidate that needs only a swap is a far stronger
  //: claim than one of twenty-five letters that could have gone in that slot.
  //: Measured: "tets" ranked alphabetically offered tats, teas, teds, tees and
  //: tens, and never "test", which is the one word anybody typing "tets" meant.
  const DOC_ALPHABET = "abcdefghijklmnopqrstuvwxyz'";
  const DOC_EDIT_SWAP = 0;
  const DOC_EDIT_DROP = 1; // one letter too many was typed
  const DOC_EDIT_ADD = 2; // one letter was missed
  const DOC_EDIT_SWAP_LETTER = 3; // the wrong letter was typed

  function docEditsOnce(word) {
    const out = new Map();
    const note = (candidate, rank) => {
      if (candidate === word) return;
      const seen = out.get(candidate);
      if (seen === undefined || rank < seen) out.set(candidate, rank);
    };
    for (let i = 0; i <= word.length; i += 1) {
      const head = word.slice(0, i);
      const tail = word.slice(i);
      if (tail) note(head + tail.slice(1), DOC_EDIT_DROP);
      if (tail.length > 1) note(head + tail[1] + tail[0] + tail.slice(2), DOC_EDIT_SWAP);
      for (const letter of DOC_ALPHABET) {
        if (tail) note(head + letter + tail.slice(1), DOC_EDIT_SWAP_LETTER);
        note(head + letter + tail, DOC_EDIT_ADD);
      }
    }
    return out;
  }

  function docSpellRoot(word) {
    return word.toLowerCase().replace(/['\u2019]s$/i, "");
  }

  //: Real words one or two edits from a misspelling, nearest first. Two edits
  //: is only reached when one edit finds too few, because it costs the square
  //: of the work and because a word with a one-edit neighbour almost always
  //: meant that neighbour.
  const DOC_TWO_EDIT_FLOOR = 2;

  function docSpellGuesses(word, limit = DOC_SUGGEST_MAX, quick = false) {
    if (!docWordlist) return [];
    const lower = docSpellRoot(word);
    const near = [];
    const once = docEditsOnce(lower);
    for (const [candidate, rank] of once) {
      if (docWordlist.has(candidate)) near.push([candidate, rank]);
    }
    //: Two edits only when one found next to nothing. It costs the square of
    //: the work, and a word with any one-edit neighbour almost always meant one
    //: of those.
    if (!quick && near.length < DOC_TWO_EDIT_FLOOR) {
      const seen = new Set(near.map(([candidate]) => candidate));
      //: Two edits out, everything is equally weak evidence, so they all share
      //: one rank below every one-edit answer.
      outer: for (const middle of once.keys()) {
        for (const candidate of docEditsOnce(middle).keys()) {
          if (candidate === lower || seen.has(candidate)) continue;
          if (!docWordlist.has(candidate)) continue;
          seen.add(candidate);
          near.push([candidate, DOC_EDIT_SWAP_LETTER + 1]);
          if (near.length >= limit * 3) break outer;
        }
      }
    }
    near.sort((a, b) => {
      if (a[1] !== b[1]) return a[1] - b[1];
      //: Within one kind of edit: the first letter is the one a typist gets
      //: right, then the nearer length, then alphabetically so the same word
      //: always offers the same menu in the same order.
      const first = (b[0][0] === lower[0] ? 1 : 0) - (a[0][0] === lower[0] ? 1 : 0);
      if (first) return first;
      const length = Math.abs(a[0].length - lower.length) - Math.abs(b[0].length - lower.length);
      if (length) return length;
      return a[0] < b[0] ? -1 : 1;
    });
    const words = near.map(([candidate]) => candidate);
    const contraction = docSpellContraction(lower);
    if (contraction) words.unshift(contraction);
    return words.slice(0, limit);
  }





  //: "Hide all suggestions for now": the marks, the count and the list go quiet
  //: for this sitting without touching the Settings switch or the dismissed
  //: list. Not stored, like a dismissal, so it can never be forgotten about.
  //: **`rules` keeps the rule pass for an answer that changes nothing it reads**
  //: (audit 1028 D18 to D20). The grammar worker's answer and the link offers'
  //: answer each repaint through `renderDocProse`, and the rules (a spelling
  //: lookup per word, the long-sentence scan) are the larger half of its cost:
  //: the repaint after the answer cost as much as the pass the key itself had
  //: paid, for the same text and the same findings. Those two callers pass
  //: `again`, and a pass that finds the same text under the same settings gets
  //: the findings it already made (copies, because the caller shifts their
  //: offsets). Every other caller (a key, a dismissal, a setting) runs afresh.
  //: A method here rather than a function of its own: the shared scope is capped.
  //: "list" is the suggestions, "dismissed" is the ones put away in this document.


  // The prose tools (grammar, suggestion mode, the accessibility check, read
  // aloud) are in documents-prose.js, which the Library bundle loads before
  // this file. See its header.

  //: The file's surface: what other files call (L-documents-117).
  Object.assign(window, { docActiveBox, docMirrorPoint, docCaretPoint, DOC_PROSE_RULES, DOC_AUTOCORRECT, DOC_LONG_SENTENCE_WORDS, docWordlistReady, docLoadWordlist, docSpellable, docSpellNameKind, docWordKnown, DOC_EDIT_SWAP, DOC_EDIT_DROP, docEditsOnce, docSpellRoot, docSpellGuesses });

  //: These lets keep their bare names for the other files as window accessors, so one store answers every reader and writer (L-documents-118).
  for (const [name, get, set] of [
    ["docWordlist", () => docWordlist, (value) => { docWordlist = value; }],
    ["docSpellCache", () => docSpellCache, (value) => { docSpellCache = value; }],
    ["docKnownWordsCache", () => docKnownWordsCache, (value) => { docKnownWordsCache = value; }],
  ]) Object.defineProperty(window, name, { get, set, configurable: true });
})();
