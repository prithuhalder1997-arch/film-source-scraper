#!/usr/bin/env python3
"""
paywall_agent.py  —  decision agent for paywalled captures.

Not an LLM agent: the choices here are deterministic and better as rules
(faster, free, reproducible). The "agency" is a decision loop that:

  1. detects whether a rendered page is actually paywalled
  2. if so, queries the Wayback Machine CDX API for snapshots
  3. optionally asks Archive.org to make a fresh capture if none exist
  4. re-checks the archived version for a paywall
  5. returns whichever version yields the most real article text

Plugs into scrape.py:  from paywall_agent import resolve_capture
"""

import re, time, requests, urllib.parse

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

CDX = "http://web.archive.org/cdx/search/cdx"
WB  = "https://web.archive.org/web"
SAVE = "https://web.archive.org/save/"

# --- paywall detection -----------------------------------------------------

# phrases that, when dense, signal a wall rather than an article
WALL_MARKERS = [
    "subscribe to continue", "subscribe now", "create a free account",
    "sign in to read", "already a subscriber", "this article is for subscribers",
    "become a member", "you have reached your", "register to continue",
    "unlock this article", "for full access", "premium article",
]
# CSS selectors publishers commonly use for paywall overlays
WALL_SELECTORS = [
    '[class*="paywall"]', '[id*="paywall"]', '[class*="piano"]',
    '[class*="subscribe"]', '[class*="metered"]', '[data-paywall]',
]

def extract_text(page):
    """Visible article-ish text length, ignoring nav/boilerplate."""
    try:
        return page.evaluate("""() => {
            const drop = ['nav','header','footer','aside','script','style'];
            drop.forEach(t => document.querySelectorAll(t).forEach(e=>e.remove()));
            const main = document.querySelector('article, main, [role=main]') || document.body;
            return (main.innerText || '').replace(/\\s+/g,' ').trim();
        }""") or ""
    except Exception:
        return ""

def looks_paywalled(page, text):
    """Heuristic: short body + wall markers/overlay selectors present."""
    low = text.lower()
    marker_hits = sum(1 for m in WALL_MARKERS if m in low)
    # overlay elements actually present in DOM
    sel_hits = 0
    for sel in WALL_SELECTORS:
        try:
            if page.query_selector(sel):
                sel_hits += 1
        except Exception:
            pass
    short = len(text) < 900          # real articles rarely this short
    # verdict: overlay OR (short body AND at least one subscribe prompt)
    if sel_hits >= 1 and short:
        return True
    if marker_hits >= 1 and short:
        return True
    if marker_hits >= 2:             # heavy nagging even on longer stubs
        return True
    return False

# --- wayback ---------------------------------------------------------------

def wayback_snapshots(url, limit=8):
    """Newest-first list of archived (timestamp,url) for this page."""
    try:
        r = requests.get(CDX, params={
            "url": url, "output": "json", "limit": -limit,
            "filter": "statuscode:200", "collapse": "digest",
        }, headers={"User-Agent": UA}, timeout=25)
        rows = r.json()
        if len(rows) <= 1:
            return []
        # rows[0] is the header; columns: urlkey,timestamp,original,...
        snaps = [(row[1], row[2]) for row in rows[1:]]
        snaps.sort(reverse=True)                    # newest first
        return snaps
    except Exception:
        return []

def wayback_url(ts, original):
    # 'if_' suffix asks Wayback for the raw page without its toolbar frame
    return f"{WB}/{ts}if_/{original}"

def request_fresh_capture(url):
    """Ask Archive.org to snapshot the page now. Best-effort, slow."""
    try:
        requests.get(SAVE + url, headers={"User-Agent": UA}, timeout=60)
        time.sleep(4)               # give the crawler a moment
        return True
    except Exception:
        return False

# --- the agent decision loop ----------------------------------------------

def resolve_capture(page, url, allow_fresh_capture=True):
    """
    Returns dict describing what to capture:
      { 'capture_url': <url to screenshot/save>,
        'status': 'live' | 'wayback' | 'paywalled' | 'wayback-fresh',
        'note': str }
    Caller then screenshots capture_url and tags status accordingly.
    The page object is left navigated to capture_url on success.
    """
    # 1. try live
    try:
        page.goto(url, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(1200)
    except Exception as e:
        # live totally failed; go straight to wayback
        return _try_wayback(page, url, allow_fresh_capture,
                            reason=f"live load failed: {e}")

    live_text = extract_text(page)
    if not looks_paywalled(page, live_text):
        return {"capture_url": url, "status": "live",
                "note": f"clean live page ({len(live_text)} chars)"}

    # 2. paywalled -> wayback
    return _try_wayback(page, url, allow_fresh_capture,
                        reason="paywall detected on live",
                        live_text_len=len(live_text))

def _try_wayback(page, url, allow_fresh, reason, live_text_len=0):
    snaps = wayback_snapshots(url)

    # optionally create a snapshot if none exist yet
    if not snaps and allow_fresh:
        if request_fresh_capture(url):
            snaps = wayback_snapshots(url)

    best = None   # (text_len, capture_url, status)
    for ts, original in snaps[:4]:          # check a few newest
        wb = wayback_url(ts, original)
        try:
            page.goto(wb, wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(1000)
        except Exception:
            continue
        wtext = extract_text(page)
        walled = looks_paywalled(page, wtext)
        if not walled and len(wtext) > max(live_text_len, 900):
            status = "wayback" if snaps else "wayback-fresh"
            return {"capture_url": wb, "status": status,
                    "note": f"{reason}; clean archive {ts} ({len(wtext)} chars)"}
        # keep best-effort even if still walled
        if best is None or len(wtext) > best[0]:
            best = (len(wtext), wb, "paywalled")

    if best and best[0] > live_text_len:
        # archived version isn't clean but is fuller than live
        page.goto(best[1], wait_until="networkidle", timeout=45000)
        return {"capture_url": best[1], "status": "paywalled",
                "note": f"{reason}; best archive still partial ({best[0]} chars)"}

    # nothing better than live; fall back to live shot, marked paywalled
    page.goto(url, wait_until="networkidle", timeout=45000)
    return {"capture_url": url, "status": "paywalled",
            "note": f"{reason}; no usable archive found"}


if __name__ == "__main__":
    # quick self-test of the detector logic on synthetic input
    class Fake:
        def __init__(self, has_sel): self._s = has_sel
        def query_selector(self, sel): return object() if self._s else None
        def evaluate(self, js): return ""
    print("overlay+short  ->", looks_paywalled(Fake(True),  "short stub"))
    print("clean long     ->", looks_paywalled(Fake(False), "x"*1500))
    print("markers+short  ->", looks_paywalled(Fake(False),
          "subscribe to continue reading this premium article"))
