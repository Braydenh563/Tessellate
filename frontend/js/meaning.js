// meaning.js: find by meaning in every search box (Brief 94, INBOX 857).
//
// The owner: "half the time Im trying to find a specific object, feature, or
// setting and I cant remember the exact name of it". A query is read as the
// things it names, each a group of words meaning the same ("bin", "trash",
// "deleted"), with the request's own words dropped ("how do I", "make") and
// a word one slip from a known word read as that word (the composer's typo
// rule, `question_noise.distance` and `allowance`, ported below).
//
// The tables are the server's (`GET /read/words`, ai/meaning.py), asked once;
// the rule is ai/meaning.py's `alts` and `holds`, and the two are kept the same
// by tests/test_meaning.py. Lazy, in the Settings and palette bundles
// (`LAZY_MODULES`, app.js): every caller is in one of those, or asks with a
// `typeof` guard and matches the plain words without it.
//
// Callers: Settings (`findSettings`, `filterSettings`), Help and the manual
// (`helpApplySearch`, `manualMatches`), the palette and Find anything's
// action rows (`paletteScore`). The suggest code (Brief 86) calls
// `meaningAlts` for its candidates rather than carrying a copy.

const meaningTable = { groups: [], filler: new Set(), asked: false };

//: Asked the first time a query is read, not at load: a script that fetches at
//: load runs where nothing is listening (and in a bare harness).
function meaningAsk() {
  if (meaningTable.asked) return;
  meaningTable.asked = true;
  apiJson("/read/words", { silent: true })
    .then((got) => {
      meaningTable.groups = got.groups || [];
      meaningTable.filler = new Set(got.filler || []);
      //: A query typed before the tables landed is read again with them, by
      //: each box that listens (settings-find.js, app-palette.js).
      document.dispatchEvent(new Event("meaning-ready"));
    })
    .catch(() => {});
}

//: Lower-cased words, an apostrophe dropped ("I've" is "ive"), a hyphen a
//: break ("battery-efficient" is two words).
function meaningWords(text) {
  return (String(text || "").toLowerCase().match(/[a-z0-9][a-z0-9']*/g) || []).map((w) => w.replace(/'/g, ""));
}

//: The word without a plural or tense ending ("deleted" is "delet", which
//: "delete" starts with).
const MEANING_ENDS = [["ies", 3], ["ing", 5], ["ed", 4], ["es", 4], ["s", 3]];
function meaningStem(word) {
  for (const [end, keep] of MEANING_ENDS) {
    if (word.endsWith(end) && word.length - end.length >= keep) return word.slice(0, -end.length);
  }
  return word;
}

//: QWERTY neighbours: a slip to the next key costs half an edit.
const MEANING_NEAR = (() => {
  const rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"];
  const near = {};
  rows.forEach((row, r) => {
    [...row].forEach((key, c) => {
      near[key] = new Set();
      for (const dr of [-1, 0, 1]) {
        for (const dc of [-1, 0, 1]) {
          const other = rows[r + dr]?.[c + dc];
          if ((dr || dc) && other) near[key].add(other);
        }
      }
    });
  });
  return near;
})();

//: question_noise.distance: a neighbouring key 0.5, a swap 0.6, a doubled
//: letter added or dropped 0.4, a vowel 0.5, anything else 1.
function meaningDistance(a, b) {
  let rows = [];
  for (let i = 0; i <= a.length; i++) rows.push(new Array(b.length + 1).fill(0));
  for (let i = 1; i <= a.length; i++) rows[i][0] = i;
  for (let j = 1; j <= b.length; j++) rows[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      const drop = i > 1 && a[i - 1] === a[i - 2] ? 0.4 : "aeiou".includes(a[i - 1]) ? 0.5 : 1;
      const add = j > 1 && b[j - 1] === b[j - 2] ? 0.4 : "aeiou".includes(b[j - 1]) ? 0.5 : 1;
      const sub = a[i - 1] === b[j - 1] ? 0 : MEANING_NEAR[a[i - 1]]?.has(b[j - 1]) ? 0.5 : 1;
      let best = Math.min(rows[i - 1][j] + drop, rows[i][j - 1] + add, rows[i - 1][j - 1] + sub);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) best = Math.min(best, rows[i - 2][j - 2] + 0.6);
      rows[i][j] = best;
    }
  }
  return rows[a.length][b.length];
}

//: question_noise.allowance: how far a word may be from the one it is read as.
function meaningAllowance(word) {
  const n = word.length;
  return n <= 2 ? 0 : n === 3 ? 0.6 : n <= 5 ? 1 : n <= 8 ? 1.5 : 2;
}

//: Every word the tables know, with the caller's own (its rows' names).
function meaningVocab(extra) {
  const out = new Set(meaningTable.filler);
  for (const group of meaningTable.groups) for (const said of group) for (const w of said.split(" ")) out.add(w);
  for (const w of extra || []) out.add(w);
  return out;
}

//: The known word a slip of `word` was meant to be, or null.
function meaningFold(word, vocab) {
  if (vocab.has(word) || word.length < 4 || /^\d+$/.test(word)) return null;
  let best = null;
  let bestD = meaningAllowance(word) + 1e-9;
  for (const known of vocab) {
    if (Math.abs(known.length - word.length) > 2) continue;
    if (known[0] !== word[0] && known.slice(0, 2) !== word[1] + word[0]) continue;
    const d = meaningDistance(word, known);
    if (d < bestD) {
      best = known;
      bestD = d;
    }
  }
  return best;
}

