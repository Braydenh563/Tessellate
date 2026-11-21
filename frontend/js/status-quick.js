// status-quick.js: the Ask again chips and the most-used list on the Notes view (`loadRecentQuestions`,
// `loadMostUsed`). Moved out of status.js (LEDGER L698, L639) to come off the boot file: lazy, the
// `statusQuick` bundle with stand-ins in lazy-entries.js. Both were already async and every caller
// ignores or chains the promise, so the stand-in's promise answers them the same way.


// --- quick access: recent questions + most-used entries (Phase 5) -------------------

async function loadRecentQuestions() {
  const box = document.getElementById("recent-questions");
  if (!box) return;
  //: Shared with the dashboard's Recent questions widget (`cacheMs`), which
  //: asks for the same list in the same second at boot. Any write clears it.
  const questions = await apiJson("/chat/recent", { cacheMs: 30000 }).catch(() => []);
  box.replaceChildren();
  box.classList.toggle("hidden", questions.length === 0);
  if (questions.length === 0) return;
  const label = document.createElement("span");
  label.className = "muted";
  label.textContent = "Ask again:";
  box.appendChild(label);
  for (const question of questions) {
    //: The clock is what says "you asked this before" (INBOX 394 a): the chip
    //: is drawn like the suggestions beside it, so the icon carries the
    //: difference the fill used to.
    const short = question.length > 48 ? question.slice(0, 47) + "…" : question;
    const again = chip(`ph:clock-counter-clockwise ${short}`, "", () => {
      $("question").value = question;
      askQuestion();
    });
    again.title = question;
    box.appendChild(again);
  }
  ensureModule("askHistory").then(() => askAgainMenu(box, questions));
}

async function loadMostUsed() {
  const box = document.getElementById("most-used-box");
  const list = document.getElementById("most-used");
  if (!box || !list) return;
  const entries = await apiJson("/entries/most-accessed", { cacheMs: 30000 }).catch(() => []);
  list.replaceChildren();
  box.classList.toggle("hidden", entries.length === 0);
  for (const entry of entries) {
    const li = document.createElement("li");
    li.title = entry.content;
    const text = document.createElement("span");
    // Reported directly: a clip landing mid-token (`` `code` `` cut before
    // its closing backtick) left a stray `` ` `` sitting in the rendered
    // text: `safeMdSlice` drops the dangling marker instead of the plain
    // `slice(0, 25)` this used to do.
    //
    // Block syntax stripped first. renderInlineMarkdown is inline-only, so a
    // note beginning "# Groceries" rendered the literal "# Groceries", the
    // same gap the dashboard's mini-lists had, here too since this list uses
    // the same two-function combination.
    //: A picture's markdown is not words: cut at 25 characters it showed as a
    //: raw `![Sketch...` (dog3-1026 row 15).
    const flat = stripFrontmatter(entry.content)
      .replace(/!\[[^\]\n]{0,99}\]\([^)\n]{0,999}\)/g, "")
      .replace(/^\s*(?:#{1,6}\s+|>\s?|[-*+]\s+|\d+\.\s+)/gm, "")
      .trim() || "Picture";
    const { text: sliced, truncated } = safeMdSlice(flat, 25);
    renderInlineMarkdown(text, sliced, [], true);
    if (truncated) text.appendChild(document.createTextNode("…"));
    const count = document.createElement("span");
    count.className = "count";
    count.textContent = `×${entry.access_count}`;
    //: What the number counts (blind test 2026-10-31: "x4, of what?").
    count.title = `Opened or asked about ${entry.access_count} ${entry.access_count === 1 ? "time" : "times"}`;
    li.append(text, count);
    li.addEventListener("click", () => flashEntry(entry.id));
    list.appendChild(li);
  }
}
