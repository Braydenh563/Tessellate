# Left by the chattime agent (Brief 103, INBOX 868; INBOX 871)

- Messages saved before stamps existed show no time (the owner: "a time stamp on each chat message"): showing the chat's own time on every old line would be wrong, so they stay bare; a one-off backfill from `created_at` is not possible, the messages carry no times. chat-time.js `stampChatTimes`.
- The chat list row still reads "3h ago" (relativeTime of the last message), not a clock time: sheets-selects.js `loadConversationList`; the exact time is not in its tooltip because the boot scripts sit at their gzip cap (TOTAL_CAP 320,600).
- Not driven with a real model: a live streamed answer getting its time when the meta row lands (driven with `addAssistantBubble` plus `messageMetaLine` in scratchpad/ui-sweeps/chattime.js, not `/chat/stream`).
- Library's chat rows and the Shelved list still show their own `updated_at`, not `last_at`.
