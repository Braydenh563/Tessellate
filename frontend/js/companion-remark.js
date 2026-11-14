// companion-remark.js: what the companion says about the notebook, now and
// then (INBOX 743: "better popup messages and more varied"). The composer's
// remarks (`composer_voice.remarks`, no model) reach the page through
// `GET /insights/remarks`: a reminder due, a note from this day in an earlier
// year, an open item, a quiet day. Lazy: the boot carries only a stand-in
// (lazy-entries.js) that fetches this file when the mood tick first asks.
//
// Never twice in a week: each remark has a `fact` (what it is about) and the
// facts it has said are kept on this computer with their time; at most three a
// day, none within 20 s of a key press (CHAT_PLAN P11). Said in
// the speech bubble the poke lines use (`nameMarkSay`), held for as long as it
// takes to read, and only while it could act at all (`nameMarkBuddyReact`
// already refused under reduced motion, a hidden page, a menu, a carry).
(() => {
  //: The facts it has said and when ({fact: ms}), kept on this computer. A fact is what a remark is
  //: about (a note, a reminder), not its words, so rewording never says it twice (CHAT_PLAN P11).
  const NMB_REMARK_SAID = "nm-buddy-remarks-said";
  const NMB_REMARK_DAY = "nm-buddy-remarks-day";
  //: At most this many a day, none within this long of a key press, one switch (What it does).
  const NMB_REMARK_DAILY = 3;
  const NMB_REMARK_KEY_QUIET_MS = 20000;
  const NMB_REMARK_STORE = 200;
  const NMB_DAY_MS = 86400000;

  //: The first remark whose fact has not been said within its days (7, or ever for a tension).
  function nameMarkRemarkPick(remarks, said, now) {
    return (remarks || []).find((r) => r.text && !(said[r.fact || r.key] > now - (r.ttl_days || 7) * NMB_DAY_MS));
  }

  //: Whether a remark may be said now: under the day's count and not just after typing.
  function nameMarkRemarkMay(day, today, now, keyAt) {
    return (day.day !== today || day.n < NMB_REMARK_DAILY) && now - (keyAt || 0) >= NMB_REMARK_KEY_QUIET_MS;
  }

  //: A dated plan's reminder, offered on the bubble itself and made on a press.
  function nameMarkRemarkAct(bubble, act) {
    if (!bubble || !act) return;
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "ghost small nm-say-act";
    chip.textContent = act.label;
    //: The bubble ignores the pointer (`.nm-say`), its one chip does not.
    chip.style.pointerEvents = "auto";
    chip.style.marginTop = "var(--space-1)";
    chip.addEventListener("click", async () => {
      chip.disabled = true;
      try {
        const made = await apiJson("/reminders", { method: "POST", body: JSON.stringify({ text: act.text, due_at: act.due_at, entry_id: act.entry_id }) });
        reminderMadeUndo(made);
        chip.remove();
      } catch (error) {
        chip.disabled = false;
        toast(error.message || "Couldn't make that reminder.", true);
      }
    });
    bubble.appendChild(chip);
  }

  async function nameMarkBuddyRemark() {
    const now = Date.now();
    const today = new Date(now).toLocaleDateString("en-CA");
    const day = prefs.json(NMB_REMARK_DAY, {});
    if (!nameMarkRemarkMay(day, today, now, nmb.keyAt)) return;
    let body;
    try {
      body = await apiJson("/insights/remarks", { silent: true });
    } catch (e) {
      return;
    }
    const said = prefs.json(NMB_REMARK_SAID, {});
    const next = nameMarkRemarkPick(body.remarks, said, now);
    const buddy = document.getElementById("nm-buddy");
    //: It may have been picked up, hidden or put to sleep while the call ran.
    if (!next || !buddy?.isConnected || nameMarkBuddyStill() || document.hidden) return;
    if (buddy.classList.contains("nm-buddy-dragging") || buddy.classList.contains("nmb-sleep")) return;
    //: Typing began while the call ran: the remark waits for the next tick, unsaid.
    if (!nameMarkRemarkMay(day, today, Date.now(), nmb.keyAt)) return;
    const kept = Object.entries({ ...said, [next.fact || next.key]: now }).sort((a, b) => b[1] - a[1]).slice(0, NMB_REMARK_STORE);
    prefs.setJSON(NMB_REMARK_SAID, Object.fromEntries(kept));
    prefs.setJSON(NMB_REMARK_DAY, { day: today, n: (day.day === today ? day.n : 0) + 1 });
    //: After a frame has drawn the page (INBOX 1726: 213ms, 210 of it forced layout).
    nmb.afterClean(() => {
      if (!buddy.isConnected || nameMarkBuddyStill() || document.hidden) return;
      nameMarkBuddyExpress("happy", 2400);
      nameMarkSay(buddy, next.text, Math.min(12000, 2500 + 60 * next.text.length) + (next.act ? 8000 : 0));
      const bubble = buddy.querySelector(".nm-say");
      //: An act is the bubble's tap; without one, its source is (open the first note it names).
      const source = (next.sources || []).find((id) => Number.isInteger(id));
      if (next.act) nameMarkRemarkAct(bubble, next.act);
      else if (source && bubble) {
        bubble.classList.add("nm-say-source");
        bubble.title = "Open the note this is from";
        bubble.addEventListener("click", (event) => {
          event.stopPropagation();
          bubble.remove();
          switchTab("notes").then(() => flashEntry(source));
        });
      }
    });
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { nameMarkBuddyRemark });
})();
