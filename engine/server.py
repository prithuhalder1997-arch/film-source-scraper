#!/usr/bin/env python3
"""
Local capture engine — exposes the scraping pipeline as an HTTP service
on 127.0.0.1 so the Zotero plugin (or a curl call) can drive it.

This does NOT replace your pipeline; it wraps scrape.py / paywall_agent.py
unchanged. All the capability stays here in Python + Playwright.

The Zotero plugin calls:
    POST /scrape   { "film": {title,director,year}, "collectionKey": "ABC123" }
    GET  /health
    GET  /status/<job_id>

Runs jobs in a background thread and streams progress the plugin can poll.
Bound to localhost only — never exposed to the network.
"""

import os, sys, json, uuid, threading, pathlib, traceback
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# import the existing pipeline unchanged
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))          # so scrape.py/paywall_agent.py resolve

from playwright.sync_api import sync_playwright
import scrape                                   # your pipeline module

APP_VERSION = "1.0.0"
app = FastAPI(title="Film→Zotero Capture Engine", version=APP_VERSION)

# The plugin runs inside Zotero's origin; allow it to call localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],                        # localhost-only service; safe
    allow_methods=["*"], allow_headers=["*"],
)

JOBS = {}   # job_id -> {status, log[], done, error}

class FilmSpec(BaseModel):
    title: str
    director: Optional[str] = ""
    year: Optional[int] = None

class ScrapeRequest(BaseModel):
    film: FilmSpec
    collectionKey: Optional[str] = None         # Zotero collection to file into
    hits_per_source: int = 3
    use_wayback: bool = True

@app.get("/health")
def health():
    return {"ok": True, "version": APP_VERSION,
            "brave_key": bool(scrape.BRAVE_KEY),
            "zotero_up": scrape.zotero_up()}

def _run_job(job_id: str, req: ScrapeRequest):
    job = JOBS[job_id]
    def log(msg):
        job["log"].append(msg)
    try:
        scrape.PER_SOURCE = req.hits_per_source
        film = {"title": req.film.title,
                "director": req.film.director or "",
                "year": req.film.year}
        # the plugin passes a real collectionKey; store it so save_* can target it
        scrape.TARGET_COLLECTION = req.collectionKey
        log(f"Starting capture for '{film['title']}'")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=scrape.UA,
                                    viewport={"width":1440,"height":900})
            # monkeypatch print inside process_film to also push to job log
            _orig_print = __builtins__["print"] if isinstance(__builtins__, dict) else print
            scrape.process_film(film, page, dry=False)
            browser.close()
        job["status"] = "done"
        job["done"] = True
        log("Capture complete.")
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job["done"] = True
        log("ERROR: " + str(e))
        log(traceback.format_exc())

@app.post("/scrape")
def scrape_endpoint(req: ScrapeRequest):
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status": "running", "log": [], "done": False, "error": None}
    t = threading.Thread(target=_run_job, args=(job_id, req), daemon=True)
    t.start()
    return {"job_id": job_id}

@app.get("/status/{job_id}")
def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return {"error": "no such job"}
    return job

def main():
    port = int(os.environ.get("ENGINE_PORT", "23200"))
    print(f"Capture engine listening on http://127.0.0.1:{port}")
    print("Keep this window/app open while using the Zotero plugin.")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

if __name__ == "__main__":
    main()
