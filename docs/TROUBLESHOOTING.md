# Troubleshooting

- [The app will not start](#the-app-will-not-start)
- [The port is already in use](#the-port-is-already-in-use)
- [A phone or another computer cannot open it, or warns about the certificate](#a-phone-or-another-computer-cannot-open-it-or-warns-about-the-certificate)
- [The first launch is slow or downloads something](#the-first-launch-is-slow-or-downloads-something)
- [Upgraded from a version with PyTorch: the old files](#upgraded-from-a-version-with-pytorch-the-old-files)
- [Linux: the packaged app has no window](#linux-the-packaged-app-has-no-window)
- [The AI status says the AI is off](#the-ai-status-says-the-ai-is-off)
- [Web search returns nothing, or says DuckDuckGo is rate-limiting](#web-search-returns-nothing-or-says-duckduckgo-is-rate-limiting)
- [SearXNG will not start, or starts and never answers](#searxng-will-not-start-or-starts-and-never-answers)
- [I forgot my password](#i-forgot-my-password)
- [Something looks wrong and I want to see what happened](#something-looks-wrong-and-i-want-to-see-what-happened)

## The app will not start

**Started from a source checkout?** Run the launcher with `--doctor`
(`./start.sh --doctor` or `start.bat --doctor`). It prints one row per thing that
can stop a launch, with a tick or a cross and a one-line fix for each cross:
Python's version, whether the virtual environment can import what the server
needs, free disk, whether the port is free, your model provider, and the last
error from the previous run's log. If the environment looks broken, `--reinstall`
rebuilds it from scratch. `--logs` opens the folder of launcher logs, which hold
the last ten runs.

**Installed with the Windows installer?** Use the **Repair Tessellate**
shortcut in the Start Menu. It clears the window's cached profile and starts the
app again, and never touches your notes or settings. A startup error is written
to `desktop-stdio.log` in the `logs` folder inside your data folder
(`%APPDATA%\Tessellate`, or `%APPDATA%\MemoryMap AI` before the rename).

**Windows blocked the installer?** The blue "Windows protected your PC" screen is
expected, because the build is not code-signed yet. Click **More info**, then
**Run anyway**.

## The port is already in use

Tessellate serves on port 8000. If something else has it, `--doctor` says so, and
`--port N` starts the app on another one (`./start.sh --port 8010`). For the
packaged apps and `python -m tessellate`, set `TESSELLATE_PORT` instead. An
already-running Tessellate on that port is not an error: open it, and use Settings,
Background tasks, Quit Tessellate if you want it closed.

## A phone or another computer cannot open it, or warns about the certificate

Other devices are off until you allow them: **Settings, Account & security,
Other devices, Allow other devices on this network**. Turning it on asks for your
current password and takes effect at the next start.

The address to open on the other device is `https://` followed by this
computer's network address and port 8443 (`TESSELLATE_LAN_PORT` changes it). This
computer keeps plain `http://localhost:8000`. The certificate is made on this
computer and signed by itself, so a phone or browser warns the first time:
compare the SHA-256 fingerprint in the warning's certificate details with the one
Settings shows, and continue only if they match. Regenerate certificate, in the
same place, makes a new one without a restart, and the other device then warns
again. If nothing answers, check that this computer's firewall allows port 8443.

## The first launch is slow or downloads something

Search and filing by meaning use a built-in model that needs the
`fastembed` package. The first time it is needed, and it is not
installed, the app asks once (Download or No thanks). After a yes it installs it by
itself, and Settings, Search and index, Download search by meaning turns it on
later: a one-time download of about 130 MB that needs the internet. Settings, Search and index, Search engine says when it is
running, and Settings, Background tasks lists the job. Search falls back to
keywords until it finishes, and nothing else waits for it.

To avoid the download, pick an Ollama embedding model (`nomic-embed-text`) in the
same place, or set `TESSELLATE_NO_AUTO_INSTALL` to stop the download whatever the answer.

## Upgraded from a version with PyTorch: the old files

Search by meaning ran on `sentence-transformers` and PyTorch until October
2026; it runs on `fastembed` (ONNX Runtime) now. The old model files do not
work with it, so after an upgrade search by meaning needs one download (about
130 MB, replacing the old engine) and Tessellate asks first: the notice and
the welcome card say the engine moved, and search uses keywords until you
answer yes. Nothing is downloaded without that yes. Notes embedded with
BGE Small or Multilingual E5 Small keep their search data and none is
embedded again; notes embedded with any other model are read again in the
background once the download lands.

The old engine's files stay where they were, and Tessellate no longer uses
them. Once the new model is ready, Settings, Search and index, Old search files
lists the old model folders with their sizes, and Remove deletes one; in the
packaged app it also removes PyTorch and sentence-transformers from the
extras folder. From a source install, remove the packages by hand:

```
pip uninstall -y sentence-transformers torch
```

from the project folder's virtual environment frees about 1.4 GB. The old
model folder (`models--BAAI--bge-small-en-v1.5` in the Hugging Face cache,
about 130 MB) is what Remove deletes; the new one is
`models--Qdrant--bge-small-en-v1.5-onnx-Q`.

## Linux: the packaged app has no window

The window needs GTK and WebKit as system packages. On Debian and Ubuntu:

```
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1
```

Check that you unpacked the `.tar.gz` and not the `.zip`: a zip may drop the
executable bit, which leaves a launcher that will not start and says nothing.

## The AI status says the AI is off

The AI status sits in the status bar at the foot of the window, and "AI off" is
a grey sparkle with a slash through it, not amber or red; hover or focus it for
"Notebook ready · AI off". It is a supported state: the app is built to degrade. Capture and
full-text search work exactly as normal, and only auto-filing and chat answers
need a model. Red is reserved for a model that failed to load or a server that
cannot be reached, which is rarer, because it needs the server to be reachable but
failing rather than simply not running.

Start Ollama, or your OpenAI-compatible server, and check Settings, Models,
Model backend. If you use LM Studio, llama.cpp or vLLM, the address must end in
`/v1` and match the server's port: [MODELS.md](MODELS.md) lists them.

## Web search returns nothing, or says DuckDuckGo is rate-limiting

Web search must be on first: **Settings, Web search**. Scraping DuckDuckGo gets
rate-limited, and the app says so rather than showing an empty panel. Waiting a
few minutes usually clears it.

The real fix is your own SearXNG instance: **Settings, Web search, Start
SearXNG**. Tessellate installs it (in a container if you have Docker, otherwise
in a virtual environment of its own), configures the JSON API, and points search
at it.

## SearXNG will not start, or starts and never answers

Everything you need is in **Settings, Web search**:

- **The port line** says whether port 8888 is free, held by a working SearXNG
  (fine, Tessellate will use it), or held by something else, which is the only
  case you have to fix. `TESSELLATE_SEARXNG_PORT` picks another port.
- **What SearXNG reported** is a fold with the instance's own output: the actual
  traceback, not a guess. It is kept in `searxng/searxng.log` in your data folder
  too.
- **Reinstall** deletes the downloaded copy and its virtual environment and
  builds a fresh one. This is the fix when an install was interrupted, or the
  Python it was built against has since been upgraded: it looks installed and
  dies on start. Your `settings.yml` is kept, because it holds the instance's
  secret key and any edits you made, and it is not what breaks.

## I forgot my password

Press **Forgot your password?** on the lock screen, on the computer the notebook
lives on. With your recovery key (shown when you set up, or made in Settings,
Account & security) you choose a new password and keep your private notes.
Without it, "I don't have it" asks for a six-digit code that Tessellate prints in the terminal it runs in (ten minutes, one use), then resets the password, as
`python -m tessellate --reset-password` does in a terminal: ordinary notes,
documents, boards and settings are kept; **private notes stay sealed**, because
only the password or the recovery key opens them. The reset also turns off
"Allow other devices on this network". More in
[PRIVACY.md](PRIVACY.md#if-you-forget-the-password).

## Something looks wrong and I want to see what happened

**Settings, Logs** is a live view of what the app is doing, with no terminal to
hunt for. It streams as things happen, follows the newest records (and pauses the
moment you scroll up to read one), filters by text, level and which log, and
folds tracebacks open under the record they belong to. Server and browser logs
sit in one time-ordered list, so an error in the page and the request behind it
are side by side. The live view is held in memory and not written to disk, and it
says so when the buffer has had to drop older records rather than leaving a
silent gap. The launcher's own logs are the exception: they are files, described
under [The app will not start](#the-app-will-not-start).

**Got an error you want to send someone?** Every record has its own copy button
that takes the traceback with it, and an opened traceback has a **Copy
traceback** button too, so one error is one click. **Copy all** copies what is on
screen and relabels itself ("Copy 12 shown") whenever a filter is hiding
something.

**Reporting a bug?** The **Support bundle** button on the same screen saves a zip
with the log, your settings, and app and model status, which is what a bug report
needs. Nothing is sent anywhere: the file goes to your disk and sharing it is your
choice. Free-text settings are listed by name and length only (your display name
appears as `str, 31 chars`), a user name and password typed into the model server
address are left out, and no note, document, chat or reminder content is
included. A README inside the zip says exactly what it holds.

**Odd behaviour after an update?** Settings, Import & export, App cache, Clear app
cache reloads the app with fresh files. Nothing in your notebook is touched.
