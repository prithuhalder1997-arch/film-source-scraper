# Building the distributables (maintainer guide)

You ship **two** things. End users install both once; after that it's one click.

```
  ┌─ CaptureEngine installer  (.dmg on mac / .exe on win / .AppImage on linux)
  └─ film-source-scraper.xpi  (the Zotero plugin)
```

## 1. Build the Capture Engine app

On EACH OS you want to support (build on a Mac to get a .dmg, on Windows for
.exe — PyInstaller doesn't cross-compile):

```bash
pip install -r engine/requirements.txt pyinstaller
python -m playwright install chromium        # so the spec can bundle it
pyinstaller packaging/engine.spec
```

Output: `dist/CaptureEngine/` — a self-contained app folder with Python,
Playwright, and Chromium all inside. No end-user pip or terminal needed.

### Wrap it in a friendly installer
- **macOS**: `create-dmg dist/CaptureEngine.dmg dist/CaptureEngine/` → users
  drag to Applications. (Codesign + notarize to avoid Gatekeeper warnings.)
- **Windows**: point Inno Setup or NSIS at `dist/CaptureEngine/`.
- **Linux**: package the folder as an `.AppImage`.

The app, when launched, prints a "keep me open" line and serves on
`127.0.0.1:23200`. On first run it writes a `config.json` where the user pastes
their free Brave key (one plain-text file, no terminal).

## 2. Build the Zotero plugin

```bash
cd zotero-plugin
zip -r ../film-source-scraper.xpi manifest.json bootstrap.js content/
```

That `.xpi` is the whole plugin. Users install via Zotero →
Tools → Add-ons → gear → Install Add-on From File.

## 3. Publish (open source)

- Push the repo to GitHub.
- Attach `film-source-scraper.xpi` and the three OS installers to a GitHub
  **Release** (the plugin's "Download engine" button points at /releases).
- Add an `updates.json` so Zotero auto-updates the plugin (Zotero plugin docs
  describe the format; the manifest already references it).
- Optionally submit to the Zotero community plugins list.

## What the end user (non-coder) actually does — total

1. Download + install the Capture Engine (drag to Applications / run .exe). Once.
2. Launch it; paste a free Brave key into the config file it opens. Once.
3. Install the .xpi in Zotero. Once.
4. Forever after: right-click a collection named after a film →
   **"Scrape film sources for this collection"** → watch the progress window.

No Python. No pip. No command line. Full pipeline power intact, because the
power lives in the engine and only the *button* lives in Zotero.
