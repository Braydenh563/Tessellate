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
const NMB_REMARK_SEEN = "nm-buddy-remarks-seen";

function nameMarkBuddyRemarkSeen() {
  try {
    const kept = JSON.parse(localStorage.getItem(NMB_REMARK_SEEN) || "[]");
    return Array.isArray(kept) ? kept : [];
  } catch (e) {
    return [];
  }
}

async function nameMarkBuddyRemark() {
  let body;
  try {
    body = await apiJson("/insights/remarks", { silent: true });
  } catch (e) {
    return;
  }
  const seen = nameMarkBuddyRemarkSeen();
  const next = (body.remarks || []).find((r) => r.text && !seen.includes(r.key));
  const buddy = document.getElementById("nm-buddy");
  //: It may have been picked up, hidden or put to sleep while the call ran.
  if (!next || !buddy?.isConnected || nameMarkBuddyStill() || document.hidden) return;
  if (buddy.classList.contains("nm-buddy-dragging") || buddy.classList.contains("nmb-sleep")) return;
  try {
    localStorage.setItem(NMB_REMARK_SEEN, JSON.stringify([...seen, next.key].slice(-80)));
  } catch (e) {
    /* kept or not, it was said */
  }
  nameMarkBuddyExpress("happy", 2400);
  nameMarkSay(buddy, next.text, Math.min(12000, 2500 + 60 * next.text.length));
}
