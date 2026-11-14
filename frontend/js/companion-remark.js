// companion-remark.js: what the companion says about the notebook, now and
// then (INBOX 743: "better popup messages and more varied"). The composer's
// remarks (`composer_voice.remarks`, no model) reach the page through
// `GET /insights/remarks`: a reminder due, a note from this day in an earlier
// year, an open item, a quiet day. Lazy: the boot carries only a stand-in
// (lazy-entries.js) that fetches this file when the mood tick first asks.
//
// Never twice: each remark has a `key` (a hash of its words) and the keys it
// has said are kept on this computer, so a new line is always new. Said in
// the speech bubble the poke lines use (`nameMarkSay`), held for as long as it
// takes to read, and only while it could act at all (`nameMarkBuddyReact`
// already refused under reduced motion, a hidden page, a menu, a carry).
(() => {
  const NMB_REMARK_SEEN = "nm-buddy-remarks-seen";

  async function nameMarkBuddyRemark() {
    let body;
    try {
      body = await apiJson("/insights/remarks", { silent: true });
    } catch (e) {
      return;
    }
    //: Quiet while the person types (CHAT_PLAN composer row 1): the same four
    //: seconds the rest of the companion waits (`nameMarkBuddyCalmAllows`), and
    //: nothing is marked said, so the next tick still has the line.
    if (Date.now() - (nmb.keyAt || 0) < 4000) return;
    const seen = prefs.json(NMB_REMARK_SEEN, []);
    const next = (body.remarks || []).find((r) => r.text && !seen.includes(r.key));
    const buddy = document.getElementById("nm-buddy");
    //: It may have been picked up, hidden or put to sleep while the call ran.
    if (!next || !buddy?.isConnected || nameMarkBuddyStill() || document.hidden) return;
    if (buddy.classList.contains("nm-buddy-dragging") || buddy.classList.contains("nmb-sleep")) return;
    prefs.setJSON(NMB_REMARK_SEEN, [...seen, next.key].slice(-80));
    //: After a frame has drawn the page (INBOX 1726: 213ms, 210 of it forced layout).
    nmb.afterClean(() => {
      if (!buddy.isConnected || nameMarkBuddyStill() || document.hidden) return;
      nameMarkBuddyExpress("happy", 2400);
      nameMarkSay(buddy, next.text, Math.min(12000, 2500 + 60 * next.text.length));
      //: Its source one tap away: the bubble opens the first note it names.
      const source = (next.sources || []).find((id) => Number.isInteger(id));
      const bubble = buddy.querySelector(".nm-say");
      if (source && bubble) {
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
