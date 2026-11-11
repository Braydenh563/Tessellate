// spell-second.js: the second opinion on words, inside harper-worker.js (INBOX 1731).
//
// Wrapped whole so its helpers stay out of the page's shared scope; the worker
// reads what it needs from `self.spellSecond` at the foot. Loaded by the worker
// only (`import "./spell-second.js"`), so nothing of it is in any boot script.
//
// What it does and why:
//
// Harper's word-level lints were the owner's "half the suggestions": "Uni" in
// "Uni is done!! :D" was underlined and the menu offered "Dei" (Harper reads
// "uni" as a negative prefix). Three layers answer that, all here so nothing
// reaches the boot bundle:
//   - a Hunspell dictionary for the person's dialect (LibreOffice's en_AU,
//     SCOWL's en_GB-ise; `frontend/vendor/spelling/`), read by `nspell`, and
//     the words the person's own notes use twice or more (`own`, sent by the
//     page; never from a private note), say whether a word is a word;
//   - suggestions that change more than a third of a short word are dropped
//     ("Uni" to "Dei" is two of three letters);
//   - what is left is ranked by how common the word is (SCOWL's size buckets).
// The dictionaries and the frequency list load on the first word that needs
// them, so a note with nothing to check never fetches them.

(() => {
  const SPELLING_DIR = new URL("../vendor/spelling/", import.meta.url);
  const WORD_ONLY = /^[A-Za-z]+(?:['’][A-Za-z]+)*$/;
  //: Lint kinds that judge whether a word is a word, which the dictionaries and
  //: the person's own words may overrule. A confusable pair ("their" and
  //: "there") is a grammar judgement and is never overruled this way.
  const VOCABULARY_KINDS = new Set(["Spelling", "Typo", "Regionalism"]);
  const NEGATIVE_WORD = /negative word you intended/i;

  let ownWords = new Set();
  const spellers = new Map();

  //: The one request this file makes: a static file from the open /vendor mount,
  //: in a Web Worker that has no `api()`.
  function fileText(name) {
    return fetch(new URL(name, SPELLING_DIR)).then((response) => response.text());
  }
  let frequency = null;

  function foldWord(word) {
    return String(word).toLowerCase().replace(/’/g, "'").replace(/'s$/, "");
  }

  //: Which Hunspell files a dialect reads. A dialect with no file of its own
  //: (American, Canadian, none) accepts a word either of the two knows, and
  //: suggests from the first.
  function dictionariesFor(dialect) {
    if (dialect === "au") return ["en_AU"];
    if (dialect === "uk" || dialect === "in") return ["en_GB"];
    return ["en_AU", "en_GB"];
  }

  function speller(name) {
    let loaded = spellers.get(name);
    if (!loaded) {
      loaded = (async () => {
        const [{ default: nspell }, aff, dic] = await Promise.all([
          import("../vendor/spelling/nspell.js"),
          fileText(`${name}.aff`),
          fileText(`${name}.dic`),
        ]);
        return nspell(aff, dic);
      })();
      spellers.set(name, loaded);
    }
    return loaded;
  }

  //: A word's frequency bucket: 1 is the commonest (SCOWL size 35), 4 is a word
  //: in none of the three lists. The file is "# 35", "# 40", "# 50" and a word
  //: per line under each.
  function frequencyList() {
    if (!frequency) {
      frequency = fileText("frequency.txt").then((text) => {
          const ranks = new Map();
          let bucket = 4;
          for (const line of text.split("\n")) {
            if (line.startsWith("#")) {
              const size = Number(line.slice(1));
              if (size) bucket = size === 35 ? 1 : size === 40 ? 2 : 3;
            } else if (line) {
              ranks.set(line.trim(), bucket);
            }
          }
          return ranks;
        });
    }
    return frequency;
  }

  async function wordKnown(dialect, word) {
    if (ownWords.has(foldWord(word))) return true;
    for (const name of dictionariesFor(dialect)) {
      const checker = await speller(name);
      if (checker.correct(word)) return true;
    }
    return false;
  }

  //: Optimal string alignment distance: the typos this is for are a swapped
  //: pair, a doubled or dropped letter, a neighbouring key.
  function editDistance(a, b) {
    const rows = [];
    for (let i = 0; i <= a.length; i += 1) {
      rows.push(new Array(b.length + 1).fill(0));
      rows[i][0] = i;
    }
    for (let j = 0; j <= b.length; j += 1) rows[0][j] = j;
    for (let i = 1; i <= a.length; i += 1) {
      for (let j = 1; j <= b.length; j += 1) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        let best = Math.min(rows[i - 1][j] + 1, rows[i][j - 1] + 1, rows[i - 1][j - 1] + cost);
        if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) best = Math.min(best, rows[i - 2][j - 2] + 1);
        rows[i][j] = best;
      }
    }
    return rows[a.length][b.length];
  }

  //: A suggestion may change at most a third of the word, and at least one
  //: letter: "Uni" to "Dei" is two of three and is not offered, "recieve" to
  //: "receive" is one of seven and is.
  function withinThird(word, candidate) {
    const from = foldWord(word);
    const to = String(candidate).toLowerCase();
    return editDistance(from, to) <= Math.max(1, Math.floor(from.length / 3));
  }

  function matchCase(sample, word) {
    if (!word || sample === sample.toLowerCase()) return word;
    return sample === sample.toUpperCase() && sample.length > 1 ? word.toUpperCase() : word[0].toUpperCase() + word.slice(1);
  }

  //: The answers for one word: Harper's own plus the dictionary's, those that
  //: change too much dropped, a split into two words kept only when both halves
  //: are words, and the rest in order of how common they are, then how near.
  async function rankedSuggestions(dialect, word, offered = []) {
    const names = dictionariesFor(dialect);
    const checker = await speller(names[0]);
    const pool = [];
    for (const text of [...offered, ...checker.suggest(word)]) {
      if (text && !pool.includes(text) && text.toLowerCase() !== word.toLowerCase()) pool.push(text);
    }
    const ranks = await frequencyList();
    const scored = [];
    for (const [index, text] of pool.entries()) {
      const parts = text.split(/\s+/);
      if (parts.length > 1) {
        let allWords = true;
        for (const part of parts) allWords = allWords && (await wordKnown(dialect, part));
        if (!allWords) continue;
      }
      if (!withinThird(word, text.replace(/\s+/g, ""))) continue;
      const rank = Math.min(...parts.map((part) => ranks.get(part.toLowerCase()) || 4));
      const near = editDistance(foldWord(word), text.toLowerCase());
      //: A swap of two letters is the strongest evidence of a typo ("teh" is
      //: "the", not "ten"), as in the page's own checker.
      const swapped = near === 1 && [...foldWord(word)].sort().join("") === [...text.toLowerCase()].sort().join("");
      scored.push([rank, swapped ? 0.5 : near, index, matchCase(word, text)]);
    }
    scored.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
    return scored.slice(0, 5).map((row) => row[3]);
  }

  //: One Harper lint after the second opinion: the lint to send, or null when
  //: the word is a word.
  async function refined(lint, dialect, text) {
    const span = text.slice(lint.start, lint.end);
    if (!WORD_ONLY.test(span)) return lint;
    if (
      lint.kind === "Capitalization" &&
      /^[A-Z][a-z]+$/.test(span) &&
      lint.suggestions.some((s) => s.text === "NaN" || (s.text.length > 1 && s.text === s.text.toUpperCase()))
    ) {
      //: "Sam" is not SAM and "Nan" is not NaN: a name in a notebook.
      return null;
    }
    const negative = lint.kind === "WordChoice" && NEGATIVE_WORD.test(lint.message);
    if (!VOCABULARY_KINDS.has(lint.kind) && !negative) return lint;
    //: A dialect with no dictionary of its own (American, Canadian, none) must
    //: not let British or Australian ones overrule Harper's own "this is the
    //: other spelling" lint: "colour" is a finding for an American notebook.
    const ownDictionary = dialect === "au" || dialect === "uk" || dialect === "in";
    if (lint.kind !== "Spelling" || ownDictionary ? await wordKnown(dialect, span) : ownWords.has(foldWord(span))) return null;
    const offered = lint.suggestions.filter((s) => s.kind === "Replace").map((s) => s.text);
    const kept = await rankedSuggestions(dialect, span, offered);
    //: A "negative word" lint with nothing sensible to offer has nothing to say.
    if (negative && !kept.length) return null;
    return { ...lint, suggestions: kept.map((word) => ({ kind: "Replace", text: word })) };
  }

  async function spellAnswers(dialect, words) {
    const out = {};
    for (const word of words.slice(0, 200)) {
      if (!WORD_ONLY.test(word)) continue;
      const known = await wordKnown(dialect, word);
      out[word] = { known, suggestions: known ? [] : await rankedSuggestions(dialect, word) };
    }
    return out;
  }


  //: The person's own words, sent whole each time they change.
  function setOwnWords(words) {
    ownWords = new Set((words || []).map(foldWord));
  }

  //: **Spelling packs for other languages (D30).** A pack is a Hunspell `.aff` and `.dic` the
  //: person installed from Settings, Packages; the page fetches the two files (a worker's
  //: own fetch carries no token) and sends them once per language, here, where the build
  //: (about a second for German or Spanish, four for French) stays off the page's thread.
  //: Nothing of it is read until a document in that language is open.
  const packs = new Map();

  async function packLoad(lang, aff, dic) {
    const { default: nspell } = await import("../vendor/spelling/nspell.js");
    packs.set(lang, nspell(aff, dic));
  }

  //: The same answer shape as `spellAnswers`. A language with no pack loaded answers
  //: nothing, never "unknown": the page then leaves the words alone rather than flagging them.
  function packAnswers(lang, words) {
    const checker = packs.get(lang);
    const out = {};
    if (!checker) return out;
    for (const word of words.slice(0, 200)) {
      //: Hunspell's French and Spanish files spell the apostrophe straight.
      const plain = String(word).replace(/’/g, "'");
      const known = ownWords.has(foldWord(word)) || checker.correct(plain);
      const near = known ? [] : checker.suggest(plain).filter((text) => withinThird(plain, text)).slice(0, 5);
      out[word] = { known, suggestions: near.map((text) => matchCase(plain, text)) };
    }
    return out;
  }

  self.spellSecond = { refined, spellAnswers, setOwnWords, packLoad, packAnswers };
})();
