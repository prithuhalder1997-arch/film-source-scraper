# How this is packaged for non-coders (without weakening the pipeline)

The problem: a pure Zotero plugin can't run Playwright, the paywall agent, or
Python — so packaging it as a plugin alone would gut the capability. But a raw
Python pipeline demands a terminal. Both were unacceptable.

The solution is to split along the natural seam:

```
        WHAT THE USER SEES                 WHERE THE POWER IS
  ┌──────────────────────────┐      ┌───────────────────────────────┐
  │  Zotero plugin (.xpi)     │ HTTP │  Capture Engine (native app)  │
  │  • right-click a          │─────▶│  • FastAPI on 127.0.0.1:23200 │
  │    collection             │      │  • your scrape.py, unchanged  │
  │  • progress window        │◀─────│  • paywall_agent.py, unchanged│
  │  • ~250 lines of JS        │ poll │  • Playwright + bundled       │
  │  • ZERO scraping logic     │      │    Chromium (no pip needed)   │
  └──────────────────────────┘      └───────────────────────────────┘
```

**Nothing about the pipeline is dumbed down.** The engine imports `scrape.py`
and `paywall_agent.py` verbatim; the Wayback fallback, headless full-page
screenshots, and PDF handling all run exactly as in the CLI version. The plugin
is a thin remote control.

**Nothing about setup requires coding.** The engine ships as a double-click app
(PyInstaller bundle with Chromium inside). The user pastes one API key into one
text file. The plugin installs like any Zotero add-on.

This is the same shape as Ollama + its GUIs, or Docker Desktop + the CLI: a
local background service plus a light front-end. Proven, not a hack.

## Components
- `scrape.py`, `paywall_agent.py`, `films.json` — the pipeline (also usable
  standalone from a terminal, unchanged; see README.md).
- `engine/server.py` — wraps the pipeline as a localhost HTTP service.
- `engine/launcher.py` — points Playwright at bundled Chromium, loads keys.
- `zotero-plugin/` — the .xpi source (button + progress + engine polling).
- `packaging/` — PyInstaller spec + BUILD.md to produce the installers.

## Three ways to run, same engine
1. **Non-coder**: install engine app + .xpi, right-click a collection.
2. **You, quickly**: `python engine/server.py` then use the plugin.
3. **You, scripted**: `./run.sh` — the original CLI path, still works.
