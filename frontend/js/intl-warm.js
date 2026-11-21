// Tessellate: the page's first Intl call, made off the main thread.
//
// The first `toLocaleTimeString` (or any Intl formatter) in a renderer sets up
// ICU's locale, calendar and time-zone data: 73 to 281 ms at 4x CPU on the
// main thread, whichever formatter comes first. Those caches belong to the
// process, so a worker that makes the same calls first leaves the page's own
// first call at 0.2 to 1.5 ms in the app (measured in a bare page, 6 runs each, 2026-11-21).
// shell-reminders.js starts this and paints its clocks when it answers.
//: `toLocaleString` covers the time patterns too; no clock reads this, so the 12 or 24 hour setting does not apply.
new Date().toLocaleString();
new Date().toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
new Intl.NumberFormat().format(1234.5);
self.postMessage(1);
close();
