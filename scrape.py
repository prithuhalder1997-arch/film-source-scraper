#!/usr/bin/env python3
"""
Film -> Zotero automation pipeline.

For each film in films.json:
  1. search each source-type (review, interview, reddit, criticism, news, paper)
  2. for HTML hits  -> open in headless browser, full-page screenshot,
                       save snapshot into a per-film Zotero collection
  3. for PDF hits   -> download PDF, save as Zotero item + attachment
                       into the same collection

Zotero must be RUNNING (desktop app) so its local connector API on
127.0.0.1:23119 is reachable. No Zotero add-on needed.

Usage:
    export BRAVE_API_KEY=...            # free tier at brave.com/search/api
    python scrape.py                    # all films
    python scrape.py "Sister Midnight"  # one film
    python scrape.py --dry-run          # search only, save nothing
"""

import os, sys, json, time, re, hashlib, pathlib, argparse, urllib.parse
import requests
from playwright.sync_api import sync_playwright
from paywall_agent import resolve_capture

ROOT       = pathlib.Path(__file__).parent
FILMS      = json.loads((ROOT / "films.json").read_text())
OUTDIR     = ROOT / "downloads"
ZOTERO     = "http://127.0.0.1:23119"          # Zotero local connector API
BRAVE_KEY  = os.environ.get("BRAVE_API_KEY", "")
BRAVE_URL  = "https://api.search.brave.com/res/v1/web/search"
PER_SOURCE = int(os.environ.get("HITS_PER_SOURCE", "3"))   # top-N per query
TARGET_COLLECTION = None   # set by the engine when driven from the Zotero plugin
UA         = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# ---------------------------------------------------------------- search ----

def search(query, count=PER_SOURCE):
    """Return list of {url,title} from Brave. Falls back to DuckDuckGo HTML."""
    if BRAVE_KEY:
        try:
            r = requests.get(BRAVE_URL,
                headers={"X-Subscription-Token": BRAVE_KEY,
                         "Accept": "application/json"},
                params={"q": query, "count": count}, timeout=20)
            r.raise_for_status()
            web = r.json().get("web", {}).get("results", [])
            return [{"url": x["url"], "title": x.get("title", "")} for x in web[:count]]
        except Exception as e:
            print(f"    ! brave failed ({e}); falling back to ddg")
    # Fallback: DuckDuckGo HTML (no key, less reliable, rate-limited)
    try:
        r = requests.post("https://html.duckduckgo.com/html/",
                          data={"q": query}, headers={"User-Agent": UA}, timeout=20)
        hits = re.findall(r'result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text)
        out = []
        for href, title in hits[:count]:
            u = urllib.parse.unquote(href)
            m = re.search(r'uddg=([^&]+)', u)
            if m:
                u = urllib.parse.unquote(m.group(1))
            out.append({"url": u, "title": re.sub("<[^>]+>", "", title)})
        return out
    except Exception as e:
        print(f"    ! ddg fallback failed ({e})")
        return []

# ------------------------------------------------------------ zotero api ----

def zotero_up():
    try:
        requests.get(f"{ZOTERO}/connector/ping", timeout=5)
        return True
    except Exception:
        return False

def ensure_collection(name):
    """
    Zotero's connector API has no 'create collection' endpoint, so we set the
    target collection via /connector/updateSession-style save. Simplest robust
    path: save items untargeted, then the user keeps a saved-search/tag.
    Instead we tag every item with the film name AND drop a local copy in a
    per-film folder, which is 100% reliable. See notes at bottom of script.
    """
    (OUTDIR / safe(name)).mkdir(parents=True, exist_ok=True)

def save_snapshot(url, title, film, status="live"):
    """Save an HTML page as a Zotero snapshot, tagged with film + capture status."""
    payload = {
        "url": url,
        "title": title or url,
        "html": None,          # let Zotero fetch+snapshot server-side
        "tags": [{"tag": film}, {"tag": f"capture:{status}"}],
    }
    if TARGET_COLLECTION:
        payload["collections"] = [TARGET_COLLECTION]
    try:
        r = requests.post(f"{ZOTERO}/connector/saveSnapshot",
                          json=payload, headers={"User-Agent": UA}, timeout=60)
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"      ! snapshot save failed: {e}")
        return False

