# Privacy and security

The app is built around one rule: **nothing leaves your machine unless you
ask it to.** The server listens on this computer only, every data route sits
behind the unlock, and no asset is ever loaded from a CDN.

This page says what the app does and why. To report a vulnerability, see
[SECURITY.md](../SECURITY.md).

- [Is the AI itself local?](#is-the-ai-itself-local)
- [What touches the network](#what-touches-the-network)
- [Proof, from the app's own record](#proof-from-the-apps-own-record)
- [Web search](#web-search)
- [Private notes](#private-notes)
- [Other devices on your network](#other-devices-on-your-network)
- [Signing in and sessions](#signing-in-and-sessions)
- [Your browser is treated as untrusted too](#your-browser-is-treated-as-untrusted-too)
- [Backups](#backups)
- [If you forget the password](#if-you-forget-the-password)

## Is the AI itself local?

Yes, and it is enforced, not just intended. Every chat and agent request goes
to a model server on your own computer or network, and **Settings, Models,
Keep Atlas on this machine** is on by default: an address that is not on this
computer or your own network is refused, not warned about. The check runs when
you set the address and again when the app builds its client at startup, so a
hand-edited `preferences.json` or a restored backup cannot quietly route your
notes somewhere else. Turning the lock off is a deliberate click, for people
who want a hosted API.

The provider is an address you control. It defaults to Ollama on this machine,
and the OpenAI-compatible option defaults to `http://localhost:1234/v1`. Point
either at a remote service and your prompts, and the notes used to answer them,
go to that service. The app will not do it on its own. Ollama's own hosted
service (`ollama.com`) is not local, and the lock refuses it like any other
remote address.

## What touches the network

"Local" has to be precise, because it is the whole promise.
Five things do touch the network, each started by you or a one-off on first
use, and none of them is your notes:

| What | When | What goes out |
| --- | --- | --- |
| Model downloads | You press Download in Settings, Models | The model name, to Ollama's registry, or to Hugging Face for an `hf.co` name. Ollama does the fetching |
| The search model | Only after a yes: the app asks once, the first time search by meaning is needed (Download or No thanks), and Settings, Search and index holds the switch | The `sentence-transformers` package from PyPI and `BAAI/bge-small-en-v1.5` from Hugging Face. Until you say yes, search uses keywords and nothing is fetched. `TESSELLATE_NO_AUTO_INSTALL` stops it for good, and an Ollama embedding model avoids it |
| Optional packages and SearXNG | You press Install in Settings, Packages, or Start SearXNG in Settings, Web search | pip downloads; Run Python files (Pyodide) from GitHub and Tool calling without Ollama (needle) from Hugging Face, both checked against a sha256; SearXNG's source from GitHub |
| Web search | Only while Settings, Web search is on, which also covers the reader view and page clipping | Your search words, or the address of the page you open. Never your notes |
| The update check | Only if you turn on Settings, About, Updates, Check GitHub for a newer version, or press Check for updates | A request to GitHub's releases API, with no data about you. The first start asks once whether to check automatically (in the terminal for `start.sh`, in the app otherwise), and until you answer nothing about updating touches the network, a launcher copy's pull included |

Your notes, your questions and everything the AI writes about them stay on your
machine in every case. The AI provider is a separate matter, covered above.

## Proof, from the app's own record

**Settings, Privacy** shows every connection this app has made, as it happened:
the destinations since launch and all time, where your model server points, who
can open the app, and which switches let the app connect past this computer.
The record comes from the interpreter itself, which reports every connection
and name lookup the app's process makes, so no code path can skip it. Your
model server and a SearXNG instance are separate programs with their own
connections, which this record cannot see. Their addresses are shown instead.

## Web search

Off until you turn it on in **Settings, Web search**. When it is on:

- only your search words leave the computer, never your notes;
- requests send an ordinary browser User-Agent rather than one naming this app,
  keep no cookies between searches, send no `Referer`, and set DNT and
  Sec-GPC;
- queries go by POST, so they stay out of request lines and access logs;
- tracking parameters (`utm_*`, `fbclid`, `gclid` and the like) are stripped
  from result URLs before you see them;
- **your own [SearXNG](https://searxng.org) is the recommended engine.**
  Tessellate installs and runs it for you in one click, with no Docker and no
  account, and the query then never leaves your own network. The default,
  *Automatic*, uses it whenever it is running and falls back to DuckDuckGo
  until you have one, so search works either way;
- the results panel says which engine actually answered each search, so the
  choice you made in Settings is visible at the moment it applies.

**Opening a page** (the reader view, page clipping and the agent's `read_url`
tool) is address-checked on every redirect hop, then pinned to the address that
passed, so a page that answers "302 to 127.0.0.1" cannot turn "open this link"
into a probe of your own services. Only text comes back: scripts, styles and
page chrome are stripped on the server, so nothing from a third-party page can
run in the app.

The **web clipper** bookmark is different: it sends the page as your browser
already shows it, so it fetches nothing and works with web search off.

**Agent mode and outside text.** Once a turn has read text from outside (a web
page, a clipped or imported note, an imported document), every change to the
notebook and every web request waits for your confirmation, and the card says
what it will do. A page cannot steer the agent into rewriting your notes
unasked.

## Private notes

Private notes are encrypted at rest with a key wrapped by your password, and
kept out of search, the graph and every AI tool: the model cannot reach around
the front door.

The key is derived with **scrypt** (n=2^15), a deliberately slow, memory-hard
function, then used with AES-GCM. Slow is not impossible. The wait between
wrong passwords only guards the running app, and a copy of the database file or
of a backup can be guessed offline as fast as a computer can run scrypt. A
four-digit PIN falls to that in minutes; a long passphrase does not. So a new
password needs at least eight characters, and one that is still easy to guess
(a common word, a run like 12345678) is accepted with a warning that says why.
A password set before this keeps working. If you keep private notes, use a
passphrase.

Making a note private also:

- replaces any saved Ask answer or chat reply that cited it, or repeats a run of
  its words, with a line saying its words were removed (your question stays);
- merges the search index and clears the note's old entries from the database
  file and its write-ahead log;
- means every backup is a cleaned copy, so none of its words survive in the
  file.

## Other devices on your network

Off by default. With it off, the app listens on `127.0.0.1` and nothing on your
network can reach it. **Settings, Account & security, Other devices, Allow
other devices on this network** lets a phone or a second computer open the
notebook. Then:

- it always asks for your password, whatever this computer is set to, and
  private notes still ask for it too;
- turning it on asks for your current password, and takes effect at the next
  start;
- the network side is **HTTPS on its own port**, 8443 beside the usual 8000
  (`TESSELLATE_LAN_PORT` overrides it). This computer keeps plain http on its own
  port;
- the certificate is made on this computer the first time the switch is on, with
  no network involved, and kept in your data folder, readable by you only. It is
  self-signed, so a device warns the first time it opens the address. Compare
  the SHA-256 fingerprint in its certificate details with the one Settings
  shows, and continue only if they match. Regenerate certificate makes a new
  one;
- a request that names a domain other than this computer is refused, so a web
  page that re-points its own name at your machine (DNS rebinding) gets
  nothing.

The app never listens beyond this computer while no password is set, and a
request from the network before a password exists is refused.

## Signing in and sessions

Tessellate is single-user by design: one notebook and one password, all on this
machine. To keep separate notebooks, use a different data folder
(`TESSELLATE_DATA_DIR`), or Spaces inside one notebook, rather than a second
account.

- **The password is optional on a computer only you use.** Settings, Account &
  security, Signing in turns off "Ask for a password when the app opens". The
  app then opens straight in on this computer. Another device still needs the
  password, and so do private notes.
- **Sessions expire.** After 12 hours unused by default, which Auto-lock when
  idle changes anywhere from 5 minutes to 12 hours, and after 7 days however
  busy. A session is a token held in memory only, so restarting the app locks it
  again, and expiring forgets the private-note key, not just the token.
- **Wrong passwords earn a growing wait**, everywhere a password is checked
  (unlock, change password, re-encrypting private notes), so a short PIN cannot
  be guessed at speed through the app.
- **A password over 72 bytes works**, and one over 1,024 characters is refused.
  Changing your password ends every other session.
- **A PIN unlocks this computer only, and is never in the notebook.** Settings,
  Account & security, PIN for this computer sets one of 4 to 12 digits, behind
  the password. The vault key is wrapped under it (scrypt and AES-GCM) and kept
  by the operating system's protected store for your user: Windows DPAPI, the
  macOS Keychain, or the Linux Secret Service. Where none is available a PIN
  cannot be set up; it is never written to a file. A copied notebook or backup
  carries nothing a PIN opens. Only this computer's own keyboard may use it:
  phones and other devices need the password, and so do changing the password,
  the PIN and LAN access. Five wrong PINs delete it, and a password change, a
  re-encryption, a restore or a reset removes it.

## Your browser is treated as untrusted too

Listening on localhost keeps the network out. It does nothing about a page open
in another tab, which can ask your browser to send requests to
`http://localhost:8000` on your behalf. This is how local dev servers and
Ollama itself have been attacked. So:

- a request that states an origin other than Tessellate's own is **refused**,
  including before you have set a password, when nothing else stands between a
  stray page and your new notebook;
- a strict **Content-Security-Policy** on every response allows scripts and
  styles only from the app itself, with no inline code and **no remote host at
  all**, which the no-CDN rule makes possible;
- a request body is capped at 1 MB until you are signed in;
- an attachment is served as a download unless it is a picture or a PDF, and
  those are sandboxed, so an uploaded script can never run in the app;
- the SearXNG instance the app runs is published to `127.0.0.1` only;
- on Linux and macOS the notebook folder is readable by its owner only.

CodeQL runs static security analysis on every push to `main`, on every pull
request whatever its base, and weekly. The "whatever its base" matters: a branch
filter on the pull request matches its base, so a pull request opened against a
feature branch was once never scanned.

## Backups

The app takes a snapshot of your notebook once a day when it starts, and Back up
now takes one on request. Snapshots live in your data folder (`backups/`) and
never leave your computer, and restoring one first snapshots the current state,
so a restore can be undone. A restore signs every session out and asks for your
password again, so restored private notes open with the key that came with them.

Settings, Import & export can also write a **full backup**: the database, media
and attached files as one file. Type a password and it is sealed as a `.mmenc`
file (AES-GCM, with the same scrypt key derivation the private notes use). Leave
the password empty and it is a plain `.zip`. **Restore a full backup**, in the
same place, reads either kind, after a safety snapshot. A wrong password or a
file that is not a notebook changes nothing.

Every backup is as sensitive as the database itself, so keep it somewhere you
trust.

## If you forget the password

Press **Forgot your password?** on the lock screen. It works only on the computer
the notebook lives on: a phone or another computer on your network is told to do
it there, and another website's page cannot ask for it. It offers two paths.

**With your recovery key.** A recovery key is 160 random bits, shown once as
eight groups of four letters and digits, when you finish setting up (you can
skip it) or from Settings, Account & security (Make a recovery key, or Replace
it, which asks for your current password). Keep it away from this computer, in a
password manager or on paper. Download .txt is the browser's own download in a
tab; in the desktop app it opens a Save dialog that starts in Documents and
refuses the notebook's own folder, never the exports folder beside the notebook.
It works like a second password: it locks a second
copy of the key that encrypts private notes, with its own salt and the same
scrypt and AES-GCM. The app never stores the key itself, never logs it and never
gives it to the AI. Type it with a new password and private notes are kept; every
open session is signed out, the key you used stops working, and a new one is
shown once. Wrong keys earn the same growing waits as wrong passwords.
Re-encrypting private notes also replaces the recovery key, since the old one
locked the old encryption key.

**Without it.** The same reset as this command, which you can also run in a
terminal:

```
python -m tessellate --reset-password
```

Both ask you to confirm (type RESET), then clear the password so you can set a
new one. What happens to your notes:

- **Ordinary notes are not encrypted** by your password. Notes, documents,
  boards, files and settings are plain rows in SQLite and are kept.
- **Private notes are.** Their key is locked by the password and the recovery
  key, so without either nobody can decrypt them, this reset included. They
  stay sealed for good. A sealed full backup still opens with its own password.

The reset also turns off "Allow other devices on this network". No backdoor was
added, on purpose: the recovery key is yours, and the app keeps no copy.
