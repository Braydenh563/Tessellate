// Loaded on first use (app.js `LAZY_MODULES.ndjson`): every caller runs
// `await ensureModule("ndjson")` before `api.ndjson`, because a streamed
// answer is never on the boot path (tests/test_static_compression.py).

//: **The one NDJSON stream reader** (L170): Ask, Chat, the Guide, the digest and the writing desk each
//: kept their own `getReader` loop, five copies of the same split on newlines. `onEvent` gets each
//: parsed line; a line that does not parse is logged and skipped, so one bad frame cannot lose an answer
//: that is half written. `idleMs` rejects with `idleMessage` when nothing at all arrives for that long
//: (a stalled backend has nothing else to catch it) and cancels the fetch.
api.ndjson = async (response, onEvent, { idleMs = 0, idleMessage = "The stream stopped responding.", label = "Stream" } = {}) => {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffered = "";
  const take = (raw) => {
    if (!raw.trim()) return;
    let event;
    try {
      event = JSON.parse(raw);
    } catch {
      recordBrowserLog("WARN", [`[${label}] Unparseable line: ${raw.slice(0, 80)}`]);
      return;
    }
    return onEvent(event);
  };
  const next = () => {
    if (!idleMs) return reader.read();
    let timer;
    const idle = new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("stream_idle_timeout")), idleMs); });
    return Promise.race([reader.read(), idle]).catch((err) => {
      if (err.message !== "stream_idle_timeout") throw err;
      reader.cancel().catch(() => {});
      throw new Error(idleMessage);
    }).finally(() => clearTimeout(timer));
  };
  for (;;) {
    const { done, value } = await next();
    if (done) break;
    buffered += decoder.decode(value, { stream: true });
    const lines = buffered.split("\n");
    buffered = lines.pop();
    for (const line of lines) take(line);
  }
  take(buffered);
};