def save_pdf_item(pdf_path, url, title, film):
    """Create a Zotero item from a downloaded PDF via saveItems."""
    payload = {
        "items": [{
            "itemType": "document",
            "title": title or pdf_path.name,
            "url": url,
            "tags": [{"tag": film}],
            "attachments": [{
                "title": pdf_path.name,
                "mimeType": "application/pdf",
                "url": url,
                "path": str(pdf_path),
            }],
        }],
        "uri": url,
    }
    if TARGET_COLLECTION:
        payload["collections"] = [TARGET_COLLECTION]
    try:
        r = requests.post(f"{ZOTERO}/connector/saveItems",
                          json=payload, headers={"User-Agent": UA}, timeout=60)
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"      ! item save failed: {e}")
        return False

# ------------------------------------------------------------- fetching ----

def safe(s):
    return re.sub(r"[^\w\-. ]", "_", s).strip()[:80]

def is_pdf(url, resp_headers=None):
    if url.lower().split("?")[0].endswith(".pdf"):
        return True
    if resp_headers and "application/pdf" in resp_headers.get("content-type", ""):
        return True
    return False

def download_pdf(url, folder):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=60, stream=True)
        if not is_pdf(url, r.headers):
            return None
        h = hashlib.md5(url.encode()).hexdigest()[:8]
        p = folder / f"{h}.pdf"
        p.write_bytes(r.content)
        return p
    except Exception as e:
        print(f"      ! pdf download failed: {e}")
        return None

def screenshot(page, url, folder, use_agent=True):
    """
    Full-page screenshot of an article/review/reddit thread.
    When use_agent: routes through the paywall agent, which may swap in a
    Wayback snapshot. Returns (img_path, title, capture_url, status).
    """
    capture_url, status, note = url, "live", ""
    try:
        if use_agent:
            decision = resolve_capture(page, url)
            capture_url = decision["capture_url"]
            status      = decision["status"]
            note        = decision["note"]
            if status != "live":
                print(f"      · agent: {status} — {note}")
        else:
            page.goto(url, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(1500)
        # auto-scroll to trigger lazy content
        page.evaluate("""async () => {
            await new Promise(res => {
                let y=0; const t=setInterval(()=>{ window.scrollBy(0,600);
                y+=600; if(y>document.body.scrollHeight){clearInterval(t);res();}},120);
            });
        }""")
        page.wait_for_timeout(800)
        h = hashlib.md5(url.encode()).hexdigest()[:8]
        img = folder / f"{h}.png"
        page.screenshot(path=str(img), full_page=True)
        title = page.title()
        return img, title, capture_url, status
    except Exception as e:
        print(f"      ! screenshot failed: {e}")
        return None, None, url, "error"

# ---------------------------------------------------------------- driver ----

def process_film(film, page, dry=False):
    title = film["title"]
    print(f"\n=== {title} ===")
    ensure_collection(title)
    folder = OUTDIR / safe(title)
    seen = set()

    for kind, tmpl in FILMS["query_templates"].items():
        q = tmpl.format(title=title,
                        director=film.get("director") or "",
                        year=film.get("year") or "").strip()
        print(f"  [{kind}] {q}")
        for hit in search(q):
            url = hit["url"]
            if url in seen:
                continue
            seen.add(url)
            print(f"    -> {url}")
            if dry:
                continue

            if is_pdf(url):
                pdf = download_pdf(url, folder)
                if pdf and save_pdf_item(pdf, url, hit["title"], title):
                    print("      ✓ pdf saved to Zotero")
            else:
                img, ptitle, cap_url, status = screenshot(page, url, folder)
                if img:
                    # save the version the agent chose (live or wayback);
                    # tag with status so paywalled/wayback items are findable
                    ok = save_snapshot(cap_url, ptitle or hit["title"], title,
                                       status=status)
                    label = {"live":"snapshot saved",
                             "wayback":"saved via Wayback",
                             "wayback-fresh":"saved via fresh Wayback capture",
                             "paywalled":"paywalled — best-effort shot kept"}.get(status, "saved")
                    print(f"      ✓ {label}" if ok else f"      ({label}, local only)")
            time.sleep(1.0)   # be polite

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("film", nargs="?", help="single film title (optional)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    OUTDIR.mkdir(exist_ok=True)
    if not args.dry_run and not zotero_up():
        print("!! Zotero desktop is not running (127.0.0.1:23119 unreachable).")
        print("   Start Zotero and retry, or use --dry-run to test search only.")
        sys.exit(1)

    films = FILMS["films"]
    if args.film:
        films = [f for f in films if f["title"].lower() == args.film.lower()]
        if not films:
            print(f"No film named {args.film!r} in films.json"); sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA, viewport={"width":1440,"height":900})
        for f in films:
            process_film(f, page, dry=args.dry_run)
        browser.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
