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
2. **Launch the engine and add a search key.** On first run it opens a
   `config.json` file. Paste a free **[Tavily](https://tavily.com)** API key
   between the quotes, save, and relaunch. Tavily is recommended because it
   needs **no credit card** and gives **1,000 free searches per month** — each
   film uses ~6 searches, so that's roughly 160 film-runs a month, and it
   resets monthly. (Other providers work too — see Search providers below. The
   engine also runs with no key at all, using a slower DuckDuckGo fallback that
   often returns few results.)
3. **Install the Zotero plugin.** In Zotero: **Tools → Add-ons → gear icon →
   Install Add-on From File** → pick `film-source-scraper.xpi` from Releases.

That's it. Keep the engine running in the background whenever you scrape.

## Use

1. Make a Zotero collection named exactly after the film (e.g. `Sister Midnight`).
2. Right-click it → **Scrape film sources for this collection**.
3. Watch the progress window. Results file into the collection as they capture.

The collection name *is* the search — no config to edit per film.

---

## Search providers & limits

The scraper needs a search provider to find sources. It tries whichever you've
configured, in priority order, and falls back to the next if one isn't set or
returns nothing:

| Provider | Credit card? | Free allowance | Set env var |
|----------|--------------|----------------|-------------|
| **Tavily** (recommended) | No | 1,000 searches/month | `TAVILY_API_KEY` |
| Serper | No | 2,500 one-time trial | `SERPER_API_KEY` |
| Brave | Yes (as of 2026) | $5/mo credit | `BRAVE_API_KEY` |
| DuckDuckGo | No key at all | unreliable, last resort | — |

**How much does a run cost?** One film = ~6 searches (one per source type:
review, criticism, interview, news, reddit, paper). On Tavily's free tier
(1,000/month) that's roughly **160 film-runs per month**, resetting monthly.
For a 12-film thesis library, a full sweep is ~72 searches — you can run the
whole set many times over within the free allowance.

Set whichever key you have and the scraper uses it automatically. You never put
the key in the code — it's read from the environment (`config.json` for the
packaged app, or an env var when running from source), which is why no key ever
ends up in this repo.

---

## Run from source (developers)

You don't need the packaged app to use this; the pipeline runs standalone.

```bash
git clone https://github.com/prithuhalder1997-arch/film-source-scraper
cd film-source-scraper
pip install -r engine/requirements.txt
python -m playwright install chromium

export TAVILY_API_KEY=...         # free, no card, from tavily.com
# (or SERPER_API_KEY / BRAVE_API_KEY — whichever you have; see Search providers below)
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

- **Discovery** — tries your configured search provider in priority order:
  Tavily → Serper → Brave → DuckDuckGo (keyless last-resort). See Search
  providers below.
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
APIs. Search via [Tavily](https://tavily.com) (or Serper/Brave). Built to
sit alongside [Zotero](https://www.zotero.org).
