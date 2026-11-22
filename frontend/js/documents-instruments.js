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
        docSpellWordsSliced(text, words, () => docWordlistReadyNow(words)); // trimmed, in 8 ms slices (documents-spell.js)
      })
      .catch(() => {
        //: Once, not on a loop: a failed fetch here means the file is missing
        //: from the build, and retrying on every keystroke would turn one
        //: mistake into a request storm. The browser's own checker stays on.
        docWordlistState.loading = false;
        docWordlistState.failed = true;
      });
  }

  //: The set is whole: the checker reads it from here on.
  function docWordlistReadyNow(words) {
    docWordlist = words;
    docWordlistState.loading = false;
    //: The suggestions share the pool, so it is rebuilt, and the pass that ran without a dictionary runs again, a frame
    //: after the set and not in its task: the two together were a 267 ms frame after a first paint (L-world-class-40).
    docKnownWordsCache = null;
    docSpellCache = new Map();
    afterFrames(() => setTimeout(() => {
      docCmApplySpellcheck();
      renderDocProse();
    }), 1);
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
  Object.assign(window, { docCaretPoint, DOC_PROSE_RULES, DOC_AUTOCORRECT, DOC_LONG_SENTENCE_WORDS, docWordlistReady, docLoadWordlist, docSpellable, docSpellNameKind, docWordKnown, DOC_EDIT_SWAP, DOC_EDIT_DROP, docEditsOnce, docSpellRoot, docSpellGuesses, renderDocStats });

  //: These lets keep their bare names for the other files as window accessors, so one store answers every reader and writer (L-documents-118).
  for (const [name, get, set] of [
    ["docWordlist", () => docWordlist, (value) => { docWordlist = value; }],
    ["docSpellCache", () => docSpellCache, (value) => { docSpellCache = value; }],
    ["docKnownWordsCache", () => docKnownWordsCache, (value) => { docKnownWordsCache = value; }],
  ]) Object.defineProperty(window, name, { get, set, configurable: true });

  // A target word count, set per document and kept client-side, it's a
  // writing aid, not notebook data, so it doesn't need a column or to survive
  // a restore onto another machine the way the document's own content does.
  function docWordGoalKey(id) {
    return `docWordGoal:${id}`;
  }

  function getDocWordGoal(id) {
    if (!id) return 0;
    return Number(prefs.get(docWordGoalKey(id), null)) || 0;
  }

  function setDocWordGoal(id, goal) {
    if (!id) return;
    if (goal > 0) {
      prefs.set(docWordGoalKey(id), String(goal));
    } else {
      prefs.remove(docWordGoalKey(id));
    }
  }

  //: **The goal, and only the goal.** The word count, the reading time and the
  //: character count moved to the editor's own status bar (`renderDocStatusBar`)
  //: when the top dock was rebuilt, reported as "redesign, rearrange, fix, and
  //: update the section with the word count, word goal etc elements". Facts
  //: about the text belong beside the text; what is left here is the *target*,
  //: which is a thing you set rather than a thing you read, and it is drawn as
  //: its own control on the same bar.
  //:
  //: Kept as a separate function from the status bar's because it is called from
  //: four places that mean "the document changed", and because a goal is
  //: per-document state while the counts are pure arithmetic over the box.
  function renderDocStats() {
    const button = $("doc-word-goal");
    const label = $("doc-goal-label");
    if (!button || !label) return;
    //: A word-count goal is for writing: a code file has no use for one, so it
    //: also skips the word count (a whole-document pass: about 200 ms a pause
    //: on a 7,000-line file at 4x CPU, audit 1031 row 23 CE3).
    const code = docIsCodeFile();
    button.classList.toggle("hidden", code);
    if (code) return;
    const { words } = docPlainText.counts(docCommentStrip(docText()));
    const goal = currentDoc ? getDocWordGoal(currentDoc.id) : 0;
    button.setAttribute("aria-pressed", String(goal > 0));
    button.classList.toggle("has-findings", goal > 0 && words >= goal);
    if (!goal) {
      label.textContent = "Set a goal";
      button.title = "Set a word-count goal for this document";
      //: The progress ring is meaningless without a target, so it is not drawn
      //: rather than drawn empty, an empty meter reads as "you have written
      //: nothing", which is a different and usually false claim.
      button.style.removeProperty("--doc-goal-pct");
      button.classList.remove("has-goal");
      return;
    }
    const pct = Math.min(100, Math.round((words / goal) * 100));
    label.textContent = `${words.toLocaleString()} / ${goal.toLocaleString()} · ${pct}%`;
    button.title = `Goal: ${goal.toLocaleString()} words: click to change it`;
    //: A custom property rather than an inline `style` attribute, which this
    //: app's CSP refuses. Same rule the Loose ends meter follows.
    button.style.setProperty("--doc-goal-pct", `${pct}%`);
    button.classList.add("has-goal");
  }

  function promptDocWordGoal() {
    if (!currentDoc) return;
    const current = getDocWordGoal(currentDoc.id);
    $("doc-word-goal-input").value = current || "";
    $("doc-word-goal-dialog").showModal();
    $("doc-word-goal-input").focus();
  }

  $("doc-word-goal").addEventListener("click", promptDocWordGoal);

  $("doc-counts")?.addEventListener("click", () => docRunTextTool("stats"));

  $("doc-counts")?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    docRunTextTool("stats");
  });

  //: **A button with no width is not a place to stand** (audit 1102 DX21): at 390
  //: the counts give way entirely (an ellipsis in a 0px box), still visible to
  //: the tab key as a focus stop nobody can see. It leaves the tab order while it
  //: has no room and comes back when it has; the same statistics are one press
  //: away in the document menu. Watched by `docGutterObserver`, whose callback
  //: knows this one element.
  watchDocGutter($("doc-counts"));

  //: **A word goal for the day, and a streak** (L-documents-2). Words added to prose documents are counted per local day in
  //: prefs (`docWriting`); a day that reaches the goal extends the streak, and a missed day starts it again. A jump of
  //: more than WB words in one count is a paste or a load, not writing, and is not credited. Set from the word count's
  //: menu (right-click, or the menu key); everything stays on this device. Fed by `renderDocCounts` with a `doc:counted` event.
  // writing-streak:begin
  (() => {
    const counts = $("doc-counts");
    if (!counts) return;
    const KEY = "docWriting";
    const GOALS = [250, 500, 1000, 2000];
    const PASTE = 200;
    let seen = { id: null, words: 0 };
    const dayOf = (date) => [date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"), String(date.getDate()).padStart(2, "0")].join("-");
    const today = () => dayOf(new Date());
    const yesterday = () => {
      const date = new Date();
      date.setDate(date.getDate() - 1);
      return dayOf(date);
    };
    const read = () => {
      let state = {};
      try {
        state = JSON.parse(prefs.get(KEY, "{}")) || {};
      } catch {
        state = {};
      }
      const day = today();
      return { goal: Number(state.goal) || 0, day, words: state.day === day ? Number(state.words) || 0 : 0, streak: Number(state.streak) || 0, last: state.last || "" };
    };
    const write = (state) => prefs.set(KEY, JSON.stringify(state));
    //: A streak that was last extended before yesterday has ended, whatever it was.
    const live = (state) => (state.last === state.day || state.last === yesterday() ? state.streak : 0);
    const line = (state) => {
      const days = live(state);
      const streak = days ? `, ${days}-day streak` : "";
      return state.goal ? `${state.words.toLocaleString()} of ${state.goal.toLocaleString()} words today${streak}` : `${state.words.toLocaleString()} words added today`;
    };
    counts.addEventListener("doc:counted", (event) => {
      const { id, words } = event.detail;
      const before = seen.id === id ? seen.words : null;
      seen = { id, words };
      const state = read();
      const delta = before === null ? 0 : words - before;
      if (delta > 0 && delta <= PASTE) {
        state.words += delta;
        if (state.goal && state.words >= state.goal && state.last !== state.day) {
          state.streak = state.last === yesterday() ? state.streak + 1 : 1;
          state.last = state.day;
        }
        write(state);
      }
      if (state.goal) counts.textContent += ` · ${state.words.toLocaleString()} of ${state.goal.toLocaleString()} today`;
      counts.title = `${DOC_COUNTS_TITLE_PROSE}. Right-click for the daily word goal`;
    });
    const openMenu = (x, y) => {
      if (docIsCodeFile()) return false;
      const state = read();
      const set = (goal) => () => write({ ...state, goal });
      const items = [{ group: "Today", label: "ph:pencil-simple-line " + line(state), disabled: true, run: () => {} }];
      for (const goal of GOALS) {
        items.push({ group: "Daily word goal", label: `${state.goal === goal ? "ph:check" : "ph:flag"} ${goal.toLocaleString()} words`, run: set(goal) });
      }
      items.push({ group: "Daily word goal", label: "ph:x No daily goal", run: set(0) });
      openMenuAtPoint(items, "Daily word goal", x, y, counts);
      return true;
    };
    counts.addEventListener("contextmenu", (event) => {
      const box = counts.getBoundingClientRect();
      if (openMenu(event.clientX || box.left, event.clientY || box.top)) event.preventDefault();
    });
    //: A finger's twin of the right-click (a hold on the counts).
    wireLongPress(counts, (event, point) => openMenu(point.x, point.y));
  })();

  // writing-streak:end
  $("doc-word-goal-submit").addEventListener("click", () => {
    if (!currentDoc) return;
    //: The field's own limits say what is wrong (1031 DC9: a negative goal
    //: closed the dialog with no goal and no word), the way the form does.
    if (!$("doc-word-goal-input").reportValidity()) return;
    const goal = Math.max(0, Math.round(Number($("doc-word-goal-input").value)) || 0);
    setDocWordGoal(currentDoc.id, goal);
    renderDocStats();
    $("doc-word-goal-dialog").close();
  });

  //: **A second door onto the line numbers, in the menu that is already about
  //: how the document is shown.** The owner: "if I select a txt document,
  //: and/or other code file document, and these can have line numbers as well."
  //: They could, and the only control that said so lived on the formatting
  //: strip, which PLAN.md D1 collapsed by default for good reasons that had
  //: nothing to do with this. A preference nobody can find is a preference the
  //: app does not have.
  //:
  //: The same `setDocGutter`, so this and the strip's button are two views of
  //: one remembered choice rather than two settings; `applyDocGutter` writes
  //: both their pressed states back.
  //: The two draw switches show the stored choice (their change handlers are in documents-view.js).
  if ($("doc-code-wrap")) $("doc-code-wrap").checked = docToolPref("codeWrap", false);

  if ($("doc-whitespace")) $("doc-whitespace").checked = docToolPref("whitespace", false);

  //: **A misspelling's row names its nearest word** (audit 1102 DX19): "libary"
  //: and "tomorow" showed only "not in the dictionary" until the row was opened.
  //: One edit only (`quick`), cached on the finding, for the rows drawn; the menu
  //: still offers every candidate. Empty when the dictionary was sure (the row
  //: then has its own answer) or one edit finds nothing.
  docSpellGuesses.hint = (finding) => {
    if (finding.rule !== "spelling" || finding.replacement !== null) return "";
    finding.hint ??= docMatchCase(finding.text, docSpellGuesses(finding.text, 1, true)[0] || "");
    return finding.hint;
  };

  //: The dictionary dialog is a surface built on its first open (index.html), so its controls are wired then.
  onSurface("docDictionary", () => {
    $("doc-dictionary-close")?.addEventListener("click", () => $("doc-dictionary-dialog")?.close());

    $("doc-spelling-variant")?.addEventListener("change", async (event) => {
      prefsCache = await apiJson("/preferences", {
        method: "PUT",
        body: JSON.stringify({ spelling_variant: event.currentTarget.value }),
      }).catch(() => prefsCache);
      //: The variant decides which half of the pair table is a finding, so the lookup has to be rebuilt before the next pass reads it.
      docVariantFor = null;
      //: And the grammar checker's dialect with it (British or American rules).
      docGrammarCache = { text: null, findings: [] };
      renderDocProse();
    });

    //: Kinds of suggestion (L333): a ticked box is a kind shown; the ones left unticked are saved as `prose_kinds_off` and sent with every grammar ask, so the worker drops them.
    $("doc-prose-groups")?.addEventListener("change", async (event) => {
      const off = [...event.currentTarget.querySelectorAll("[data-prose-group]")].filter((box) => !box.checked).map((box) => box.dataset.proseGroup);
      prefsCache = await apiJson("/preferences", {
        method: "PUT",
        body: JSON.stringify({ prose_kinds_off: off }),
      }).catch(() => prefsCache);
      docGrammarCache = { text: null, findings: [] };
      renderDocProse();
    });

    $("doc-link-offers")?.addEventListener("change", async (event) => {
      prefsCache = await apiJson("/preferences", {
        method: "PUT",
        body: JSON.stringify({ link_offers: event.currentTarget.checked }),
      }).catch(() => prefsCache);
      DOC_LINK_OFFERS.text = null;
      DOC_LINK_OFFERS.findings = [];
      renderDocProse();
    });

    //: Link text (K11): the same preference as Settings, Writing. The grammar answer is thrown away because what it keeps depends on the switch.
    $("doc-check-link-text")?.addEventListener("change", async (event) => {
      prefsCache = await apiJson("/preferences", {
        method: "PUT",
        body: JSON.stringify({ check_link_text: event.currentTarget.checked }),
      }).catch(() => prefsCache);
      docGrammarCache = { text: null, findings: [] };
      renderDocProse();
    });

    $("doc-grammar-check")?.addEventListener("change", async (event) => {
      prefsCache = await apiJson("/preferences", {
        method: "PUT",
        body: JSON.stringify({ grammar_check: event.currentTarget.checked }),
      }).catch(() => prefsCache);
      docGrammarCache = { text: null, findings: [] };
      renderDocProse();
    });

    //: The same preference Settings, Preferences sets (`smart_punctuation`), here
    //: beside the other writing checks; saved on the change, as the two above are.
    $("doc-smart-punctuation")?.addEventListener("change", async (event) => {
      prefsCache = await apiJson("/preferences", {
        method: "PUT",
        body: JSON.stringify({ smart_punctuation: event.currentTarget.checked }),
      }).catch(() => prefsCache);
    });
  });

  for (const [name, id] of Object.entries(DOC_TOOL_KEYS)) {
    const input = $(id);
    if (!input) continue;
    //: `complete` defaults on and `autocorrect` defaults off, which is the
    //: difference between *offering* something and *doing* it to your text.
    input.checked = docToolPref(name, name === "complete");
    input.addEventListener("change", () => {
      docSaveToolPref(name, input.checked);
      if (name === "complete" && !input.checked) hideDocComplete();
    });
  }
  // =============================================================================
  // The dictionary, the spelling variant, and the popup you get from a flagged word
  // =============================================================================
  //
  // Asked for: *"the auto correct and grammar checker needs to be improved
  // because I cant click on the flagged word or phrase and see a popup for
  // suggested fixes or other options like adding to dictionary (a way to manage
  // that dictionary), auto correct spelling (us, uk spelling etc), language
  // translation etc. integrate all the usability that these features need and how
  // the user would expect to use them."*
  //
  // The check itself was already right; what it had no shape for was *disagreeing
  // with it*. A checker you cannot argue with is one you turn off, because the
  // third time it flags your project's name you have no way to say "this is a
  // word". So: every finding is a control, and the control's menu carries the
  // four answers a person actually has, fix it, this is a word, not this time,
  // and (for a spelling) always correct it for me.
  //
  // **The dictionary lives on the server** (`writing_dictionary`, routes_settings)
  // rather than in `localStorage`, and the reason is the same as the spelling
  // variant's: a word list you have to rebuild after clearing browser data is a
  // list nobody adds to, and a variant that differs between the desktop shell and
  // a browser tab is a checker that contradicts itself.


  //: The setting's five values (VC6) read the one table: Australian and Indian
  //: spell as the British column does for every pair here; Canadian is the
  //: mixed one (`DOC_CA_KEEPS_UK`). The label is what a finding says.





  // --- ranking the suggestions (DOCUMENTS_PLAN Phase 0 item 2) ------------------
  //
  // **Where a suggestion can honestly come from in an app with no dictionary
  // file.** This checker knows a fixed list of unambiguous typos and a UK/US
  // pair table, and that is the whole of its certainty. For a word it simply
  // does not recognise it had nothing to offer at all, and a menu whose only
  // row is "ignore this" is a menu that teaches you to stop opening it.
  //
  // So the order is by how much the app actually knows, strongest first:
  //
  //   1. the rule's own answer, where a rule was sure enough to have one;
  //   2. the other spelling of a UK/US pair, so a document set to UK still sees
  //      the US form offered rather than pretended out of existence;
  //   3. the nearest words by edit distance in the words this app can claim to
  //      know: your own dictionary, plus both halves of the pair table and the
  //      corrections in the typo list;
  //   4. the nearest words in your own writing, which is the only place your
  //      project names, your people and your jargon exist.
  //
  // Nothing here is a guess dressed as an answer: every row is a real word from
  // a list you could go and look at, and 3 and 4 are ordered by a distance the
  // reader can feel (one letter out sorts above two).




  //: The answers to a finding (rows as data, and the buttons drawn from them): documents-suggest.js, fetched on first
  //: use. Each is a stand-in the piece's function of the same name replaces on load, so a caller awaits it.


  //: **The popup, the translate hand-off, Discuss in chat and the AI review** are
  //: documents-suggest.js, fetched on first use. Each name here is a stand-in: the
  //: piece's own function of the same name replaces it on load, so calling the name
  //: again after the fetch reaches the real one. Nothing reads their return.

  //: Last line, deliberately: everything above has to exist before the first
  //: paint. See `renderDocTools`.
  renderDocTools();

  // =============================================================================
  // The engine: CodeMirror 6 under the documents editor (DOCUMENTS_PLAN Phase 2)
  // =============================================================================
  //
  // **Loaded when the first document is opened, never at boot.** The bundle is
  // 772 KB (269 KB gzipped) and most sessions in this app never touch the
  // Documents tab at all, so paying for it on every cold start would be a
  // second of nothing in exchange for a feature that may not be used. INBOX 48
  // argued the same shape for the graph's own vendored library. `?v=` is not
  // applied: vendor URLs are exempt from the cache stamp
  // (tests/test_asset_cache_busting.py) because the version lives in the pin in
  // `frontend/vendor/codemirror/package.json`, not in the app's release number.
  //
  // **The textarea stays.** If the script fails to load, or the browser refuses
  // it, `docSurface()` keeps answering with `#doc-content` and the editor keeps
  // working exactly as it did. That is the whole reason the fallback is still
  // in the markup, and it is why every call site had to go through the adapter
  // first: this file must never be able to tell which one it is talking to.
})();
