# Film Source Scraper

Auto-collect reviews, interviews, criticism, news, Reddit threads, and academic
papers for a film — and file them straight into a Zotero collection, with a
Wayback Machine fallback that gets past soft paywalls.

Right-click a Zotero collection named after a film → **Scrape film sources** →
walk away. Everything relevant lands in that collection, tagged by source type
and capture method.

> Built for film-studies research libraries where every film needs its own dossier
> of press, criticism, and scholarship. Add a collection, click once, move on.

---

## What it does

For each film, it searches six source types and captures each hit:

| Source type | What it finds |
|-------------|---------------|
| `review`    | film reviews from press and blogs |
| `criticism` | analysis, essays, scholarly commentary |
| `interview` | director/cast interviews |
| `news`      | festival coverage, promotion, announcements |
| `reddit`    | discussion threads |
| `paper`     | academic PDFs (`filetype:pdf`) |

- **Articles / Reddit / interviews** → full-page screenshot + saved as a Zotero
  snapshot in the collection.
- **PDFs** → downloaded and attached as a Zotero item.
- **Paywalled pages** → routed through a decision agent that checks the
  Wayback Machine, grabs the fullest clean archived copy, and tags the result
  so you can tell live vs. archived vs. still-walled captures apart.

Every item is tagged with the film name and a `capture:*` status
(`live`, `wayback`, `wayback-fresh`, `paywalled`).

---

## How it's built

Two parts talk over `localhost`. The **plugin** is a thin button; the **engine**
holds all the power.

```
   Zotero plugin (.xpi)              Capture Engine (native app)
   right-click a collection  ──HTTP──▶  FastAPI on 127.0.0.1:23200
   progress window           ◀─poll──   Playwright + Wayback agent
   (no scraping logic)                  (bundled Chromium, no pip)
```

Nothing about the pipeline is weakened to fit inside Zotero, and nothing about
setup requires a terminal. Same shape as Ollama + its GUIs, or Docker Desktop +
its CLI. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full rationale.

---

## Install (non-coders — one-time, no terminal)

1. **Install the Capture Engine.** Download the installer for your OS from the
   [Releases page](../../releases) and run it (drag to Applications on macOS,
   run the `.exe` on Windows, or the `.AppImage` on Linux).
2. **Launch the engine and add your search key.** On first run it opens a
   `config.json` file — paste a free [Brave Search API key](https://brave.com/search/api)
   between the quotes, save, and relaunch. (It works without a key using a
   slower fallback, but a key is strongly recommended — the free tier covers
   dozens of full runs.)
3. **Install the Zotero plugin.** In Zotero: **Tools → Add-ons → gear icon →
   Install Add-on From File** → pick `film-source-scraper.xpi` from Releases.

That's it. Keep the engine running in the background whenever you scrape.

## Use

1. Make a Zotero collection named exactly after the film (e.g. `Sister Midnight`).
2. Right-click it → **Scrape film sources for this collection**.
3. Watch the progress window. Results file into the collection as they capture.

The collection name *is* the search — no config to edit per film.

---

## Run from source (developers)

You don't need the packaged app to use this; the pipeline runs standalone.

```bash
git clone https://github.com/prithuhalder1997-arch/film-source-scraper
cd film-source-scraper
pip install -r engine/requirements.txt
python -m playwright install chromium

export BRAVE_API_KEY=...          # from brave.com/search/api
```

**As a CLI** (edit your film list in `films.json`):

```bash
./run.sh                          # all films
./run.sh "Sister Midnight"        # one film
python scrape.py --dry-run        # search only, saves nothing
```

**As the engine** (then drive it from the Zotero plugin):

```bash
python engine/server.py           # serves on 127.0.0.1:23200
```

Zotero must be open in all cases (the pipeline talks to its local connector on
`127.0.0.1:23119`).

---

## Building the distributables

See [`packaging/BUILD.md`](packaging/BUILD.md). In short: `pyinstaller
packaging/engine.spec` bundles the engine + Chromium into a double-click app
per OS (PyInstaller doesn't cross-compile — build on each target OS), and
`zip -r film-source-scraper.xpi manifest.json bootstrap.js content/` builds the
plugin. Attach all of them to a GitHub Release.

---

## Honest limits

- **Hard academic paywalls** (Taylor & Francis, Sage, EUP, etc.) can't be
  bypassed — the PDF was never served to any crawler, so Wayback only has the
  abstract. Grab those via your institutional login through Zotero's normal
  browser connector. They'll show up tagged `capture:paywalled`.
- **Cloudflare-hard sites** block headless browsers; those also land as
  `capture:paywalled` (best-effort shot kept locally regardless).
- **"Save everything" is noisy** by design — expect some junk hits to prune.
- **Reddit rate-limits** aggressively; keep hits-per-source low (default 3).
- Screenshots are always kept in `downloads/<film>/` even if a Zotero save
  fails, so nothing is lost.

---

## How it works under the hood

- **Discovery** — Brave Search API (DuckDuckGo HTML as a no-key fallback).
- **Capture** — headless Chromium via Playwright; auto-scrolls for lazy content,
  full-page PNG.
- **Paywall agent** (`paywall_agent.py`) — deterministic decision loop: detect
  paywall → query Wayback CDX → optionally trigger a fresh archive → re-check →
  keep the version with the most real article text. No LLM, no API key.
- **Filing** — items save into the collection via the Zotero connector API,
  tagged by film and capture status.

---

## Contributing

Issues and PRs welcome. Good first contributions: additional source-type query
templates, publisher-specific paywall selectors in `paywall_agent.py`, and
installer packaging for OSes you can build on.

## License

MIT — see [`LICENSE`](LICENSE). *(Add the file; see follow-up steps.)*

## Acknowledgements

Wayback fallback uses the [Internet Archive](https://archive.org) CDX and Save
APIs. Search via the [Brave Search API](https://brave.com/search/api). Built to
sit alongside [Zotero](https://www.zotero.org).
