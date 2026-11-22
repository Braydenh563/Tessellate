// L-world-class-891: a folder import of thousands of files froze the page for
// seconds while the browser built the multipart body inside `fetch` (CDP:
// 3.4 s of fetch self time at 5,000 files). File handles cross to a worker
// by reference, so the body is built and sent here, off the page's thread.
// The page's `api()` still owns headers, errors and the lock screen: this
// sends what it is given and hands back the status, headers and text.
// Files arrive staged in chunks (one clone of 5,000 Files is 511 ms of page
// thread) and are kept for both of an import's posts, the dry run and the run.
let staged = [];
self.onmessage = async ({ data }) => {
  if (data.stage) {
    if (data.first) staged = [];
    staged.push(...data.stage);
    return;
  }
  const { id, path, headers, fields } = data;
  try {
    //: The page set no body, so `api()` added a JSON type; FormData sets its own.
    delete headers["Content-Type"];
    const form = new FormData();
    for (const [file, name] of staged) form.append("files", file, name);
    for (const [key, value] of fields || []) form.append(key, value);
    const response = await fetch(path, { method: "POST", body: form, headers });
    self.postMessage({ id, status: response.status, statusText: response.statusText, headers: [...response.headers], text: await response.text() });
  } catch (error) {
    self.postMessage({ id, failed: error?.message || "Failed to fetch" });
  }
};