function meaningGroupOf(word) {
  const root = meaningStem(word);
  return meaningTable.groups.find((group) => group.some((said) => !said.includes(" ") && (word === said || root === meaningStem(said)))) || null;
}

//: The things `query` names, each as the words that mean it, head first.
//: `vocab` is the caller's own words (a Set), so a slip of a row's name is
//: read as that name.
function meaningAlts(query, vocab) {
  meaningAsk();
  const known = meaningVocab(vocab);
  const said = meaningWords(query).map((w) => meaningFold(w, known) || w);
  let rest = ` ${said.join(" ")} `;
  const out = [];
  for (const group of meaningTable.groups) {
    //: Longest first, every one: "to do list" before "to do".
    const phrases = [...group].sort((a, b) => b.length - a.length).filter((p) => p.includes(" ") && rest.includes(` ${p} `));
    for (const phrase of phrases) rest = rest.replace(` ${phrase} `, " ");
    if (phrases.length) out.push([...group]);
  }
  const left = rest.split(" ").filter(Boolean);
  const named = left.filter((w) => !meaningTable.filler.has(w));
  for (const word of named.length || out.length ? named : left) {
    const group = meaningGroupOf(word);
    //: Said twice ("what it remembers about me") is one thing.
    const same = group && out.find((g) => g.includes(group[0]));
    if (same) {
      //: Every word typed for the thing counts as typed ("which ai model"
      //: holds "model" as closely as "ai").
      if (same.includes(word)) same.splice(same.indexOf(word), 1);
      same.unshift(word);
      continue;
    }
    const found = meaningStem(word) === word ? [word] : [word, meaningStem(word)];
    out.push(found.concat((group || []).filter((w) => !found.includes(w))));
  }
  return out;
}

//: A word held whole, or with an ending ("delet" in "deleted", "animation" in
//: "animations"), never as the start of another word ("memory" is not in
//: "Tessellate", "pin" not in "spinning").
const MEANING_ENDING = "(?:s|es|ed|d|e|ing|ings|er|ers|ion|ions|ly|y)?";
const meaningPatterns = new Map();
function meaningPattern(word) {
  let rx = meaningPatterns.get(word);
  if (!rx) {
    rx = new RegExp(` ${word.replace(/-/g, " ").replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}${MEANING_ENDING}(?= )`);
    meaningPatterns.set(word, rx);
  }
  return rx;
}

function meaningText(text) {
  return ` ${meaningWords(text).join(" ")} `;
}

//: Where in its group the first word `text` holds is, or -1: the typed word
//: is 0, the thing's own name next, and the rest in the order written.
function meaningAt(group, lowered) {
  return group.findIndex((w) => meaningPattern(w).test(lowered));
}

//: How many of the things named `text` does not hold.
function meaningMissing(things, text) {
  const lowered = meaningText(text);
  return things.filter((group) => meaningAt(group, lowered) < 0).length;
}

function meaningHolds(things, text) {
  //: Nothing read from the words (Japanese has no a-z word) holds nothing: an empty list is
  //: not "every thing is held", which listed every command for 考え (audit 1031 N13).
  return things.length > 0 && meaningMissing(things, text) === 0;
}

//: How close `text` comes to the words typed: for each thing it holds, 1 for
//: the word as typed, a half for the next word of its group, a third for the
//: one after ("mascot" finds "Corner companion", the group's head, before
//: "Atlas and faces"). The rank between rows that hold the same things.
function meaningCloseness(things, text) {
  const lowered = meaningText(text);
  let sum = 0;
  for (const group of things) {
    const at = meaningAt(group, lowered);
    if (at >= 0) sum += 1 / (1 + at);
  }
  return sum;
}

//: The words of a query that name something, the request's own dropped
//: ("get my deleted stuff back" is "deleted"); all of them when every one
//: is a request word.
function meaningNamed(query) {
  meaningAsk();
  const words = meaningWords(query);
  const named = words.filter((w) => !meaningTable.filler.has(w));
  return named.length ? named : words;
}

//: **Close in meaning** (Brief 94): with an embedding model on, the rows of a
//: box nearest the query by meaning (`POST /read/near`), as indices into
//: `texts`, best first. Without one the server says so once and this stops
//: asking until the page reloads; a box's word matches stand either way.
//: Asked a quarter second after the last keystroke, so typing is not a
//: request per letter.
const meaningNearState = { off: false, timer: null };
function meaningNear(query, texts) {
  if (meaningNearState.off || String(query || "").trim().length < 3 || !texts.length) return Promise.resolve([]);
  clearTimeout(meaningNearState.timer);
  return new Promise((resolve) => {
    meaningNearState.timer = setTimeout(() => {
      apiJson("/read/near", { method: "POST", body: JSON.stringify({ q: query.trim().slice(0, 200), texts: texts.slice(0, 600) }), silent: true })
        .then((got) => {
          if (!got.available) meaningNearState.off = true;
          resolve((got.near || []).map((n) => n.i));
        })
        .catch(() => resolve([]));
    }, 250);
  });
}
