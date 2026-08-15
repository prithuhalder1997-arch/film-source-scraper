#!/usr/bin/env python3
"""
Launcher entry point for the packaged app.

When frozen by PyInstaller, the bundled Chromium lives inside the app. We point
Playwright at it via PLAYWRIGHT_BROWSERS_PATH before importing anything that
launches a browser, so the end user never runs `playwright install`.

It also reads keys from a config file next to the app (or a first-run prompt),
so non-coders set their Brave key once via a plain text file rather than env
vars in a terminal.
"""

import os, sys, json, pathlib

def _resource_dir():
    # PyInstaller sets sys._MEIPASS to the unpacked bundle dir
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys._MEIPASS)
    return pathlib.Path(__file__).parent.parent

def _config_dir():
    # a stable, user-writable place for keys, next to the app data
    if sys.platform == "darwin":
        d = pathlib.Path.home() / "Library" / "Application Support" / "FilmScraper"
    elif sys.platform.startswith("win"):
        d = pathlib.Path(os.environ.get("APPDATA", pathlib.Path.home())) / "FilmScraper"
    else:
        d = pathlib.Path.home() / ".config" / "filmscraper"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _load_keys():
    """Read config.json for keys; create a template on first run."""
    cfg_path = _config_dir() / "config.json"
    if not cfg_path.exists():
        cfg_path.write_text(json.dumps({
            "TAVILY_API_KEY": "",
            "SERPER_API_KEY": "",
            "BRAVE_API_KEY": "",
            "_note": "Paste ONE search API key between the quotes, then save and "
                     "restart the engine. Recommended: Tavily (free, NO credit "
                     "card, 1000/mo) at https://tavily.com  --  or Serper "
                     "(no card, 2500 trial) at https://serper.dev  --  Brave "
                     "(needs a card as of 2026) at https://brave.com/search/api. "
                     "The engine runs without any key too, using a slower "
                     "keyless fallback that may return few results."
        }, indent=2))
        print(f"First run: set a search API key in\n  {cfg_path}\n"
              f"then restart. Tavily is recommended (free, no credit card).")
    try:
        cfg = json.loads(cfg_path.read_text())
        for k in ("TAVILY_API_KEY", "SERPER_API_KEY", "BRAVE_API_KEY"):
            if cfg.get(k):
                os.environ[k] = cfg[k]
    except Exception:
        pass

def _point_at_bundled_chromium():
    if getattr(sys, "frozen", False):
        bundled = _resource_dir() / "ms-playwright"
        if bundled.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled)

def main():
    _point_at_bundled_chromium()
    _load_keys()
    # import AFTER env is set so Playwright picks up the bundled browser
    sys.path.insert(0, str(_resource_dir()))
    import server
    server.main()

if __name__ == "__main__":
    main()
