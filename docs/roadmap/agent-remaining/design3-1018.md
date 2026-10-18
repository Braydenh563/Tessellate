# design3, 2026-10-18 (INBOX 1300, bugs-1018b.md design rows)

Items: C06 (stats panel, link cards and reader, calculator), C07, C08, C28, C14, in that order. Port 8795, data /tmp/mm-design3.

- done: C06 stats panel (`reply_panel` routes_chat.py, `renderReplyPanel` reply-kit.js, lazy `replyKit`)
- done: C06 web result cards and the page reader (ask-compose.js `renderWebSources`, `readWebPage`; `read_url` folds in chat and the popup agent)
- done: C06 calculator (`openCalculator` reply-kit.js, `/utilities/work` and `/utilities/units` routes_utilities.py, palette row, /calc alone, Guide topic `calculator`)
- moved for the boot budget (588,400 cap, 66 bytes left after C06): `renderRelatedElsewhere` to reply-kit.js; Ask, popup and Chat draw panels through one `drawAnswerPanels` -> `replyDrawAll`
- done: C06 cb3e871
- done: C07 note previews (`replyFinish`, `replyNotePreviews` reply-kit.js; `finishReply` capture-ask.js, called by Chat, Ask, popup, Guide); `renderToolsUnsupportedNotice` moved to reply-kit.js for the boot budget
- next: C08 long-block fold, `replyFoldLong` in reply-kit.js (draft in the session scratchpad d3/fold-part.js), called first in `replyFinish`
