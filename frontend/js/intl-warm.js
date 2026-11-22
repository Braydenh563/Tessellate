// Tessellate: the page's first Intl call, made off the main thread.
//
// The first `toLocaleTimeString` (or any Intl formatter) in a renderer sets up
// ICU's locale, calendar and time-zone data: 73 to 281 ms at 4x CPU on the
// main thread, whichever formatter comes first. Those caches belong to the
// process, so a worker that makes the same calls first leaves the page's own
// first call at 0.2 to 1.5 ms in the app (measured in a bare page, 6 runs each, 2026-11-21).
// shell-reminders.js starts this and paints its clocks when it answers.
//: The call the page's first formatter makes, `toLocaleString()`, as measured.
//: Nothing here is shown, so neither the one date shape (whenText) nor the 12
//: or 24 hour setting applies.
const now = new Date();
now.toLocaleString();
now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
new Intl.NumberFormat().format(1234.5);
self.postMessage(1);
close();
