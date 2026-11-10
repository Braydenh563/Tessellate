// origin-bridge.js: the page of its own behind origin-bridge.html. The desktop
// window moved from http://127.0.0.1:PORT to http://localhost:PORT (Windows
// Hello refuses an IP address as an RP id) and localStorage belongs to one
// origin, so the saved settings cross once, through the server
// (api/routes_origin_handoff.py: this computer only, single use, no token).
// On 127.0.0.1 (`?to=localhost`) it posts every key and moves on; on the new
// origin it takes them once, unless its own storage already holds the marker.
(() => {
  const MARK = "origin-moved";
  const target = new URLSearchParams(location.search).get("to") || "";
  const post = (path, body) =>
    fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  const go = (url) => location.replace(url);

  async function leave() {
    const items = {};
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      items[key] = localStorage.getItem(key);
    }
    try {
      await post("/origin-handoff/put", { items });
    } catch {
      // the new origin starts with defaults; nothing else is lost
    }
    go(`${location.protocol}//${target}:${location.port}/origin-bridge.html`);
  }

  async function arrive() {
    if (!localStorage.getItem(MARK)) {
      try {
        const { items } = await (await post("/origin-handoff/take")).json();
        for (const [key, value] of Object.entries(items || {})) {
          if (localStorage.getItem(key) === null) localStorage.setItem(key, value);
        }
      } catch {
        // keep going: the marker below stops a retry loop
      }
      localStorage.setItem(MARK, "1");
    }
    go("/");
  }

  if (/^(localhost|[a-z0-9-]{1,63}\.localhost)$/.test(target) && location.hostname !== target) leave();
  else arrive();
})();
